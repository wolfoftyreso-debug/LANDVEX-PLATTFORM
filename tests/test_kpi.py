"""Tester för KPI-motorn (registry, invert-medveten status, alerts).
Kör: python3 -m tests.test_kpi"""
from __future__ import annotations

from engine.kpi import (
    CATEGORIES, KpiDefinition, REGISTRY, derive_status, evaluate_alerts,
    rank_relevance,
)


def _defn(**kw):
    base = dict(kpi_index=1, code="x", name="X", category="demografi_halsa")
    base.update(kw)
    return KpiDefinition(**base)


def test_registry_categories_valid():
    assert all(d.category in CATEGORIES for d in REGISTRY)
    assert len(REGISTRY) >= 5


def test_bad_category_rejected():
    try:
        _defn(category="nonsense")
        assert False, "borde ha kastat"
    except ValueError:
        pass


def test_status_normal_kpi():
    # ej inverterad: uppgång = positive
    assert derive_status(110, 100, is_inverted=False)["status"] == "positive"
    # nedgång >5% = critical
    assert derive_status(90, 100, is_inverted=False)["status"] == "critical"
    # liten förändring = neutral
    assert derive_status(100.2, 100, is_inverted=False)["status"] == "neutral"


def test_status_inverted_kpi():
    # inverterad (arbetslöshet): nedgång = förbättring = positive
    assert derive_status(4, 8, is_inverted=True)["status"] == "positive"
    # uppgång >5% = critical
    assert derive_status(9, 8, is_inverted=True)["status"] == "critical"


def test_alert_absolute_breach_below():
    # life_expectancy: warning 82, critical 80, direction below
    d = _defn(code="life", warning=82, critical=80, direction="below")
    assert evaluate_alerts(d, 79)[0]["severity"] == "critical"
    assert evaluate_alerts(d, 81)[0]["severity"] == "warning"
    assert evaluate_alerts(d, 85) == []


def test_alert_absolute_breach_above():
    d = _defn(code="crime", warning=40, critical=50, direction="above")
    assert evaluate_alerts(d, 55)[0]["severity"] == "critical"
    assert evaluate_alerts(d, 45)[0]["severity"] == "warning"


def test_alert_velocity_signed():
    # employment velocity_critical -2 → larm vid fall ≥2%
    d = _defn(code="emp", direction="below", velocity_warning=-1,
              velocity_critical=-2)
    a = evaluate_alerts(d, 96, previous=100)   # −4%
    assert any(x["alert_type"] == "velocity_warning"
               and x["severity"] == "critical" for x in a)
    # stigning triggar inte en negativ velocity-tröskel
    assert not any(x["alert_type"] == "velocity_warning"
                   for x in evaluate_alerts(d, 104, previous=100))


def test_rank_relevance_orders_by_total():
    rows = [
        {"code": "low", "impact": 10, "acceleration": 10, "breadth": 10,
         "persistence": 10, "responsibility": 10, "data_confidence": 10},
        {"code": "high", "impact": 90, "acceleration": 90, "breadth": 90,
         "persistence": 90, "responsibility": 90, "data_confidence": 90},
    ]
    ranked = rank_relevance(rows)
    assert ranked[0]["code"] == "high"
    assert ranked[0]["relevance"]["total"] > ranked[1]["relevance"]["total"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
