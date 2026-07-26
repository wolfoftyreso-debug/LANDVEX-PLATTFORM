"""Tester för anslutnings-cockpit. Kör: python3 -m tests.test_sources"""
from __future__ import annotations

import os
import time

from api.sources import sources_status
from engine.datasources.base import DataSource, Resolver
from engine.models import Location, SignalValue


def test_lists_all_adapters():
    s = sources_status()
    ids = {x["id"] for x in s["sources"]}
    assert {"scb", "kolada", "svk", "permits", "places", "aamos"} <= ids
    assert s["total"] == len(s["sources"])


def test_env_var_flips_state_to_live():
    os.environ.pop("LANDVEX_KOLADA_URL", None)
    before = next(x for x in sources_status()["sources"] if x["id"] == "kolada")
    assert before["state"] == "mock"
    os.environ["LANDVEX_KOLADA_URL"] = "https://api.kolada.se/v2"
    try:
        after = next(x for x in sources_status()["sources"] if x["id"] == "kolada")
        assert after["state"] == "live"
        assert "LANDVEX_KOLADA_URL" in after["activate_with"]
    finally:
        os.environ.pop("LANDVEX_KOLADA_URL", None)


def test_each_source_names_its_env_and_official_source():
    for x in sources_status()["sources"]:
        assert x["activate_with"] and x["official_source"] and x["provides"]



# ── Tidsbudget per anrop ─────────────────────────────────────────────────
class _SlowSource(DataSource):
    name = "slow"

    def __init__(self, cost_s: float = 0.4):
        self.cost_s = cost_s
        self.calls = 0

    def fetch(self, location, vertical_id, signal_ids):
        self.calls += 1
        time.sleep(self.cost_s)
        return {}, {}


class _MockLike(DataSource):
    name = "mock"

    def fetch(self, location, vertical_id, signal_ids):
        return ({s: SignalValue(s, 1.0, source="mock", quality=0.1)
                 for s in signal_ids}, {})


_LOC = Location(lat=59.3, lon=18.1)


def test_one_answer_does_not_pay_every_slow_source_in_the_chain():
    """Sex tröga källor à 0,4 s gav 2,4 s väntan. Med sex sekunder per
    källa i skarpt läge blev /v1/report tretton sekunder mot en budget på
    700 ms — och svaret blev ändå mock till slut."""
    slow = [_SlowSource(0.4) for _ in range(6)]
    r = Resolver([*slow, _MockLike()], budget_ms=600)
    t0 = time.perf_counter()
    values, extras = r.resolve(_LOC, "frisor", ["a", "b"])
    spent = (time.perf_counter() - t0) * 1000.0
    assert spent < 1600, f"budgeten höll inte: {spent:.0f} ms"
    assert sum(s.calls for s in slow) < 6, "alla tröga källor frågades ändå"
    assert values, "svaret blev tomt i stället för ärligt märkt mock"


def test_skipping_a_source_is_reported_never_silent():
    """Ett tunnare svar utan förklaring är samma fel som tyst nedgradering."""
    r = Resolver([_SlowSource(0.4), _SlowSource(0.4), _SlowSource(0.4),
                  _MockLike()], budget_ms=300)
    _, extras = r.resolve(_LOC, "frisor", ["a"])
    note = extras.get("resolver")
    assert note, "källor hoppades över utan att det syns i svaret"
    assert note["skipped_sources"]
    assert note["budget_ms"] == 300 and note["spent_ms"] > 0
    assert "mock" in note["why_en"] and "data_coverage" in note["why_en"]


def test_mock_is_never_skipped_so_an_answer_is_never_empty():
    """Taket får göra svaret tunnare, aldrig tomt."""
    r = Resolver([_SlowSource(0.5), _MockLike()], budget_ms=1)
    values, extras = r.resolve(_LOC, "frisor", ["a", "b"])
    assert set(values) == {"a", "b"}
    assert all(v.source == "mock" for v in values.values())


def test_no_budget_means_no_ceiling_for_batch_work():
    """Ett nattjobb har ingen som väntar; då ska taket gå att stänga av."""
    slow = [_SlowSource(0.1) for _ in range(4)]
    r = Resolver([*slow, _MockLike()], budget_ms=0)
    r.resolve(_LOC, "frisor", ["a"])
    assert all(s.calls == 1 for s in slow)
    assert "resolver" not in {}     # inget överhopp att redovisa


def test_a_fast_chain_is_never_reported_as_skipped():
    r = Resolver([_SlowSource(0.001), _MockLike()], budget_ms=1200)
    _, extras = r.resolve(_LOC, "frisor", ["a"])
    assert "resolver" not in extras


def test_a_source_timeout_is_shorter_than_the_endpoint_budget():
    """Sex sekunder per källa var längre än hela svarets budget."""
    from engine.datasources import permits, places, scb
    import inspect
    for mod, cls in ((scb, "ScbClient"), (permits, "PermitsClient"),
                     (places, "PlacesClient")):
        sig = inspect.signature(getattr(mod, cls).__init__)
        t = sig.parameters["timeout"].default
        assert t <= 3.0, f"{cls} väntar {t}s — längre än svaret får ta"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
