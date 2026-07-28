"""Bekräfta sensor-adaptrarna mot de RIKTIGA mätnäten.

    LANDVEX_WEATHER_URL=https://opendata-download-metobs.smhi.se \\
        python3 -m scripts.sensor_probe weather

    LANDVEX_TRAFFIC_URL=https://api.trafikinfo.trafikverket.se/v2/data.json \\
    LANDVEX_TRAFFIC_KEY=... python3 -m scripts.sensor_probe road_flow

    python3 -m scripts.sensor_probe all

Adaptrarna bär `verified_live = False` tills den här körts någonstans med
nätverk. Sökvägarna och svarsformaten är de dokumenterade; parsningen är
testad mot fixturer. Det som återstår är att bekräfta att sökvägen svarar
som dokumentationen påstår — och det går bara att göra genom att fråga.

SAMMA DISCIPLIN SOM REGISTERPROBEN: ett nät som inte går att NÅ ger inget
resultat alls, inte ett underkänt. Att skriva ned "misslyckades" när det i
själva verket var brandväggen förstör kunskap i stället för att skapa den.

    exit 0  minst en adapter bekräftad
    exit 1  nådde fram, men svaret såg inte ut som dokumentationen
    exit 3  kom aldrig fram (nät spärrat, DNS, proxy) — inget nedskrivet
"""
from __future__ import annotations

import json
import os
import sys

from engine.datasources.faults import unreachable
from engine.datasources.sensor_apis import PROVIDERS
from engine.sensors import SENSORS

# Klient-id → den miljövariabel just DEN klienten läser. Raden tog
# tidigare `connected_by` ur sensorraden, som bara känner det första
# nätets variabel — så den som ville koppla in det andra nätet fick
# instruktionen att sätta det förstas, och undrade varför ingenting
# hände.
_ENV_PER_KLIENT = {c.id: c.ENV for grupp in PROVIDERS.values()
                   for c in grupp}


