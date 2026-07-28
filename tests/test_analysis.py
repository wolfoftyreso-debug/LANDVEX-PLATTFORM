"""Sökningen måste vägra oftare än den rapporterar.

Den som söker samband i tvåtusen par hittar alltid några. Den farligaste
varianten i just den här plattformen är subtilare än så: två SIMULERADE
serier korrelerar exakt som generatorn byggde dem, och ett sådant
"samband" är ett eko av vår egen kod som ser ut som ett fynd om världen.

Sviten prövar därför främst det som INTE ska hända.

Kör: python3 -m tests.test_analysis
"""
from __future__ import annotations

from engine import analysis as A
from engine.models import Location, SignalValue


class _Kalla:
    """Resolver-stubbe med bestämda källor och värden per signal."""

    def __init__(self, spec: dict):
        self.spec = spec

    def resolve(self, location: Location, vertical_id: str,
                signal_ids: list[str]):
        ut = {}
        for sid, (kalla, fn) in self.spec.items():
            if sid in signal_ids:
                ut[sid] = SignalValue(sid, float(fn(location.lat)),
                                      source=kalla, quality=0.8)
        return ut, {}


def test_two_simulated_signals_never_become_a_finding():
    """Det värsta enskilda felet modulen kunde göra: publicera vår egen
    generator som ett samband om världen."""
    A.reset()
    r = A.relationships("us", resolver=_Kalla({
        "pop_radius": ("mock", lambda x: x * 10),
        "income_index": ("mock", lambda x: x * 10 + 1)}), limit=30)
    assert r["count"] == 0
    assert r["skipped_all_mock"] == 1 and r["pairs_tested"] == 1
    assert "generator built them" in r["skipped_en"]


def test_one_real_side_is_enough_to_test_a_pair():
    A.reset()
    r = A.relationships("us", resolver=_Kalla({
        "pop_radius": ("osm", lambda x: x * 10),
        "income_index": ("mock", lambda x: x * 10 + 1)}), limit=30)
    assert r["skipped_all_mock"] == 0 and r["pairs_tested"] == 1
    assert r["count"] == 1
    f = r["findings"][0]
    assert f["pearson"] > 0.99 and f["direction"] == "positive"
    assert f["sources"]["pop_radius"] == ["osm"]


def test_a_weak_relationship_is_not_a_finding():
    A.reset()
    r = A.relationships("us", resolver=_Kalla({
        "pop_radius": ("osm", lambda x: (x * 7919) % 13),
        "income_index": ("mock", lambda x: (x * 104729) % 17)}), limit=40)
    assert r["pairs_tested"] == 1
    assert all(abs(f["pearson"]) >= A.MIN_R for f in r["findings"])


def test_too_few_regions_reports_nothing_at_all():
    """En korrelation på fem punkter är en linje genom brus."""
    A.reset()
    r = A.relationships("us", resolver=_Kalla({
        "pop_radius": ("osm", lambda x: x),
        "income_index": ("mock", lambda x: x)}), limit=A.MIN_N - 1)
    assert r["pairs_tested"] == 0 and r["count"] == 0


def test_every_finding_carries_how_many_pairs_were_tested():
    """Ett samband ur tio prövade par och ett ur tvåtusen är inte samma
    påstående — och talet får inte bara stå i en sammanfattning som går
    att klippa bort."""
    A.reset()
    r = A.relationships("us", resolver=_Kalla({
        "pop_radius": ("osm", lambda x: x),
        "income_index": ("mock", lambda x: x * 2),
        "share_65plus": ("mock", lambda x: x * 3)}), limit=30)
    assert r["findings"], "inget att pröva på"
    for f in r["findings"]:
        assert f["pairs_tested"] == r["pairs_tested"] >= 1
        assert "n" in f and f["n"] >= A.MIN_N


