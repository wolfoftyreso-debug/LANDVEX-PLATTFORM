"""Tester för signifikans-väljaren. Kör: python3 -m tests.test_worthiness"""
from __future__ import annotations

from engine import worthiness as W


def test_excludes_noise_and_insufficient():
    assert W.worthiness({"relevance_level": "L0", "change_percent": 90})["worthy"] is False
    assert W.worthiness({"data_availability": "insufficient", "change_percent": 90})["worthy"] is False


def test_high_relevance_big_change_is_hero():
    r = W.worthiness({"relevance_level": "L4", "change_percent": 60,
                      "confidence": 1.0, "data_availability": "verified",
                      "source_count": 3, "is_breaking_pattern": True,
                      "consecutive_months": 6, "cross_domain_links": 5,
                      "affected_population_percent": 100})
    assert r["worthy"] and r["priority"] == "hero" and r["total"] >= 85


def test_magnitude_breakpoints():
    def m(p): return W.worthiness({"relevance_level": "L1", "change_percent": p})["factors"].get("magnitude")
    assert m(60) == 25 and m(30) == 20 and m(12) == 15 and m(6) == 10 and m(3) == 5 and m(1) == 0


def test_small_change_low_relevance_not_worthy():
    assert W.worthiness({"relevance_level": "L1", "change_percent": 1})["worthy"] is False


def test_select_for_wrap_caps_buckets():
    snaps = [{"relevance_level": "L4", "change_percent": 60, "confidence": 1.0,
              "source_count": 3, "cross_domain_links": 5,
              "is_breaking_pattern": True, "consecutive_months": 6,
              "affected_population_percent": 100} for _ in range(5)]
    out = W.select_for_wrap(snaps)
    assert len(out["buckets"]["hero"]) == 2   # cap 2
    assert all(s["worthiness"]["worthy"] for s in out["ranked"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
