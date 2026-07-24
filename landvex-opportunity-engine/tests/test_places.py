"""Tester för places/konkurrens-adaptern. Kör utan pytest/nätverk:
python3 -m tests.test_places"""
from __future__ import annotations

from engine.datasources.adapters import PlacesSource
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.datasources.places import PlacesClient
from engine.models import Location

_LOC = Location(59.33, 18.06, address="Stockholm")

_OBJ = ('{"competition_pressure": 6.5, "provider_gap": 1.3, '
        '"competitors": [{"name": "A"}, {"name": "B"}]}')
_LIST = '[{"name": "A"}, {"name": "B"}, {"name": "C"}]'


def _client(fixture: str) -> PlacesClient:
    return PlacesClient(base_url="https://places.example/api",
                        transport=lambda url, t: fixture)


def test_not_connected_is_empty():
    c = PlacesClient(base_url="")
    assert not c.connected
    assert c.fetch_places(59.3, 18.0, "frisor") == ({}, [])
    assert c.status()["status"] == "ej_ansluten"


def test_object_feed():
    c = _client(_OBJ)
    sig, comp = c.fetch_places(59.33, 18.06, "frisor")
    assert sig == {"competition_pressure": 6.5, "provider_gap": 1.3}
    assert len(comp) == 2


def test_list_feed_derives_pressure():
    c = _client(_LIST)
    sig, comp = c.fetch_places(59.33, 18.06, "frisor")
    assert sig == {"competition_pressure": 3.0}     # count, no fabricated gap
    assert "provider_gap" not in sig
    assert len(comp) == 3


def test_source_in_resolver_with_competitors():
    src = PlacesSource(client=_client(_OBJ))
    res = Resolver([src, MockSource()])
    values, extras = res.resolve(_LOC, "frisor",
                                 ["competition_pressure", "provider_gap"])
    assert values["competition_pressure"].source == "places"
    assert values["competition_pressure"].value == 6.5
    assert values["provider_gap"].source == "places"
    assert extras.get("competitors")


def test_source_pauses_on_error_falls_to_mock():
    def boom(url, t):
        raise RuntimeError("down")
    src = PlacesSource(client=PlacesClient(base_url="https://x", transport=boom))
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "frisor", ["competition_pressure"])
    assert values["competition_pressure"].source == "mock"


def test_not_wired_default_stays_mock():
    src = PlacesSource(client=PlacesClient(base_url=""))
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "frisor", ["competition_pressure"])
    assert values["competition_pressure"].source == "mock"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
