"""Tester för affärsprofil + Sverigesvep. Körs utan pytest:
python3 -m tests.test_scan"""
from __future__ import annotations

from engine import scan as scan_mod
from engine.models import Location
from engine.profile import (BusinessProfile, profile_from_dict,
                            profile_options)
from engine.scan import SCAN_LEVELS, scan
from engine.scoring import analyze
from engine.verticals import VERTICALS


def _profile(**kw) -> BusinessProfile:
    return profile_from_dict({"vertical_id": "frisor", **kw})


# ── Profil ───────────────────────────────────────────────────────────

def test_profile_options_cover_all_fields():
    opts = profile_options()
    for key in ("vertical_id", "budget_band", "team_size", "business_model",
                "risk_tolerance", "commute_km", "environments",
                "horizon_years", "goal"):
        assert key in opts and opts[key], key
        assert all("label_sv" in o for o in opts[key]), key
    assert {o["id"] for o in opts["vertical_id"]} == set(VERTICALS)


def test_profile_validation():
    p = _profile(budget_band="2-5m", goal="bygga_kedja",
                 environments=["stad", "turistort"], name="Min salong")
    assert p.environments == ("stad", "turistort")
    for bad in [{"vertical_id": "rymdturism"},
                {"vertical_id": "frisor", "budget_band": "1kr"},
                {"vertical_id": "frisor", "goal": "världsherravälde"},
                {"vertical_id": "frisor", "environments": ["månen"]},
                {"vertical_id": "frisor", "commute_km": -5},
                {"vertical_id": "frisor", "commute_km": 30}]:  # saknar hemkoordinater
        try:
            profile_from_dict(bad)
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


# ── Signalnedbrytning i rapporten (grund för korten) ─────────────────

def test_report_exposes_signals_and_risk_score():
    r = analyze(Location(59.3145, 18.0705), "frisor")
    assert r.signals and all(
        set(s) == {"value", "source", "quality", "normalized"}
        for s in r.signals.values())
    assert all(0.0 <= s["normalized"] <= 1.0 for s in r.signals.values())
    assert 0.0 <= r.risk_score <= 1.0


# ── Svepet ───────────────────────────────────────────────────────────

def test_scan_ranks_and_bands():
    res = scan(_profile(), top_n=5)
    assert res["candidates_scanned"] == 40
    assert len(res["heatmap"]) == 40
    assert all(h["band"] in ("gron", "gul", "rod") for h in res["heatmap"])
    hs = res["hotspots"]
    assert len(hs) == 5
    assert [h["rank"] for h in hs] == [1, 2, 3, 4, 5]
    assert all(hs[i]["rank_score"] >= hs[i + 1]["rank_score"]
               for i in range(len(hs) - 1))


def test_scan_deterministic():
    a, b = scan(_profile()), scan(_profile())
    assert a == b


def test_decision_card_contract():
    card = scan(_profile(), top_n=1)["hotspots"][0]
    for key in ("kommun", "opportunity_score", "rank_score", "confidence",
                "risk_index", "risk_level", "market_momentum",
                "competition_gap", "time_window_months", "drivers",
                "economy_scenario", "expected_roi", "next_steps_sv",
                "motivering_sv", "factors", "environment", "data_coverage"):
        assert key in card, key
    assert 0 <= card["confidence"] <= 100
    assert 0 <= card["risk_index"] <= 100
    assert 6 <= card["time_window_months"] <= 36
    assert 1 <= len(card["drivers"]) <= 10
    assert all(d["direction"] in ("driver", "hammar") for d in card["drivers"])
    # Ärlighetsprinciperna: ROI utlovas inte, schablonen är märkt.
    assert card["expected_roi"]["status"] == "ej_tillgangligt"
    assert "prognos" in card["economy_scenario"]["notis_sv"]


def test_commute_filter():
    res = scan(_profile(commute_km=100, home_lat=59.33, home_lon=18.06))
    assert res["excluded"]["pendling"] > 0
    assert res["candidates_scanned"] < 40
    names = {h["kommun"] for h in res["heatmap"]}
    assert "Umeå" not in names and "Malmö" not in names
    assert "Uppsala" in names


def test_environment_filter():
    res = scan(_profile(environments=["turistort"]))
    assert all("turistort" in h["environment"] for h in res["hotspots"])
    assert res["excluded"]["miljo"] > 0
    # Värmekartan visar fortfarande hela svepet.
    assert len(res["heatmap"]) == 40


def test_risk_tolerance_affects_ranking():
    low = scan(_profile(risk_tolerance="lag"))
    agg = scan(_profile(risk_tolerance="aggressiv"))
    by_kommun = {h["kommun"]: h["rank_score"] for h in low["hotspots"]}
    diffs = [h["rank_score"] - by_kommun[h["kommun"]]
             for h in agg["hotspots"] if h["kommun"] in by_kommun]
    # Aggressiv tolerans tar bort riskstraffet → högre rank_score.
    assert diffs and all(d > 0 for d in diffs)
    # Grundscoren påverkas aldrig av profilen.
    assert all(h["opportunity_score"] == next(
        g["opportunity_score"] for g in low["hotspots"]
        if g["kommun"] == h["kommun"])
        for h in agg["hotspots"] if h["kommun"] in by_kommun)


def test_detail_level_scans_five_points_per_kommun():
    over = scan(_profile(), level="oversikt")
    det = scan(_profile(), level="detaljerad")
    assert over["candidates_scanned"] == 40
    assert det["candidates_scanned"] == 200
    assert det["kommuner_scanned"] == 40
    # Fortfarande max en hotspot per kommun – bästa punkten vinner.
    koder = [h["kommun_kod"] for h in det["hotspots"]]
    assert len(koder) == len(set(koder))
    assert all(h["punkt"] in dict.fromkeys(
        lbl for _, _, lbl in SCAN_LEVELS["detaljerad"]) for h in det["hotspots"])
    assert scan(_profile(), level="detaljerad") == det   # determinism
    try:
        scan(_profile(), level="ultra")
    except ValueError:
        pass
    else:
        raise AssertionError("Okänd nivå ska ge ValueError")


def test_new_verticals_scan_and_have_schablons():
    # Schablontabellerna ska täcka alla vertikaler (annars kraschar kortet).
    assert set(scan_mod._REVENUE_PER_PERSON_TKR) == set(VERTICALS)
    assert set(scan_mod._STARTUP_TKR) == set(VERTICALS)
    for vid in ("bilverkstad", "veterinar", "lager"):
        res = scan(profile_from_dict({"vertical_id": vid}), top_n=3)
        assert len(res["hotspots"]) == 3, vid
        card = res["hotspots"][0]
        assert card["drivers"], vid
        assert card["economy_scenario"]["omsattningsscenario_tkr_ar"] > 0, vid


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
