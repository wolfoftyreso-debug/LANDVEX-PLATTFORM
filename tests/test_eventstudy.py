"""Tester för händelsestudie (före/efter + diff-in-diff).
Kör: python3 -m tests.test_eventstudy"""
from __future__ import annotations

from engine import eventstudy as E


def test_before_after_level_and_trend():
    # olyckor: stabilt ~10 före, stiger efter interventionen vid index 5
    series = [10, 10, 11, 9, 10, 13, 15, 17, 19, 21]
    r = E.before_after(series, 5, metric="accidents", event="legalization")
    assert r["pre"]["n"] == 5 and r["post"]["n"] == 5
    assert r["level_change"] > 0
    assert r["post"]["trend"] == "up"
    assert "not an experiment" in r["caveat"]


def test_before_after_bad_split():
    try:
        E.before_after([1, 2, 3], 0)
        raise AssertionError()
    except ValueError:
        pass


def test_diff_in_diff_nets_out_common_trend():
    # Båda grupperna stiger +5 (gemensam trend); behandlade stiger +8 → DiD +3.
    treated_pre = [10, 10]; treated_post = [18, 18]     # +8
    control_pre = [10, 10]; control_post = [15, 15]     # +5
    r = E.diff_in_diff(treated_pre, treated_post, control_pre, control_post,
                       event="legalization")
    assert r["treated_change"] == 8.0 and r["control_change"] == 5.0
    assert r["did_estimate"] == 3.0
    assert "parallel" in r["assumption"].lower()
    assert "one framing" in r["framing"]["note"]


def test_diff_in_diff_zero_when_parallel():
    # Behandlade och kontroller rör sig lika → ingen nettoeffekt.
    r = E.diff_in_diff([5, 5], [9, 9], [20, 20], [24, 24])
    assert r["did_estimate"] == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
