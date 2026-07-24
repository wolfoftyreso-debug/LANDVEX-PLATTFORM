"""Tester för Risk Intelligence / Business Signals-lagret.

Kör utan pytest/nätverk:
    python3 -m tests.test_risk_intel
"""
from __future__ import annotations

from engine.models import Location
from engine.risk_intel import (risk_intelligence, RISK_CATEGORIES,
                               business_signals_framework,
                               counterparty_health_framework,
                               risk_intel_catalog)

_LOC = Location(38.25, -85.75, address="Louisville")


def test_dual_scores_present():
    r = risk_intelligence(_LOC, "elektriker", specialization="laddboxar",
                          market="us")
    assert 0 <= r["opportunity_score"] <= 100
    assert 0 <= r["risk_score"] <= 100
    assert r["risk_band_en"] in ("Low", "Medium", "High", "Very high")


def test_ten_categories_computed_or_monitoring():
    r = risk_intelligence(_LOC, "elektriker", market="us")
    cats = r["risk_categories"]
    assert len(cats) == len(RISK_CATEGORIES) == 10
    for c in cats:
        assert c["status"] in ("computed", "monitoring")
        if c["status"] == "computed":
            assert 0 <= c["risk"] <= 100
            assert c["drivers"], "beräknad kategori ska bära drivsignaler"
        else:
            # Monitoring-kategori: ingen påhittad siffra, bara watchlist.
            assert "risk" not in c
            assert c["watch_en"]


def test_monitoring_categories_are_honest():
    r = risk_intelligence(_LOC, "elektriker", market="us")
    # Kund-/motpartsrisk kräver kreditdata → monitoring, aldrig beräknad.
    cust = next(c for c in r["risk_categories"] if c["id"] == "customer")
    assert cust["status"] == "monitoring"
    assert 0.0 <= r["computed_coverage"] <= 1.0


def test_risk_score_only_aggregates_computed():
    r = risk_intelligence(_LOC, "elektriker", market="us")
    computed = [c for c in r["risk_categories"] if c["status"] == "computed"]
    assert computed, "minst en kategori ska gå att beräkna"
    assert r["computed_coverage"] == round(len(computed) / 10, 2)


def test_trend_not_faked():
    r = risk_intelligence(_LOC, "elektriker", market="us")
    assert r["trend"]["status"] == "requires_monitoring_history"


def test_counterparty_framework_is_cautious():
    cf = counterparty_health_framework()
    assert cf["objective_signals"] and cf["precautions_en"]
    # Får aldrig avråda från affären / dra juridiska slutsatser.
    g = cf["guardrail_en"].lower()
    assert "never" in g and "legal" in g


def test_business_signals_framework_categories():
    bs = business_signals_framework()
    for key in ("financial", "customer", "staffing", "business", "project",
                "market", "public", "supplier"):
        assert key in bs["categories"], f"saknar signalkategori {key}"


def test_recommendations_present():
    r = risk_intelligence(_LOC, "elektriker", market="us")
    assert r["recommendations"]
    for rec in r["recommendations"]:
        assert rec["action_en"] and rec["trigger_en"]


def test_determinism():
    a = risk_intelligence(_LOC, "elektriker", specialization="laddboxar",
                          market="us")
    b = risk_intelligence(_LOC, "elektriker", specialization="laddboxar",
                          market="us")
    assert a == b


def test_catalog_is_data():
    cat = risk_intel_catalog()
    assert len(cat["risk_categories"]) == 10
    assert cat["business_signal_categories"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
