"""Tester för feed-event-bussen. Kör: python3 -m tests.test_feeds"""
from __future__ import annotations

from engine import feeds as F


def test_top_changes_threshold_and_severity():
    rows = [{"code": "a", "region": "SE", "trend_percent": 8, "confidence": 0.9},
            {"code": "b", "region": "SE", "trend_percent": 1, "confidence": 0.9}]
    ev = F.generate("daily_top_changes", rows)
    assert len(ev) == 1 and ev[0]["kpi_ids"] == ["a"]     # b under tröskel 3
    assert ev[0]["severity"] == "high"                    # 8% ≥ 5


def test_checksum_dedup_across_calls():
    rows = [{"code": "a", "region": "SE", "trend_percent": 8, "confidence": 0.9}]
    seen = set()
    first = F.generate("daily_top_changes", rows, seen)
    second = F.generate("daily_top_changes", rows, seen)
    assert len(first) == 1 and len(second) == 0           # samma händelse, dedup


def test_structural_decline_critical():
    rows = [{"code": "x", "region": "SE", "trend_percent": -4,
             "declining_periods": 4, "total_decline_pct": -18, "confidence": 0.8}]
    ev = F.generate("structural_decline", rows)
    assert ev and ev[0]["severity"] == "critical"         # ≤ −15


def test_structural_decline_ignores_short_runs():
    rows = [{"code": "x", "region": "SE", "trend_percent": -4,
             "declining_periods": 2, "total_decline_pct": -8}]
    assert F.generate("structural_decline", rows) == []


def test_priority_alerts_signal_gate():
    rows = [{"code": "z", "region": "SE", "signal_strength": 0.95,
             "confidence": 0.9, "status": "critical"},
            {"code": "w", "region": "SE", "signal_strength": 0.5, "confidence": 0.9}]
    ev = F.generate("priority_alerts", rows)
    assert len(ev) == 1 and ev[0]["severity"] == "critical"


def test_regional_anomalies_needs_two():
    one = [{"code": "a", "region": "SE", "trend_percent": 9, "confidence": 0.8}]
    two = one + [{"code": "b", "region": "SE", "trend_percent": 12, "confidence": 0.8}]
    assert F.generate("regional_anomalies", one) == []
    assert len(F.generate("regional_anomalies", two)) == 1


def test_unknown_feed_raises():
    try:
        F.generate("nope", [])
        raise AssertionError()
    except ValueError:
        pass


def test_catalog():
    assert {"daily_top_changes", "structural_decline"} <= {f["code"] for f in F.catalog()}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
