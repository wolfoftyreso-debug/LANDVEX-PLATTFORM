"""Sensorklienter — ett protokoll per mätnät, inte en generisk shim.

`engine/sensors.py` beskriver vilka sensorklasser som kan mata
upptäcktslagret. Den här modulen kopplar in de två som är genuint öppna
och dokumenterade:

  Trafikverket   TrafficFlow via Datex-liknande XML-query mot
                 api.trafikinfo.trafikverket.se/v2/data.json. Kräver en
                 authenticationkey (gratis, men en nyckel). Matar
                 `traffic_shift` — en upptäcktstyp som annars inte hade
                 NÅGON byggd mätare alls.
  SMHI           metobs open data, ren REST utan nyckel. Matar
                 `pattern_deviation` och används framför allt för att
                 UTESLUTA väder som förklaring till en avvikelse.

ÄRLIGHET OM VERIFIERING: sökvägarna och svarsformaten nedan är de
dokumenterade, men de är INTE live-verifierade härifrån — utgående nät är
spärrat i utvecklingsmiljön. Varje klient bär därför `verified_live =
False` tills `scripts/sensor_probe.py` körts mot det riktiga API:t i en
miljö med nätverk. Parsningen är däremot testad mot fixturer i varje
API:s dokumenterade form, så det som återstår är att bekräfta sökvägen —
inte koden. Samma disciplin som register_apis.py.

Alla klienter delar `Breaker` från faults.py: ett mätnät har hundratals
punkter, och en nere källa får kosta ETT misslyckat anrop, inte ett per
punkt.

Rent stdlib, injicerbar transport.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .faults import OUR_BUGS, Breaker

_UA = "landvex-opportunity-engine/sensors"


def _http_post(url: str, payload: bytes, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "text/xml", "Accept": "application/json",
                 "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


def _http_get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


class SensorClient:
    """Gemensamt: en mätpunkt → ett värde, eller None. Aldrig ett påhitt."""

    id = "sensor"
    sensor_class = ""
    verified_live = False

    def __init__(self, transport=None, base_url: str | None = None,
                 timeout: float = 6.0, **kw):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get(self.ENV, "")).rstrip("/")
        self._breaker = Breaker(transport or self._default_transport,
                                timeout=timeout, **kw)

    ENV = ""
    _default_transport = staticmethod(_http_get)

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    @property
    def down(self) -> bool:
        return self._breaker.down

    @property
    def last_error(self):
        """Senaste omvärldsfelet, så en probe kan skilja en spärrad
        brandvägg från ett svar som inte gick att tolka."""
        return self._breaker.last_error

    def describe(self) -> dict:
        return {"client": self.id, "sensor_class": self.sensor_class,
                "connected": self.connected, "paused": self.down,
                "verified_live": self.verified_live,
                "activate_with": self.ENV,
                "note_en": "Documented endpoint, not verified live from this "
                           "environment. Run scripts/sensor_probe.py where "
                           "the network is open."}


# ── Trafikverket: vägflöde ──────────────────────────────────────────────
_TRV_QUERY = (
    '<REQUEST><LOGIN authenticationkey="{key}"/>'
    '<QUERY objecttype="TrafficFlow" schemaversion="1.5" limit="{limit}">'
    '<FILTER><WITHIN name="Geometry.WGS84" shape="center" '
    'value="{lon} {lat}" radius="{radius}"/></FILTER>'
    '</QUERY></REQUEST>'
)


class TrafikverketFlow(SensorClient):
    """Fordonsflöde per mätpunkt inom en radie.

    Svarsform (dokumenterad): {"RESPONSE": {"RESULT": [{"TrafficFlow":
    [{"SiteId": .., "VehicleFlowRate": .., "AverageVehicleSpeed": ..,
      "MeasurementTime": ".."}]}]}}
    """

    id = "trafikverket"
    sensor_class = "road_flow"
    ENV = "LANDVEX_TRAFFIC_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet
    _default_transport = staticmethod(_http_post)

    def __init__(self, *a, api_key: str | None = None, **kw):
        super().__init__(*a, **kw)
        self.api_key = (api_key if api_key is not None
                        else os.environ.get("LANDVEX_TRAFFIC_KEY", ""))

    @property
    def connected(self) -> bool:
        # Utan nyckel finns ingen väg fram, hur satt bas-URL:en än är.
        return bool(self.base_url) and bool(self.api_key)

    def flow(self, lat: float, lon: float, *, radius_m: int = 5000,
             limit: int = 20) -> dict | None:
        if not self.connected:
            return None
        payload = _TRV_QUERY.format(key=self.api_key, lat=lat, lon=lon,
                                    radius=int(radius_m),
                                    limit=int(limit)).encode("utf-8")
        raw = self._breaker.fetch(self.base_url, payload)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
            rader = data["RESPONSE"]["RESULT"][0]["TrafficFlow"]
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001 – svaret gick inte att tolka
            return None
        return _sammanfatta_flode(rader)


def _sammanfatta_flode(rader: list) -> dict | None:
    """Mätpunkter → ett flöde. None när ingen punkt bar ett tal.

    Medelvärdet vägs INTE: varje mätpunkt räknas lika, och antalet punkter
    följer med så att läsaren ser om siffran vilar på en slinga eller på
    tjugo.
    """
    flow, speed = [], []
    for r in rader if isinstance(rader, list) else []:
        if not isinstance(r, dict):
            continue
        v = r.get("VehicleFlowRate")
        s = r.get("AverageVehicleSpeed")
        if isinstance(v, (int, float)):
            flow.append(float(v))
        if isinstance(s, (int, float)):
            speed.append(float(s))
    if not flow:
        return None
    return {
        "vehicles_per_hour": round(sum(flow) / len(flow), 1),
        "average_speed_kmh": (round(sum(speed) / len(speed), 1)
                              if speed else None),
        "measurement_points": len(flow),
        "source": "Trafikverket TrafficFlow",
        "measured": True,
        "basis_en": (f"Mean across {len(flow)} measurement point(s) within "
                     f"the radius, each counted once. Fewer points means a "
                     f"narrower basis, not a less certain road."),
    }


# ── SMHI: väderobservationer ────────────────────────────────────────────
# metobs-parametrar: 1 = lufttemperatur (momentan), 7 = nederbörd 1 h.
SMHI_PARAMETERS: dict[str, dict] = {
    "air_temperature_c": {"parameter": 1, "label_en": "Air temperature"},
    "precipitation_mm": {"parameter": 7, "label_en": "Precipitation, 1 h"},
}


class SmhiWeather(SensorClient):
    """Senaste timmens observation från en SMHI-station.

    Svarsform (dokumenterad): {"value": [{"date": <ms>, "value": "3.2",
    "quality": "G"}], "station": {"key": "..", "name": ".."}}
    """

    id = "smhi"
    sensor_class = "weather"
    ENV = "LANDVEX_WEATHER_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def latest(self, signal_id: str, station: str) -> dict | None:
        spec = SMHI_PARAMETERS.get(signal_id)
        if not (self.connected and spec):
            return None
        url = (f"{self.base_url}/api/version/1.0/parameter/"
               f"{spec['parameter']}/station/{urllib.parse.quote(station)}"
               f"/period/latest-hour/data.json")
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
            punkter = data.get("value") or []
            senaste = punkter[-1]
            varde = float(senaste["value"])
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        kvalitet = senaste.get("quality")
        return {
            "signal": signal_id, "value": varde,
            "label_en": spec["label_en"],
            "station": (data.get("station") or {}).get("name", station),
            "observed_at_ms": senaste.get("date"),
            "quality": kvalitet,
            "measured": True,
            "source": "SMHI metobs",
            # SMHI märker G = kontrollerad, Y = grovkontrollerad. Att
            # tiga om skillnaden vore att presentera en preliminär
            # avläsning som en fastställd.
            "basis_en": ("SMHI quality flag "
                         f"{kvalitet!r}: 'G' is checked, 'Y' is coarsely "
                         "checked and may still be revised."),
        }




# ── OpenAQ: luftkvalitet ────────────────────────────────────────────────
class OpenAqAir(SensorClient):
    """Senaste mätvärdet per parameter inom en radie.

    Svarsform (OpenAQ v3, dokumenterad): {"results": [{"parameter":
    {"name": "no2", "units": "µg/m³"}, "value": 21.4, "coordinates":
    {...}, "datetime": {"utc": ".."}}]}

    Nyckel krävs (gratis). Utan den finns ingen väg fram.
    """

    id = "openaq"
    sensor_class = "air_quality"
    ENV = "LANDVEX_AIR_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    # OpenAQ:s egna parameternamn → våra signal-id:n.
    PARAMETERS = {"no2": "no2_ug_m3", "pm10": "pm10_ug_m3",
                  "pm25": "pm25_ug_m3"}

    def __init__(self, *a, api_key: str | None = None, **kw):
        super().__init__(*a, **kw)
        self.api_key = (api_key if api_key is not None
                        else os.environ.get("LANDVEX_AIR_KEY", ""))

    @property
    def connected(self) -> bool:
        return bool(self.base_url) and bool(self.api_key)

    def latest(self, lat: float, lon: float, *,
               radius_m: int = 12000) -> dict | None:
        if not self.connected:
            return None
        url = (f"{self.base_url}/v3/parameters/latest?"
               + urllib.parse.urlencode(
                   {"coordinates": f"{lat},{lon}",
                    "radius": int(radius_m), "limit": 100}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            rader = json.loads(raw.decode("utf-8")).get("results") or []
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return _sammanfatta_luft(rader, self.PARAMETERS)


def _sammanfatta_luft(rader: list, parametrar: dict) -> dict | None:
    """Stationer → ett värde per parameter. None när ingen bar ett tal.

    Medelvärde över stationerna i radien, med antalet kvar i svaret: en
    station i en gatukanjon och tio spridda över en stad är två helt
    olika underlag, och skillnaden får inte försvinna i ett tal.
    """
    per: dict[str, list] = {}
    for r in rader if isinstance(rader, list) else []:
        if not isinstance(r, dict):
            continue
        namn = ((r.get("parameter") or {}).get("name") or "").lower()
        sid = parametrar.get(namn)
        v = r.get("value")
        if sid and isinstance(v, (int, float)):
            per.setdefault(sid, []).append(float(v))
    if not per:
        return None
    return {
        "values": {k: round(sum(v) / len(v), 2) for k, v in per.items()},
        "stations": {k: len(v) for k, v in per.items()},
        "measured": True,
        "source": "OpenAQ v3",
        "basis_en": ("Mean per parameter across the stations inside the "
                     "radius. One station in a street canyon and ten spread "
                     "across a city are different bases for the same "
                     "number, so the count stays in the answer."),
    }


# ── SMHI hydrologi: vattenstånd ─────────────────────────────────────────
class SmhiHydro(SensorClient):
    """Vattenföring och vattenstånd från SMHI:s hydrologiska nät.

    Samma REST-form som metobs: parameter → station → period → data.json.
    """

    id = "smhi_hydro"
    sensor_class = "water_level"
    ENV = "LANDVEX_HYDRO_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    PARAMETERS = {"discharge_m3s": {"parameter": 1,
                                    "label_en": "Discharge"},
                  "water_level_cm": {"parameter": 2,
                                     "label_en": "Water level"}}

    def latest(self, signal_id: str, station: str) -> dict | None:
        spec = self.PARAMETERS.get(signal_id)
        if not (self.connected and spec):
            return None
        url = (f"{self.base_url}/api/version/1.0/parameter/"
               f"{spec['parameter']}/station/{urllib.parse.quote(station)}"
               f"/period/latest-day/data.json")
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
            senaste = (data.get("value") or [])[-1]
            varde = float(senaste["value"])
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return {
            "signal": signal_id, "value": varde,
            "label_en": spec["label_en"],
            "station": (data.get("station") or {}).get("name", station),
            "observed_at_ms": senaste.get("date"),
            "measured": True, "source": "SMHI hydrology",
            "basis_en": ("One gauge, one cross-section. What reaches a "
                         "basement depends on terrain and culverts this "
                         "series knows nothing about."),
        }


# ── Copernicus STAC: satellitpassager ───────────────────────────────────
class CopernicusStac(SensorClient):
    """Vilka scener som täcker en punkt mellan två datum.

    STAC är en standard: POST /search med {collections, intersects,
    datetime, limit} → {"features": [{"id": .., "properties":
    {"datetime": .., "eo:cloud_cover": ..}}]}.

    Klienten hämtar INTE bilder och räknar inte förändring. Den svarar på
    den fråga som avgör om en jämförelse alls är möjlig: finns det två
    tillräckligt molnfria passager över den här punkten?
    """

    id = "copernicus_stac"
    sensor_class = "earth_observation"
    ENV = "LANDVEX_EO_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet
    _default_transport = staticmethod(_http_post)

    def coverage(self, lat: float, lon: float, *, start: str, end: str,
                 collection: str = "sentinel-2-l2a",
                 max_cloud: float = 30.0) -> dict | None:
        if not self.connected:
            return None
        krop = json.dumps({
            "collections": [collection],
            "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{start}/{end}", "limit": 100,
        }).encode("utf-8")
        raw = self._breaker.fetch(f"{self.base_url}/search", krop)
        if raw is None:
            return None
        try:
            scener = json.loads(raw.decode("utf-8")).get("features") or []
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return _sammanfatta_scener(scener, max_cloud, collection)


def _sammanfatta_scener(scener: list, max_cloud: float,
                        collection: str) -> dict | None:
    if not isinstance(scener, list):
        return None
    moln = []
    for f in scener:
        p = (f or {}).get("properties") or {}
        c = p.get("eo:cloud_cover")
        moln.append(float(c) if isinstance(c, (int, float)) else None)
    anvandbara = [c for c in moln if c is not None and c <= max_cloud]
    return {
        "scenes": len(scener),
        "usable_scenes": len(anvandbara),
        "max_cloud_pct": max_cloud,
        "collection": collection,
        "comparable": len(anvandbara) >= 2,
        "measured": True,
        "source": "Copernicus Data Space (STAC)",
        # Det här är hela poängen med klienten: den säger om en jämförelse
        # är MÖJLIG, inte vad den skulle visa. Två moln över samma tomt är
        # inte "ingen förändring" — det är ingen observation.
        "basis_en": (
            f"{len(anvandbara)} of {len(scener)} scene(s) are under "
            f"{max_cloud:g}% cloud. Fewer than two means no comparison can "
            f"be made at all; cloud over a parcel is not evidence that "
            f"nothing changed, it is an absence of observation."),
    }


# ── Generisk sensorfeed: ägarlevererade mätvärden ───────────────────────
class GenericSensorFeed(SensorClient):
    """Kontraktet en fastighetsägare, ett fjärrvärmebolag eller en
    leverantör levererar in i.

    Formen är medvetet minimal och dokumenterad:
        GET {base}/readings?stream=<id>&since=<iso>
        → {"readings": [{"at": "..", "value": 12.3, "unit": "kWh"}],
           "stream": {"id": "..", "label": "..", "owner": ".."}}

    De fyra klasserna utan öppet API — fastighetsmätare, fjärrvärme,
    vatten, rörelsedata — delar den här formen i stället för att få var
    sin halvfärdig adapter mot ett API som inte finns publikt.
    """

    id = "generic_feed"
    sensor_class = "building_meter"
    ENV = "LANDVEX_METER_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def __init__(self, *a, sensor_class: str | None = None, **kw):
        if sensor_class:
            self.sensor_class = sensor_class
        super().__init__(*a, **kw)

    def readings(self, stream: str, since: str = "") -> dict | None:
        if not self.connected:
            return None
        url = (f"{self.base_url}/readings?"
               + urllib.parse.urlencode(
                   {"stream": stream, **({"since": since} if since else {})}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
            rader = data.get("readings") or []
            varden = [float(r["value"]) for r in rader
                      if isinstance(r.get("value"), (int, float))]
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        if not varden:
            return None
        strom = data.get("stream") or {}
        return {
            "stream": strom.get("id", stream),
            "label_en": strom.get("label", ""),
            "owner": strom.get("owner", ""),
            "readings": len(varden),
            "latest": varden[-1],
            "mean": round(sum(varden) / len(varden), 3),
            "unit": (rader[-1] or {}).get("unit", ""),
            "measured": True, "source": "owner-supplied feed",
            "basis_en": ("Supplied by the owner of the asset, not measured "
                         "independently. It is as good as their meter and "
                         "their honesty, and neither is verifiable from "
                         "here."),
        }




# ── USGS: seismik ───────────────────────────────────────────────────────
class UsgsSeismic(SensorClient):
    """Skalv över en magnitud inom en radie, senaste dygnet.

    GeoJSON, ingen nyckel. Svarsform (dokumenterad): {"features":
    [{"properties": {"mag": 4.2, "place": "..", "time": <ms>}}]}
    """

    id = "usgs"
    sensor_class = "seismic"
    ENV = "LANDVEX_SEISMIC_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def events(self, lat: float, lon: float, *, radius_km: float = 200.0,
               min_magnitude: float = 2.5, days: int = 1) -> dict | None:
        if not self.connected:
            return None
        url = (f"{self.base_url}/fdsnws/event/1/query?"
               + urllib.parse.urlencode({
                   "format": "geojson", "latitude": lat, "longitude": lon,
                   "maxradiuskm": radius_km, "minmagnitude": min_magnitude,
                   "limit": 200,
                   # Fönstret skickas IN, härleds aldrig här: en modul som
                   # frågar sin egen klocka går inte att testa deterministiskt.
                   "starttime": f"-P{int(days)}D"}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            f = json.loads(raw.decode("utf-8")).get("features") or []
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return _sammanfatta_skalv(f, min_magnitude, radius_km, "USGS FDSN")


def _sammanfatta_skalv(features: list, min_magnitude: float,
                       radius_km: float, source: str) -> dict | None:
    """FDSN-GeoJSON → ett svar. Delas av USGS och EMSC.

    Två kataloger som svarar på samma FDSN-fråga ska sammanfattas av
    SAMMA kod, annars kan en skillnad mellan dem lika gärna komma från
    två olika parsningar som från två olika seismiska nät — och då är
    hela jämförelsen värdelös.
    """
    if not isinstance(features, list):
        return None
    mags = [x["properties"]["mag"] for x in features
            if isinstance((x.get("properties") or {}).get("mag"),
                          (int, float))]
    return {
        "events": len(features), "with_magnitude": len(mags),
        "max_magnitude": max(mags) if mags else None,
        "min_magnitude_queried": min_magnitude,
        "radius_km": radius_km, "measured": True, "source": source,
        "basis_en": (f"Events at or above M{min_magnitude:g} within "
                     f"{radius_km:g} km, as catalogued by {source}. Absence "
                     f"here means no event ABOVE that threshold was "
                     f"catalogued — not that the ground was still. Two "
                     f"catalogues routinely differ by a few tenths of a "
                     f"magnitude for the same event; that is a real "
                     f"disagreement about the measurement, not a bug."),
    }


# ── Digitraffic (FI): fartyg och väg, öppet utan nyckel ─────────────────
class DigitrafficMarine(SensorClient):
    """Fartygspositioner i finskt farvatten. Öppet, ingen nyckel.

    Svarsform: {"features": [{"mmsi": .., "properties": {"sog": ..,
    "navStat": ..}}]}
    """

    id = "digitraffic_marine"
    sensor_class = "vessel_traffic"
    ENV = "LANDVEX_AIS_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def vessels(self, *, min_speed_kn: float = 0.5) -> dict | None:
        if not self.connected:
            return None
        raw = self._breaker.fetch(f"{self.base_url}/api/ais/v1/locations")
        if raw is None:
            return None
        try:
            f = json.loads(raw.decode("utf-8")).get("features") or []
            farter = [(x.get("properties") or {}).get("sog") for x in f]
            rorliga = [s for s in farter
                       if isinstance(s, (int, float)) and s >= min_speed_kn]
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        if not f:
            return None
        return {
            "vessels": len(f), "under_way": len(rorliga),
            "measured": True, "source": "Digitraffic (Fintraffic) AIS",
            "basis_en": ("Positions as broadcast. AIS carries what the crew "
                         "entered; a vessel with the transponder off is "
                         "simply absent, and absence is not stillness."),
        }


class DigitrafficRoad(SensorClient):
    """Vägflöde i Finland — ANDRA leverantören för road_flow.

    Poängen är inte fler mätpunkter utan en OBEROENDE mätning: två nät som
    säger samma sak är det som gör ett underlag robust.
    """

    id = "digitraffic_road"
    sensor_class = "road_flow"
    ENV = "LANDVEX_TRAFFIC_FI_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def flow(self, station: str) -> dict | None:
        if not self.connected:
            return None
        raw = self._breaker.fetch(
            f"{self.base_url}/api/tms/v1/stations/"
            f"{urllib.parse.quote(station)}/data")
        if raw is None:
            return None
        try:
            varden = json.loads(raw.decode("utf-8")).get("sensorValues") or []
            flode = [v["value"] for v in varden
                     if str(v.get("name", "")).upper().startswith("OHITUKSET")
                     and isinstance(v.get("value"), (int, float))]
            fart = [v["value"] for v in varden
                    if str(v.get("name", "")).upper().startswith("KESKINOPEUS")
                    and isinstance(v.get("value"), (int, float))]
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        if not flode:
            return None
        return {
            "vehicles_per_hour": round(sum(flode) / len(flode), 1),
            "average_speed_kmh": (round(sum(fart) / len(fart), 1)
                                  if fart else None),
            "measurement_points": len(flode),
            "measured": True, "source": "Digitraffic (Fintraffic) TMS",
            "basis_en": (f"{len(flode)} sensor value(s) from one station. "
                         f"A single station is one cross-section, not a "
                         f"corridor."),
        }


# ── NOAA/NWS: väder i USA — ANDRA leverantören för weather ──────────────
class NwsWeather(SensorClient):
    """Senaste observation från en NWS-station. Öppet, ingen nyckel.

    Svarsform: {"properties": {"temperature": {"value": 3.2,
    "unitCode": "wmoUnit:degC"}, "station": ".."}}
    """

    id = "nws"
    sensor_class = "weather"
    ENV = "LANDVEX_WEATHER_US_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def latest(self, signal_id: str, station: str) -> dict | None:
        if not (self.connected and signal_id == "air_temperature_c"):
            return None
        raw = self._breaker.fetch(
            f"{self.base_url}/stations/{urllib.parse.quote(station)}"
            f"/observations/latest")
        if raw is None:
            return None
        try:
            p = json.loads(raw.decode("utf-8"))["properties"]
            varde = p["temperature"]["value"]
            if not isinstance(varde, (int, float)):
                return None
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return {
            "signal": signal_id, "value": float(varde),
            "label_en": "Air temperature", "station": station,
            "measured": True, "source": "NOAA / National Weather Service",
            "basis_en": ("Latest hourly observation. NWS publishes "
                         "unvalidated observations first; a value can be "
                         "revised or withdrawn."),
        }


# ── EMSC: seismik — ANDRA leverantören för seismic ──────────────────────
class EmscSeismic(SensorClient):
    """Europeisk skalvkatalog, samma FDSN-protokoll som USGS.

    Poängen är inte fler skalv utan en ANNAN KATALOG. Två seismiska nät
    lokaliserar och magnitudsätter samma händelse var för sig, och när de
    inte är överens är det ett fynd om mätningen — inte ett fel.

    EMSC:s parameternamn skiljer sig från USGS (`minmag`, `maxradius` i
    grader), och det är precis den sortens detalj som gör att en generisk
    "FDSN-shim" hade tystnat i stället för att svara.
    """

    id = "emsc"
    sensor_class = "seismic"
    ENV = "LANDVEX_SEISMIC_EMSC_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def events(self, lat: float, lon: float, *, radius_km: float = 200.0,
               min_magnitude: float = 2.5, days: int = 1) -> dict | None:
        if not self.connected:
            return None
        url = (f"{self.base_url}/fdsnws/event/1/query?"
               + urllib.parse.urlencode({
                   "format": "json", "lat": lat, "lon": lon,
                   # EMSC tar radien i GRADER, inte kilometer. 1° ≈ 111 km
                   # längs en storcirkel; att skicka km hade gett en radie
                   # hundra gånger för stor och ett svar som såg rimligt ut.
                   "maxradius": round(radius_km / 111.0, 4),
                   "minmag": min_magnitude, "limit": 200,
                   "start": f"-P{int(days)}D"}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            f = json.loads(raw.decode("utf-8")).get("features") or []
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return _sammanfatta_skalv(f, min_magnitude, radius_km,
                                  "EMSC (seismicportal.eu)")


# ── Sensor.Community: luft — ANDRA leverantören för air_quality ─────────
class SensorCommunityAir(SensorClient):
    """Medborgardrivna luftsensorer. Öppet, ingen nyckel.

    Oberoendet är starkare än vanligt: det är inte bara en annan ägare
    utan en annan MÄTPRINCIP. OpenAQ läser myndigheternas
    referensinstrument; det här är billiga optiska partikelräknare hos
    privatpersoner. Att de två pekar åt samma håll säger därför mer än
    två referensstationer som gör det.

    Svarsform (dokumenterad): [{"sensor": {"id": .., "sensor_type":
    {"name": "SDS011"}}, "sensordatavalues": [{"value_type": "P1",
    "value": "12.3"}], "location": {..}}]
    """

    id = "sensor_community"
    sensor_class = "air_quality"
    ENV = "LANDVEX_AIR_COMMUNITY_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    # P1/P2 är nätets egna namn. NO₂ finns INTE — och den luckan döljs
    # inte genom att mappa den till något som råkar likna.
    PARAMETERS = {"P1": "pm10_ug_m3", "P2": "pm25_ug_m3"}

    def latest(self, lat: float, lon: float, *,
               radius_km: float = 12.0) -> dict | None:
        if not self.connected:
            return None
        url = (f"{self.base_url}/airrohr/v1/filter/"
               f"area={lat},{lon},{radius_km:g}")
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            rader = json.loads(raw.decode("utf-8"))
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return _sammanfatta_medborgarluft(rader, self.PARAMETERS)


def _sammanfatta_medborgarluft(rader: list, parametrar: dict) -> dict | None:
    per: dict[str, list] = {}
    sensorer = set()
    for r in rader if isinstance(rader, list) else []:
        if not isinstance(r, dict):
            continue
        sensorer.add(((r.get("sensor") or {}).get("id")))
        for v in r.get("sensordatavalues") or []:
            sid = parametrar.get(str((v or {}).get("value_type", "")))
            if not sid:
                continue
            try:
                tal = float(v["value"])
            except (TypeError, ValueError, KeyError):
                continue      # ett obrukbart värde är inte ett nollvärde
            # Nyckeln skapas EFTER att värdet gått att läsa. Ett
            # setdefault före konverteringen lämnade en tom lista kvar för
            # parametern, och medelvärdet delade med noll.
            per.setdefault(sid, []).append(tal)
    if not per:
        return None
    return {
        "values": {k: round(sum(v) / len(v), 2) for k, v in per.items()},
        "readings": {k: len(v) for k, v in per.items()},
        "sensors": len([s for s in sensorer if s is not None]),
        "measured": True, "source": "Sensor.Community",
        "basis_en": (
            "Low-cost optical particle counters run by private "
            "individuals. They read high in humid air and are not "
            "calibrated against a reference instrument, so they are a "
            "second opinion on DIRECTION rather than on level. NO₂ is not "
            "measured by this network at all — the parameter is absent "
            "here, not zero."),
    }


# ── USGS Water Services: vatten — ANDRA leverantören för water_level ────
# Omräkning till SMHI:s enheter. Två nät som jämförs i olika enheter blir
# "conflicting" av ren aritmetik, och det är den sortens tysta fel hela
# korroboreringslagret finns för att fånga.
_CFS_TILL_M3S = 0.0283168
_FOT_TILL_CM = 30.48


class UsgsWater(SensorClient):
    """Vattenföring och vattenstånd från USGS NWIS. Öppet, ingen nyckel.

    Svarsform (dokumenterad): {"value": {"timeSeries": [{"sourceInfo":
    {"siteName": ".."}, "variable": {"variableCode": [{"value":
    "00060"}]}, "values": [{"value": [{"value": "123", "dateTime":
    ".."}]}]}]}}
    """

    id = "usgs_water"
    sensor_class = "water_level"
    ENV = "LANDVEX_HYDRO_US_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    # USGS parameterkod → (vårt signal-id, faktor till vår enhet)
    PARAMETERS = {"00060": ("discharge_m3s", _CFS_TILL_M3S),
                  "00065": ("water_level_cm", _FOT_TILL_CM)}

    def latest(self, signal_id: str, station: str) -> dict | None:
        koder = {k for k, (sid, _) in self.PARAMETERS.items()
                 if sid == signal_id}
        if not (self.connected and koder):
            return None
        url = (f"{self.base_url}/nwis/iv/?"
               + urllib.parse.urlencode({
                   "format": "json", "sites": station,
                   "parameterCd": ",".join(sorted(koder)),
                   "siteStatus": "all"}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            serier = (json.loads(raw.decode("utf-8"))
                      .get("value", {}).get("timeSeries") or [])
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        return _sammanfatta_usgs_vatten(serier, signal_id, station,
                                        self.PARAMETERS)


def _sammanfatta_usgs_vatten(serier: list, signal_id: str, station: str,
                             parametrar: dict) -> dict | None:
    for s in serier if isinstance(serier, list) else []:
        if not isinstance(s, dict):
            continue
        kod = ((s.get("variable") or {}).get("variableCode") or [{}])[0] \
            .get("value")
        spec = parametrar.get(str(kod))
        if not spec or spec[0] != signal_id:
            continue
        try:
            punkter = (s.get("values") or [{}])[0].get("value") or []
            ra = float(punkter[-1]["value"])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if ra <= -999998:      # NWIS skriver -999999 för "ingen avläsning"
            continue
        enhet_in = "ft³/s" if signal_id == "discharge_m3s" else "ft"
        enhet_ut = "m³/s" if signal_id == "discharge_m3s" else "cm"
        return {
            "signal": signal_id, "value": round(ra * spec[1], 3),
            "raw_value": ra, "raw_unit": enhet_in, "unit": enhet_ut,
            "label_en": ("Discharge" if signal_id == "discharge_m3s"
                         else "Water level"),
            "station": ((s.get("sourceInfo") or {})
                        .get("siteName") or station),
            "observed_at": (punkter[-1] or {}).get("dateTime", ""),
            "measured": True, "source": "USGS Water Services (NWIS)",
            "basis_en": (
                f"Converted from {enhet_in} to {enhet_ut} "
                f"(×{spec[1]:g}) so it can stand beside the Swedish "
                f"hydrological series. Comparing two networks in "
                f"different units produces 'conflicting' by arithmetic "
                f"alone — one gauge, one cross-section, same limit as any "
                f"other."),
        }
    return None


# ── NASA CMR: satellit — ANDRA leverantören för earth_observation ───────
class NasaCmrScenes(SensorClient):
    """Landsat-passager via NASA:s Common Metadata Repository.

    Oberoendet sitter i KONSTELLATIONEN: Copernicus svarar för Sentinel,
    det här för Landsat. Två satelliter i olika banor över samma tomt är
    två chanser att se förbi ett moln — och två helt skilda ägarkedjor.

    Svarsform (dokumenterad): {"feed": {"entry": [{"id": "..",
    "time_start": "..", "cloud_cover": "12.0"}]}}
    """

    id = "nasa_cmr"
    sensor_class = "earth_observation"
    ENV = "LANDVEX_EO_NASA_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def coverage(self, lat: float, lon: float, *, start: str, end: str,
                 collection: str = "LANDSAT_OT_C2_L2",
                 max_cloud: float = 30.0) -> dict | None:
        if not self.connected:
            return None
        url = (f"{self.base_url}/search/granules.json?"
               + urllib.parse.urlencode({
                   "short_name": collection,
                   "point": f"{lon},{lat}",
                   "temporal": f"{start}T00:00:00Z,{end}T00:00:00Z",
                   "page_size": 100}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            poster = ((json.loads(raw.decode("utf-8")).get("feed") or {})
                      .get("entry") or [])
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        # CMR skriver molntäcket som STRÄNG. Att jämföra "12.0" med ett
        # tal ger TypeError i Python 3 — scenen hade tyst räknats som
        # oanvändbar, och en tom karta hade sett ut som "ingen passage".
        scener = []
        for p in poster if isinstance(poster, list) else []:
            c = (p or {}).get("cloud_cover")
            try:
                moln = float(c) if c is not None else None
            except (TypeError, ValueError):
                moln = None
            scener.append({"properties": {"eo:cloud_cover": moln}})
        return _sammanfatta_scener(scener, max_cloud, collection)


# ── BarentsWatch: AIS — ANDRA leverantören för vessel_traffic ───────────
def _http_form(url: str, payload: bytes, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


def _http_get_bearer(url: str, token: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _UA,
                      "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


class BarentsWatchAis(SensorClient):
    """Norska AIS via BarentsWatch. Kräver ett registrerat konto.

    Till skillnad från Digitraffic ligger det här bakom OAuth2 client
    credentials: id och hemlighet växlas mot ett kortlivat token som
    sedan bärs som Bearer. Utan bägge finns ingen väg fram, och klienten
    säger det i stället för att returnera en tom lista — en tom lista
    hade lästs som "inga fartyg i farvattnet".

    Svarsform (dokumenterad): [{"mmsi": .., "speedOverGround": ..,
    "navigationalStatus": ..}]
    """

    id = "barentswatch"
    sensor_class = "vessel_traffic"
    ENV = "LANDVEX_AIS_NO_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet
    _default_transport = staticmethod(_http_get_bearer)

    def __init__(self, *a, client_id: str | None = None,
                 client_secret: str | None = None,
                 token_url: str | None = None,
                 token_transport=None, **kw):
        super().__init__(*a, **kw)
        self.client_id = (client_id if client_id is not None
                          else os.environ.get("LANDVEX_AIS_NO_CLIENT_ID", ""))
        self._secret = (client_secret if client_secret is not None
                        else os.environ.get("LANDVEX_AIS_NO_SECRET", ""))
        self.token_url = (token_url if token_url is not None else
                          os.environ.get("LANDVEX_AIS_NO_TOKEN_URL",
                                         "https://id.barentswatch.no"
                                         "/connect/token"))
        self._token_transport = token_transport or _http_form
        self._token = ""

    @property
    def connected(self) -> bool:
        # Tre delar krävs. Saknas en är källan inte "nere" — den är inte
        # ansökt om, vilket är en helt annan sak att åtgärda.
        return bool(self.base_url and self.client_id and self._secret)

    def _hamta_token(self) -> str:
        if self._token:
            return self._token
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id, "client_secret": self._secret,
            "scope": "ais"}).encode("utf-8")
        try:
            raw = self._token_transport(self.token_url, payload,
                                        self._breaker.timeout)
            self._token = json.loads(raw.decode("utf-8"))["access_token"]
        except OUR_BUGS:
            raise
        except Exception as e:      # noqa: BLE001
            # Går token-utbytet inte igenom är hela källan otillgänglig.
            # Felet sparas där proben letar efter det.
            self._breaker.last_error = e
            self._breaker.trip()
            return ""
        return self._token

    def vessels(self, *, min_speed_kn: float = 0.5) -> dict | None:
        if not self.connected:
            return None
        token = self._hamta_token()
        if not token:
            return None
        raw = self._breaker.fetch(f"{self.base_url}/v1/latest/combined",
                                  token)
        if raw is None:
            return None
        try:
            rader = json.loads(raw.decode("utf-8"))
            farter = [(r or {}).get("speedOverGround") for r in rader]
            rorliga = [s for s in farter
                       if isinstance(s, (int, float)) and s >= min_speed_kn]
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        if not isinstance(rader, list) or not rader:
            return None
        return {
            "vessels": len(rader), "under_way": len(rorliga),
            "measured": True, "source": "BarentsWatch AIS (Kystverket)",
            "basis_en": ("Norwegian coastal AIS. Same limit as any AIS "
                         "feed — it carries what the crew entered, and a "
                         "vessel with the transponder off is simply "
                         "absent. Independent of Fintraffic in operator, "
                         "waters and collection chain, but not in "
                         "technology: a fault in AIS itself would move "
                         "both."),
        }


_XML_MAX_BYTES = 8 << 20        # 8 MiB; ett dygns last är några tiotal kB


def _entsoe_kvantiteter(raw: bytes) -> list[float]:
    """Läs `quantity` ur ett ENTSO-E-dokument, utan XML-beroende.

    `xml.etree` är sårbart för entitetsexpansion ("billion laughs") och
    externa entiteter, och `defusedxml` är ett beroende kärnan inte får
    ta. Båda attackerna kräver en DEKLARATION i dokumentet, så svaret
    avvisas om det bär en — och storleken har ett tak innan parsern ens
    får se det. Det är en riktig spärr, inte en dämpning: ett dokument
    utan DOCTYPE kan inte expandera någonting.
    """
    if len(raw) > _XML_MAX_BYTES:
        raise ValueError(f"ENTSO-E answered with {len(raw)} bytes, over the "
                         f"{_XML_MAX_BYTES} limit — not parsed")
    huvud = raw[:4096].lstrip().lower()
    if b"<!doctype" in huvud or b"<!entity" in raw[:65536].lower():
        raise ValueError("the document declares entities; refused unparsed "
                         "rather than expanded")
    import xml.etree.ElementTree as ET      # noqa: S405 – se docstring ovan
    rot = ET.fromstring(raw.decode("utf-8"))   # noqa: S314 – deklarationer
    # Namnrymden varierar med dokumentversion; matcha på taggens lokala
    # namn i stället för att hårdkoda en URI som ändras.
    return [float(e.text) for e in rot.iter()
            if e.tag.rsplit("}", 1)[-1] == "quantity" and e.text]


# ── De två nät som redan fanns men aldrig räknades ──────────────────────
# `grid_telemetry` och `field_observation` stod som
# `independent_providers: 0` i /v1/sensors trots att båda HAR ett nät —
# deras klienter (SvkClient, DirectQuixzoomClient) byggdes före den här
# tabellen och registrerades aldrig i den. En nolla läses som "ingenting
# byggt", och värre: klasserna föll ur listan över dem som saknar ett
# ANDRA nät, så luckan syntes inte alls i lägesrapporten.
#
# Adaptrarna nedan lägger inte till någon förmåga. De gör de befintliga
# näten RÄKNINGSBARA.
class SvkGrid(SensorClient):
    """Svenska kraftnät — nätet som redan fanns för grid_telemetry."""

    id = "svk"
    sensor_class = "grid_telemetry"
    ENV = "LANDVEX_SVK_URL"
    verified_live = False

    def __init__(self, *a, client=None, **kw):
        super().__init__(*a, **kw)
        if client is None:
            from .svk import SvkClient
            # Exakt samma bas-URL, aldrig 'or None': ett tomt
            # värde som faller tillbaka på miljön hade låtit
            # wrappern säga 'ej ansluten' om en klient som är det.
            client = SvkClient(base_url=self.base_url)
        self._client = client

    def production_mix(self) -> dict | None:
        if not self.connected:
            return None
        return self._client.production_mix()


class QuixzoomField(SensorClient):
    """quiXzoom — nätet som redan fanns för field_observation."""

    id = "quixzoom"
    sensor_class = "field_observation"
    ENV = "LANDVEX_QUIXZOOM_URL"
    verified_live = False

    def __init__(self, *a, client=None, **kw):
        super().__init__(*a, **kw)
        if client is None:
            from .quixzoom_direct import DirectQuixzoomClient
            client = DirectQuixzoomClient(base_url=self.base_url)
        self._client = client

    def missions(self, lat: float, lon: float,
                 radius_km: float = 5.0) -> dict | None:
        if not self.connected:
            return None
        return self._client.quixzoom_missions(lat, lon, radius_km)


# ── ENTSO-E: elnät — ANDRA leverantören för grid_telemetry ──────────────
class EntsoeGrid(SensorClient):
    """Europeisk transparensplattform. Kräver en ansökt (gratis) token.

    Sensorraden för grid_telemetry namnger redan ENTSO-E som operatör
    vid sidan av Svenska kraftnät — men bara den ena var byggd, så
    klassen hade i praktiken ett nät.

    ENTSO-E svarar med XML, inte JSON. Klienten läser därför bara det den
    behöver ur dokumentet i stället för att låtsas att svaret är JSON.
    """

    id = "entsoe"
    sensor_class = "grid_telemetry"
    ENV = "LANDVEX_ENTSOE_URL"
    verified_live = False   # sätts av scripts/probe_all där nätet är öppet

    def __init__(self, *a, token: str | None = None, **kw):
        super().__init__(*a, **kw)
        self.token = (token if token is not None
                      else os.environ.get("LANDVEX_ENTSOE_TOKEN", ""))

    @property
    def connected(self) -> bool:
        # Utan token finns ingen väg fram. "Inte ansökt om" är ett annat
        # tillstånd än "nere", och det åtgärdas av en ansökan.
        return bool(self.base_url) and bool(self.token)

    def load(self, area: str, *, start: str, end: str) -> dict | None:
        """Faktisk last per budområde (documentType A65, processType A16)."""
        if not self.connected:
            return None
        url = (f"{self.base_url}/api?"
               + urllib.parse.urlencode({
                   "securityToken": self.token, "documentType": "A65",
                   "processType": "A16", "outBiddingZone_Domain": area,
                   "periodStart": start, "periodEnd": end}))
        raw = self._breaker.fetch(url)
        if raw is None:
            return None
        try:
            varden = _entsoe_kvantiteter(raw)
        except OUR_BUGS:
            raise
        except Exception:      # noqa: BLE001
            return None
        if not varden:
            return None
        return {
            "area": area, "points": len(varden),
            "latest_mw": varden[-1],
            "mean_mw": round(sum(varden) / len(varden), 1),
            "measured": True, "source": "ENTSO-E Transparency Platform",
            "basis_en": ("Actual load per bidding zone as published by the "
                         "TSOs themselves. Same limit as any zone "
                         "aggregate: a factory starting up and a wind lull "
                         "move it identically, and neither is attributable "
                         "to a site. Published values are revised for "
                         "weeks after the fact."),
        }


# En sensorklass kan ha FLERA leverantörer. Det är hela poängen: två
# oberoende nät som mäter samma sak är det som gör ett underlag robust,
# och strukturen som bara tillät en dolde att skillnaden fanns.
#
# Ordningen är inte godtycklig: den första leverantören är den `CLIENTS`
# och `client_for` väljer, alltså den som svarar när bara ett svar
# behövs. Den ska vara den med bredast täckning för vår hemmamarknad.
PROVIDERS: dict[str, tuple] = {
    "road_flow": (TrafikverketFlow, DigitrafficRoad),
    "weather": (SmhiWeather, NwsWeather),
    "air_quality": (OpenAqAir, SensorCommunityAir),
    "water_level": (SmhiHydro, UsgsWater),
    "earth_observation": (CopernicusStac, NasaCmrScenes),
    "vessel_traffic": (DigitrafficMarine, BarentsWatchAis),
    "seismic": (UsgsSeismic, EmscSeismic),
    "grid_telemetry": (SvkGrid, EntsoeGrid),
    "building_meter": (GenericSensorFeed,),
    # Ett nät, och det syns nu som ett i stället för som noll. quiXzoom
    # är vår egen insamlingskedja; ett andra nät för samma sak vore en
    # annan fältplattform, och någon sådan finns inte att koppla in.
    "field_observation": (QuixzoomField,),
}

# Bakåtkompatibel: första leverantören per klass.
CLIENTS = {k: v[0] for k, v in PROVIDERS.items()}


def providers_for(sensor_class: str) -> tuple:
    return PROVIDERS.get(sensor_class, ())


def independent_count(sensor_class: str) -> int:
    """Hur många OBEROENDE nät som kan mäta klassen. En källa är en källa;
    två är det som gör att man kan tro på den."""
    return len(PROVIDERS.get(sensor_class, ()))


def client_for(sensor_class: str, **kw) -> SensorClient | None:
    """Ett svar när bara ett behövs — den första leverantören."""
    cls = CLIENTS.get(sensor_class)
    return cls(**kw) if cls else None


def clients_for(sensor_class: str, **kw) -> list[SensorClient]:
    """ALLA nät som kan mäta klassen. Det är den här listan man frågar
    när svaret ska kunna bekräftas av något annat än sig självt."""
    return [cls(**kw) for cls in PROVIDERS.get(sensor_class, ())]


def all_clients() -> list[type]:
    """Varje leverantörsklass, en gång, i registerordning."""
    ut, sedda = [], set()
    for grupp in PROVIDERS.values():
        for cls in grupp:
            if cls.__name__ not in sedda:
                sedda.add(cls.__name__)
                ut.append(cls)
    return ut


def clients_status() -> list[dict]:
    """Vad varje BYGGD klient säger om sig själv.

    Gick tidigare på `CLIENTS.values()` — första leverantören per klass —
    vilket gjorde de andra näten osynliga i /v1/sensors. Ett andra nät
    som inte syns är ett andra nät ingen vet att de kan koppla in.
    """
    return [cls().describe() for cls in all_clients()]
