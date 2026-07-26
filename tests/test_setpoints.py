"""Tester för setpoint-/toleranslagret.
Kör: python3 -m tests.test_setpoints"""
from __future__ import annotations

from engine import setpoints as S


def test_catalog_has_calibrated_rows():
    cat = S.catalog()
    codes = {r["code"] for r in cat}
    assert {"tfr", "debt_to_gdp", "gini", "social_trust"} <= codes
    assert len(cat) >= 9


def test_maastricht_debt_zones():
    assert S.assess_zone("debt_to_gdp", 55)["zone"] == "optimal"
    assert S.assess_zone("debt_to_gdp", 70)["zone"] == "acceptable"
    assert S.assess_zone("debt_to_gdp", 90)["zone"] == "warning"
    assert S.assess_zone("debt_to_gdp", 130)["zone"] == "critical"


def test_higher_better_life_expectancy():
    assert S.assess_zone("life_expectancy", 83)["zone"] == "optimal"
    assert S.assess_zone("life_expectancy", 81)["zone"] == "acceptable"
    assert S.assess_zone("life_expectancy", 79)["zone"] == "warning"
    assert S.assess_zone("life_expectancy", 74)["zone"] == "critical"


def test_neutral_optimal_inflation_both_sides():
    assert S.assess_zone("inflation_cpi", 2.0)["zone"] == "optimal"
    assert S.assess_zone("inflation_cpi", 0.8)["zone"] == "warning"    # låg, ej ännu kritisk
    assert S.assess_zone("inflation_cpi", -0.5)["zone"] == "critical"  # deflation
    assert S.assess_zone("inflation_cpi", 5.0)["zone"] == "critical"   # överhettat


def test_deviation_pct_signed():
    a = S.assess_zone("gini", 0.36)
    assert a["zone"] == "warning" and a["deviation_pct"] > 0    # över 0.30
    b = S.assess_zone("gini", 0.24)
    assert b["deviation_pct"] < 0


def test_zone_score_monotone():
    assert S.zone_score("debt_to_gdp", 50) > S.zone_score("debt_to_gdp", 90)
    assert S.zone_score("debt_to_gdp", 90) > S.zone_score("debt_to_gdp", 200)


def test_unknown_code_raises():
    try:
        S.assess_zone("nope", 1)
        raise AssertionError()
    except ValueError:
        pass


def test_catalog_serialises_inf_as_null():
    row = next(r for r in S.catalog() if r["code"] == "life_expectancy")
    assert row["optimal"][1] is None   # övre gräns oändlig → null


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
