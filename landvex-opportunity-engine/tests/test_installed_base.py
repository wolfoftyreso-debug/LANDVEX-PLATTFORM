"""Tester för Installed Base Engine. Körs utan pytest:
python3 -m tests.test_installed_base"""
from __future__ import annotations

from engine.ask import ask, parse
from engine.installed_base import (PRODUCT_TYPES, product_catalog,
                                   service_analysis, service_demand_map)
from engine.signals import CATALOG
from engine.verticals import VERTICALS
from engine.workforce import OCCUPATIONS


def test_product_types_are_valid_data():
    assert len(PRODUCT_TYPES) >= 8
    for p in PRODUCT_TYPES.values():
        assert p.bas_signal in CATALOG, p.id
        assert p.bas_mode in ("per_unit", "per_1000pop", "density_scaled")
        assert 0 < p.serviceintervall_ar <= p.livslangd_ar, p.id
        assert p.vertical_id in VERTICALS, p.id
        assert p.occupation_id is None or p.occupation_id in OCCUPATIONS, p.id
        assert p.certifiering_en and p.felmonster_en and p.sasong_en
        for sid, _ in p.tillvaxt_signaler:
            assert sid in CATALOG, (p.id, sid)
    assert all(c["betjanas_av_en"] for c in product_catalog())


def test_service_analysis_contract():
    res = service_analysis("0180")                       # Stockholm, 2031
    assert res["kommun"] == "Stockholm"
    assert len(res["produkter"]) == len(PRODUCT_TYPES)
    utbyten = [p["utbyten_till_malar"] for p in res["produkter"]]
    assert utbyten == sorted(utbyten, reverse=True)      # störst våg först
    for p in res["produkter"]:
        assert p["installerad_bas"] >= 0
        assert p["servicetillfallen_per_ar"] >= 0
        assert p["teknikerbehov"] >= 0
        assert p["teknikerlage"]["text_en"]
        # Kedjan är konsistent: utbyten ≤ bas, service ∝ bas/intervall.
        assert p["utbyten_till_malar"] <= p["installerad_bas"]
    assert "estimate" in res["antaganden_en"][0]     # ärlighet
    assert service_analysis("0180") == res               # determinism


def test_service_map_contract_and_mismatch():
    res = service_demand_map("varmepump_luft")
    assert len(res["regioner"]) == 40 and len(res["heatmap"]) == 40
    utbyten = [r["utbyten_till_malar"] for r in res["regioner"]]
    assert utbyten == sorted(utbyten, reverse=True)
    assert all(h["band"] in ("gron", "gul", "rod") for h in res["heatmap"])
    # Mismatch-flaggan: bas + brist → affärsmöjlighet, aldrig utan bas.
    for r in res["regioner"]:
        if r["mismatch"]:
            assert r["installerad_bas"] > 0
            assert r["teknikerlage"]["status"] == "brist"
    # Personbilar saknar modellerat serviceyrke – ärligt fält.
    bil = service_demand_map("personbil")
    assert bil["regioner"][0]["teknikerlage"]["status"] == "ej_modellerat"
    for bad in ("segway", ""):
        try:
            service_demand_map(bad)
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


def test_kyltekniker_added_to_workforce():
    assert "kyltekniker" in OCCUPATIONS
    o = OCCUPATIONS["kyltekniker"]
    assert abs(sum(w for _, w in o.drivers) - 1.0) < 1e-6


def test_ask_service_intents_and_answers():
    q = parse("Vilken region har flest värmepumpar som närmar sig utbytesålder?")
    assert q.intent == "service_karta" and q.product_id == "varmepump_luft"
    q2 = parse("Var är det bäst att starta ett företag som servar laddboxar?")
    assert q2.intent == "service_karta" and q2.product_id == "laddbox"
    q3 = parse("Hur ser servicebehovet ut i Umeå?")
    assert q3.intent == "servicebehov_kommun"
    q4 = parse("Var kommer behovet av kyltekniker att öka de kommande fem åren?")
    assert q4.intent == "nationell_brist" and q4.occupation_id == "kyltekniker"

    res = ask("Vilken region har flest värmepumpar som närmar sig utbytesålder?")
    assert res["intent"] == "service_karta"
    assert len(res["karta"]["heatmap"]) == 40
    assert "estimate" in res["rader"][0]["detalj"]["installerad_bas"]

    res2 = ask("Hur ser servicebehovet ut i Umeå?")
    assert res2["intent"] == "servicebehov_kommun"
    assert len(res2["rader"]) == len(PRODUCT_TYPES)
    d = res2["rader"][0]["detalj"]
    assert d["certifiering"] and d["motivering_en"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
