"""Tester för statistik-kitet (stdlib, ingen numpy).
Kör: python3 -m tests.test_stats"""
from __future__ import annotations

from engine import stats


def test_mean_and_pstdev():
    assert stats.mean([2, 4, 6]) == 4.0
    assert stats.pstdev([2, 4, 6]) == round((8 / 3) ** 0.5, 15)
    assert stats.pstdev([5]) == 0.0


def test_trend_strength_direction():
    up = stats.trend_strength([1, 2, 3, 4, 5])   # 5 punkter = 4 upp-steg
    assert up["direction"] == "up" and up["max_run"] == 4
    assert stats.trend_strength([1, 2])["direction"] == "up"   # enkelt steg
    down = stats.trend_strength([5, 4, 3])
    assert down["direction"] == "down"


def test_cusum_detects_shift():
    # stabil sedan hopp → change-point
    series = [10, 10, 10, 10, 30, 30, 30, 30]
    r = stats.cusum_changepoint(series)
    assert r["detected"] is True and r["index"] >= 0


def test_cusum_flat_no_detection():
    assert stats.cusum_changepoint([5, 5, 5, 5, 5])["detected"] is False


def test_pearson_perfect_correlation():
    assert stats.pearson([1, 2, 3], [2, 4, 6]) == 1.0
    assert stats.pearson([1, 2, 3], [6, 4, 2]) == -1.0


def test_spearman_monotonic():
    # icke-linjär men monoton → spearman 1.0
    assert stats.spearman([1, 2, 3, 4], [1, 4, 9, 16]) == 1.0


def test_lag_correlation_finds_shift():
    # y[t] = x[t-1]: genuint fördröjd (ej bara linjär shift som är lag-0-invariant)
    x = [1, 5, 2, 8, 3, 9]
    y = [0, 1, 5, 2, 8, 3]
    r = stats.lag_correlation(x, y)
    assert r["best_lag"] == 1 and abs(r["correlation"]) > 0.99


def test_zscore_anomaly():
    base = [10, 10, 11, 9, 10, 10]
    normal = stats.zscore_anomaly(base, value=10)
    assert normal["is_anomaly"] is False
    spike = stats.zscore_anomaly(base, value=100)
    assert spike["is_anomaly"] is True and 0 < spike["confidence"] <= 0.95


def test_linreg_trend():
    up = stats.linreg_trend([1, 2, 3, 4, 5])
    assert up["direction"] == "up" and up["r2"] == 1.0 and up["significant"]
    flat = stats.linreg_trend([5, 5, 5, 5])
    assert flat["direction"] == "stable"


def test_percentile_rank():
    assert stats.percentile_rank(50, [10, 20, 30, 40, 50]) == 90.0
    assert stats.percentile_rank(5, [10, 20, 30]) == 0.0


def test_minmax():
    assert stats.minmax(5, 0, 10) == 50.0
    assert stats.minmax(-5, 0, 10) == 0.0
    assert stats.minmax(15, 0, 10) == 100.0
    assert stats.minmax(5, 5, 5) == 0.0


def test_degenerate_inputs_safe():
    assert stats.pearson([1], [1]) == 0.0
    assert stats.cusum_changepoint([])["detected"] is False
    assert stats.zscore_anomaly([1])["is_anomaly"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
