"""Permits / detail-plans probe — run in a NETWORKED environment.

Confirms what LANDVEX_PERMITS_URL returns before trusting it (same idea as
the AAMOS / SCB / programs probes): whether it answered, and which of the
three signals (building_permits, detail_plans, development_m2) it provides
for a point — so the field mapping in engine/datasources/permits.py can be
confirmed against the live feed.

    LANDVEX_PERMITS_URL='https://.../permits' python3 -m scripts.permits_probe
    # optional: LAT, LON

Exit 0 if the source answered with at least one signal, 1 otherwise.
Read-only.
"""
from __future__ import annotations

import os
import sys

from engine.datasources.permits import PermitsClient, SIGNALS

LAT = float(os.environ.get("LAT", "59.33"))
LON = float(os.environ.get("LON", "18.06"))


def main() -> int:
    client = PermitsClient()
    print(f"Permits probe → {client.base_url or '(LANDVEX_PERMITS_URL unset)'}")
    if not client.connected:
        print("  ✗ not connected — set LANDVEX_PERMITS_URL to the permits / "
              "detail-plans endpoint (municipal open data, Boverket, Kolada, "
              "or an aggregator).")
        return 1
    print(f"  query: lat={LAT} lon={LON}\n")
    try:
        raw = client.fetch_permits(LAT, LON)
    except Exception as e:  # noqa: BLE001 - diagnostics
        print(f"  ✗ request failed — {type(e).__name__}: {str(e)[:120]}")
        return 1
    if not raw:
        print("  ~ source answered but provided none of "
              f"{list(SIGNALS)}. Check the response shape (object with those "
              "keys, or a list of permit records) and the mapping in "
              "engine/datasources/permits.py:fetch_permits.")
        return 1
    for s in SIGNALS:
        mark = "✓" if s in raw else "·"
        print(f"  {mark} {s:18} {raw.get(s, '(not provided)')}")
    print("\nRESULT: permits source reachable. Confirm the mapping above, then "
          "these signals flow into every engine (momentum, outlook, project "
          "risk, Contradiction Index) automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
