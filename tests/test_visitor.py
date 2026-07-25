"""Tester för besökarsömmen mot kundonboardingen.
Kör: python3 -m tests.test_visitor"""
from __future__ import annotations

from engine import visitor as V


def test_contract_is_documented_for_an_external_onboarding():
    c = V.contract()
    fields = {f["field"] for f in c["fields"]}
    assert {"visitor_id", "role", "place", "decisions"} <= fields
    req = {f["field"] for f in c["fields"] if f["required"]}
    assert req == {"visitor_id", "role"}
    assert c["roles"] and c["ladder"]
    for step in c["ladder"]:
        assert step["requires"] and step["unlocks_en"]


def test_onboarding_payload_maps_through_aliases():
    prof = V.from_onboarding({"customer_id": "acme-42", "persona": "business",
                              "city": "se-1880", "industry": "elektriker",
                              "irrelevant_crm_field": "ignore me"})
    assert prof["visitor_id"] == "acme-42"
    assert prof["role"] == "business"
    assert prof["place"] == "se-1880" and prof["trade"] == "elektriker"
    assert "irrelevant_crm_field" not in prof
    assert "decisions" in prof["missing"]        # ärligt redovisat


def test_unknown_role_is_rejected_not_silently_remapped():
    try:
        V.from_onboarding({"id": "x", "role": "buisness"})   # stavfel
        raise AssertionError("okänd roll accepterades")
    except ValueError as e:
        assert "unknown role" in str(e)


def test_knowing_nothing_says_so_and_asks_who_you_are():
    g = V.guide({})
    assert g["status"] == "identify"
    assert g["completeness"]["level"] == "unknown"
    assert g["completeness"]["next_field"] == "role"
    assert len(g["options"]) == 6
    for o in g["options"]:
        assert o["question_en"] and o["visitor_en"]


def test_knowing_a_little_starts_guiding():
    """Kundens tes: vet systemet lite grann kan det börja guida."""
    g = V.guide({"visitor_id": "u1", "role": "business"})
    assert g["completeness"]["level"] == "partial"
    assert g["status"] == "ask"
    assert g["completeness"]["next_field"] == "place"
    assert "establish" in g["ask_en"]              # rollanpassad fråga
    assert g["your_question_en"] and g["answered_by"].startswith("/v1/")


def test_knowing_enough_switches_from_asking_to_answering():
    g = V.guide({"visitor_id": "u1", "role": "business", "place": "se-1880",
                 "trade": "elektriker"})
    assert g["completeness"]["level"] == "known"
    assert g["status"] == "answer"
    assert "ask_en" not in g
    kinds = {s["kind"] for s in g["stakes_suggested"]}
    assert {"place", "sector"} <= kinds


def test_carrying_a_decision_unlocks_routing():
    g = V.guide({"visitor_id": "u1", "role": "municipality",
                 "place": "se-1880", "decisions": ["dec-1"]})
    assert g["completeness"]["level"] == "routed"
    assert g["completeness"]["next_field"] is None
    assert any(s["kind"] == "decision" for s in g["stakes_suggested"])


def test_suggested_stakes_never_invent_anything():
    assert V.suggested_stakes({"role": "citizen"}) == []
    s = V.suggested_stakes({"place": "se-0180"})
    assert len(s) == 1 and s[0]["value"] == "se-0180"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
