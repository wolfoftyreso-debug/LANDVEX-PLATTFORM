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


CLIENTS = {c.sensor_class: c for c in (TrafikverketFlow, SmhiWeather)}


def client_for(sensor_class: str, **kw) -> SensorClient | None:
    cls = CLIENTS.get(sensor_class)
    return cls(**kw) if cls else None


def clients_status() -> list[dict]:
    return [cls().describe() for cls in CLIENTS.values()]
