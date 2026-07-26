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
    args = [a for a in argv[1:] if not a.startswith("--")]
    apply = "--apply" in argv
    kommun = args[0] if args else "0180"
    geo = args[1] if len(args) > 1 else "SE"
    results = {"kolada": {}, "eurostat": {}}
    cat = catalog()
    print(f"Kolada: {cat['kolada']['verified_count']} confirmed, "
          f"{cat['kolada']['candidate_count']} candidates")
    k = KoladaLivability()
    reach_ok = True
    if not k.connected:
        print("  ! LANDVEX_KOLADA_URL not set — nothing to probe.")
    elif not k.reachable()[0]:
        reach_ok = False
        print(f"  ! Host unreachable ({k.reachable()[1][:80]}).")
        print("    NOT recording anything: an unreachable host says nothing "
              "about whether a KPI exists. Recording it would erase what is "
              "already known.")
    else:
        for sid, spec in KOLADA_SIGNALS.items():
            got = k.value(sid, kommun)
            mark = "confirmed" if spec["verified"] else "candidate"
            results["kolada"][sid] = got is not None
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
        return _finish(results, apply and reach_ok, reach_ok)
    ok, why = e.reachable()
    if not ok:
        print(f"Eurostat: host unreachable ({why[:70]}) — recording nothing.")
        return _finish({"kolada": results["kolada"]}, apply and reach_ok,
                       reach_ok)
    for sid, spec in EUROSTAT_SIGNALS.items():
        got = e.value(sid, geo)
        results["eurostat"][sid] = got is not None
        if got is None:
            print(f"  ✗ {sid:24s} {spec['dataset']:16s} no answer")
        else:
            print(f"  ✓ {sid:24s} {spec['dataset']:16s} "
                  f"raw={got['raw_value']} → {got['value']} {got['year']}")
    return _finish(results, apply and reach_ok, reach_ok)


def _finish(results: dict, apply: bool, reachable: bool = True) -> int:
    if not reachable:
        print("\nNothing recorded — the hosts could not be reached, so this "
              "run proves nothing about the KPIs. Existing knowledge is left "
              "untouched.")
        return 3
    if not apply:
        print("\n(dry run — pass --apply to record which KPIs answered)")
        return 0
    from datetime import datetime, timezone
    from engine.datasources.livability_sources import save_verification
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = save_verification(results, stamp)
    ok = sum(1 for f in results.values() for v in f.values() if v)
    bad = sum(1 for f in results.values() for v in f.values() if not v)
    print(f"\nRecorded to {path}: {ok} answered, {bad} did not.")
    if bad:
        print("The ones that did not answer stay unverified and keep the "
              "lower quality weight — replace or remove them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
