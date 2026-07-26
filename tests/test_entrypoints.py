"""Tester för ingångar + administrativt register.
Kör: python3 -m tests.test_entrypoints"""
from __future__ import annotations

from engine import admin as A
from engine import entrypoints as E
from engine.feeds import FEEDS


def test_entrypoints_have_tools_and_event_feeds():
    eps = E.entrypoints()
    ids = {e["id"] for e in eps}
    assert {"citizen", "business", "investor", "municipality",
            "journalist", "researcher"} <= ids
    feed_codes = {f.code for f in FEEDS}
    for e in eps:
        assert e["tools"] and e["question_en"]
        # varje ingång slutar i ett SVAR (beslutsstöd, inte verktygslåda)
        assert e["answered_by"].startswith("/v1/")
        assert e["decision_en"] and e["deliverable_en"]
        # varje event-feed refererar en verklig feed (event-driven overlay)
        assert all(fc in feed_codes for fc in e["event_feeds"])


def test_entrypoint_lookup_and_unknown():
    assert E.entrypoint("investor")["lens"] == "risk & return"
    try:
        E.entrypoint("nope"); raise AssertionError()
    except ValueError:
        pass


def test_admin_full_state_coverage():
    assert len(A.US_STATES) == 50
    assert len(A.CA_PROVINCES) == 13
    assert len(A.CH_CANTONS) == 26
    assert len(A.DE_LANDER) == 16
    assert len(A.SE_LAN) == 21
    assert len(A.FR_REGIONS) == 13
    assert len(A.ES_COMMUNITIES) == 17
    assert len(A.IT_REGIONS) == 20
    assert len(A.DK_REGIONS) == 5
    assert len(A.NL_PROVINCES) == 12


def test_admin_units_and_countries():
    cs = {c["country"] for c in A.admin_countries()}
    assert {"us", "ca", "ch", "de", "se", "fr", "es", "it", "dk", "nl"} <= cs
    us = A.admin_units("us")
    assert us["count"] == 50 and any(u["code"] == "TX" for u in us["units"])
    assert us["coverage"] == "full"
    ch = A.admin_units("ch")
    assert any(u["name"] == "Genève" for u in ch["units"])


def test_admin_municipal_seed_is_honestly_partial():
    se = A.admin_units("se", level=2)
    assert se["coverage"] == "partial" and se["official_total"] == 290
    assert any(u["name"] == "Örebro" for u in se["units"])
    # parent-filter: Örebro kommun ligger i Örebro län (18)
    lan18 = A.admin_units("se", level=2, parent="18")
    assert [u["name"] for u in lan18["units"]] == ["Örebro"]
    us = A.admin_units("us", level=2, parent="CA")
    assert all(u["parent"] == "CA" for u in us["units"]) and us["count"] >= 5


def test_admin_municipal_live_register_wins():
    fixture = [{"code": "0001", "name": "Testby", "parent": "01"}]
    reg = A.MunicipalRegister(
        base_url="http://geo.example",
        transport=lambda url, t: __import__("json").dumps(fixture))
    out = A.admin_units("se", level=2, register=reg)
    assert out["coverage"] == "full" and out["units"][0]["name"] == "Testby"
    # trasig källa ⇒ ärlig degradering till seed, aldrig krasch
    broken = A.MunicipalRegister(base_url="http://geo.example",
                                 transport=lambda url, t: "not json")
    out2 = A.admin_units("se", level=2, register=broken)
    assert out2["coverage"] == "partial"


def test_admin_unknown_country_and_level_raise():
    try:
        A.admin_units("zz"); raise AssertionError()
    except ValueError:
        pass
    try:
        A.admin_units("se", level=4); raise AssertionError()
    except ValueError:
        pass


def test_postal_tier_is_documented_not_invented():
    se = A.admin_units("se", level=3)
    assert se["level"] == 3 and se["register"] == "PostNord"
    assert se["coverage"] == "register_only"      # ingen lista bärs inline
    assert "5 digits" in se["format"]
    us = A.admin_units("us", level=3)
    assert us["label_en"] == "ZIP Code" and us["official_total"] > 40000
    try:
        A.postal_register("zz"); raise AssertionError()
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
