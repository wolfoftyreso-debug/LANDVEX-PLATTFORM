"""Lägesbilden får inte kunna ljuga.

En plan i ett dokument åldras i tysthet: punkter som blivit klara står
kvar, siffror som var sanna en gång blir fel, och en läsare som upptäcker
EN felaktighet slutar tro på hela sidan. `scripts/standing.py` mäter
därför nuläget ur koden vid körning och räknar av klara punkter själv.

Det förutsätter två saker som testas här: att mätningen faktiskt läser
koden, och att varje planpost som har en automatisk kontroll pekar på
något som existerar. En kontroll mot ett beslut som inte finns blir
aldrig sann, och punkten skulle stå kvar som "öppen" för alltid utan att
någon förstår varför.

Kör: python3 -m tests.test_standing
"""
from __future__ import annotations

from scripts import standing


def test_the_numbers_come_from_the_code_not_from_the_file():
    """Kärnan. Om mätningen vore hårdkodad vore hela filen värdelös."""
    from engine import offering
    from engine.markets import MARKETS
    m = standing.matning()
    assert m["markets"] == len(MARKETS)
    assert m["decisions_total"] == len(offering.DECISIONS)
    assert set(m["decisions_built"]) == {
        d["id"] for d in offering.DECISIONS if d["status"] == "built"}
    assert m["regions"] > m["markets"], "regioner ska vara fler än marknader"


def test_every_automatic_check_points_at_something_real():
    """En kontroll mot ett beslut som inte finns blir aldrig sann, och
    punkten står kvar som öppen för alltid."""
    from engine import offering
    ids = {d["id"] for d in offering.DECISIONS}
    m = standing.matning()
    for p in standing.PLAN:
        if p["done_when"] is None:
            continue
        # Kontrollen ska gå att köra mot en riktig mätning utan att kasta.
        assert isinstance(p["done_when"](m), bool), p["id"]
    # De planposter som ÄR beslut i erbjudandet ska heta samma sak där.
    for pid in ("export_findings", "scheduled_runs", "own_dashboards",
                "white_label"):
        assert pid in ids, f"{pid} finns i planen men inte i DECISIONS"
        assert any(p["id"] == pid for p in standing.PLAN), pid


def test_a_finished_item_closes_itself():
    """Bevisad, inte antagen: en post vars kontroll är sann ska markeras
    klar och räknas bort."""
    m = standing.matning()
    falsk = dict(m)
    falsk["decisions_built"] = list(m["decisions_built"]) + ["export_findings"]
    p = {x["id"]: x for x in standing.plan(falsk)}
    assert p["export_findings"]["done"] is True
    assert "export_findings" not in [
        x["id"] for x in standing.plan(falsk) if x["done"] is not True]
    # Och med den riktiga mätningen är den fortfarande öppen.
    assert {x["id"] for x in standing.plan(m) if x["done"] is not True} >= {
        "export_findings"}


def test_verified_sources_count_both_kinds_of_client():
    """Sensorklienterna bär verified_live som klassattribut,
    registerklasserna som fält i sin katalograd. Räknas bara den ena ser
    bilden bättre ut än den är."""
    m = standing.matning()
    totalt = m["sources_verified"] + m["sources_unverified"]
    from engine.datasources import register_apis, sensor_apis
    n_sensor = len({c.__name__ for g in sensor_apis.PROVIDERS.values()
                    for c in g})
    n_register = len(register_apis.providers_status()["providers"])
    assert totalt == n_sensor + n_register, (totalt, n_sensor, n_register)


def test_a_class_without_an_adapter_is_not_reported_as_missing_a_second_one():
    """Den saknar inte ett andra nät — den saknar det första. Att räkna
    den i båda listorna gör luckan större än den är."""
    m = standing.matning()
    assert not (set(m["classes_with_one_provider"])
                & set(m["sensor_classes_without_adapter"]))


def test_the_report_says_what_it_cannot_know():
    """Konkurrentbilden är analys, inte mätning. Att inte skriva ut det
    vore att låta en gissning se ut som ett mätvärde."""
    r = standing.rapport()
    assert "analysis, not from a measurement" in r["not_measurable_en"]
    assert "network" in r["not_measurable_en"]
    for p in r["plan"]:
        assert p["market_en"], f"{p['id']} saknar marknadskontext"


def test_the_handover_carries_the_rules_that_must_not_be_negotiated_away():
    """Markdown-utdatan är en överlämning till en annan session. Utan
    doktrinen i den ärver mottagaren siffrorna men inte omdömet."""
    md = standing.markdown(standing.rapport())
    for regel in ("mock", "data_coverage", "AAMOS", ".env",
                  "verified.json", "test_contract"):
        assert regel in md, f"överlämningen nämner inte {regel}"
    assert "make test" in md and "make preflight" in md


def test_both_output_formats_carry_the_same_facts():
    """En markdown som säger något annat än rapporten är en andra
    sanning."""
    r = standing.rapport()
    md = standing.markdown(r)
    m = r["measured"]
    assert f"{m['markets']} marknader" in md
    assert f"{len(m['decisions_built'])} av {m['decisions_total']}" in md
    assert f"{m['sources_verified']} av" in md
    for g in r["gaps"]:
        assert g["what_en"] in md


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
