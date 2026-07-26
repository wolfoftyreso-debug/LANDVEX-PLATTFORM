"""Prestandagrind för QUIXZOOM – gör "prestanda är en funktion" körbar.

    python3 -m scripts.perf_budget measurements.json
    python3 -m scripts.perf_budget measurements.json --budgets docs/quixzoom-budgets.json

En funktion bevakas av tester. En prestandaprincip som bara står i ett
dokument bevakas av ingenting. Det här skriptet läser mätningar från
appens telemetri (eller en Playwright-/Lighthouse-körning), jämför mot
budgetarna och **fäller bygget** när en budget överskrids.

Mätfilens form – en lista av tal per budget-id, i millisekunder:

    {"app_start": [820, 910, 1180, ...], "tap_response": [21, 33, ...]}

Två fel behandlas olika, av samma skäl som registerproben:

  * En budget som SAKNAR mätningar är inte godkänd – den är omätt. Utan
    `--strict` rapporteras den som lucka; med `--strict` fäller den.
    Att tolka tystnad som godkänt är hur budgetar tyst slutar gälla.
  * För få mätpunkter för percentilen (t.ex. 12 värden för p99) ger ett
    ärligt "otillräckligt underlag", aldrig ett godkänt.

Rent stdlib, inga beroenden, körbart i vilken CI som helst.
"""
from __future__ import annotations

import json
import math
import os
import sys

DEFAULT_BUDGETS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs", "quixzoom-budgets.json")


def percentile(values: list[float], p: float) -> float:
    """Percentil med linjär interpolation (samma metod varje gång)."""
    if not values:
        raise ValueError("no values")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return xs[int(k)]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def min_samples_for(p: float) -> int:
    """Hur många mätpunkter percentilen kräver för att betyda något.

    p95 behöver minst 20 punkter, p99 minst 100 – annars beskriver
    percentilen bara den värsta mätningen och låtsas vara statistik.
    """
    return max(5, int(math.ceil(100.0 / max(1e-9, 100.0 - p))))


def evaluate(measurements: dict, budgets: dict) -> dict:
    rows, failed, missing, thin = [], 0, 0, 0
    for b in budgets["budgets"]:
        bid, p = b["id"], float(b["percentile"])
        vals = [float(v) for v in (measurements.get(bid) or [])
                if isinstance(v, (int, float))]
        need = min_samples_for(p)
        row = {"id": bid, "label_en": b["label_en"],
               "budget_ms": b["budget_ms"], "percentile": p,
               "measured_from": b["from"], "measured_to": b["to"],
               "samples": len(vals)}
        if not vals:
            row.update({"status": "unmeasured", "value_ms": None,
                        "note_en": "No measurements supplied. Not a pass — "
                                   "an unmeasured budget is simply unknown."})
            missing += 1
        elif len(vals) < need:
            row.update({"status": "insufficient", "value_ms": None,
                        "note_en": f"{len(vals)} samples for p{p:g} needs "
                                   f">= {need}; the percentile would just be "
                                   f"the worst reading wearing a hat."})
            thin += 1
        else:
            v = round(percentile(vals, p), 2)
            ok = v <= float(b["budget_ms"])
            row.update({"status": "pass" if ok else "fail", "value_ms": v,
                        "over_by_ms": None if ok else
                        round(v - float(b["budget_ms"]), 2)})
            if not ok:
                failed += 1
        rows.append(row)
    return {"results": rows, "failed": failed, "unmeasured": missing,
            "insufficient": thin, "total": len(rows)}


def report(res: dict, strict: bool) -> int:
    mark = {"pass": "PASS", "fail": "FAIL", "unmeasured": "----",
            "insufficient": "????"}
    print(f"{'':4}  {'budget':22s} {'target':>9s} {'measured':>10s}  where")
    for r in res["results"]:
        val = "—" if r["value_ms"] is None else f"{r['value_ms']:.1f} ms"
        tgt = f"p{r['percentile']:g} <{r['budget_ms']}ms"
        print(f"{mark[r['status']]}  {r['label_en'][:22]:22s} {tgt:>9s} "
              f"{val:>10s}  {r['measured_from']} → {r['measured_to']}")
        if r["status"] == "fail":
            print(f"      over budget by {r['over_by_ms']} ms "
                  f"({r['samples']} samples)")
        elif r.get("note_en"):
            print(f"      {r['note_en']}")
    print()
    print(f"{res['total']} budgets · {res['failed']} over budget · "
          f"{res['unmeasured']} unmeasured · {res['insufficient']} thin")
    if res["failed"]:
        print("\nBudget exceeded. Performance is a feature, so this is a "
              "failing test — not a warning to triage later.")
        return 1
    if strict and (res["unmeasured"] or res["insufficient"]):
        print("\n--strict: a budget nobody measured cannot pass. Add the "
              "measurement or remove the budget; do not leave it silent.")
        return 2
    if res["unmeasured"] or res["insufficient"]:
        print("\nAll measured budgets are within target. The unmeasured ones "
              "are reported as unknown, not as passing.")
    else:
        print("\nAll budgets measured and within target.")
    return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    strict = "--strict" in argv
    bpath = DEFAULT_BUDGETS
    for i, a in enumerate(argv):
        if a == "--budgets" and i + 1 < len(argv):
            bpath = argv[i + 1]
            args = [x for x in args if x != bpath]
    if not args:
        print(__doc__)
        return 64
    try:
        measurements = json.load(open(args[0], encoding="utf-8"))
        budgets = json.load(open(bpath, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"could not read input: {e}")
        return 66
    return report(evaluate(measurements, budgets), strict)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
