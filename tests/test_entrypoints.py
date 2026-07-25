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
        E.entrypoint("nope"); assert False
    except ValueError:
        pass


def test_admin_full_state_coverage():
    assert len(A.US_STATES) == 50
    assert len(A.CH_CANTONS) == 26
    assert len(A.DE_LANDER) == 16
    assert len(A.SE_LAN) == 21


def test_admin_units_and_countries():
    cs = {c["country"] for c in A.admin_countries()}
    assert {"us", "ch", "de", "se"} <= cs
    us = A.admin_units("us")
    assert us["count"] == 50 and any(u["code"] == "TX" for u in us["units"])
    ch = A.admin_units("ch")
    assert any(u["name"] == "Genève" for u in ch["units"])


def test_admin_unknown_country_raises():
    try:
        A.admin_units("zz"); assert False
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
