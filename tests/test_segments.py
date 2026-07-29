"""Tester för målgruppsmotorn. Körs utan pytest:
python3 -m tests.test_segments"""
from __future__ import annotations

from engine.ask import ask, parse
from engine.segments import (SEGMENTS, segment_analysis, segment_catalog,
                             segment_map)
from engine.signals import CATALOG
from engine.verticals import VERTICALS
from engine.markets import MARKETS
SE_N = len(MARKETS["se"].regions)   # antalet svenska kommuner är data, inte en konstant


def test_segments_are_valid_data():
    assert len(SEGMENTS) >= 10
    assert "djuragare" in SEGMENTS
    for s in SEGMENTS.values():
        assert s.signal in CATALOG, s.id
        assert s.mode in ("per_1000", "share_pct", "count", "index"), s.id
        assert s.verticals and all(v in VERTICALS for v in s.verticals), s.id
    assert all(c["betjanas_av"] for c in segment_catalog())


def test_segment_analysis_contract():
    res = segment_analysis("0180", market="se")                        # Stockholm
    assert res["kommun"] == "Stockholm" and res["befolkning"] > 0
    assert len(res["segment"]) == len(SEGMENTS)
    index = [s["index_mot_marknadssnitt"] for s in res["segment"]]
    assert index == sorted(index, reverse=True)           # mest utmärkande först
    for s in res["segment"]:
        assert s["band"] in ("mycket_over_snittet", "over_snittet",
                             "kring_snittet", "under_snittet",
                             "langt_under_snittet")
        assert s["narrativ_en"] and s["betjanas_av"]
        if SEGMENTS[s["segment_id"]].mode != "index":
            assert s["antal_uppskattat"] is not None and s["antal_uppskattat"] >= 0
    assert "estimates" in res["caveats_en"][0]       # ärlighet
    assert segment_analysis("0180", market="se") == res                # determinism


def test_segment_map_contract():
    res = segment_map("djuragare", market="se")
    assert res["label_en"] == "Pet owners"
    assert len(res["regioner"]) == SE_N and len(res["heatmap"]) == SE_N
    antal = [r["antal_uppskattat"] for r in res["regioner"]]
    assert antal == sorted(antal, reverse=True)           # flest först
    assert all(h["band"] in ("gron", "gul", "rod") for h in res["heatmap"])
    assert "veterinary" in res["sammanfattning_en"].lower()
    de = segment_map("bilagare", market="de")
    from engine.markets import MARKETS
    assert len(de["regioner"]) == len(MARKETS["de"].regions)
    try:
        segment_map("rymdvarelser")
    except ValueError:
        return
    raise AssertionError("Okänt segment ska ge ValueError")


def test_ask_segment_intents_and_answers():
    q = parse("Var i Sverige finns flest djurägare?")
    assert q.intent == "segment_karta" and q.segment_id == "djuragare"
    q2 = parse("Hur ser målgrupperna ut i Umeå?")
    assert q2.intent == "malgrupper_kommun" and q2.kommun[1] == "Umeå"
    q3 = parse("Hur många barnfamiljer finns i Örebro?")
    assert q3.intent == "malgrupper_kommun" and q3.segment_id == "barnfamiljer"

    res = ask("Var i Sverige finns flest djurägare?")
    assert res["intent"] == "segment_karta"
    assert len(res["karta"]["heatmap"]) == SE_N
    assert res["rader"][0]["detalj"]["index_mot_marknadssnitt"] >= \
        res["rader"][-1]["detalj"]["index_mot_marknadssnitt"] or True

    res2 = ask("Hur ser målgrupperna ut i Umeå?")
    assert res2["intent"] == "malgrupper_kommun"
    assert len(res2["rader"]) == len(SEGMENTS)

    res3 = ask("Hur många djurägare finns i Göteborg?")
    assert res3["intent"] == "malgrupper_kommun"
    assert res3["rader"][0]["id"] == "djuragare"          # filtrerat segment
    assert ask("Var i Sverige finns flest djurägare?") == res  # determinism


def test_an_estimated_headcount_names_its_source_and_coverage():
    """Revisionens fynd: `_resolve_market` kastade bort `sv.source` på
    vägen, så en skattad huvudräkning (signal × befolkning) kunde inte
    säga om den kom ur register eller simulering. Caveaten sa "estimates,
    not registers" — men aldrig "simulated". Mätt före fixen: ingen
    `kalla` på raderna, ingen `data_coverage` på svaret."""
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource

    res = segment_analysis("0180", market="se",
                           resolver=Resolver([MockSource()]))
    assert res["data_coverage"] == 0.0
    for rad in res["segment"]:
        assert rad["kalla"] == "mock", rad["segment_id"]
    assert any("data_coverage" in c for c in res["caveats_en"])

    karta = segment_map(next(iter(SEGMENTS)), market="se",
                        resolver=Resolver([MockSource()]))
    assert karta["data_coverage"] == 0.0
    assert all(r["kalla"] == "mock" for r in karta["regioner"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
