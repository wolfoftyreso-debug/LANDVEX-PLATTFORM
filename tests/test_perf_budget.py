"""Tester för prestandagrinden (QUIXZOOM-doktrinen).
Kör: python3 -m tests.test_perf_budget"""
from __future__ import annotations

import json
import os

from scripts.perf_budget import (DEFAULT_BUDGETS, evaluate, min_samples_for,
                                 percentile)

BUDGETS = json.load(open(DEFAULT_BUDGETS, encoding="utf-8"))


def test_every_budget_states_where_it_is_measured():
    """Ett tal utan mätpunkt är en åsikt, inte en budget."""
    ids = set()
    for b in BUDGETS["budgets"]:
        assert b["from"] and b["to"], b["id"]
        assert b["budget_ms"] > 0 and 50 <= b["percentile"] <= 100, b["id"]
        assert b["why_en"], b["id"]
        assert b["id"] not in ids, f"dubblett: {b['id']}"
        ids.add(b["id"])
    assert {"app_start", "tap_response", "camera_start",
            "capture_queued", "scroll_frame"} <= ids


def test_the_one_that_may_never_fail_is_measured_hardest():
    """Att tappa en observation är att tappa fältarbete."""
    q = [b for b in BUDGETS["budgets"] if b["id"] == "capture_queued"][0]
    assert q["percentile"] == 99
    assert min_samples_for(99) > min_samples_for(95)


def test_percentile_is_one_defined_method():
    xs = list(range(1, 101))
    assert percentile(xs, 50) == 50.5
    assert percentile(xs, 95) == 95.05
    assert percentile([7], 99) == 7


def test_within_budget_passes_and_over_budget_fails():
    ok = evaluate({"tap_response": [20] * 30}, BUDGETS)
    row = [r for r in ok["results"] if r["id"] == "tap_response"][0]
    assert row["status"] == "pass" and ok["failed"] == 0

    bad = evaluate({"tap_response": [20] * 25 + [400] * 5}, BUDGETS)
    row = [r for r in bad["results"] if r["id"] == "tap_response"][0]
    assert row["status"] == "fail" and row["over_by_ms"] > 0
    assert bad["failed"] == 1


def test_an_unmeasured_budget_is_never_a_pass():
    """Tystnad får aldrig tolkas som godkänt — så slutar budgetar gälla."""
    res = evaluate({}, BUDGETS)
    assert res["failed"] == 0
    assert res["unmeasured"] == len(BUDGETS["budgets"])
    for r in res["results"]:
        assert r["status"] == "unmeasured"
        assert "Not a pass" in r["note_en"]


def test_too_few_samples_is_reported_not_approved():
    res = evaluate({"capture_queued": [10, 12, 9]}, BUDGETS)   # p99 av 3
    row = [r for r in res["results"] if r["id"] == "capture_queued"][0]
    assert row["status"] == "insufficient"
    assert row["value_ms"] is None and res["failed"] == 0
    assert "samples" in row["note_en"]


def test_state_rules_never_let_the_ui_claim_a_server_fact_early():
    """Optimistisk om enheten, ärlig om servern."""
    rules = {r["event"]: r for r in BUDGETS["state_rules"]}
    assert rules["photo captured"]["ui_may_claim"] == "Saved"
    assert rules["photo captured"]["immediate"] is True
    # "Sending" direkt — men aldrig "Delivered" innan servern svarat
    assert rules["upload started"]["ui_may_claim"] == "Sending"
    assert rules["upload started"]["immediate"] is True
    assert rules["server acknowledged"]["ui_may_claim"] == "Delivered"
    assert rules["server acknowledged"]["immediate"] is False
    for r in BUDGETS["state_rules"]:
        if r["immediate"]:
            assert r["ui_may_claim"] != "Delivered", r["event"]


def test_a_failing_budget_is_an_error_not_a_warning():
    """Prestanda är en funktion: överskriden budget fäller bygget."""
    from scripts.perf_budget import report
    res = evaluate({"app_start": [3000] * 30}, BUDGETS)
    assert report(res, strict=False) == 1
    # och en omätt budget fäller under --strict
    assert report(evaluate({}, BUDGETS), strict=True) == 2
    assert report(evaluate({}, BUDGETS), strict=False) == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
