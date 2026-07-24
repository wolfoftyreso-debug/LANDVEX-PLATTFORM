"""Tester för permits/detaljplan-adaptern. Kör utan pytest/nätverk:
python3 -m tests.test_permits"""
from __future__ import annotations

from engine.datasources.adapters import PermitsSource
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.datasources.permits import PermitsClient
from engine.models import Location
from engine.scoring import analyze

_LOC = Location(59.33, 18.06, address="Stockholm")

_OBJ = '{"building_permits": 42, "detail_plans": 7, "development_m2": 120}'
_LIST = '[{"area_m2": 5000}, {"area_m2": 3000}, {}]'


def _client(fixture: str) -> PermitsClient:
    return PermitsClient(base_url="https://permits.example/api",
                         transport=lambda url, t: fixture)


def test_not_connected_is_empty():
    c = PermitsClient(base_url="")
    assert not c.connected
    assert c.fetch_permits(59.3, 18.0) == {}
    assert c.status()["status"] == "ej_ansluten"


def test_object_feed():
    c = _client(_OBJ)
    d = c.fetch_permits(59.33, 18.06)
    assert d == {"building_permits": 42.0, "detail_plans": 7.0,
                 "development_m2": 120.0}


def test_list_feed_counts_and_area():
    c = _client(_LIST)
    d = c.fetch_permits(59.33, 18.06)
    assert d["building_permits"] == 3.0          # counted
    assert d["development_m2"] == 8.0             # (5000+3000)/1000


def test_source_provides_real_signals_in_resolver():
    src = PermitsSource(client=_client(_OBJ))
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "bygg",
                            ["building_permits", "detail_plans", "population_total"])
    assert values["building_permits"].source == "permits"
    assert values["building_permits"].value == 42.0
    assert values["detail_plans"].source == "permits"
    # A signal the permits feed doesn't cover still comes from mock.
    assert values["population_total"].source == "mock"


def test_source_pauses_on_error_falls_to_mock():
    def boom(url, t):
        raise RuntimeError("down")
    src = PermitsSource(client=PermitsClient(base_url="https://x", transport=boom))
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "bygg", ["building_permits"])
    assert values["building_permits"].source == "mock"   # honest fallback


def test_not_wired_default_stays_mock():
    # Default PermitsSource (no env URL) is not connected → mock coverage.
    src = PermitsSource(client=PermitsClient(base_url=""))
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "bygg", ["building_permits"])
    assert values["building_permits"].source == "mock"


def test_coverage_rises_with_real_permits():
    src = PermitsSource(client=_client(_OBJ))
    rep = analyze(_LOC, "bygg", resolver=Resolver([src, MockSource()]))
    # At least the permit signals are real now → coverage > 0.
    assert rep.data_coverage > 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
