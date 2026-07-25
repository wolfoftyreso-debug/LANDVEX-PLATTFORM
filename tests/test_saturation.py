"""Tester för marknadsmättnad + företagsregister.
Kör: python3 -m tests.test_saturation"""
from __future__ import annotations

import json

from engine import registers as R
from engine import saturation as S
from engine.saturation_scan import market_saturation


def _peers(densities, population=10000):
    return [{"name": f"p{i}", "count": d * population / 10000,
             "population": population} for i, d in enumerate(densities)]


def test_register_map_covers_eu_and_usa():
    cat = R.register_catalog()
    countries = {r["country"] for r in cat["registers"]}
    assert {"se", "de", "fr", "es", "it", "nl", "dk", "no", "fi", "pl"} <= countries
    assert {"us", "ca"} <= countries
    for r in cat["registers"]:
        assert r["authority"] and r["classification"] and r["granularity"]
    assert cat["activate_with"] == "LANDVEX_REGISTER_URL"


def test_industry_codes_switch_between_nace_and_naics():
    se = R.industry_code("elektriker", "se")
    us = R.industry_code("elektriker", "us")
    assert se["scheme"] == "NACE" and se["code"] == "43.21"
    assert us["scheme"] == "NAICS" and us["code"] == "238210"
    assert R.industry_code("nonexistent", "se") is None


def test_register_client_is_honest_when_not_connected():
    c = R.RegisterClient(base_url="")
    assert c.connected is False
    assert c.establishments("se", "0138", "elektriker") is None


def test_register_client_reads_a_real_count():
    fixture = {"count": 23, "year": 2025, "source": "SCB"}
    c = R.RegisterClient(base_url="http://reg.example",
                         transport=lambda u, t: json.dumps(fixture))
    got = c.establishments("se", "0138", "elektriker")
    assert got["count"] == 23 and got["measured"] is True
    assert got["code"] == "43.21"
    # trasigt svar ⇒ None, aldrig ett påhittat antal
    bad = R.RegisterClient(base_url="http://reg.example",
                           transport=lambda u, t: "not json")
    assert bad.establishments("se", "0138", "elektriker") is None


def test_saturation_bands_follow_the_percentile():
    assert S.band_for(5)[0] == "underserved"
    assert S.band_for(20)[0] == "room"
    assert S.band_for(50)[0] == "balanced"
    assert S.band_for(80)[0] == "tight"
    assert S.band_for(95)[0] == "saturated"


def test_saturation_refuses_without_enough_peers():
    out = S.saturation("elektriker", "0138", "Tyresö", population=10000,
                       supply={"count": 5, "measured": True},
                       peers=_peers([1, 2]))
    assert out["status"] == "insufficient_basis"
    assert any("comparable regions" in r for r in out["reasons"])


def test_saturation_reports_whether_the_count_is_measured():
    est = S.saturation("elektriker", "0138", "Tyresö", population=10000,
                       supply={"count": 5, "measured": False},
                       peers=_peers([1, 2, 3, 4, 5, 6]))
    assert est["supply"]["measured"] is False
    assert "ESTIMATE" in est["supply"]["basis_en"]
    real = S.saturation("elektriker", "0138", "Tyresö", population=10000,
                        supply={"count": 5, "measured": True,
                                "source": "SCB", "year": 2025},
                        peers=_peers([1, 2, 3, 4, 5, 6]))
    assert real["supply"]["measured"] is True
    assert "register" in real["supply"]["basis_en"].lower()


def test_saturation_says_what_would_move_it_to_the_median():
    out = S.saturation("elektriker", "0138", "Tyresö", population=10000,
                       supply={"count": 1, "measured": True},
                       peers=_peers([4, 5, 6, 7, 8, 9]))
    assert out["status"] == "assessed"
    assert out["band"] in ("underserved", "room")
    assert out["to_reach_peer_median"] > 0
    assert "more establishments" in out["to_reach_peer_median_en"]


def test_density_not_treated_as_opportunity():
    out = S.saturation("elektriker", "0138", "Tyresö", population=10000,
                       supply={"count": 9, "measured": True},
                       peers=_peers([1, 2, 3, 4, 5, 6]), demand_index=30)
    assert out["band"] in ("tight", "saturated")
    assert "demand is not strong" in out["demand_reading_en"]
    assert "not the same as opportunity" in out["caveat_en"]
    assert out["framing"]["choices"]["not_a_verdict"] is True


def test_tyreso_is_covered_and_answerable():
    """Den faktiska frågan: hur mättad är elektrikermarknaden i Tyresö?"""
    r = market_saturation("elektriker", "Tyresö", market="se", peer_limit=25)
    assert r["status"] == "assessed"
    assert r["region"] == "Tyresö"
    assert r["peers_compared"] >= S.MIN_PEERS
    assert r["band"] in {b for _, b, _ in S.BANDS}
    assert r["industry_code"]["code"] == "43.21"
    # utan anslutet register MÅSTE siffran vara märkt som uppskattning
    assert r["supply"]["measured"] is False
    assert "ESTIMATE" in r["supply"]["basis_en"]


def test_uncovered_region_raises_rather_than_answering_for_another():
    try:
        market_saturation("elektriker", "Leningrad", market="se")
        raise AssertionError("svarade om en region som inte täcks")
    except ValueError as e:
        assert "not covered" in str(e).lower()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
