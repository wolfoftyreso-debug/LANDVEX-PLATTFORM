"""Live-prob mot Kolada och Eurostat för livsvillkorssignalerna.

    LANDVEX_KOLADA_URL=https://api.kolada.se/v2 python3 -m scripts.livability_probe 0138
    LANDVEX_EUROSTAT_LIVE=1 python3 -m scripts.livability_probe 0138 SE

Avgör vilka KPI-/dataset-id:n som faktiskt svarar. Kandidater som inte
svarar ska plockas bort eller ersättas – de får aldrig stå kvar och se
kopplade ut.
"""
from __future__ import annotations

import sys

from engine.datasources.livability_sources import (EUROSTAT_SIGNALS,
                                                   KOLADA_SIGNALS,
                                                   EurostatLivability,
                                                   KoladaLivability, catalog)


def main(argv: list[str]) -> int:
    kommun = argv[1] if len(argv) > 1 else "0180"
    geo = argv[2] if len(argv) > 2 else "SE"
    cat = catalog()
    print(f"Kolada: {cat['kolada']['verified_count']} confirmed, "
          f"{cat['kolada']['candidate_count']} candidates")
    k = KoladaLivability()
    if not k.connected:
        print("  ! LANDVEX_KOLADA_URL not set — nothing to probe.")
    else:
        for sid, spec in KOLADA_SIGNALS.items():
            got = k.value(sid, kommun)
            mark = "confirmed" if spec["verified"] else "candidate"
            if got is None:
                print(f"  ✗ {sid:24s} {spec['kpi']:8s} ({mark}) no answer")
            else:
                print(f"  ✓ {sid:24s} {spec['kpi']:8s} ({mark}) "
                      f"raw={got['raw_value']} → {got['value']} "
                      f"[{got['transform']}] {got['year']}")
    print()
    e = EurostatLivability()
    if not e.connected:
        print("Eurostat: LANDVEX_EUROSTAT_LIVE=1 not set — nothing to probe.")
        return 0
    for sid, spec in EUROSTAT_SIGNALS.items():
        got = e.value(sid, geo)
        if got is None:
            print(f"  ✗ {sid:24s} {spec['dataset']:16s} no answer")
        else:
            print(f"  ✓ {sid:24s} {spec['dataset']:16s} "
                  f"raw={got['raw_value']} → {got['value']} {got['year']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
