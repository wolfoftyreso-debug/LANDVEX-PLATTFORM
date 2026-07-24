"""SCB PxWeb live probe — run in a NETWORKED environment.

Pre-flight diagnostic for the one calibrated real source (Sweden). The
PxWeb table paths in engine/datasources/scb.py were written from SCB's
metadata but never live-verified (dev network blocked api.scb.se). This
script queries each table for a real municipality and reports, per table,
whether SCB actually answered and with what value — so you can confirm the
paths before trusting SCB data in production.

    python3 -m scripts.scb_probe            # Stockholm (default)
    python3 -m scripts.scb_probe 57.70 11.97  # a lat/lon (→ nearest kommun)

Exit code 0 if at least one SCB table answered, 1 if none did (paths wrong,
API down, or no network egress). Read-only: only GETs public SCB tables.
"""
from __future__ import annotations

import sys

from engine.datasources.scb import (ScbClient, KommunLocator, PXWEB_BASE,
                                     POP_TABLE, INCOME_TABLE, DENSITY_TABLE,
                                     population_signals, income_index_signal,
                                     density_signal)


def _line(ok: bool, table: str, detail: str) -> None:
    print(f"  {'✓' if ok else '✗'} {table:32} {detail}")


def main() -> int:
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 59.3145
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 18.0705
    print(f"SCB PxWeb probe → {PXWEB_BASE}\n  point: {lat}, {lon}")

    hit = KommunLocator().locate(lat, lon)
    if not hit:
        print("  ✗ no municipality within threshold — pick a Swedish point.")
        return 1
    code, name = hit
    print(f"  municipality: {name} ({code})\n")

    client = ScbClient()
    answered = 0

    # Each probe: (label, table path, callable → value/summary)
    probes = [
        ("population (age/year)", POP_TABLE,
         lambda: population_signals(client, code)),
        ("income index", INCOME_TABLE,
         lambda: income_index_signal(client, code)),
        ("residential density", DENSITY_TABLE,
         lambda: density_signal(client, code)),
    ]
    for label, table, call in probes:
        try:
            val = call()
            answered += 1
            summary = (str({k: round(v, 2) for k, v in val[0].items()})
                       if isinstance(val, tuple) else
                       (round(val, 2) if isinstance(val, (int, float)) else val))
            _line(True, table, f"{label}: {summary}")
        except Exception as e:  # noqa: BLE001 - diagnostics
            _line(False, table, f"{label}: FAILED — {type(e).__name__}: "
                                f"{str(e)[:90]}")

    print()
    if answered:
        print(f"RESULT: {answered}/{len(probes)} SCB tables answered. Any ✗ "
              "means that table path needs correcting against api.scb.se "
              "(check the table id and the metadata-driven query).")
        return 0
    print("RESULT: no SCB table answered. Verify network egress to "
          "api.scb.se and the table paths in engine/datasources/scb.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
