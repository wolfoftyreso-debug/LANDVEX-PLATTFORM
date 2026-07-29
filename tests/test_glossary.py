"""Ordlistan är löftet att varje tal på ytan går att slå upp — och
specialiseringen är det som gör ett Opportunity Score personligt.
Revisionen fann att ingen svit prövade någon av dem riktat: en
glossary-post utan cannot_en, eller en specialisering som pekar på en
faktor som inte finns, hade passerat obemärkt.

Kör: python3 -m tests.test_glossary
"""
from __future__ import annotations

from engine.glossary import METRICS, catalog, explain
from engine.specialization import (SPECIALIZATIONS, specialization_boost,
                                   specialization_catalog,
                                   specializations_for)
from engine.verticals import VERTICALS


def test_every_metric_explains_what_it_cannot_say():
    """En ordlista som bara säger vad talet betyder är en säljtext.
    Doktrinens kärna är cannot_en — och den ska bära substans, inte en
    ifylld ruta."""
    for mid, m in METRICS.items():
        for falt in ("label_en", "means_en", "reads_en", "cannot_en",
                     "from_en"):
            assert m.get(falt, "").strip(), f"{mid}.{falt}"
        assert len(m["cannot_en"]) > 60, (
            f"{mid}: cannot_en är för tunn för att hindra en felläsning")
        assert len(m["means_en"]) > 40, mid


def test_the_from_field_points_into_the_codebase():
    """Proveniens: varje tal säger VAR det räknas. En from_en utan
    fil-referens är ett 'lita på oss'."""
    for mid, m in METRICS.items():
        assert ("engine/" in m["from_en"] or "api/" in m["from_en"]
                or "quiXzoom" in m["from_en"]), f"{mid}: {m['from_en']}"


def test_explain_and_catalog_agree():
    assert explain("confidence") == METRICS["confidence"]
    assert explain("finns_inte") is None
    kat = catalog()
    assert kat["count"] == len(METRICS)


def test_every_specialization_boosts_factors_that_exist():
    """En boost på en faktor som inte finns i vertikalen är en död rad:
    den ser ut som en produktegenskap och multiplicerar ingenting."""
    for vid, specs in SPECIALIZATIONS.items():
        assert vid in VERTICALS, vid
        faktorer = {f.id for f in VERTICALS[vid].factors}
        for s in specs:
            assert s.factor_boost, f"{vid}/{s.id}: tom boost"
            for fid, mult in s.factor_boost.items():
                assert fid in faktorer, (
                    f"{vid}/{s.id} boostar {fid} som inte finns i "
                    f"vertikalens faktorer {sorted(faktorer)}")
                assert 0.5 <= mult <= 3.0, (
                    f"{vid}/{s.id}.{fid}: multiplikator {mult} utanför "
                    f"rimligt spann — en boost ska vikta om, inte ersätta "
                    f"modellen")
            assert s.notis_en and len(s.notis_en) > 30, f"{vid}/{s.id}"


def test_the_boost_lookup_answers_only_for_real_choices():
    vid = next(iter(SPECIALIZATIONS))
    forsta = SPECIALIZATIONS[vid][0]
    assert specialization_boost(vid, forsta.id) == dict(forsta.factor_boost)
    assert specialization_boost(vid, None) == {}
    assert specialization_boost(vid, "finns_inte") == {}
    assert specialization_boost("okand_vertikal", "x") == {}
    assert {s["id"] for s in specializations_for(vid)} == \
        {s.id for s in SPECIALIZATIONS[vid]}
    assert specialization_catalog()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
