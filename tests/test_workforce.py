"""Tester för Workforce Intelligence Engine. Körs utan pytest:
python3 -m tests.test_workforce"""
from __future__ import annotations

from engine.signals import CATALOG
from engine.workforce import (BASE_YEAR, OCCUPATIONS, forecast,
                              national_map, occupation_catalog, simulate)


def test_catalog_is_valid_data():
    assert len(OCCUPATIONS) >= 12
    for o in OCCUPATIONS.values():
        assert o.per_1000 > 0 and 0 < o.pension_rate < 0.1, o.id
        assert o.edu_per_100k >= 0
        total_w = sum(w for _, w in o.drivers)
        assert abs(total_w - 1.0) < 1e-6, (o.id, total_w)
        for sid, _ in o.drivers:
            assert sid in CATALOG, (o.id, sid)
    for c in occupation_catalog():
        assert set(c) == {"id", "label_en", "sector_en",
                          "medellon_tkr_manad", "automationsrisk_schablon"}
        assert 0.0 <= c["automationsrisk_schablon"] <= 1.0


def test_forecast_contract_and_honesty():
    res = forecast("0180", target_year=2035, market="se")
    assert res["kommun"] == "Stockholm"
    assert len(res["prognoser"]) == len(OCCUPATIONS)
    for f in res["prognoser"]:
        assert f["behov_nu"] > 0
        lo, hi = f["intervall"]
        assert lo <= f["behov_prognos"] <= hi          # intervall täcker punkten
        assert 0 <= f["konfidens"] <= 100
        assert f["band"] in ("balans", "okande_brist", "kritisk_brist")
        assert f["antaganden"] and f["drivare"]        # transparens
        assert len(f["bana"]) == 2035 - BASE_YEAR
        assert f["bana"][-1]["gap"] == f["brist"]
    assert res["caveats_en"]                           # aldrig "absolut sanning"
    prio = res["utbildningsprioriteringar"]
    assert prio and all(p["motivering_en"] for p in prio)
    assert [p["rang"] for p in prio] == list(range(1, len(prio) + 1))


def test_forecast_deterministic_and_validates():
    assert forecast("0180", market="se") == forecast("0180", market="se")
    for bad in [("9999", 2035, None), ("0180", 2026, None),
                ("0180", 2099, None), ("0180", 2035, ["rymdpilot"])]:
        try:
            forecast(bad[0], bad[1], bad[2])
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


def test_longer_horizon_widens_interval_and_lowers_confidence():
    f30 = next(f for f in forecast("0180", 2030, market="se")["prognoser"]
               if f["occupation_id"] == "elektriker")
    f40 = next(f for f in forecast("0180", 2040, market="se")["prognoser"]
               if f["occupation_id"] == "elektriker")
    rel30 = (f30["intervall"][1] - f30["intervall"][0]) / f30["behov_prognos"]
    rel40 = (f40["intervall"][1] - f40["intervall"][0]) / f40["behov_prognos"]
    assert rel40 > rel30
    assert f40["konfidens"] < f30["konfidens"]


def test_simulation_reduces_gap():
    base = simulate("0180", "elektriker", 0, 2035, market="se")
    sim = simulate("0180", "elektriker", 200, 2035, market="se")
    assert base["brist_med_atgard"] == base["brist_utan_atgard"]
    assert sim["brist_utan_atgard"] == base["brist_utan_atgard"]
    assert sim["brist_med_atgard"] < sim["brist_utan_atgard"]
    assert sim["minskning"] > 0
    # Massiv satsning bör nå balans före målåret.
    big = simulate("0180", "elektriker", 5000, 2035, market="se")
    assert big["balansar"] is not None and big["balansar"] <= 2035
    try:
        simulate("0180", "elektriker", -5, 2035, market="se")
    except ValueError:
        pass
    else:
        raise AssertionError("Negativa platser ska avvisas")


def test_national_map_bands():
    res = national_map("sjukskoterska", 2035, market="se")
    assert len(res["kommuner"]) == 40
    assert all(k["band"] in ("balans", "okande_brist", "kritisk_brist")
               for k in res["kommuner"])
    # Sorterad: störst brist först.
    brist = [k["brist"] for k in res["kommuner"]]
    assert brist == sorted(brist, reverse=True)
    assert res["caveats_en"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
