"""Kolada pre-flight probe — run in a NETWORKED environment.

    LANDVEX_KOLADA_URL=https://api.kolada.se/v2 python3 -m scripts.kolada_probe

Hits the real Kolada v2 API for each mapped KPI (national, latest years) and
reports 200/shape so the id mapping can be verified before trusting it.
Read-only. Exit 0 if any KPI returned a total value, 1 otherwise.
"""
from __future__ import annotations

import sys

from engine.datasources.kolada import KPI_IDS, KoladaClient


def main() -> int:
    client = KoladaClient()
    print(f"Kolada probe → {client.base_url or '(LANDVEX_KOLADA_URL not set)'}\n")
    if not client.connected:
        print("RESULT: not connected — set LANDVEX_KOLADA_URL=https://api.kolada.se/v2")
        return 1
    hit = False
    for code in sorted(KPI_IDS):
        try:
            r = client.fetch_kpi(code, municipality="0000")
        except Exception as e:  # noqa: BLE001 - diagnostics
            print(f"  ✗ {code:28} {type(e).__name__}: {str(e)[:50]}")
            continue
        if r and r["value"] is not None:
            hit = True
            print(f"  ✓ {code:28} {KPI_IDS[code]} = {r['value']} ({r['year']})")
        else:
            print(f"  ~ {code:28} {KPI_IDS[code]} — no total value")
    print()
    print("RESULT: Kolada reachable." if hit else "RESULT: no values returned.")
    return 0 if hit else 1


if __name__ == "__main__":
    sys.exit(main())
