"""Tester för meritmotorn – framgång premierad på samma bevisregler.
Kör: python3 -m tests.test_merit"""
from __future__ import annotations

from engine import merit as M
from engine.merit_scan import market_merit, region_merit


def _sig(**kw):
    return {k: {"value": v, "source": "mock"} for k, v in kw.items()}


FULL = _sig(business_density=60, pop_growth_pct=5, labor_participation=80,
            education_outcomes=75, office_workers=3000, tourism_index=40,
            logistics_access=7, building_permits=150, infra_invest=200,
            detail_plans=10, housing_affordability=60, life_satisfaction=70,
            energy_resilience=80, digital_connectivity=85)


def test_dimensions_are_data_with_signals_that_exist():
    from engine.signals import CATALOG
    assert len(M.DIMENSIONS) == 6
    for did, spec in M.DIMENSIONS.items():
        assert spec["label_en"] and spec["means_en"]
        assert abs(sum(w for _, w in spec["signals"]) - 1.0) < 1e-6, did
        for sid, _ in spec["signals"]:
            assert sid in CATALOG, (did, sid)


def test_thin_coverage_refuses_to_judge_either_way():
    out = M.merit("0138", "Tyresö", _sig(business_density=60))
    assert out["status"] == "insufficient_basis"
    assert "either way" in out["reason_en"]


def test_merit_reports_how_and_why_without_claiming_causation():
    peers = {d: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0] for d in M.DIMENSIONS}
    out = M.merit("0880", "Kalmar", FULL, peer_scores=peers)
    assert out["status"] == "assessed"
    assert out["leads_on"], "ledde inte på någon dimension trots svaga peers"
    assert "leads on" in out["how_en"]
    assert "measurably different" in out["why_en"]
    # Aldrig kausalitet – varken i text eller i inramningen.
    assert out["framing"]["choices"]["not_causal"] is True
    for word in ("because", "caused", "thanks to"):
        assert word not in out["why_en"].lower()


def test_every_driver_carries_its_source():
    peers = {d: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0] for d in M.DIMENSIONS}
    out = M.merit("0880", "Kalmar", FULL, peer_scores=peers)
    for d in out["dimensions"]:
        for drv in d["drivers"]:
            assert drv["source"], (d["dimension"], drv["signal_id"])
            assert "normalized" in drv and "value" in drv
    # simulerade värden ska synas som simulerade
    assert all(drv["source"] == "mock"
               for d in out["dimensions"] for drv in d["drivers"])


def test_the_same_standard_is_stated_explicitly():
    peers = {d: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0] for d in M.DIMENSIONS}
    out = M.merit("0880", "Kalmar", FULL, peer_scores=peers)
    txt = out["same_standard_en"].lower()
    assert "same" in txt and "causation" in txt
    assert "refusal to answer when coverage is thin" in txt


def test_not_leading_is_reported_as_a_finding_not_an_omission():
    peers = {d: [95.0, 96.0, 97.0, 98.0, 99.0, 99.5] for d in M.DIMENSIONS}
    out = M.merit("0138", "Tyresö", FULL, peer_scores=peers)
    assert out["leads_on"] == []
    assert "not lead" in out["how_en"] and "not an omission" in out["how_en"]


def test_percentiles_need_a_peer_group():
    out = M.merit("0880", "Kalmar", FULL, peer_scores={d: [1.0, 2.0]
                                                      for d in M.DIMENSIONS})
    for d in out["dimensions"]:
        assert d["percentile"] is None and d["leads"] is None


def test_ranking_is_ordered_and_every_row_explains_itself():
    r = market_merit("se", top_n=8)
    assert r["assessed"] >= M.MIN_PEERS
    scores = [m["overall"] for m in r["ranking"]]
    assert scores == sorted(scores, reverse=True)
    for i, m in enumerate(r["ranking"], 1):
        assert m["rank"] == i
        assert m["how_en"] and m["why_en"] and m["same_standard_en"]
    assert r["framing"]["choices"]["not_causal"] is True


def test_region_merit_compares_against_the_rest_of_the_market():
    out = region_merit("Örebro", market="se")
    assert out["status"] == "assessed" and out["region"] == "Örebro"
    assert any(d["percentile"] is not None for d in out["dimensions"])
    try:
        region_merit("Leningrad", market="se")
        raise AssertionError("bedömde en region som inte täcks")
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
