"""Places / competition probe — run in a NETWORKED environment.

Confirms what LANDVEX_PLACES_URL returns before trusting it (same idea as
the AAMOS / SCB / programs / permits probes): whether it answered, which of
competition_pressure / provider_gap it provides, and how many competitors —
so the field mapping in engine/datasources/places.py can be confirmed live.

    LANDVEX_PLACES_URL='https://.../places' python3 -m scripts.places_probe
    # optional: LAT, LON, VERTICAL

Exit 0 if the source answered with at least one signal, 1 otherwise.
Read-only.
"""
from __future__ import annotations

import os
import sys

from engine.datasources.places import PlacesClient, SIGNALS

LAT = float(os.environ.get("LAT", "59.33"))
LON = float(os.environ.get("LON", "18.06"))
VERTICAL = os.environ.get("VERTICAL", "frisor")


def main() -> int:
    client = PlacesClient()
    print(f"Places probe → {client.base_url or '(LANDVEX_PLACES_URL unset)'}")
    if not client.connected:
        print("  ✗ not connected — set LANDVEX_PLACES_URL to the places / "
              "competition endpoint (Google Places, Bolagsverket, review "
              "data, or an aggregator).")
        return 1
    print(f"  query: lat={LAT} lon={LON} vertical={VERTICAL}\n")
    try:
        raw, competitors = client.fetch_places(LAT, LON, VERTICAL)
    except Exception as e:  # noqa: BLE001 - diagnostics
        print(f"  ✗ request failed — {type(e).__name__}: {str(e)[:120]}")
        return 1
    if not raw:
        print("  ~ source answered but provided none of "
              f"{list(SIGNALS)}. Check the response shape (object with those "
              "keys / a competitors list) and the mapping in "
              "engine/datasources/places.py:fetch_places.")
        return 1
    for s in SIGNALS:
        mark = "✓" if s in raw else "·"
        print(f"  {mark} {s:20} {raw.get(s, '(not provided)')}")
    print(f"  · competitors        {len(competitors)} record(s)")
    print("\nRESULT: places source reachable. Confirm the mapping above, then "
          "these signals strengthen competition risk and the competition gap "
          "automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