def test_no_causal_word_survives_into_the_answer():
    A.reset()
    r = A.relationships("us", resolver=_Kalla({
        "pop_radius": ("osm", lambda x: x),
        "income_index": ("mock", lambda x: x)}), limit=30)
    text = " ".join([r["means_en"], r["cannot_en"], r["caveat"]]
                    + [f["detail_en"] for f in r["findings"]]).lower()
    for ord_ in ("causes", "caused by", "leads to", "because of"):
        assert ord_ not in text, ord_
    assert "not causation" in r["caveat"].lower()


def test_a_cross_section_is_not_called_a_trend():
    """Plattformen har ingen historik att korrelera över tid. Att låtsas
    annat vore att uppfinna en tidsaxel."""
    A.reset()
    r = A.relationships("us", limit=20)
    assert "cross-section, not a time series" in r["means_en"]


# ── Motsägelser ─────────────────────────────────────────────────────────
def test_a_contradiction_built_only_on_mock_is_not_a_finding():
    """Vår egen generator som motsäger sig själv säger ingenting om
    världen."""
    A.reset()
    c = A.contradictions("us", limit=6)
    assert c["count"] == 0
    assert c["skipped_all_mock"] == c["regions_examined"] or \
        c["regions_examined"] == 0
    assert "not a finding about the world" in c["skipped_en"]


def _halvt_verklig(*signaler: str):
    """Resolver där NAMNGIVNA signaler påstås komma ur en riktig källa
    och resten är mock. Så ser läget ut dagen den första riktiga källan
    kopplas in — och det är då spärren nedan blir skarp."""
    import dataclasses

    from engine.datasources.mock import MockSource
    from engine.scoring import Resolver

    class R:
        def __init__(self):
            self.inner = Resolver([MockSource()])

        def resolve(self, loc, purpose, signals):
            values, meta = self.inner.resolve(loc, purpose, signals)
            for sid in signaler:
                if sid in values:
                    values[sid] = dataclasses.replace(values[sid],
                                                      source="osm")
            return values, meta

    return R()


def test_one_real_side_against_simulated_paper_is_not_a_contradiction():
    """Det farligaste felet i hela sveparen, och det var på riktigt där.

    Spärren släppte igenom så fort NÅGON drivare var verklig. Mätt före
    fixen: med bara den observerade sidan verklig rapporterades Solna som
    en kontradiktion på 36 med `sources: ["mock", "osm"]` — presenterat
    som "a finding about the place". Hela avståndet kom ur mockdata.
    """
    for sida in (("development_m2", "renovation_index"),
                 ("building_permits", "detail_plans")):
        c = A.contradictions("se", resolver=_halvt_verklig(*sida), limit=6)
        assert c["count"] == 0, f"halvt verkligt fynd: {c['findings']}"
        assert c["skipped_one_sided"] == c["regions_examined"]
        assert "measures the simulation" in c["skipped_en"]


def test_a_contradiction_where_both_sides_are_real_still_lands():
    """Spärren får inte tysta det den finns för att släppa fram."""
    c = A.contradictions(
        "se", resolver=_halvt_verklig("development_m2", "building_permits"),
        limit=6)
    assert c["skipped_one_sided"] == 0
    assert c["count"] >= 1
    assert all(f["sources"] for f in c["findings"])


def test_the_sweep_sees_what_the_harvest_actually_brought_home():
    """`relationships` fick sin egen resolver; motsägelsesvepet fick den
    aldrig och föll till scoring-modulens mock-only-resolver.

    Följden såg ut som ett besked om världen: sju skördade amerikanska
    bygglovsregister låg i lagret, och svepet rapporterade ändå VARENDA
    region som "allt simulerat". Mätt efter fixen blir samma regioner
    `skipped_one_sided` — verkligt papper, simulerad mark — vilket är
    sanningen om underlaget.
    """
    import os
    import time

    from engine import harvest as H

    H.reset()
    A.reset()
    os.environ["LANDVEX_PERMITS_ON"] = "1"
    try:
        nu = time.time()
        H.store_rows([
            {"source": "socrata_permits", "region_code": kod, "market": "us",
             "signal_id": "building_permits", "value": 48213.0,
             "lat": lat, "lon": lon, "observed_at": nu}
            for kod, lat, lon in (("us-newyork", 40.71, -74.01),
                                  ("us-chicago", 41.88, -87.63))])
        c = A.contradictions("us", limit=3)      # newyork, losangeles, chicago
        assert c["skipped_one_sided"] >= 2, (
            f"svepet såg inte de skördade bygglovsraderna: {c}")
        assert c["count"] == 0
    finally:
        os.environ.pop("LANDVEX_PERMITS_ON", None)
        H.reset()


