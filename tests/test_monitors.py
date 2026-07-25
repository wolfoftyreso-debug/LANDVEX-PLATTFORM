"""Tester för kontroll-infrastrukturlagret (bevakningar + cron + eskalering).
Kör: python3 -m tests.test_monitors"""
from __future__ import annotations

from engine import accountability
from engine import monitors as M


def setup():
    M.reset()
    accountability.reset()


def test_rules_catalog_is_data():
    ids = {r["id"] for r in M.rules_catalog()}
    assert {"threshold", "changepoint", "anomaly", "sustained_decline"} <= ids
    for r in M.rules_catalog():
        assert r["label_en"] and "params" in r and r["min_points"] >= 1


def test_define_requires_owner_and_known_rule():
    setup()
    try:
        M.define("debt_gdp", "national", "threshold", "")
        raise AssertionError("owner-lös bevakning tilläts")
    except ValueError:
        pass
    try:
        M.define("debt_gdp", "national", "nope", "gov")
        raise AssertionError("okänd regel tilläts")
    except ValueError:
        pass
    m = M.define("debt_gdp", "national", "threshold", "finance-unit",
                 params={"level": 60, "direction": "above"})
    assert m["id"] and m["owner"] == "finance-unit" and m["enabled"]


def test_threshold_triggers_and_reports_coverage():
    setup()
    m = M.define("debt_gdp", "SE", "threshold", "gov",
                 params={"level": 60, "direction": "above"})
    hot = M.evaluate(m, [55, 58, 62])
    assert hot["triggered"] and hot["data_coverage"]["sufficient"]
    assert hot["framing"]["choices"]["not_causal"] is True
    cold = M.evaluate(m, [40, 42, 41])
    assert not cold["triggered"]
    # Förklaringen får aldrig påstå en jämförelse som inte hände: 41 är
    # INTE ≥ 60, så texten ska säga att nivån inte passerats.
    assert "≥" not in cold["detail"] and "not crossed" in cold["detail"]
    assert "≥" in hot["detail"]
    thin = M.evaluate(m, [])            # regeln kräver ≥1 punkt
    assert not thin["triggered"] and thin["severity"] == "insufficient"


def test_anomaly_and_changepoint_and_decline():
    setup()
    a = M.define("price", "x", "anomaly", "o", params={"z_threshold": 2.0})
    assert M.evaluate(a, [10, 10, 10, 10, 10, 10, 40])["triggered"]
    c = M.define("load", "x", "changepoint", "o", params={"threshold": 2.5})
    assert M.evaluate(c, [1, 1, 1, 9, 9, 9])["triggered"]
    d = M.define("sales", "x", "sustained_decline", "o",
                 params={"min_r2": 0.5})
    assert M.evaluate(d, [100, 80, 60, 40, 20])["triggered"]
    assert not M.evaluate(d, [50, 51, 49, 52, 50])["triggered"]


def test_cadence_due_is_deterministic():
    daily = {"every": "daily"}
    assert M.due(daily, None, 1000.0)                 # aldrig körd
    assert not M.due(daily, 1000.0, 1000.0 + 3600)    # 1h < 1 dygn
    assert M.due(daily, 1000.0, 1000.0 + 86400 + 1)   # >1 dygn
    fast = {"every": "interval", "interval_minutes": 15}
    assert M.due(fast, 0.0, 15 * 60)
    try:
        M.cadence_minutes({"every": "yearly"})
        raise AssertionError("okänd kadens tilläts")
    except ValueError:
        pass


def test_run_due_only_runs_due_and_dedups():
    setup()
    m = M.define("debt_gdp", "SE", "threshold", "gov",
                 params={"level": 60}, cadence={"every": "daily"})
    series = {m["id"]: [55, 58, 62]}
    r1 = M.run_due([m], 100000.0, series)
    assert r1["fired"] == 1 and m["id"] in r1["ran"]
    # samma checksumma dedupas inom samma seen-set
    seen = {f["checksum"] for f in r1["findings"]}
    r2 = M.run_due([m], 100000.0 + 2 * 86400, series, seen=seen)
    assert r2["findings"] == []          # dedupad
    # ej förfallen ⇒ hoppas över
    m2 = dict(m, last_run=100000.0)
    r3 = M.run_due([m2], 100000.0 + 60, series)
    assert r3["ran"] == []


def test_escalate_creates_owned_decision():
    setup()
    m = M.define("debt_gdp", "SE", "threshold", "gov", params={"level": 60})
    f = M.evaluate(m, [55, 58, 62])
    owners = {"formellt": "finance-minister", "operativt": "debt-office",
              "uppfoljning": "audit-office"}
    expected = {"metric": "debt_gdp", "direction": "decrease", "target": 60}
    out = M.escalate(f, owners, expected, committed_at="2026-01-01")
    assert out["decision"]["owners"]["formellt"] == "finance-minister"
    assert out["decision"]["id"] in {d["id"]
                                     for d in accountability._all_decisions()}
    # ett icke-triggat finding kan inte eskaleras
    cold = M.evaluate(m, [40, 41, 42])
    try:
        M.escalate(cold, owners, expected)
        raise AssertionError("icke-triggat finding eskalerades")
    except ValueError:
        pass


def test_catalog_exposes_rules_and_monitors():
    setup()
    M.define("debt_gdp", "SE", "threshold", "gov", params={"level": 60})
    cat = M.catalog()
    assert cat["rules"] and cat["monitors"] and "interval" in cat["cadences"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
