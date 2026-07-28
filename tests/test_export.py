"""Export som inte tappar förbehållen på vägen ut.

Det farliga med export är inte formatet. Det är att ett Opportunity Score
i en CSV-fil ser ut som ett mätvärde så fort det lämnat skärmen där
täckningsgraden och brasklapparna stod. Testerna nedan prövar just det:
att provenienser följer med i VARJE format, att formaten vi inte kan
leverera vägras vid namn i stället för att approximeras, och att en
kunds egna rader aldrig kan skrivas ut utan tenant.

Kör: python3 -m tests.test_export
"""
from __future__ import annotations

import csv
import io
import json

from engine import export as E


def _utan_kommentarer(text: str) -> list[dict]:
    rader = [r for r in text.splitlines() if not r.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(rader))))


def test_every_format_carries_the_caveats_into_the_file():
    """En brasklapp som stannar på skärmen skyddar ingen."""
    p = {"vertical": "gym", "market": "us", "top_n": 3}

    c = E.export("hotspots", "csv", p)
    kommentarer = [r for r in c["content"].splitlines() if r.startswith("#")]
    assert any("caveat:" in r for r in kommentarer)
    assert any("engine 1." in r or "engine 0." in r for r in kommentarer)

    n = E.export("hotspots", "ndjson", p)
    forsta = json.loads(n["content"].splitlines()[0])
    assert forsta["_landvex"]["caveats_en"]
    assert forsta["_landvex"]["engine_version"]

    g = E.export("hotspots", "geojson", p)
    doc = json.loads(g["content"])
    assert doc["landvex"]["caveats_en"]
    assert doc["type"] == "FeatureCollection"


def test_the_csv_still_parses_as_csv():
    """Kommentarrader får inte göra filen oläsbar — pandas läser dem med
    comment='#', och den som klipper bort dem gör det medvetet."""
    r = E.export("hotspots", "csv", {"vertical": "gym", "market": "us",
                                     "top_n": 3})
    rader = _utan_kommentarer(r["content"])
    assert len(rader) == 3 == r["row_count"]
    assert rader[0]["region"] and rader[0]["opportunity_score"]


def test_formats_we_cannot_deliver_are_refused_by_name():
    """En CSV med filändelsen .xlsx är en lögn med ett Excel-ikon på."""
    for f in ("pdf", "xlsx", "parquet", "shapefile"):
        try:
            E.export("hotspots", f, {"vertical": "gym"})
        except E.ExportRefused as e:
            assert f in str(e) and len(str(e)) > 40, f   # skälet står med
        else:
            raise AssertionError(f"{f} levererades — som vad?")


def test_an_unknown_format_lists_both_what_works_and_what_is_refused():
    try:
        E.export("hotspots", "xml", {"vertical": "gym"})
    except E.ExportRefused as e:
        assert "csv" in str(e) and "pdf" in str(e)
    else:
        raise AssertionError("okänt format tilläts")


def test_a_customers_own_rows_cannot_be_exported_without_a_tenant():
    """Utan tenant skulle filen innehålla allas rader. Det är den sortens
    misstag som bara upptäcks efteråt."""
    try:
        E.export("compliance", "csv", {})
    except E.ExportRefused as e:
        assert "tenant" in str(e)
    else:
        raise AssertionError("kundens register exporterades utan tenant")


def test_a_tenant_only_ever_exports_its_own_rows():
    from engine import inspections as I

    I.reset()
    I.save_routine(I.routine("v", "Weekly", "flagpole", 7,
                             checks=["present"], tenant="flaggab"))
    I.save_asset(I.asset("fp1", "flagpole", address="Hantverkargatan 1",
                         tenant="flaggab"))
    I.save_asset(I.asset("boj1", "lifebuoy", address="Badet",
                         tenant="kommunen"))
    mina = _utan_kommentarer(
        E.export("compliance", "csv", {}, tenant="flaggab")["content"])
    assert [r["asset_id"] for r in mina] == ["fp1"]
    andras = E.export("compliance", "csv", {}, tenant="kommunen")
    assert "fp1" not in andras["content"]
    I.reset()


def test_geojson_refuses_rather_than_drawing_an_empty_map():
    """Ett dataset utan koordinater ger en tom FeatureCollection, och en
    tom karta ser ut som 'inget finns här' i stället för 'fel format'."""
    from engine import inspections as I

    I.reset()
    I.save_routine(I.routine("v", "Weekly", "flagpole", 7,
                             checks=["present"], tenant="t"))
    I.save_asset(I.asset("utan_koord", "flagpole", tenant="t"))
    try:
        E.export("compliance", "geojson", {}, tenant="t")
    except E.ExportRefused as e:
        assert "coordinates" in str(e)
    else:
        raise AssertionError("tom karta levererades")
    I.reset()


def test_geojson_drops_no_column_it_was_given():
    """Skälet att vägra shapefile är att den trunkerar kolumnnamn. Då får
    inte vårt eget GeoJSON tappa fält på vägen."""
    r = E.export("imbalances", "csv", {"vertical": "vvs", "market": "se",
                                       "top_n": 2})
    kolumner = set(_utan_kommentarer(r["content"])[0])
    g = json.loads(E.export("imbalances", "geojson",
                            {"vertical": "vvs", "market": "se",
                             "top_n": 2})["content"])
    props = set(g["features"][0]["properties"])
    assert props == kolumner - {"lat", "lon"}


def test_every_dataset_names_the_package_it_needs():
    """Exporten får inte bli en väg runt paketet: köp export, läs allt."""
    from api.licensing import PLANS

    kanda = set().union(*(set(p["capabilities"]) for p in PLANS.values()))
    for d in E.DATASETS:
        assert d["capability"] in kanda, d["id"]
        assert d["answers_from"].startswith("/v1/"), d["id"]
        assert d["label_en"] and d["params_en"], d["id"]


def test_the_catalog_states_what_is_refused_as_plainly_as_what_works():
    k = E.catalog()
    assert {d["id"] for d in k["datasets"]} == {d["id"] for d in E.DATASETS}
    assert {f["id"] for f in k["refused"]} == set(E.REFUSED_FORMATS)
    for f in k["refused"]:
        assert len(f["why_en"]) > 40, f["id"]
    for f in k["formats"]:
        assert f["provenance_en"], f["id"]
    # Katalogen får inte innehålla den anropbara funktionen: den är inte
    # JSON-serialiserbar, och /v1/export skulle falla på sista raden.
    assert json.dumps(k)


def test_an_unknown_dataset_says_which_ones_exist():
    try:
        E.export("allt", "csv", {})
    except E.ExportRefused as e:
        assert "hotspots" in str(e)
    else:
        raise AssertionError("okänd datamängd tilläts")


def test_the_same_export_twice_is_the_same_file():
    """Determinism gäller även på vägen ut — bortsett från tidsstämpeln,
    som är det enda som får skilja."""
    p = {"vertical": "gym", "market": "us", "top_n": 3}
    a = _utan_kommentarer(E.export("hotspots", "csv", p)["content"])
    b = _utan_kommentarer(E.export("hotspots", "csv", p)["content"])
    assert a == b


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
