"""Reality Coverage/Freshness/Confidence: en rollup, ingen ny mätning.

Tre saker skulle förstöra syftet med modulen, och sviten prövar dem
före allt annat:

  1. Ett Freshness/Confidence-tal på en objektklass `infrastructure.py`
     inte känner till — det vore en gissning maskerad som en mätning.
  2. En Coverage-rad för en klass ingen har registrerat.
  3. Reality Risk som tystnar i stället för att vägra med skäl.

Kör: python3 -m tests.test_reality_kpi
"""
from __future__ import annotations

from engine import inspections as I
from engine import infrastructure as INFRA
from engine.reality_kpi import reality_kpi

NU = 1_800_000_000.0


def _flagpole_scenario():
    """Två flaggstänger, en aktuell och en förfallen — samma fixtur-
    form som `scripts/seed_inspections.py` men minimal."""
    rutin = I.routine("flaggkontroll", "Flag check", "flagpole", 7,
                      checks=("visible",), tenant="t1")
    a1 = I.asset("fp-1", "flagpole", tenant="t1")
    a2 = I.asset("fp-2", "flagpole", tenant="t1")
    c1 = I.record("fp-1", "flaggkontroll", "pass",
                  performed_at="2026-07-28", evidence_ref="ev-1", tenant="t1")
    return [a1, a2], [rutin], [c1]


def _car_parking_scenario():
    a = I.asset("p-1", "car_parking", tenant="t1")
    obs = INFRA.observe("p-1", "car_parking", {"free_spaces": 3},
                        mission_id="m-1", observer_network="quixzoom",
                        tenant="t1", observed_at=NU - 5 * 60)
    return [a], [obs]


# ── 1. Ingen gissning på okänd klass ────────────────────────────────────
def test_a_routine_only_kind_never_gets_a_freshness_or_confidence_row():
    """"flagpole" har en rutin men ingen `infrastructure.OBJECT_TYPES`-
    definition — Freshness/Confidence får inte hitta på ett tal för den."""
    assets, routines, checks = _flagpole_scenario()
    assert "flagpole" not in INFRA.OBJECT_TYPES
    out = reality_kpi(assets, routines, checks, [], today="2026-07-30", now=NU)
    rad = next(r for r in out["kinds"] if r["kind"] == "flagpole")
    assert rad["freshness"] is None
    assert rad["confidence"] is None
    assert rad["coverage"] is not None


# ── 2. Ingen rad för en oregistrerad klass ──────────────────────────────
def test_no_row_for_a_kind_nobody_registered():
    assets, routines, checks = _flagpole_scenario()
    out = reality_kpi(assets, routines, checks, [], today="2026-07-30", now=NU)
    kinds = {r["kind"] for r in out["kinds"]}
    assert "car_parking" not in kinds
    assert "bus_stop" not in kinds


# ── 3. Coverage matchar compliance() exakt ──────────────────────────────
def test_coverage_matches_compliance_share_current():
    assets, routines, checks = _flagpole_scenario()
    out = reality_kpi(assets, routines, checks, [], today="2026-07-30", now=NU)
    rad = next(r for r in out["kinds"] if r["kind"] == "flagpole")
    direkt = I.compliance(assets, routines, checks, "2026-07-30")
    assert rad["coverage"]["share_current"] == direkt["share_current"]
    assert rad["coverage"]["objects"] == direkt["count"]


# ── 4. Freshness/Confidence för en känd klass ───────────────────────────
def test_a_known_kind_gets_real_freshness_and_confidence():
    assets, observations = _car_parking_scenario()
    out = reality_kpi(assets, [], [], observations, now=NU)
    rad = next(r for r in out["kinds"] if r["kind"] == "car_parking")
    assert rad["freshness"]["share_current"] is not None
    assert 0.0 <= rad["freshness"]["share_current"] <= 1.0
    # En ensam observatör kan aldrig nå över "weak" — se _band() i
    # infrastructure.py — så corroborated-andelen ska vara 0, inte
    # påhittat högre.
    assert rad["confidence"]["share_corroborated"] == 0.0


# ── 5. Risk vägrar, tystnar aldrig ──────────────────────────────────────
def test_reality_risk_refuses_with_a_reason_instead_of_silence():
    assets, routines, checks = _flagpole_scenario()
    out = reality_kpi(assets, routines, checks, [], today="2026-07-30", now=NU)
    assert "risk_en" in out
    assert "not computed" in out["risk_en"]
    assert "no engine" in out["risk_en"]


# ── 6. Tom verklighet ger en tom lista, inte ett fel ────────────────────
def test_nothing_registered_is_an_empty_list_not_an_error():
    out = reality_kpi([], [], [], [], today="2026-07-30", now=NU)
    assert out["kinds"] == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
