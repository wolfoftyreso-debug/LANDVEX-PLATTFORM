"""Tester för Index Engine (Intelligence Map). Körs utan pytest:
python3 -m tests.test_indices"""
from __future__ import annotations

from engine.indices import (CONTRADICTION_THRESHOLD, INDEX_TYPES,
                            city_assessment, index_catalog, index_map)
from engine.markets import MARKETS
from engine.signals import CATALOG


def test_index_types_are_valid_data():
    assert set(INDEX_TYPES) == {"infrastructure_risk", "commercial_activity",
                                "safety_index", "climate_risk", "urban_growth"}
    for ix in INDEX_TYPES.values():
        assert ix.riktning in ("risk", "styrka")
        assert ix.niva in ("free", "live")
        assert abs(sum(w for _, w in ix.signals) - 1.0) < 1e-6, ix.id
        for sid, _ in ix.signals:
            assert sid in CATALOG, (ix.id, sid)
    kat = index_catalog()
    assert len(kat) == 6                              # 5 index + kontradiktion
    assert any(k["id"] == "contradiction_index" for k in kat)


def test_city_assessment_is_traceable():
    res = city_assessment("0180", market="se")                     # Stockholm
    assert len(res["index"]) == 6
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
    assert len(res["regioner"]) == 40
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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
