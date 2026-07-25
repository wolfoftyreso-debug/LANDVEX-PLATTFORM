"""Täckningstester – en bransch/marknad får aldrig vara halvt inlagd.

"Allt är data" håller bara om varje ny rad läggs in i SAMTLIGA tabeller
som kedjan svep → plan → ekonomi läser. Den här sviten låser det, så en
halvlagd bransch faller på testet i stället för i en användares ansikte.

Kör: python3 -m tests.test_coverage
"""
from __future__ import annotations

from engine.admin import ADMIN_LEVELS, MUNICIPAL_SEED, POSTAL_REGISTERS
from engine.markets import MARKETS
from engine.plan import PLAN_DATA
from engine.workforce import OCCUPATIONS
from engine.scan import _REVENUE_PER_PERSON_TKR, _STARTUP_TKR
from engine.signals import CATALOG
from engine.verticals import VERTICALS


def test_every_vertical_is_complete_across_all_tables():
    missing = {}
    for vid in VERTICALS:
        gaps = []
        if vid not in _REVENUE_PER_PERSON_TKR:
            gaps.append("scan._REVENUE_PER_PERSON_TKR")
        if vid not in _STARTUP_TKR:
            gaps.append("scan._STARTUP_TKR")
        if vid not in PLAN_DATA:
            gaps.append("plan.PLAN_DATA")
        if gaps:
            missing[vid] = gaps
    assert not missing, f"halvlagda branscher: {missing}"


def test_no_orphan_rows_in_the_side_tables():
    """Rader utan bransch är lika illa: de kan aldrig nås."""
    for name, table in (("_REVENUE_PER_PERSON_TKR", _REVENUE_PER_PERSON_TKR),
                        ("_STARTUP_TKR", _STARTUP_TKR),
                        ("PLAN_DATA", PLAN_DATA)):
        orphans = set(table) - set(VERTICALS)
        assert not orphans, f"{name} har rader utan VerticalProfile: {orphans}"


def test_vertical_weights_and_signals_are_valid():
    for vid, v in VERTICALS.items():
        total = sum(f.weight for f in v.factors)
        assert abs(total - 1.0) < 1e-6, f"{vid}: vikterna summerar till {total}"
        assert v.label_en, vid
        for f in v.factors:
            sw = sum(w for _, w in f.signals)
            assert abs(sw - 1.0) < 1e-6, f"{vid}.{f.id}: signalvikter {sw}"
            for sid, _ in f.signals:
                assert sid in CATALOG, f"{vid}.{f.id}: okänd signal {sid}"


def test_plan_rows_are_sane():
    for vid, spec in PLAN_DATA.items():
        assert spec.m2[0] < spec.m2[1], vid
        assert spec.utrustning_tkr[0] <= spec.utrustning_tkr[1], vid
        assert 0 < spec.marginal[0] <= spec.marginal[1] < 1, vid
        assert spec.leverantorer_en, vid
        # yrken får vara tomt (alla branscher har inte ett yrke i katalogen),
        # men det som ANGES måste finnas – annars pekar planens rekryterings-
        # läge på ett yrke Workforce-motorn inte känner till.
        for occ in spec.yrken:
            assert occ in OCCUPATIONS, f"{vid}: okänt yrke {occ}"


def test_startup_and_revenue_rows_are_sane():
    for vid, band in _STARTUP_TKR.items():
        assert band[0] < band[1], f"{vid}: startkapitalintervall bakvänt"
    for vid, rev in _REVENUE_PER_PERSON_TKR.items():
        assert rev > 0, vid


def test_every_market_has_regions_and_a_bbox():
    for mid, m in MARKETS.items():
        assert m.regions, f"{mid}: marknad utan regioner"
        assert len(m.bbox) == 4, mid
        assert m.currency and m.label_en, mid


def test_admin_registers_are_consistent():
    for c, d in ADMIN_LEVELS.items():
        assert d["units"] and d["level_en"], c
        assert d["sub_official_total"] > 0, c
        codes = [u[0] for u in d["units"]]
        assert len(codes) == len(set(codes)), f"{c}: dubbletter i nivå 1"
    for c, units in MUNICIPAL_SEED.items():
        assert c in ADMIN_LEVELS, f"seed för okänt land: {c}"
        parents = {u[2] for u in units}
        known = {u[0] for u in ADMIN_LEVELS[c]["units"]}
        assert parents <= known, f"{c}: seed pekar på okänd nivå-1: {parents-known}"
        assert len(units) <= ADMIN_LEVELS[c]["sub_official_total"], c
        codes = [u[0] for u in units]
        assert len(codes) == len(set(codes)), f"{c}: dubbletter i seed"


def test_postal_registers_point_at_a_real_country():
    for c, reg in POSTAL_REGISTERS.items():
        assert c in ADMIN_LEVELS, f"postregister för okänt land: {c}"
        assert reg["register"] and reg["format"], c
        assert reg["official_total"] > 0, c


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