def test_a_contradiction_needs_no_sample_to_be_real():
    c = A.contradictions("us", limit=1)
    assert "A single region is enough" in c["means_en"]
    assert "which one is wrong" in c["cannot_en"].lower() or \
        "WHICH side is wrong" in c["cannot_en"]


def test_an_unknown_market_is_refused_by_both_searches():
    for fn in (A.contradictions, A.relationships):
        try:
            fn("atlantis")
        except ValueError as e:
            assert "atlantis" in str(e)
        else:
            raise AssertionError(f"{fn.__name__} tillät okänd marknad")


# ── Registret ───────────────────────────────────────────────────────────
def test_the_same_finding_twice_is_one_row():
    """Samma motsägelse två dygn i rad är ett fynd, inte två."""
    A.reset()
    f = A._fynd("contradiction", "us", "us-newyork",
                {"detail_en": "planned 80 vs observed 20"}, "")
    assert A.record([f]) == 1
    assert A.record([f]) == 0
    assert A.register()["count"] == 1
    A.reset()


def test_the_register_can_be_read_by_kind_and_market():
    A.reset()
    A.record([
        A._fynd("contradiction", "us", "a", {"detail_en": "x"}, ""),
        A._fynd("relationship", "se", "b~c", {"detail_en": "y"}, "")])
    assert A.register()["count"] == 2
    assert A.register(kind="contradiction")["count"] == 1
    assert A.register(market="se")["count"] == 1
    assert A.register()["by_kind"] == {"contradiction": 1, "relationship": 1}
    A.reset()


def test_an_empty_register_says_it_looked():
    """Tomt efter en körning är ett resultat. Tomt för att ingen kört är
    något annat, och de får inte se likadana ut."""
    A.reset()
    r = A.register()
    assert r["count"] == 0 and "looked and found" in r["quiet_en"]
    A.record([A._fynd("contradiction", "us", "a", {"detail_en": "x"}, "")])
    assert A.register()["quiet_en"] == ""
    A.reset()


def test_a_register_of_findings_is_not_a_register_of_truths():
    assert "not a register of truths" in A.register()["cannot_en"]
    k = A.catalog()
    assert "Nothing here is causal" in k["cannot_en"]
    assert "BOTH signals are simulated" in k["principle_en"]
    import json
    assert json.dumps(k)


def test_a_run_counts_only_what_the_register_did_not_have():
    A.reset()
    forsta = A.run("us", limit=14)
    igen = A.run("us", limit=14)
    assert igen["new_findings"] == 0, "samma svep lade till fynd igen"
    assert forsta["found"] == igen["found"]
    A.reset()


def test_the_scheduler_can_run_the_search():
    from engine import scheduler as S

    A.reset()
    S.reset()
    S.save_job(S.job("sok", "analyse", tenant="t",
                     params={"market": "us", "limit": 14}))
    r = S.run_due("t", 1_800_000_000.0)["ran"][0]
    assert r["status"] == "ok"
    assert "pair(s) skipped" in r["detail_en"]
    S.reset()
    A.reset()


def test_the_search_needs_the_same_package_as_the_sweep():
    from api.licensing import required_capability

    assert required_capability("/v1/analysis") == "opportunity"
    assert required_capability("/v1/analysis/run") == "opportunity"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
