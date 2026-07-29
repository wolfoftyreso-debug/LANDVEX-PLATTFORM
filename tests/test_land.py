"""Markvärde: det enda talet som får användas mot en verklig fastighet.

Fastighetsvärdering är den plats där plattformen kan göra mest skada.
Ett tal som SER UT som ett marknadsvärde används i en förhandling, en
kreditansökan eller en taxering — och det får aldrig komma ur signaler
som normaliserats mot varandra. Sviten prövar därför:

  1. att inget läge alls beräknas under täckningsgolvet,
  2. att svaret inte bär valuta eller kvadratmeterpris någonstans,
  3. att signaler som talar EMOT markvärdet faktiskt sänker
     läget (dubbelinvertering fångades här, se COUNTER_SIGNALS).

Kör: python3 -m tests.test_land
"""
from __future__ import annotations

import dataclasses

from engine import land as L


def _mock_only():
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource
    return Resolver([MockSource()])


def _akta(*signaler: str, varden: dict | None = None):
    """Resolver där namngivna signaler påstås komma ur riktig källa —
    och valfritt bär ett bestämt värde."""
    class R:
        def __init__(self):
            self.inner = _mock_only()

        def resolve(self, loc, purpose, signals):
            values, meta = self.inner.resolve(loc, purpose, signals)
            for sid in signaler:
                if sid in values:
                    v = (varden or {}).get(sid, values[sid].value)
                    values[sid] = dataclasses.replace(
                        values[sid], source="scb", value=v)
            return values, meta
    return R()


def test_below_the_coverage_floor_there_is_no_position_at_all():
    """Ett markvärdesindex på simulerade signaler är en gissning med en
    decimal på — och den gissningen skulle användas mot en verklig
    fastighet."""
    r = L.assess("0180", market="se", resolver=_mock_only())
    assert r["status"] == "insufficient"
    assert r["position"] is None and r["band"] is None
    assert "used against a real property" in r["refusal_en"]
    assert r["gate"]["required"] == L.MIN_COVERAGE
    # familjerna visas ändå — vägran är inte tystnad
    assert len(r["families"]) == len(L.FAMILIES)
    assert r["how_to_fix_en"] and "/v1/coverage" in r["how_to_fix_en"]


