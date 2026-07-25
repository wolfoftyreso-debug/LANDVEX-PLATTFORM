"""Tester för peer-benchmark. Kör: python3 -m tests.test_benchmark"""
from __future__ import annotations

from engine import benchmark as B


# Örebro: p-platser per 100 jobb, mot jämförbara medelstora städer.
_PEERS = [42, 45, 38, 51, 47, 40, 44, 49, 46, 43]   # ~normalspann 38–51


def test_needs_enough_peers():
    assert B.benchmark(40, [1, 2])["status"] == "insufficient_peers"


def test_value_in_normal_range_not_supported():
    r = B.benchmark(44, _PEERS, label="Örebro", metric="parking_per_100_jobs")
    assert r["band"] == "normal" and r["is_outlier"] is False
    assert "NOT supported" in r["verdict"]


def test_low_outlier_supported():
    r = B.benchmark(20, _PEERS, label="Örebro")   # klart under peers
    assert r["band"] == "low_outlier" and r["is_outlier"] is True
    assert r["zscore"] < 0 and "supported by the data" in r["verdict"]


def test_percentile_and_framing_present():
    r = B.benchmark(51, _PEERS)
    assert 0 <= r["percentile"] <= 100
    assert "which peers were chosen" in r["framing"]["choices"]["note"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
