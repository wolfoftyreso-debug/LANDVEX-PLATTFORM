"""Tester för Gap Analysis + etableringsplan. Körs utan pytest:
python3 -m tests.test_gaps_plan"""
from __future__ import annotations

from engine.ask import ask, parse
from engine.gaps import gap_analysis
from engine.plan import PLAN_DATA, establishment_plan
from engine.verticals import VERTICALS
from engine.workforce import OCCUPATIONS


# ── Gap Analysis ─────────────────────────────────────────────────────

def test_gap_contract_and_ranking():
    res = gap_analysis("bilverkstad", top_n=5)
    assert res["sammanfattning_sv"]
    obal = res["obalanser"]
    assert len(obal) == 5
    scores = [e["obalans_score"] for e in obal]
    assert scores == sorted(scores, reverse=True)
    for e in obal:
        assert 0 <= e["obalans_score"] <= 100
        assert e["klass"] in ("stark_obalans", "potentiell_obalans",
                              "svag_obalans")
        for axel in ("efterfragan", "utbudsunderskott", "utveckling"):
            assert 0 <= e[axel] <= 100, axel
        assert e["forklaring"]["efterfragan"] and e["forklaring"]["utbud"]
        assert all("bedomning_sv" in r and "kalla" in r
                   for r in e["forklaring"]["efterfragan"])
        assert e["narrativ_sv"]
    assert len(res["heatmap"]) == 40
    assert res["caveats_sv"]
    assert gap_analysis("bilverkstad", top_n=5) == res     # determinism


def test_gap_in_germany_and_validation():
    res = gap_analysis("vvs", market="de", top_n=3)
    assert res["market"] == "de" and len(res["heatmap"]) == 16
    try:
        gap_analysis("rymdturism")
    except ValueError:
        return
    raise AssertionError("Okänd vertikal ska ge ValueError")


# ── Etableringsplan ──────────────────────────────────────────────────

def test_plan_data_covers_all_verticals():
    assert set(PLAN_DATA) == set(VERTICALS)
    for vid, spec in PLAN_DATA.items():
        assert spec.m2[0] <= spec.m2[1] and spec.utrustning_tkr[0] <= spec.utrustning_tkr[1]
        assert 0 < spec.marginal[0] <= spec.marginal[1] < 1
        for occ in spec.yrken:
            assert occ in OCCUPATIONS, (vid, occ)


def test_plan_contract():
    p = establishment_plan("2482", "bilverkstad")          # Skellefteå
    assert p["kommun"] == "Skellefteå"
    for key in ("lokal", "investering_tkr", "finansiering", "personal",
                "leverantorer_sv", "ekonomi", "risker", "nasta_steg_sv",
                "caveats_sv"):
        assert key in p, key
    inv = p["investering_tkr"]
    assert inv["totalt"][0] == inv["startkapital"][0] + inv["utrustning"][0]
    eko = p["ekonomi"]
    assert eko["aterbetalningstid_ar"] is None or \
        0 < eko["aterbetalningstid_ar"][0] <= eko["aterbetalningstid_ar"][1]
    assert "prognos" in eko["notis_sv"]                    # schablonmärkning
    assert len(p["risker"]) == 3
    assert p["personal"]["yrken"] and all(
        y["rekryteringslage_sv"] for y in p["personal"]["yrken"])
    assert establishment_plan("2482", "bilverkstad") == p  # determinism


def test_plan_uncalibrated_market_is_honest():
    p = establishment_plan("de-berlin", "vvs", market="de")
    assert p["ekonomi"]["status"] == "ej_kalibrerad"
    # Personalens rekryteringsläge fungerar ändå (workforce är global).
    assert p["personal"]["yrken"]


def test_plan_validation():
    for bad in [("9999", "frisor", "se"), ("0180", "rymd", "se"),
                ("0180", "frisor", "xx")]:
        try:
            establishment_plan(bad[0], bad[1], market=bad[2])
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


# ── Fråga Landvex ────────────────────────────────────────────────────

def test_ask_gap_and_plan_intents():
    q = parse("Var finns störst obalans för bilverkstäder?")
    assert q.intent == "gap_analys" and q.vertical_id == "bilverkstad"
    q2 = parse("Gör en etableringsplan för bilverkstad i Skellefteå.")
    assert q2.intent == "etableringsplan"
    assert q2.kommun[1] == "Skellefteå"

    res = ask("Var finns störst obalans för bilverkstäder?")
    assert res["intent"] == "gap_analys"
    assert res["rader"] and res["karta"]["typ"] == "heatmap"
    assert res["rader"][0]["detalj"]["motivering_sv"]

    res2 = ask("Gör en etableringsplan för bilverkstad i Skellefteå.")
    assert res2["intent"] == "etableringsplan"
    ids = [r["id"] for r in res2["rader"]]
    assert ids == ["lokal", "investering", "personal", "ekonomi", "risker"]
    assert "tkr" in res2["svar_sv"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
