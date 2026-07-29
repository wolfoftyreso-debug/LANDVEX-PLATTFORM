"""Tester för Index Engine (Intelligence Map). Körs utan pytest:
python3 -m tests.test_indices"""
from __future__ import annotations

from engine.indices import (CONTRADICTION_THRESHOLD, INDEX_TYPES,
                            city_assessment, index_catalog, index_map)
from engine.markets import MARKETS
from engine.signals import CATALOG
SE_N = len(MARKETS["se"].regions)   # antalet svenska kommuner är data, inte en konstant


def test_index_types_are_valid_data():
    assert set(INDEX_TYPES) == {"infrastructure_risk", "commercial_activity",
                                "safety_index", "climate_risk", "urban_growth",
                                "city_health", "sanitation", "haircut_index", "gender_balance",
                                "road_safety", "healthcare_access",
                                "housing_affordability", "air_quality",
                                "digital_readiness", "wellbeing",
                                "labor_market", "justice", "education",
                                "social_trust", "energy_resilience",
                                "mobility", "food_security",
                                "rights_inclusion"}
    for ix in INDEX_TYPES.values():
        assert ix.riktning in ("risk", "styrka")
        assert ix.niva in ("free", "live")
        assert abs(sum(w for _, w in ix.signals) - 1.0) < 1e-6, ix.id
        for sid, _ in ix.signals:
            assert sid in CATALOG, (ix.id, sid)
    kat = index_catalog()
    assert len(kat) == 24                             # 23 index + kontradiktion
    assert any(k["id"] == "contradiction_index" for k in kat)


def test_city_assessment_is_traceable():
    res = city_assessment("0180", market="se")                     # Stockholm
    assert len(res["index"]) == 24     # 23 index + Contradiction Index
    for ix in res["index"]:
        assert 0 <= ix["varde"] <= 100
        assert ix["band"] in ("lag", "mattlig", "forhojd", "hog")
        assert ix["narrativ_en"]
        # "All sourced, all traceable": varje drivare bär källa.
        assert ix["drivare"] and all("kalla" in d for d in ix["drivare"])
    kontr = next(i for i in res["index"]
                 if i["index_id"] == "contradiction_index")
    assert kontr["kontradiktion_upptackt"] == \
        (kontr["varde"] >= CONTRADICTION_THRESHOLD)
    roller = {d["roll"] for d in kontr["drivare"]}
    assert roller == {"officiellt_planerat", "observerat"}
    assert "quiXzoom" in res["caveats_en"][1]         # ärlig precisionsnot
    assert city_assessment("0180", market="se") == res             # determinism


def test_index_map_contract():
    res = index_map("infrastructure_risk", market="se")
    assert len(res["regioner"]) == SE_N
    varden = [r["varde"] for r in res["regioner"]]
    assert varden == sorted(varden, reverse=True)     # högst risk först
    assert all(h["band"] in ("gron", "gul", "orange", "rod")
               for h in res["heatmap"])
    us = index_map("urban_growth", market="us")
    assert len(us["regioner"]) == len(MARKETS["us"].regions)
    kontr = index_map("contradiction_index")
    assert all("kontradiktion_upptackt" in r for r in kontr["regioner"])
    try:
        index_map("aktiekurs")
    except ValueError:
        return
    raise AssertionError("Okänt index ska ge ValueError")


def _mock_only():
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource
    return Resolver([MockSource()])


def _halvt(*signaler: str):
    """Resolver där namngivna signaler påstås komma ur en riktig källa."""
    import dataclasses

    class R:
        def __init__(self):
            self.inner = _mock_only()

        def resolve(self, loc, purpose, signals):
            values, meta = self.inner.resolve(loc, purpose, signals)
            for sid in signaler:
                if sid in values:
                    values[sid] = dataclasses.replace(values[sid],
                                                      source="osm")
            return values, meta

    return R()


def test_a_fully_simulated_index_says_so_on_the_answer():
    """Revisionens fynd: indexmotorn var den enda Resolver-konsumenten
    utan täckningstal. Mätt före fixen: `city_assessment("0180")` på
    ren mock bar ingen `data_coverage`-nyckel alls — ett index på 100 %
    simulering såg identiskt ut med ett på riktiga källor, och läsaren
    fick veta det först genom att öppna varje drivarrad."""
    bed = city_assessment("0180", market="se", resolver=_mock_only())
    assert bed["data_coverage"] == 0.0
    for rad in bed["index"]:
        assert rad["data_coverage"] == 0.0, rad["index_id"]


def test_the_contradiction_row_names_which_sides_are_real():
    """Regeln "båda sidor eller inget fynd" bodde i analysis-svepet
    medan raden själv teg. Nu bär raden `sides_real`, och svepet läser
    den i stället för att räkna om regeln — en sanning, två läsare."""
    bed = city_assessment("0180", market="se", resolver=_mock_only())
    rad = next(r for r in bed["index"]
               if r["index_id"] == "contradiction_index")
    assert rad["sides_real"] == {"planned": False, "observed": False}

    halv = city_assessment("0180", market="se", resolver=_halvt("development_m2"))
    rad = next(r for r in halv["index"]
               if r["index_id"] == "contradiction_index")
    assert rad["sides_real"] == {"planned": False, "observed": True}
    assert rad["data_coverage"] > 0.0

    bada = city_assessment("0180", market="se", resolver=_halvt("development_m2",
                                                   "building_permits"))
    rad = next(r for r in bada["index"]
               if r["index_id"] == "contradiction_index")
    assert rad["sides_real"] == {"planned": True, "observed": True}


def test_partial_real_data_moves_the_coverage_number():
    # signaler som bevisligen ingår i indexmotorns behov
    bed = city_assessment("0180", market="se",
                          resolver=_halvt("renovation_index", "detail_plans"))
    assert 0.0 < bed["data_coverage"] < 1.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
