"""Tester för motorn. Körs utan pytest:  python3 -m tests.test_scoring"""
from __future__ import annotations

from engine.explain import pattern_insights
from engine.models import Location
from engine.scoring import analyze, required_signals
from engine.signals import CATALOG, normalize
from engine.verticals import VERTICALS

LOCS = [Location(59.3145, 18.0705, "Sthlm"),
        Location(57.7005, 12.9405, "Borås"),
        Location(63.8258, 20.2630, "Umeå")]


def test_scores_within_bounds():
    for loc in LOCS:
        for vid in VERTICALS:
            r = analyze(loc, vid)
            assert 0 <= r.opportunity_score <= 100, (vid, r.opportunity_score)
            for f in r.factors:
                assert 0 <= f.score <= 100
                assert f.narrative_en
            assert r.recommendation_en
            assert r.risk_level in ("Low", "Medium", "High")


def test_deterministic():
    loc = LOCS[0]
    a = analyze(loc, "frisor").to_dict()
    b = analyze(loc, "frisor").to_dict()
    assert a == b


def test_weights_sum_to_one():
    for v in VERTICALS.values():
        total = sum(f.weight for f in v.factors)
        assert abs(total - 1.0) < 1e-6, (v.id, total)


def test_required_signals_exist_in_catalog():
    for vid in VERTICALS:
        for sid in required_signals(vid):
            assert sid in CATALOG, sid


def test_normalization_bounds():
    for d in CATALOG.values():
        for x in (-1e6, 0, 1, 50, 1e6):
            n = normalize(d, x)
            assert 0.0 <= n <= 1.0, (d.id, x, n)
    assert normalize(next(iter(CATALOG.values())), None) is None


def test_cafe_afternoon_pattern():
    ins = pattern_insights("cafe", {"flows": {"morning": 600, "afternoon": 120}})
    assert any("after 2 pm" in t for t in ins)
    ins2 = pattern_insights("cafe", {"flows": {"morning": 600, "afternoon": 500}})
    assert not any("after 2 pm" in t for t in ins2)


def test_electrician_headroom_insight():
    ins = pattern_insights("elektriker", {
        "competitors": {"effective": 2.0}, "demand_units": 5.4})
    assert any("another" in t and "electrician" in t for t in ins)


def test_unknown_vertical_raises():
    try:
        analyze(LOCS[0], "rymdturism")
    except ValueError:
        return
    raise AssertionError("Okänd vertikal ska ge ValueError")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