def test_no_surface_anywhere_carries_a_price():
    """Fältsvep: inget nyckelnamn och inget textvärde får antyda ett
    belopp. Ett tal format som ett pris används som ett pris."""
    alla = [L.assess("0180", market="se", resolver=_mock_only()),
            L.assess("0180", market="se",
                     resolver=_akta("transit_score", "pop_radius",
                                    "income_index", "rent_index",
                                    "building_permits", "detail_plans")),
            L.catalog()]
    FORBJUDNA = ("price", "sek", "eur", "usd", "currency", "valuation",
                 "value_estimate", "per_m2", "kr_per", "market_value")

    def svep(x, vag=""):
        if isinstance(x, dict):
            for k, v in x.items():
                assert not any(f in str(k).lower() for f in FORBJUDNA), \
                    f"nyckel {vag}.{k} antyder ett pris"
                svep(v, f"{vag}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                svep(v, f"{vag}[{i}]")

    for svar in alla:
        svep(svar)
        text = svar.get("cannot_en", "")
        if text:
            assert "NOT a valuation" in text or "not a valuation" in text


def test_enough_real_data_gives_a_position_with_its_band():
    r = L.assess("0180", market="se",
                 resolver=_akta("transit_score", "pop_radius",
                                "parking_score", "income_index",
                                "rent_index", "business_density",
                                "building_permits", "detail_plans"))
    assert r["status"] == "computed"
    assert 0 <= r["position"] <= 100
    assert r["band"] in {b for _, b, _ in L.BANDS}
    assert r["data_coverage"] >= L.MIN_COVERAGE
    assert r["summary_en"] and "relative to" in r["summary_en"]
    # varje familj öppnas: drivare med källa och vikt
    for f in r["families"]:
        assert f["what_en"] and f["cannot_en"], f["id"]
        for d in f["drivers"]:
            assert "kalla" in d and "normalised" in d


def test_a_counter_signal_lowers_the_position_it_does_not_raise_it():
    """Fyndet testet gjorde: modulen inverterade signaler som katalogen
    REDAN normaliserar omvänt, så tecknet vändes tillbaka och hög
    brottslighet LYFTE markvärdet (46,2 vid crime 40 mot 51,5 vid
    crime 220). Precis den sortens tysta teckenfel som ser ut som en
    modell."""
    bas = ("transit_score", "pop_radius", "parking_score", "income_index",
           "building_permits", "detail_plans", "crime_index")
    lag = L.assess("0180", market="se",
                   resolver=_akta(*bas, varden={"crime_index": 40.0}))
    hog = L.assess("0180", market="se",
                   resolver=_akta(*bas, varden={"crime_index": 220.0}))
    assert lag["position"] > hog["position"], (
        f"hög brottslighet sänkte inte läget: {lag['position']} vs "
        f"{hog['position']}")
    assert "crime_index" in L.COUNTER_SIGNALS


def test_counter_indications_are_listed_separately_not_averaged_away():
    """Ett läge som är högt TROTS hög brottslighet är ett annat besked
    än ett högt utan invändningar."""
    r = L.assess("0180", market="se",
                 resolver=_akta("transit_score", "pop_radius",
                                "parking_score", "income_index",
                                "building_permits", "detail_plans",
                                "crime_index",
                                varden={"crime_index": 240.0}))
    assert r["counter_indications"], "hög brottslighet borde ha listats"
    rad = r["counter_indications"][0]
    assert rad["signal_id"] == "crime_index"
    assert "works against land value" in rad["why_en"]
    assert str(len(r["counter_indications"])) in r["summary_en"]


def test_a_family_with_no_data_is_named_not_silently_reweighted():
    r = L.assess("0180", market="se",
                 resolver=_akta("transit_score", "pop_radius",
                                "parking_score", "income_index",
                                "rent_index", "business_density",
                                "building_permits", "detail_plans"))
    if r["status"] == "computed":
        assert r["of_weight"] == round(
            sum(f["weight"] for f in r["families"]
                if f["score"] is not None), 2)
        for fid in r["families_refused"]:
            assert any(f["id"] == fid and f["score"] is None
                       for f in r["families"])


def test_the_weights_are_data_and_say_they_are_a_heuristic():
    assert abs(sum(f["weight"] for f in L.FAMILIES) - 1.0) < 1e-9
    for f in L.FAMILIES:
        assert abs(sum(w for _, w in f["signals"]) - 1.0) < 1e-9, f["id"]
    kat = L.catalog()
    assert "documented heuristic" in kat["weights_en"].lower() or \
        "argued with" in kat["weights_en"]
    assert kat["coverage_floor"] == L.MIN_COVERAGE


def test_every_family_signal_exists_in_the_catalogue():
    """Samma regel som för index: en familj som pekar utanför
    signalkatalogen bidrar tyst med noll — och hade rest KeyError den
    dag en källa fyllde den."""
    from engine.signals import CATALOG

    for f in L.FAMILIES:
        for sid, _ in f["signals"]:
            assert sid in CATALOG, f"{f['id']}: okänd signal {sid}"
    for sid in L.COUNTER_SIGNALS:
        assert sid in CATALOG, sid
        assert any(sid == s for f in L.FAMILIES for s, _ in f["signals"]), \
            f"{sid} är motverkande men används inte av någon familj"


def test_the_comparison_keeps_the_unplaceable_in_the_list():
    j = L.compare(["0180", "0182", "0184"], market="se",
                  resolver=_mock_only())
    assert j["count"] == 3
    namn = {r["region_code"] for r in j["ranked"]} | \
        {r["region_code"] for r in j["insufficient"]}
    assert namn == {"0180", "0182", "0184"}
    assert "looks complete and is not" in j["summary_en"]
    for r in j["insufficient"]:
        assert r["refusal_en"]


def test_an_empty_comparison_is_refused():
    try:
        L.compare([], market="se")
    except L.LandRefused:
        return
    raise AssertionError("tom jämförelse skulle ha vägrats")


def test_an_unknown_region_is_refused():
    try:
        L.assess("finns-inte", market="se", resolver=_mock_only())
    except ValueError as e:
        assert "finns-inte" in str(e)
    else:
        raise AssertionError("okänd region tilläts")


def test_it_belongs_to_the_establishment_package():
    from api.licensing import required_capability

    assert required_capability("/v1/land") == "opportunity"
    assert required_capability("/v1/land/assess") == "opportunity"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
