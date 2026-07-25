"""Tester för lambda-indexet (geometrisk λ).
Kör: python3 -m tests.test_lambda"""
from __future__ import annotations

from engine import lambda_index as L


def test_balanced_at_median():
    # alla axlar 50 → alla normaliseras till 1.0 → λ = 1.0
    r = L.lambda_score({k: 50 for k in [a[0] for a in L.AXES]})
    assert r["lambda"] == 1.0
    assert r["interpretation"]["code"] == "balanced"
    assert r["coverage"] == 1.0


def test_normalize_axis_bounds():
    assert L.normalize_axis(0) == 0.7
    assert L.normalize_axis(50) == 1.0
    assert L.normalize_axis(100) == 1.3


def test_geometric_mean_penalizes_extremes():
    # En stark axel kan INTE maska en svag: aritm. medel av 100 och 0 vore
    # 50→1.0 (balanserat), men geometriskt straffar.
    r = L.lambda_score({"ECON": 100, "HEALTH": 0})
    # normaliserat: 1.3 och 0.7 → sqrt(0.91) ≈ 0.9539 < 1.0
    assert r["lambda"] < 1.0
    assert abs(r["lambda"] - (1.3 * 0.7) ** 0.5) < 1e-3


def test_low_axes_are_inefficient():
    r = L.lambda_score({k: 10 for k in [a[0] for a in L.AXES]})
    assert r["lambda"] < 0.9
    assert "inefficient" in r["interpretation"]["code"]


def test_high_axes_are_overheated():
    r = L.lambda_score({k: 95 for k in [a[0] for a in L.AXES]})
    assert r["lambda"] > 1.10
    assert r["interpretation"]["code"] in ("overheated", "warning_high",
                                           "critical_overheat")


def test_partial_coverage_is_honest():
    r = L.lambda_score({"ECON": 50, "HEALTH": 50})
    assert r["coverage"] == round(2 / 8, 4)
    assert len(r["axes"]) == 2


def test_empty_axes():
    r = L.lambda_score({})
    assert r["lambda"] is None and r["coverage"] == 0.0


def test_primary_drivers_are_furthest_from_optimum():
    r = L.lambda_score({"ECON": 100, "HEALTH": 50, "LABOR": 48})
    # ECON avviker mest (1.3), sedan LABOR (0.988), sedan HEALTH (1.0)
    assert r["primary_drivers"][0] == "ECON"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
