"""Kommissionsmodellen är intäkten. Revisionen fann att den saknade
dedikerade tester — nivåtabellen prövades via /v1/plans-strukturen men
ingenting låste själva beräkningen: en flyttad tiergräns hade ändrat
varje leads pris utan att något test rört sig.

Kör: python3 -m tests.test_commission
"""
from __future__ import annotations

from engine.commission import (QZ_TOKEN_USD_SCHABLON, TIERS,
                               commission_catalog, commission_for_lead,
                               commission_qz)


def test_the_tiers_cover_the_whole_score_axis_without_gaps():
    """Ett hål mellan nivåerna vore en score som inte kan prissättas —
    och den skulle tyst falla till understa nivån."""
    granser = sorted((lo, hi) for lo, hi, _ in TIERS)
    assert granser[0][0] == 0.0
    assert granser[-1][1] > 1.0          # toppen täcker score 1.0
    for (_lo1, hi1), (lo2, _hi2) in zip(granser, granser[1:], strict=False):
        assert hi1 == lo2, f"hål eller överlapp vid {hi1}/{lo2}"


def test_a_better_lead_never_costs_less():
    """Monotoni är hela poängen med graderingen: en högre opportunity-
    score får aldrig ge lägre kommission."""
    forra = -1.0
    for score in (0, 10, 49, 50, 79, 80, 95, 100):
        qz = commission_qz(score)
        assert qz >= forra, f"score {score} sänkte kommissionen"
        forra = qz


def test_both_score_scales_price_identically():
    """Motorerna ger 0–100, katalogen talar 0–1. Samma lead, samma pris
    — annars avgör anroparens enhet vad kunden betalar."""
    for s01, s100 in ((0.3, 30), (0.65, 65), (0.9, 90)):
        assert commission_qz(s01) == commission_qz(s100)


def test_the_lead_row_prices_from_the_same_table_the_catalog_shows():
    """Kunden ser katalogen, fakturan bygger på lead-raden. Skiljer de
    sig är prislistan en annons, inte ett kontrakt."""
    kat = commission_catalog()
    for niva in kat["nivaer"]:
        mitt = (niva["score_min"] + niva["score_max"]) / 2
        rad = commission_for_lead(mitt)
        assert rad["qz_token"] == niva["qz_token"], niva
        assert rad["usd_schablon"] == round(
            niva["qz_token"] * QZ_TOKEN_USD_SCHABLON, 4)
    assert kat["usd_schablon_per_qz"] == QZ_TOKEN_USD_SCHABLON
    # och schablonen SÄGER att den är en schablon quiXzoom styr
    assert "quiXzoom sets the rate" in commission_for_lead(50)["notis_en"]


def test_out_of_range_scores_clamp_rather_than_crash():
    assert commission_qz(-5) == TIERS[-1][2]
    assert commission_qz(250) == TIERS[0][2]


def test_licensing_sells_exactly_this_table():
    """pro-planens kommissionsblock i /v1/plans ÄR den här katalogen —
    en kopia i licensing hade kunnat drifta från motorn som fakturerar."""
    from api.licensing import PLANS

    assert PLANS["pro"]["kommission"] == commission_catalog()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
