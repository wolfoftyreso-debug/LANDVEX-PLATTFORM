"""Tester för livsvillkorsmotorn (hushållsviktad platsvärdering).
Kör: python3 -m tests.test_livability"""
from __future__ import annotations

from engine import livability as L
from engine.livability_scan import livability_ranking


def _sig(**kw):
    return {k: {"value": v, "source": "mock"} for k, v in kw.items()}


FULL = _sig(care_supply=8, families_share=25, education_outcomes=80,
            digital_connectivity=85, crime_index=90, road_safety=80,
            housing_affordability=70, rent_index=90, healthcare_access=85,
            social_trust=75, life_satisfaction=78, transit_score=7,
            active_mobility=70, food_access=80, haircut_price=30)


def test_households_and_dimensions_are_consistent_data():
    from engine.signals import CATALOG
    for hid, h in L.HOUSEHOLDS.items():
        assert abs(sum(h["weights"].values()) - 1.0) < 1e-6, hid
        assert set(h["weights"]) == set(L.DIMENSIONS), hid
        assert h["label_en"] and h["means_en"]
    for did, spec in L.DIMENSIONS.items():
        assert spec["label_en"] and spec["means_en"]
        for sid, _ in spec["signals"]:
            assert sid in CATALOG, (did, sid)


def test_the_household_changes_the_weighting():
    """Byt hushåll och prioriteringen ska faktiskt ändras."""
    sp = L.HOUSEHOLDS["single_parent"]["weights"]
    single = L.HOUSEHOLDS["single"]["weights"]
    sn = L.HOUSEHOLDS["single_parent_special_needs"]["weights"]
    assert single["childcare"] == 0.0 and sp["childcare"] > 0.1
    assert sn["support_services"] > sp["support_services"]
    assert sn["support_services"] == max(sn.values())   # tyngst av alla


def test_scores_stay_in_range():
    for hid in L.HOUSEHOLDS:
        out = L.score_place(hid, FULL, job_demand=100.0, net_pay=100.0)
        assert out["score"] is not None
        assert 0 <= out["score"] <= 100, (hid, out["score"])
        for d in out["dimensions"]:
            assert d["score"] is None or 0 <= d["score"] <= 100


def test_unknown_household_is_rejected():
    try:
        L.score_place("astronaut", FULL)
        raise AssertionError("okänt hushåll tilläts")
    except ValueError:
        pass


def test_right_to_work_is_the_first_thing_reported():
    """En EU-medborgare möter helt olika hinder i EU och i USA."""
    eu = L.mobility("sjukskoterska", "es")
    us = L.mobility("sjukskoterska", "us")
    assert eu["barrier"] == "low" and us["barrier"] == "high"
    assert any("freedom of movement" in s for s in eu["steps_en"])
    assert any("automatic recognition" in s for s in eu["steps_en"])
    joined = " ".join(us["steps_en"])
    assert "visa" in joined and "NCLEX-RN" in joined
    assert "state board of nursing" in joined
    assert "not transfer between" in joined     # licens per delstat
    unknown = L.mobility("sjukskoterska", "ng")
    assert unknown["barrier"] == "unknown"
    assert "does not guess" in unknown["practical_en"]


def test_ranking_leads_with_the_barrier_and_shows_both_ends():
    r = livability_ranking("sjukskoterska", "single_parent",
                           markets=["se", "us"], top_n=5, per_market=6)
    assert r["ranking"] and r["worst"]
    assert any("barrier high" in b for b in r["before_you_compare_en"])
    assert "take it or leave it" in r["spread_en"]
    # varje rad bär sitt marknadshinder, inte bara toppen
    for row in r["ranking"]:
        assert row["mobility"]["barrier"] in ("low", "high", "unknown")
        assert row["carries_en"] and row["costs_en"]
    assert r["ranking"][0]["score"] >= r["worst"][0]["score"]


def test_special_needs_household_reorders_the_answer():
    a = livability_ranking("sjukskoterska", "single_parent",
                           markets=["se"], top_n=6, per_market=20)
    b = livability_ranking("sjukskoterska", "single_parent_special_needs",
                           markets=["se"], top_n=6, per_market=20)
    assert [x["region"] for x in a["ranking"]] != \
           [x["region"] for x in b["ranking"]], "vikterna gav samma lista"
    sup = [d for d in b["ranking"][0]["dimensions"]
           if d["dimension"] == "support_services"][0]
    assert sup["weight"] > 0.15 and sup["drivers"]


def test_simulated_share_and_limits_are_declared():
    r = livability_ranking("sjukskoterska", "single_parent",
                           markets=["se"], top_n=3, per_market=5)
    assert r["measured_share"] == 0.0        # allt mock i denna miljö
    joined = " ".join(r["caveats_en"]).lower()
    assert "simulated" in joined
    assert "not legal advice" in joined
    assert "case by case" in joined          # särskilt stöd avgörs individuellt
    assert "purchasing-power" in joined      # valutaomräkningen är inte PPP
    assert r["framing"]["choices"]["not_legal_advice"] is True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
