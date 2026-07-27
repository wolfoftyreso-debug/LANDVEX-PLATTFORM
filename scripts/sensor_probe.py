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
import socket
import sys
import urllib.error
import urllib.parse

from engine.datasources.sensor_apis import CLIENTS
from engine.sensors import SENSORS


def unreachable(exc) -> bool:
    """Betyder felet ONÅBAR värd (nät/policy) snarare än konstigt svar?

    En egen TCP-koll mot värden dög inte: med en utgående proxy LYCKAS
    anslutningen medan hämtningen ändå faller, och då skrevs en spärrad
    brandvägg ned som en trasig adapter — precis det falska underkännande
    proben finns för att undvika. Klassa på felet från det VERKLIGA
    anropet i stället. Samma regel som livability_sources._classify.
    """
    if exc is None:
        return False
    if isinstance(exc, urllib.error.HTTPError):
        # Servern svarade. 404 är ett riktigt svar; 403/407/5xx är inte.
        return exc.code in (403, 407, 502, 503, 504)
    return isinstance(exc, (urllib.error.URLError, socket.timeout, OSError,
                            ConnectionError))


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


PROBES = {
    "weather": _probe_weather,
    "road_flow": _probe_road_flow,
    "air_quality": _probe_air_quality,
    "water_level": _probe_water_level,
    "earth_observation": _probe_earth_observation,
    "building_meter": _probe_building_meter,
}


def main(argv: list[str]) -> int:
    valda = [a for a in argv[1:] if not a.startswith("-")] or ["all"]
    if valda == ["all"]:
        valda = list(PROBES)
    okanda = [v for v in valda if v not in PROBES]
    if okanda:
        print(f"no probe for: {', '.join(okanda)}. "
              f"Have: {', '.join(PROBES)}")
        return 64

    bekraftade, misslyckade, onadda = [], [], []
    for namn in valda:
        spec = SENSORS.get(namn, {})
        status, resultat = PROBES[namn]()
        klient = CLIENTS[namn].id
        if status == "not configured":
            print(f"  ---- {namn:12s} {klient:14s} not configured "
                  f"(set {spec.get('connected_by', '?')})")
            continue
        if status == "unreachable":
            print(f"  ???? {namn:12s} {klient:14s} never got through — "
                  f"recording NOTHING rather than a false negative")
            onadda.append(namn)
            continue
        if resultat is None:
            print(f"  FAIL {namn:12s} {klient:14s} reached the host but the "
                  f"response did not parse as documented")
            misslyckade.append(namn)
            continue
        print(f"  OK   {namn:12s} {klient:14s} "
              f"{json.dumps(resultat, ensure_ascii=False)[:96]}")
        bekraftade.append(namn)

    print()
    print(f"{len(bekraftade)} confirmed · {len(misslyckade)} did not parse · "
          f"{len(onadda)} unreachable")
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
