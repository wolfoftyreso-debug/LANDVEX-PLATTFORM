"""Programs-registry probe — run in a NETWORKED environment.

Confirms the shape of whatever LANDVEX_PROGRAMS_URL returns before trusting
it (same idea as the AAMOS/SCB probes). Reports whether it answered, JSON vs
RSS/Atom, how many records normalized, and the shape of the first record —
so the provider field-mapping in engine/datasources/programs.py can be
confirmed against the live feed.

    LANDVEX_PROGRAMS_URL='https://.../calls' python3 -m scripts.programs_probe
    # optional: LAT, LON, VERTICAL

Exit 0 if the registry answered with at least one record, 1 otherwise.
Read-only.
"""
from __future__ import annotations

import os
import sys

from engine.datasources.programs import ProgramsClient

LAT = float(os.environ.get("LAT", "59.33"))
LON = float(os.environ.get("LON", "18.06"))
VERTICAL = os.environ.get("VERTICAL", "elektriker")


def main() -> int:
    client = ProgramsClient()
    print(f"Programs registry probe → {client.base_url or '(LANDVEX_PROGRAMS_URL unset)'}")
    if not client.connected:
        print("  ✗ not connected — set LANDVEX_PROGRAMS_URL to the registry "
              "endpoint (EU Funding & Tenders / Vinnova / Energimyndigheten / "
              "regional fund).")
        return 1
    print(f"  query: lat={LAT} lon={LON} vertical={VERTICAL}\n")
    try:
        recs = client.fetch_programs(LAT, LON, VERTICAL)
    except Exception as e:  # noqa: BLE001 - diagnostics
        print(f"  ✗ request failed — {type(e).__name__}: {str(e)[:120]}")
        return 1
    if not recs:
        print("  ~ registry answered but 0 records normalized. Check the feed "
              "format (JSON list / {programs:[...]} / RSS-Atom) and the "
              "field mapping in engine/datasources/programs.py:normalize_record.")
        return 1
    print(f"  ✓ {len(recs)} record(s) normalized. First record:")
    r = recs[0]
    for k in ("label_en", "provider", "amount_local", "currency", "deadline",
              "verticals", "url"):
        print(f"      {k:14} {r.get(k)!r}")
    missing = [k for k in ("amount_local", "deadline", "url") if not r.get(k)]
    if missing:
        print(f"\n  ~ empty fields (map from the feed if available): {missing}")
    print("\nRESULT: registry reachable. Confirm the field mapping above with "
          "the provider, then it flows into /v1/opportunities automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
