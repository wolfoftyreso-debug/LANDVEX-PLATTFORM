"""Tester för beslutsstöd + krisgrind. Kör: python3 -m tests.test_decision"""
from __future__ import annotations

from engine import decision as D


def test_crisis_gate_triggers_and_localises():
    r = D.crisis_scan("I want to kill myself", country="se")
    assert r and r["crisis"] is True
    assert any("90101" in x["contact"] for x in r["resources"])
    assert "note" in r    # möts med resurser, inte data


def test_crisis_gate_default_country():
    r = D.crisis_scan("thoughts of self-harm", country="zz")
    assert r and r["resources"] == D._RESOURCES["_default"]


def test_crisis_gate_autodetects_language():
    # Svensk formulering utan explicit land → svenska resurser (ej US-988).
    sv = D.crisis_scan("Jag vill ta livet av mig")
    assert sv and any("90101" in x["contact"] for x in sv["resources"])
    # Engelsk formulering → US-linjen.
    en = D.crisis_scan("I want to end my life")
    assert en and any("988" in x["contact"] for x in en["resources"])


def test_no_crisis_returns_none():
    assert D.crisis_scan("What is the population trend in Malmö?") is None


def test_decision_graph_resolves_and_flags_gaps():
    ans = {"demand": {"confidence": 0.8, "summary": "up"},
           "competition": {"confidence": 0.3}}   # under tröskel 0.5
    res = D.evaluate("investment_decision", ans)
    st = {n["node_id"]: n["status"] for n in res["nodes"]}
    assert st["demand"] == "resolved"
    assert st["competition"] == "insufficient_data"
    assert st["risk"] == "unresolved"
    assert "competition" in res["data_gaps"]      # required + ej resolved
    assert "risk" not in res["data_gaps"]          # ej required


def test_decision_never_recommends():
    res = D.evaluate("policy_decision", {})
    assert "recommendation" in res["never_provided"]
    assert res["completeness"] == 0.0
    assert "does not recommend" in res["disclaimer"]


def test_unknown_template_raises():
    try:
        D.evaluate("nope", {})
        assert False
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
