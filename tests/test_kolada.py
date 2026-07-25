"""Tester för Kolada-adaptern. Kör: python3 -m tests.test_kolada"""
from __future__ import annotations

from engine.datasources.kolada import KPI_IDS, KoladaClient

_FIX = ('{"values":[{"kpi":"N00914","period":2024,"values":['
        '{"gender":"K","value":84.1},{"gender":"M","value":80.2},'
        '{"gender":"T","value":82.2}]}]}')


def _client(fix=_FIX):
    return KoladaClient(base_url="https://api.kolada.se/v2",
                        transport=lambda u, t: fix)


def test_not_connected_without_url():
    assert KoladaClient(base_url="").connected is False
    assert KoladaClient(base_url="").fetch_kpi("life_expectancy") is None


def test_fetch_picks_total_gender():
    r = _client().fetch_kpi("life_expectancy", municipality="1480")
    assert r["value"] == 82.2 and r["year"] == 2024
    assert r["kolada_id"] == "N00914" and r["municipality"] == "1480"


def test_unknown_code_returns_none():
    assert _client().fetch_kpi("not_a_kpi") is None


def test_bad_payload_degrades():
    c = KoladaClient(base_url="https://x", transport=lambda u, t: "not json")
    assert c.fetch_kpi("life_expectancy") is None


def test_status_lists_catalog():
    s = _client().status()
    assert s["connected"] and "violent_crime_rate" in s["kpi_catalog"]
    assert set(KPI_IDS) == set(s["kpi_catalog"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
