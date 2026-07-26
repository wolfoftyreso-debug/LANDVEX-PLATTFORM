"""Prestandagrind för QUIXZOOM – gör "prestanda är en funktion" körbar.

    python3 -m scripts.perf_budget measurements.json
    python3 -m scripts.perf_budget measurements.json --budgets docs/quixzoom-budgets.json

En funktion bevakas av tester. En prestandaprincip som bara står i ett
dokument bevakas av ingenting. Det här skriptet läser mätningar från
appens telemetri (eller en Playwright-/Lighthouse-körning), jämför mot
budgetarna och **fäller bygget** när en budget överskrids.

Mätfilens form – en lista av tal per budget-id, i millisekunder:

    {"app_start": [820, 910, 1180, ...], "tap_response": [21, 33, ...]}

Två frågor, inte en. Ett absolut tak svarar på *"är det snabbt nog för en
människa?"*. Det fångar aldrig att något blev tio gånger långsammare men
fortfarande ligger under taket. Därför finns även en BASLINJE: mät en gång
när du är nöjd, spara, och låt varje senare körning jämföras mot den.

    python3 -m scripts.perf_budget m.json --baseline docs/x-baseline.json

Taket är användarens gräns. Baslinjen är regressionslarmet. Ett projekt som
bara har det första upptäcker aldrig att det tappat farten.

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


DEFAULT_MAX_REGRESSION = 2.0     # dubbelt så långsamt = regression


def evaluate(measurements: dict, budgets: dict,
             baseline: dict | None = None,
             max_regression: float = DEFAULT_MAX_REGRESSION) -> dict:
    base_vals = (baseline or {}).get("p95", {})
    rows, failed, missing, thin, regressed = [], 0, 0, 0, 0
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
                        round(v - float(b["budget_ms"]), 2),
                        "headroom_x": (round(float(b["budget_ms"]) / v, 1)
                                       if v > 0 else None)})
            if not ok:
                failed += 1
            # Regression mot baslinjen – den fråga taket inte svarar på.
            was = base_vals.get(bid)
            if was:
                factor = v / float(was) if float(was) > 0 else 1.0
                row["baseline_ms"] = float(was)
                row["factor"] = round(factor, 2)
                if factor > max_regression:
                    row["status"] = "regressed"
                    row["note_en"] = (f"{factor:.1f}x slower than the recorded "
                                      f"baseline ({was} ms) — still under the "
                                      f"ceiling, which is exactly why a "
                                      f"ceiling alone would have missed it.")
                    regressed += 1
                    if not ok:
                        failed -= 1        # räkna den en gång
        rows.append(row)
    return {"results": rows, "failed": failed, "unmeasured": missing,
            "insufficient": thin, "regressed": regressed, "total": len(rows),
            "max_regression": max_regression,
            "has_baseline": bool(base_vals)}


def report(res: dict, strict: bool) -> int:
    mark = {"pass": "PASS", "fail": "FAIL", "unmeasured": "----",
            "insufficient": "????", "regressed": "SLOW"}
    print(f"{'':4}  {'budget':22s} {'target':>9s} {'measured':>10s}  where")
    for r in res["results"]:
        val = "—" if r["value_ms"] is None else f"{r['value_ms']:.1f} ms"
        tgt = f"p{r['percentile']:g} <{r['budget_ms']}ms"
        print(f"{mark[r['status']]}  {r['label_en'][:22]:22s} {tgt:>9s} "
              f"{val:>10s}  {r['measured_from']} → {r['measured_to']}")
        if r["status"] == "fail":
            print(f"      over budget by {r['over_by_ms']} ms "
                  f"({r['samples']} samples)")
        elif r["status"] == "regressed":
            print(f"      {r['note_en']}")
        elif r.get("note_en"):
            print(f"      {r['note_en']}")
    print()
    print(f"{res['total']} budgets · {res['failed']} over budget · "
          f"{res.get('regressed', 0)} regressed · "
          f"{res['unmeasured']} unmeasured · {res['insufficient']} thin")
    if not res.get("has_baseline"):
        loose = [r for r in res["results"]
                 if r.get("headroom_x") and r["headroom_x"] >= 20]
        if loose:
            print(f"\nNote: {len(loose)} budget(s) have 20x headroom or more "
                  f"({', '.join(r['id'] for r in loose[:4])}…). A ceiling that "
                  f"loose cannot catch a regression — record a baseline with "
                  f"--save-baseline and compare against it.")
    if res.get("regressed"):
        print("\nSlower than baseline beyond the allowed factor. Under the "
              "ceiling is not the same as unchanged.")
        return 1
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
    basepath = save_base = None
    for i, a in enumerate(argv):
        if a == "--baseline" and i + 1 < len(argv):
            basepath = argv[i + 1]
        if a == "--save-baseline" and i + 1 < len(argv):
            save_base = argv[i + 1]
    args = [x for x in args if x not in (basepath, save_base)]
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
    baseline = None
    if basepath:
        try:
            baseline = json.load(open(basepath, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"could not read baseline: {e}")
            return 66
    res = evaluate(measurements, budgets, baseline=baseline)
    code = report(res, strict)
    if save_base:
        p95 = {r["id"]: r["value_ms"] for r in res["results"]
               if r["value_ms"] is not None}
        json.dump({"p95": p95, "note_en": "Recorded baseline. Absolute "
                   "timings are machine-dependent; what travels is the "
                   "RATIO — record a baseline per environment."},
                  open(save_base, "w", encoding="utf-8"), indent=2,
                  sort_keys=True)
        print(f"\nbaseline written to {save_base} ({len(p95)} entries)")
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
