"""Bostadsmarknad: priset bara riktigt, standarden aldrig i valuta.

Bevakar: priset är None/measured=False tills LANDVEX_HOUSING_PRICE_URL
svarar (aldrig ett härlett belopp), standarden är coverage-gated precis
som land.py och bär ingen valuta, kvoten mellan dem vägrar om endera
sidan saknas och påstår varken en värdering eller en prognos, och
planerna säger "inte ansluten" i stället för "inget planerat" när
källan saknas.

Kör: python3 -m tests.test_housing_market
"""
from __future__ import annotations

import dataclasses
import json

from engine import housing_market as HM


def _mock_only():
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource
    return Resolver([MockSource()])


def _akta(*signaler: str):
    class R:
        def __init__(self):
            self.inner = _mock_only()

        def resolve(self, loc, purpose, signals):
            values, meta = self.inner.resolve(loc, purpose, signals)
            for sid in signaler:
                if sid in values:
                    values[sid] = dataclasses.replace(values[sid], source="scb")
            return values, meta
    return R()


def _fake_price_client(price=45000.0, currency="SEK", year=2025,
                       source="Lantmateriet", n=120):
    def transport(url, timeout):
        return json.dumps({"price_per_sqm": price, "currency": currency,
                           "year": year, "source": source,
                           "sample_size": n})
    return HM.HousingPriceClient(base_url="https://example.test",
                                 transport=transport)


def _fake_plan_client(plans):
    def transport(url, timeout):
        return json.dumps({"plans": plans})
    return HM.MasterPlanClient(base_url="https://example.test",
                               transport=transport)


# ── Priset ───────────────────────────────────────────────────────────────
def test_price_is_unmeasured_until_the_register_is_connected():
    p = HM.price("se", "0180", client=HM.HousingPriceClient(base_url=""))
    assert p["measured"] is False
    assert p["price_per_sqm"] is None
    assert "not connected" in p["why_en"] or "LANDVEX_HOUSING_PRICE_URL" in p["why_en"]


def test_price_is_measured_only_from_a_real_client():
    p = HM.price("se", "0180", client=_fake_price_client())
    assert p["measured"] is True
    assert p["price_per_sqm"] == 45000.0
    assert p["source"] == "Lantmateriet" and p["year"] == 2025
    assert "Lantmateriet" in p["why_en"]


def test_a_malformed_answer_is_treated_as_not_connected_not_invented():
    def bad_transport(url, timeout):
        return "not json at all"
    c = HM.HousingPriceClient(base_url="https://example.test",
                              transport=bad_transport)
    p = HM.price("se", "0180", client=c)
    assert p["measured"] is False and p["price_per_sqm"] is None


# ── Standarden ───────────────────────────────────────────────────────────
def test_below_coverage_the_standard_refuses_like_land_py():
    s = HM.standard("0180", market="se", resolver=_mock_only())
    assert s["status"] == "insufficient"
    assert s["standard"] is None and s["band"] is None
    assert s["gate"]["required"] == HM.MIN_COVERAGE


def test_enough_real_data_gives_a_standard_with_its_band():
    s = HM.standard("0180", market="se",
                    resolver=_akta("avg_building_age", "renovation_index",
                                   "housing_affordability"))
    assert s["status"] == "computed"
    assert 0 <= s["standard"] <= 100
    assert s["band"] in {b for _, b, _ in HM.BANDS}


def test_no_family_carries_a_currency_or_a_per_sqm_price():
    """Samma fältsvep som land.py: standardens del av modulen får aldrig
    se ut som ett belopp."""
    alla = [HM.standard("0180", market="se", resolver=_mock_only()),
           HM.standard("0180", market="se",
                       resolver=_akta("avg_building_age", "renovation_index",
                                      "housing_affordability")),
           HM.catalog()]
    FORBJUDNA = ("sek", "eur", "usd", "currency", "valuation",
                "value_estimate", "market_value")

    def svep(x, vag=""):
        if isinstance(x, dict):
            for k, v in x.items():
                assert not any(f in str(k).lower() for f in FORBJUDNA), \
                    f"nyckel {vag}.{k} antyder ett belopp"
                svep(v, f"{vag}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                svep(v, f"{vag}[{i}]")
    for svar in alla:
        svep(svar)


# ── Kvoten ───────────────────────────────────────────────────────────────
def test_the_ratio_refuses_when_the_price_is_not_connected():
    r = HM.price_vs_standard(
        "se", "0180", client=HM.HousingPriceClient(base_url=""),
        resolver=_akta("avg_building_age", "renovation_index",
                      "housing_affordability"))
    assert r["status"] == "refused"
    assert r["ratio"] is None
    assert "price" in r["refusal_en"].lower()


def test_the_ratio_refuses_when_the_standard_is_too_thin():
    r = HM.price_vs_standard("se", "0180", client=_fake_price_client(),
                             resolver=_mock_only())
    assert r["status"] == "refused"
    assert r["ratio"] is None
    assert "standard" in r["refusal_en"].lower()


def test_the_ratio_computes_and_disclaims_it_is_not_a_forecast():
    r = HM.price_vs_standard(
        "se", "0180", client=_fake_price_client(),
        resolver=_akta("avg_building_age", "renovation_index",
                      "housing_affordability"))
    assert r["status"] == "computed"
    assert r["ratio"] == round(
        r["price"]["price_per_sqm"] / r["standard"]["standard"], 2)
    assert "not a" in r["cannot_en"].lower()
    assert "forecast" in r["cannot_en"].lower()
    assert "valuation" in r["cannot_en"].lower()


# ── Planerna ─────────────────────────────────────────────────────────────
def test_master_plans_says_not_connected_never_nothing_planned():
    mp = HM.master_plans("se", "0180")
    assert mp["connected"] is False
    assert mp["plans"] == []
    assert "not connected" in mp["why_en"]


def test_master_plans_returns_the_real_documents_when_connected():
    plans = [{"title": "Comprehensive plan 2040", "kind": "master_plan",
             "adopted_year": 2022, "horizon_year": 2040,
             "status": "adopted", "summary_en": "Growth corridor along rail."}]
    mp = HM.master_plans("se", "0180", client=_fake_plan_client(plans))
    assert mp["connected"] is True
    assert mp["plans"] == plans


def test_price_and_master_plan_urls_are_independent_env_vars():
    """De två klienterna får aldrig dela variabel — detaljplaner
    (LANDVEX_PERMITS_URL) och översiktsplaner är olika dokument från
    olika skeden."""
    import os
    assert HM.HousingPriceClient().base_url == os.environ.get(
        "LANDVEX_HOUSING_PRICE_URL", "")
    assert HM.MasterPlanClient().base_url == os.environ.get(
        "LANDVEX_MASTER_PLAN_URL", "")


def test_it_belongs_to_the_establishment_package():
    from api.licensing import required_capability
    assert required_capability("/v1/housing-market") == "opportunity"
    assert required_capability("/v1/housing-market/price") == "opportunity"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
