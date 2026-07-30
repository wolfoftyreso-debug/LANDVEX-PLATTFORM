"""Universal Object Model, minimal: en sammanhållen vy, inte en ny
algoritm. Tre saker skulle förstöra syftet:

  1. Ett Condition-fält för en klass `infrastructure.py` inte känner
     till — samma gissningsfälla som `reality_kpi.py` redan vägrar.
  2. Ett Compliance-fält för ett objekt ingen rutin täcker.
  3. En "komplett" vy som INTE säger vilka fält som saknas.

Kör: python3 -m tests.test_object_view
"""
from __future__ import annotations

from engine import inspections as I
from engine import infrastructure as INFRA
from engine.object_view import ObjectNotFound, object_view

NU = 1_800_000_000.0


def test_unknown_object_id_is_refused_by_name():
    try:
        object_view("no-such-object", [], [], [], [], [])
    except ObjectNotFound as e:
        assert "no-such-object" in str(e)
        return
    raise AssertionError("ett okänt objekt-id accepterades")


def test_a_routine_covered_object_gets_a_real_compliance_row():
    rutin = I.routine("flaggkontroll", "Flag check", "flagpole", 7,
                      checks=("visible",), tenant="t1")
    a = I.asset("fp-1", "flagpole", tenant="t1")
    c = I.record("fp-1", "flaggkontroll", "pass", evidence_ref="ev-1",
                 performed_at="2026-07-28", tenant="t1")
    out = object_view("fp-1", [a], [rutin], [c], [], [], today="2026-07-30")
    assert out["compliance"] is not None
    assert out["compliance"]["status"] in ("ok", "due_soon")
    assert out["condition"] is None  # "flagpole" är inte i OBJECT_TYPES


def test_an_object_no_routine_covers_has_no_compliance_row():
    a = I.asset("fp-2", "flagpole", tenant="t1")
    out = object_view("fp-2", [a], [], [], [], [], today="2026-07-30")
    assert out["compliance"] is None


def test_an_infrastructure_kind_gets_a_real_condition_row():
    a = I.asset("p-1", "car_parking", tenant="t1")
    obs = INFRA.observe("p-1", "car_parking", {"free_spaces": 3},
                        mission_id="m-1", observer_network="quixzoom",
                        tenant="t1", observed_at=NU - 5 * 60)
    out = object_view("p-1", [a], [], [], [obs], [], now=NU)
    assert out["condition"] is not None
    assert out["condition"]["kind"] == "car_parking"
    assert out["compliance"] is None  # ingen rutin täcker den här


def test_history_is_sorted_newest_first():
    rutin = I.routine("r1", "R1", "flagpole", 7, checks=("visible",))
    a = I.asset("fp-3", "flagpole", tenant="t1")
    c1 = I.record("fp-3", "r1", "pass", evidence_ref="e1",
                  performed_at="2026-07-01", tenant="t1")
    c2 = I.record("fp-3", "r1", "pass", evidence_ref="e2",
                  performed_at="2026-07-20", tenant="t1")
    out = object_view("fp-3", [a], [rutin], [c1, c2], [], [])
    assert out["history_count"] == 2
    assert out["history"][0]["performed_at"] == "2026-07-20"


def test_reviews_are_scoped_to_the_objects_own_checks():
    a = I.asset("fp-4", "flagpole", tenant="t1")
    c = I.record("fp-4", "r1", "pass", evidence_ref="e1",
                 observed_by="Anna", tenant="t1")
    r = I.review(c, reviewer="Björn", outcome="confirmed", tenant="t1")
    other_review = {**r, "asset_id": "fp-other"}
    out = object_view("fp-4", [a], [], [c], [], [r, other_review])
    assert out["reviewed_count"] == 1
    assert out["reviews"][0]["reviewer"] == "Björn"


def test_the_view_names_what_it_still_cannot_show():
    """En "komplett" vy som INTE säger vad som saknas vore precis det
    överdrivna påstående doktrinen annars vägrar."""
    a = I.asset("fp-5", "flagpole", tenant="t1")
    out = object_view("fp-5", [a], [], [], [], [])
    for ord_ in ("Geometry", "Owner", "Lifecycle", "Relationships",
                "Policies"):
        assert ord_ in out["cannot_en"], f"{ord_} nämns inte i cannot_en"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
