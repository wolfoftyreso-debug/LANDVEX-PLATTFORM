"""Tester för paketeringen – beslut, inte datamängd.
Kör: python3 -m tests.test_offering"""
from __future__ import annotations

from api.catalog import API_CATALOG
from api.licensing import PLANS, required_capability
from engine import offering as O


def _all_paths() -> set[str]:
    return {ep["path"] for eng in API_CATALOG["engines"]
            for ep in eng["endpoints"]}


def test_a_built_decision_must_point_at_an_endpoint_that_exists():
    """Spärren mot att sälja obyggt: 'built' måste kunna bevisas."""
    paths = _all_paths()
    for d in O.DECISIONS:
        if d["status"] == "built":
            assert d["answered_by"], d["id"]
            assert d["answered_by"] in paths, (
                f"{d['id']} säger 'built' men {d['answered_by']} finns inte "
                f"i API-katalogen")
            assert required_capability(d["answered_by"]), d["id"]


def test_a_planned_decision_never_claims_to_answer_anything():
    for d in O.DECISIONS:
        if d["status"] == "planned":
            assert d["answered_by"] is None, d["id"]
            assert "not built" in d["decides_en"].lower() or \
                   "nothing yet" in d["decides_en"].lower(), d["id"]


def test_the_things_that_do_not_exist_are_listed_as_planned():
    """Export, dashboards och white-label finns inte – de får inte säljas."""
    planned = {d["id"] for d in O.DECISIONS if d["status"] == "planned"}
    assert {"own_dashboards", "white_label"} <= planned


def test_every_decision_is_a_question_a_person_would_ask():
    for d in O.DECISIONS:
        assert d["question_en"].endswith("?"), d["id"]
        assert d["who_en"] and d["decides_en"], d["id"]
        assert d["plan"] in ("free", "pro", "enterprise"), d["id"]


def test_tiers_inherit_downwards():
    free = {d["id"] for d in O.decisions_for("free")}
    pro = {d["id"] for d in O.decisions_for("pro")}
    ent = {d["id"] for d in O.decisions_for("enterprise")}
    assert free < pro < ent
    assert "where_to_establish" not in free
    assert "detect_without_asking" in ent


def test_surface_names_resolve_to_the_contract_ids():
    """Nyckelformatet är ett kontrakt: id:na får inte bytas."""
    assert set(PLANS) == {"free", "pro", "enterprise"}
    for name, pid in (("Explorer", "free"), ("Professional", "pro"),
                      ("professional", "pro"), ("growth", "pro"),
                      ("Enterprise Intelligence", "enterprise")):
        assert O.resolve_plan(name) == pid, name
    # och samma alias måste fungera där planer faktiskt slås upp
    from api.licensing import resolve_capabilities
    assert resolve_capabilities("professional") == resolve_capabilities("pro")
    assert resolve_capabilities("explorer") == resolve_capabilities("free")


def test_brief_scope_widens_with_the_tier():
    f, p, e = (O.brief_scope(x) for x in ("free", "pro", "enterprise"))
    assert f["may_scope_by_area"] is False
    assert p["may_scope_by_area"] and p["may_scope_by_sector"]
    assert p["may_use_own_assets"] is False
    assert e["may_use_own_assets"] is True


def test_offering_separates_built_from_planned():
    o = O.offering()
    assert len(o["plans"]) == 3
    for row in o["plans"]:
        assert row["name_en"] and row["for_en"] and row["promise_en"]
        for d in row["decisions_you_can_make"]:
            assert d["status"] == "built"
        for d in row["not_built_yet"]:
            assert d["status"] == "planned"
    assert "not data access" in o["principle_en"]
    assert "has not been written" in o["honesty_en"]
    try:
        O.offering("platinum")
        raise AssertionError("okänd plan tilläts")
    except ValueError:
        pass



