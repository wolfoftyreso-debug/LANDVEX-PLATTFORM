"""Tester för den direkta quiXzoom-klienten (:3209). Kör utan nätverk:
python3 -m tests.test_quixzoom_direct"""
from __future__ import annotations

from engine.datasources.adapters import QuixzoomSource
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.datasources.quixzoom_direct import DirectQuixzoomClient
from engine.models import Location

_LOC = Location(59.33, 18.06, address="Stockholm")

# Mission-shape enligt verklig modell: location.lng.
_MISSIONS = ('{"missions": ['
             '{"id": "m1", "location": {"lat": 59.331, "lng": 18.061}},'
             '{"id": "m2", "location": {"lat": 59.34, "lng": 18.07}},'
             '{"id": "far", "location": {"lat": 40.0, "lng": -74.0}}]}')


def _client(fixture: str, key: str = "") -> DirectQuixzoomClient:
    import os
    os.environ.pop("LANDVEX_QUIXZOOM_KEY", None)
    c = DirectQuixzoomClient(base_url="http://127.0.0.1:3209",
                             transport=lambda url, t, h: fixture)
    c.key = key
    return c


def test_not_connected():
    c = DirectQuixzoomClient(base_url="")
    assert not c.connected


def test_auth_header_bearer_default():
    c = _client(_MISSIONS, key="abc")
    assert c.auth_headers() == {"Authorization": "Bearer abc"}


def test_auth_header_custom():
    c = _client(_MISSIONS, key="abc")
    c.auth_header = "X-Api-Key"
    assert c.auth_headers() == {"X-Api-Key": "abc"}


def test_missions_parsed():
    c = _client(_MISSIONS)
    data = c.quixzoom_missions(59.33, 18.06, radius_km=10)
    assert isinstance(data["missions"], list) and len(data["missions"]) == 3


def test_source_uses_direct_client_and_filters_by_radius():
    # Två missions inom 10 km, en i New York → density = 2.
    src = QuixzoomSource(client=_client(_MISSIONS))
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "bygg", ["field_observation_density"])
    assert values["field_observation_density"].source == "quixzoom"
    assert values["field_observation_density"].value == 2.0


def test_source_pauses_on_error():
    # field_observation_density är quiXzoom-unik – mock syntetiserar den inte.
    # Vid fel pausar källan och signalen saknas ärligt (aldrig påhittad).
    def boom(url, t, h):
        raise RuntimeError("401")
    c = DirectQuixzoomClient(base_url="http://x", transport=boom)
    src = QuixzoomSource(client=c)
    res = Resolver([src, MockSource()])
    values, _ = res.resolve(_LOC, "bygg", ["field_observation_density"])
    assert "field_observation_density" not in values


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