def _probe_weather() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import SmhiWeather
    c = SmhiWeather()
    if not c.connected:
        return "not configured", None
    # 97400 = Stockholm-Observatoriekullen, en station som finns i metobs.
    r = c.latest("air_temperature_c",
                 os.environ.get("LANDVEX_WEATHER_STATION", "97400"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_road_flow() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import TrafikverketFlow
    c = TrafikverketFlow()
    if not c.connected:
        return "not configured", None
    r = c.flow(59.3145, 18.0705, radius_m=10000)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_air_quality() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import OpenAqAir
    c = OpenAqAir()
    if not c.connected:
        return "not configured", None
    r = c.latest(59.3145, 18.0705)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_water_level() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import SmhiHydro
    c = SmhiHydro()
    if not c.connected:
        return "not configured", None
    r = c.latest("water_level_cm",
                 os.environ.get("LANDVEX_HYDRO_STATION", "2255"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_earth_observation() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import CopernicusStac
    c = CopernicusStac()
    if not c.connected:
        return "not configured", None
    # Ett fönster bakåt som bara behöver finnas, inte vara aktuellt: proben
    # bekräftar sökvägen, inte världsläget. Datum tas in, aldrig härleds.
    r = c.coverage(59.3145, 18.0705,
                   start=os.environ.get("LANDVEX_EO_FROM", "2026-05-01"),
                   end=os.environ.get("LANDVEX_EO_TO", "2026-07-01"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_building_meter() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import GenericSensorFeed
    c = GenericSensorFeed()
    if not c.connected:
        return "not configured", None
    strom = os.environ.get("LANDVEX_METER_STREAM", "")
    if not strom:
        return "not configured", None
    r = c.readings(strom)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_seismic() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import UsgsSeismic
    c = UsgsSeismic()
    if not c.connected:
        return "not configured", None
    r = c.events(59.3145, 18.0705, radius_km=500.0, min_magnitude=1.0)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_vessel_traffic() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import DigitrafficMarine
    c = DigitrafficMarine()
    if not c.connected:
        return "not configured", None
    r = c.vessels()
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r



def _probe_grid_svk() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import SvkGrid
    c = SvkGrid()
    if not c.connected:
        return "not configured", None
    r = c.production_mix()
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_grid_entsoe() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import EntsoeGrid
    c = EntsoeGrid()
    if not c.connected:
        return "not configured", None
    # 10Y1001A1001A46L = SE3. Fönstret skickas IN, härleds aldrig här.
    r = c.load(os.environ.get("LANDVEX_ENTSOE_AREA", "10Y1001A1001A46L"),
               start=os.environ.get("LANDVEX_ENTSOE_FROM", "202607280000"),
               end=os.environ.get("LANDVEX_ENTSOE_TO", "202607282300"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_field_observation() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import QuixzoomField
    c = QuixzoomField()
    if not c.connected:
        return "not configured", None
    r = c.missions(59.3145, 18.0705)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_weather_nws() -> tuple[str, dict | None]:
    """NWS har legat i PROVIDERS sedan det andra nätet för weather kom in,
    men utan probe — alltså utan möjlighet att någonsin bevisas."""
    from engine.datasources.sensor_apis import NwsWeather
    c = NwsWeather()
    if not c.connected:
        return "not configured", None
    r = c.latest("air_temperature_c",
                 os.environ.get("LANDVEX_WEATHER_US_STATION", "KNYC"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_road_flow_fi() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import DigitrafficRoad
    c = DigitrafficRoad()
    if not c.connected:
        return "not configured", None
    r = c.flow(os.environ.get("LANDVEX_TRAFFIC_FI_STATION", "23001"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_air_community() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import SensorCommunityAir
    c = SensorCommunityAir()
    if not c.connected:
        return "not configured", None
    r = c.latest(59.3145, 18.0705)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_water_usgs() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import UsgsWater
    c = UsgsWater()
    if not c.connected:
        return "not configured", None
    # 07010000 = Mississippi vid St. Louis, en station som finns i NWIS.
    r = c.latest("discharge_m3s",
                 os.environ.get("LANDVEX_HYDRO_US_STATION", "07010000"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_eo_nasa() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import NasaCmrScenes
    c = NasaCmrScenes()
    if not c.connected:
        return "not configured", None
    r = c.coverage(59.3145, 18.0705,
                   start=os.environ.get("LANDVEX_EO_FROM", "2026-05-01"),
                   end=os.environ.get("LANDVEX_EO_TO", "2026-07-01"))
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_seismic_emsc() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import EmscSeismic
    c = EmscSeismic()
    if not c.connected:
        return "not configured", None
    r = c.events(59.3145, 18.0705, radius_km=500.0, min_magnitude=1.0)
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


def _probe_ais_barentswatch() -> tuple[str, dict | None]:
    from engine.datasources.sensor_apis import BarentsWatchAis
    c = BarentsWatchAis()
    if not c.connected:
        return "not configured", None
    r = c.vessels()
    if r is None and unreachable(c.last_error):
        return "unreachable", None
    return "ok", r


# Nycklad per LEVERANTÖR, inte per klass. Tabellen gick tidigare på
# sensorklass och kunde därför bara nå den första leverantören — det
# andra nätet gick inte att proba, och `verified_live` kunde aldrig
# sättas för det. Ett nät som inte går att bevisa är inget bevis.
PROBES = {
    "weather:smhi": _probe_weather,
    "weather:nws": _probe_weather_nws,
    "seismic:usgs": _probe_seismic,
    "seismic:emsc": _probe_seismic_emsc,
    "vessel_traffic:digitraffic_marine": _probe_vessel_traffic,
    "vessel_traffic:barentswatch": _probe_ais_barentswatch,
    "road_flow:trafikverket": _probe_road_flow,
    "road_flow:digitraffic_road": _probe_road_flow_fi,
    "air_quality:openaq": _probe_air_quality,
    "air_quality:sensor_community": _probe_air_community,
    "water_level:smhi_hydro": _probe_water_level,
    "water_level:usgs_water": _probe_water_usgs,
    "earth_observation:copernicus_stac": _probe_earth_observation,
    "earth_observation:nasa_cmr": _probe_eo_nasa,
    "building_meter:generic_feed": _probe_building_meter,
    "grid_telemetry:svk": _probe_grid_svk,
    "grid_telemetry:entsoe": _probe_grid_entsoe,
    "field_observation:quixzoom": _probe_field_observation,
}


def _expandera(namn: str) -> list[str]:
    """En sensorklass betyder ALLA dess nät.

    `python3 -m scripts.sensor_probe air_quality` ska fortsätta betyda
    vad det alltid har betytt — nu bara med två nät under sig i stället
    för ett.
    """
    if namn in PROBES:
        return [namn]
    traffar = [k for k in PROBES if k.split(":", 1)[0] == namn]
    return traffar


def main(argv: list[str]) -> int:
    valda = [a for a in argv[1:] if not a.startswith("-")] or ["all"]
    if valda == ["all"]:
        valda = list(PROBES)
    else:
        expanderade, okanda = [], []
        for v in valda:
            traffar = _expandera(v)
            (expanderade.extend if traffar else okanda.append)(
                traffar if traffar else v)
        if okanda:
            print(f"no probe for: {', '.join(okanda)}. "
                  f"Have: {', '.join(PROBES)}")
            return 64
        valda = expanderade

    bekraftade, misslyckade, onadda = [], [], []
    for namn in valda:
        klass, _, klient = namn.partition(":")
        spec = SENSORS.get(klass, {})
        status, resultat = PROBES[namn]()
        if status == "not configured":
            var = _ENV_PER_KLIENT.get(klient) or spec.get("connected_by", "?")
            print(f"  ---- {klass:18s} {klient:19s} not configured "
                  f"(set {var})")
            continue
        if status == "unreachable":
            print(f"  ???? {klass:18s} {klient:19s} never got through — "
                  f"recording NOTHING rather than a false negative")
            onadda.append(namn)
            continue
        if resultat is None:
            print(f"  FAIL {klass:18s} {klient:19s} reached the host but "
                  f"the response did not parse as documented")
            misslyckade.append(namn)
            continue
        print(f"  OK   {klass:18s} {klient:19s} "
              f"{json.dumps(resultat, ensure_ascii=False)[:80]}")
        bekraftade.append(namn)

    print()
    print(f"{len(bekraftade)} confirmed · {len(misslyckade)} did not parse · "
          f"{len(onadda)} unreachable")
    if not (bekraftade or misslyckade or onadda):
        # Noll bekräftade utan att något ens provades är inte ett godkänt
        # resultat — det är ingen körning alls, och en rad som säger "0
        # confirmed" bredvid exit 0 läses som att allt är i sin ordning.
        print("\nNothing was configured, so nothing was tested. This is "
              "not a pass: no network was asked anything.")
    if onadda and not bekraftade:
        print("\nNothing was recorded. An unreachable network is not a "
              "failed adapter, and writing it down as one would destroy "
              "knowledge instead of creating it.")
        return 3
    if bekraftade:
        print("\nSet verified_live = True on the confirmed clients in "
              "engine/datasources/sensor_apis.py — by hand, in a commit "
              "someone can read. A probe that edits its own source would "
              "let a single lucky call mark the code as proven.")
    return 1 if misslyckade else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
