"""Tester för Opportunity Intelligence-lagret (Business Navigation).

Kör utan pytest/nätverk (deterministisk mock-källkedja):
    python3 -m tests.test_opportunity_intel
"""
from __future__ import annotations

from engine.models import Location
from engine.opportunity_intel import (opportunity_intel, support_programs,
                                       hidden_opportunities, legal_guide,
                                       lifecycle_advisor, program_catalog)
from engine.scoring import analyze

_LOC = Location(38.25, -85.75, address="Louisville")


def test_composite_has_all_navigation_blocks():
    r = opportunity_intel(_LOC, "elektriker", specialization="laddboxar",
                          team_size="2-5", market="us")
    for key in ("support_programs", "missing_money", "hidden_opportunities",
                "legal_guide", "lifecycle", "expansion_advisor", "caveats_en"):
        assert key in r, f"saknar block: {key}"
    assert r["opportunity_score"] is not None


def test_support_programs_are_honest_estimates():
    rep = analyze(_LOC, "elektriker")
    sp = support_programs(rep, "elektriker", "laddboxar")
    assert sp["count"] >= 1
    for p in sp["programs"]:
        assert 0 <= p["fit"] <= 100
        assert 0 <= p["eligibility_probability_pct"] <= 90
        lo, hi = p["amount_band_local"]
        assert lo <= p["amount_estimate_local"] <= hi
        assert p["evidence"], "varje program ska bära bevis (signaler)"
    # Aldrig fejkat live-belopp – notisen ska ange schablon/adapter.
    assert "not yet live" in sp["notis_en"] or "live" in sp["notis_en"].lower()


def test_vertical_filter_applies():
    rep = analyze(_LOC, "restaurang")
    sp = support_programs(rep, "restaurang")
    ids = {p["id"] for p in sp["programs"]}
    # Ett elbranschspecifikt program ska inte dyka upp för restaurang.
    assert "ev_charging_infra" not in ids


def test_hidden_opportunities_carry_evidence_or_empty():
    rep = analyze(_LOC, "elektriker")
    ho = hidden_opportunities(rep, "elektriker")
    assert ho["count"] == len(ho["opportunities"])
    for o in ho["opportunities"]:
        assert o["evidence"], "en dold möjlighet ska motiveras med signaler"
        assert 0 <= o["strength"] <= 100


def test_legal_guide_includes_vertical_specific_category():
    lg = legal_guide("elektriker", bidding_public=True)
    ids = {c["id"] for c in lg["regulations"]}
    assert "electrical_safety" in ids          # branschspecifik
    assert "work_environment" in ids           # generisk
    assert "procurement_rules" in ids          # p.g.a. bidding_public
    assert "not legal advice" in lg["notis_en"]


def test_lifecycle_stage_progresses_with_size():
    assert lifecycle_advisor("enskild_firma", "1")["stage"] == "start"
    assert lifecycle_advisor("aktiebolag", "5-20")["stage"] == "expand"
    mature = lifecycle_advisor("aktiebolag", "50+")
    assert mature["stage"] == "mature"
    assert mature["prepare_next_en"]           # sista steget föreslår ändå nästa


def test_missing_money_only_counts_combinable():
    r = opportunity_intel(_LOC, "elektriker", market="us")
    for p in r["missing_money"]["unclaimed_programs"]:
        # Alla i "missing money" måste vara kombinerbara.
        prog = next(x for x in r["support_programs"]["programs"]
                    if x["id"] == p["id"])
        assert prog["combinable"]


def test_determinism():
    a = opportunity_intel(_LOC, "elektriker", specialization="laddboxar",
                          market="us")
    b = opportunity_intel(_LOC, "elektriker", specialization="laddboxar",
                          market="us")
    assert a == b


def test_catalog_is_data():
    cat = program_catalog()
    assert cat["programs"] and cat["hidden_rules"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