def test_repackaging_by_decision_does_not_erase_how_it_is_charged():
    """Att beskriva nivåerna i beslut i stället för datamängd ändrar VAD
    som säljs, aldrig HUR det debiteras. Professional har ingen månadsavgift
    — den betalas som quiXzoom-kommission per levererad lead. En prislista
    som tappar det säljer en annan affär än den som är byggd."""
    from api.licensing import PLANS
    for pid, surf in O.PLAN_SURFACE.items():
        assert surf["billing_en"], pid
    # Provisionsfaktumet FLYTTADE till engine/commercial.py när nivån
    # fick flera paketeringar — en franchise köper per lead, en kommun
    # kan bara köpa en pilot. Testet håller faktumet, inte meningen: det
    # var innebörden som skulle skyddas, inte formuleringen.
    from engine.commercial import for_plan
    lead = [x for x in for_plan("pro") if x["id"] == "per_lead"]
    assert lead, "Professional kan inte längre köpas per levererad lead"
    assert "delivery" in lead[0]["pays_when_en"].lower()
    assert "opportunity score" in lead[0]["pays_when_en"].lower()
    assert "commission" in O.PLAN_SURFACE["pro"]["billing_en"].lower()
    # samma faktum som licenslagret bär – de får inte glida isär
    assert PLANS["pro"]["pris_manad"] is None
    assert "commission" in PLANS["pro"]["beskrivning_en"].lower()
    assert PLANS["pro"]["kommission"], "kommissionstabellen saknas"
    for row in O.offering()["plans"]:
        assert row["billing_en"]



def test_each_tier_leads_with_exactly_one_decision():
    """Sjutton punkter tvingar kunden att göra säljarens urval. Ett
    beslut fram per nivå; resten levereras men står inte först."""
    o = O.offering()
    assert len(o["plans"]) == 3
    for row in o["plans"]:
        head = row["headline"]
        assert head is not None, f"{row['plan_id']} leder med ingenting"
        assert head["status"] == "built", head["id"]
        assert head["id"] == O.HEADLINE[row["plan_id"]]
        # Ingenting tappas: rubriken + resten är fortfarande allt.
        assert len(row["also_included"]) + 1 == row["built_count"]
        assert head not in row["also_included"]
        ids = {d["id"] for d in row["also_included"]} | {head["id"]}
        assert ids == {d["id"] for d in row["decisions_you_can_make"]}


def test_the_headline_of_a_tier_is_not_inherited_from_the_one_below():
    """Varje nivå ska leda med något NYTT. Leder Professional med samma
    beslut som Explorer har kunden inget skäl att uppgradera."""
    heads = {p: O.HEADLINE[p] for p in ("free", "pro", "enterprise")}
    assert len(set(heads.values())) == 3
    by_id = {d["id"]: d for d in O.DECISIONS}
    for plan, did in heads.items():
        assert by_id[did]["plan"] == plan, (
            f"{plan} leder med {did}, som hör till "
            f"{by_id[did]['plan']} — det är ärvt, inte nytt")


def test_every_decision_names_the_role_it_serves():
    """Fyndet: konsolen släppte in en elektriker i Tyresö och delstaten
    Texas genom samma fråga. Rollen fanns redan i engine/entrypoints.py —
    sex dörrar med trigger, framgångskriterium och leverabel — men
    beslutet visste inte vilken dörr det hörde till, så dörren gick inte
    att fylla."""
    from engine.entrypoints import ENTRYPOINTS
    from engine.offering import DECISIONS
    roller = {e["id"] for e in ENTRYPOINTS}
    for d in DECISIONS:
        assert d.get("audience"), f"{d['id']} saknar roll"
        assert d["audience"] in roller, (
            f"{d['id']} pekar på rollen {d['audience']!r} som inte finns i "
            f"ENTRYPOINTS — två vokabulär för samma sak är värre än ett "
            f"felaktigt, för läsaren måste veta vilket som gäller")


def test_no_role_is_left_without_a_decision():
    """En roll utan ett enda beslut är en dörr som öppnas mot en tom
    vägg."""
    from engine.entrypoints import ENTRYPOINTS
    from engine.offering import DECISIONS
    har = {d["audience"] for d in DECISIONS if d["status"] == "built"}
    tomma = [e["id"] for e in ENTRYPOINTS if e["id"] not in har]
    assert not tomma, f"roller utan byggt beslut: {tomma}"


def test_the_offering_does_not_reinvent_the_entrypoints():
    """Jag byggde en egen AUDIENCES-tabell innan jag läst
    engine/entrypoints.py, som redan bar samma sak rikare. Testet finns
    för att nästa läsare inte ska göra om det."""
    from engine import offering
    assert not hasattr(offering, "AUDIENCES"), (
        "rollerna bor i engine/entrypoints.py — lägg dem inte här igen")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
