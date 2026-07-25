"""Tester för den generiska viktade scorern.
Kör: python3 -m tests.test_scorekit"""
from __future__ import annotations

from engine import scorekit
from engine.scorekit import ACTION, ACTION_BANDS, Component, band, score


def test_weighted_average_basic():
    comps = [Component("a", 1.0), Component("b", 1.0)]
    r = score(comps, {"a": 100, "b": 0})
    assert r["total"] == 50.0


def test_weights_normalized_even_if_not_sum_one():
    # vikt 3:1 → 75/25-blandning
    comps = [Component("a", 3.0), Component("b", 1.0)]
    r = score(comps, {"a": 100, "b": 0})
    assert r["total"] == 75.0


def test_invert_flips_value():
    # risk inverteras: hög risk (100) → lågt effektivt bidrag (0)
    r = score([Component("risk", 1.0, invert=True)], {"risk": 100})
    assert r["total"] == 0.0
    r2 = score([Component("risk", 1.0, invert=True)], {"risk": 0})
    assert r2["total"] == 100.0


def test_missing_key_is_zero():
    r = score([Component("a", 1.0)], {})
    assert r["total"] == 0.0


def test_highlight_threshold():
    assert score([Component("a", 1.0)], {"a": 60})["highlight"] is True
    assert score([Component("a", 1.0)], {"a": 40})["highlight"] is False


def test_primary_reason_is_top_contributor():
    comps = [Component("a", 1.0, reason="A wins"),
             Component("b", 1.0, reason="B loses")]
    r = score(comps, {"a": 90, "b": 10})
    assert r["primary_reason"] == "A wins"


def test_action_profile_matches_dissg_formula():
    # weighted = effect*.40 + (100-cost)*.25 + (100-risk)*.20 + reversibility*.15
    vals = {"effect": 80, "cost": 20, "risk": 30, "reversibility": 60}
    r = score(list(ACTION), vals)
    expected = 80 * .40 + (100 - 20) * .25 + (100 - 30) * .20 + 60 * .15
    assert abs(r["total"] - expected) < 1e-6


def test_band_bucketing():
    assert band(85, ACTION_BANDS) == "critical"
    assert band(70, ACTION_BANDS) == "high"
    assert band(50, ACTION_BANDS) == "medium"
    assert band(10, ACTION_BANDS) == "monitor"


def test_empty_components():
    r = score([], {"a": 100})
    assert r["total"] == 0.0 and r["highlight"] is False


def test_profiles_exist():
    assert len(scorekit.RELEVANCE) == 6
    assert len(scorekit.WORTHINESS) == 5


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
