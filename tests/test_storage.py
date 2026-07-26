"""Tester för persistenslagret. Körs utan pytest:  python3 -m tests.test_storage

SqliteStore är referensimplementationen (in-memory här). PostgresStore
delar gränssnitt och verifieras separat mot riktig databas via
PostgresStore.selftest() vid driftsättning.
"""
from __future__ import annotations


from engine.datasources.adapters import ScbSource
from engine.datasources.base import DataSource, Resolver
from engine.datasources.cache import DEFAULT_TTLS, CachedSource, loc_key
from engine.datasources.mock import MockSource
from engine.models import Location, SignalValue
from engine.scoring import analyze
from engine.storage.sqlite import SqliteStore

from tests.test_scb import fake_transport
from engine.datasources import scb

STHLM = Location(59.3145, 18.0705, "Hornsgatan 52")


def _report_dict(score: float = 66.0, address: str = "Hornsgatan 52") -> dict:
    return analyze(Location(59.3145, 18.0705, address), "frisor").to_dict() | {
        "opportunity_score": score}


class CountingSource(DataSource):
    """Låtsaskälla som räknar anrop – för cachetester."""
    name = "scb"   # källnamnet styr TTL-val och source-märkning

    def __init__(self):
        self.calls = 0

    def fetch(self, location, vertical_id, signal_ids):
        self.calls += 1
        out = {}
        if "income_index" in signal_ids:
            out["income_index"] = SignalValue("income_index", 127.3,
                                              source=self.name, quality=0.7)
        return out, ({"scb": {"kommun": "0180"}} if out else {})


# ── Rapporter ────────────────────────────────────────────────────────

def test_report_roundtrip():
    store = SqliteStore(":memory:")
    rid = store.save_report(_report_dict(), created_at=1000.0)
    doc = store.get_report(rid)
    assert doc["report_id"] == rid
    assert doc["created_at"] == 1000.0
    assert doc["vertical_id"] == "frisor"
    assert doc["location"]["address"] == "Hornsgatan 52"
    assert store.get_report("finnsinte") is None


def test_report_listing_order_and_limit():
    store = SqliteStore(":memory:")
    for i in range(5):
        store.save_report(_report_dict(score=50.0 + i), created_at=1000.0 + i)
    rows = store.list_reports(limit=3)
    assert len(rows) == 3
    assert [r["created_at"] for r in rows] == [1004.0, 1003.0, 1002.0]
    assert rows[0]["opportunity_score"] == 54.0
    assert set(rows[0]) == {"report_id", "created_at", "vertical_id", "lat",
                            "lon", "address", "opportunity_score",
                            "data_coverage"}


# ── Signalcache ──────────────────────────────────────────────────────

def test_signal_cache_roundtrip():
    store = SqliteStore(":memory:")
    store.put_cached_signals("scb", "k", {"income_index": (127.3, 0.7)}, 100.0)
    store.put_cached_signals("scb", "k", {"income_index": (130.0, 0.7)}, 200.0)
    assert store.get_cached_signals("scb", "k") == {
        "income_index": (130.0, 0.7, 200.0)}          # upsert, inte dubblett
    assert store.get_cached_signals("scb", "annan") == {}
    store.put_cached_extras("scb", "k", {"a": 1}, 100.0)
    assert store.get_cached_extras("scb", "k") == ({"a": 1}, 100.0)


def test_cached_source_avoids_second_fetch():
    store = SqliteStore(":memory:")
    inner = CountingSource()
    now = [1000.0]
    src = CachedSource(inner, store, clock=lambda: now[0])
    assert src.ttl_s == DEFAULT_TTLS["scb"]

    s1, e1 = src.fetch(STHLM, "frisor", ["income_index"])
    assert inner.calls == 1 and s1["income_index"].value == 127.3

    now[0] += 3600.0                                   # inom TTL
    s2, e2 = src.fetch(STHLM, "frisor", ["income_index"])
    assert inner.calls == 1                            # cacheträff
    assert s2["income_index"].value == 127.3
    assert s2["income_index"].source == "scb"
    assert e2 == {"scb": {"kommun": "0180"}}           # extras från cache


def test_cached_source_refetches_after_ttl():
    store = SqliteStore(":memory:")
    inner = CountingSource()
    now = [1000.0]
    src = CachedSource(inner, store, ttl_s=100.0, clock=lambda: now[0])
    src.fetch(STHLM, "frisor", ["income_index"])
    now[0] += 101.0                                    # TTL passerad
    src.fetch(STHLM, "frisor", ["income_index"])
    assert inner.calls == 2


def test_cached_source_key_includes_radius():
    assert loc_key(STHLM) != loc_key(Location(59.3145, 18.0705,
                                              radius_minutes=20))


def test_cached_scb_end_to_end():
    """Fullt flöde: Resolver [cachad SCB, mock] → analyze, två gånger."""
    store = SqliteStore(":memory:")
    calls = [0]

    def counting_transport(url, payload, timeout):
        calls[0] += 1
        return fake_transport(url, payload, timeout)

    scb_src = ScbSource(client=scb.ScbClient(transport=counting_transport))
    resolver = Resolver([CachedSource(scb_src, store), MockSource()])

    r1 = analyze(STHLM, "frisor", resolver=resolver)
    assert r1.data_coverage > 0.0
    transport_after_first = calls[0]
    assert transport_after_first > 0

    r2 = analyze(STHLM, "frisor", resolver=resolver)
    assert calls[0] == transport_after_first           # allt ur cachen
    assert r2.to_dict() == r1.to_dict()                # determinism


def test_persistent_monthly_quota_survives_restart():
    """Kvoten lagras i DB och minns förbrukningen efter omstart."""
    import os
    import tempfile
    from api.security import AuthError, MonthlyQuota
    db = os.path.join(tempfile.mkdtemp(), "quota.db")
    clock = lambda: 1_750_000_000.0
    store = SqliteStore(db)
    q = MonthlyQuota(clock=clock, store=store)
    n = 0
    try:
        for _ in range(10):
            q.check("acme", 3)
            n += 1
    except AuthError:
        pass
    assert n == 3                              # tak 3 håller
    store.close()
    # "Omstart": nytt lager mot samma fil minns räkningen.
    store2 = SqliteStore(db)
    q2 = MonthlyQuota(clock=clock, store=store2)
    blocked = False
    try:
        q2.check("acme", 3)
    except AuthError as e:
        blocked = True
        assert e.status == 429
    assert blocked                             # kvoten kvarstår
    q2.check("beta", 3)                        # annan tenant opåverkad
    store2.close()


def test_quota_bump_is_atomic_under_threads():
    import os
    import tempfile
    import threading
    from api.security import AuthError, MonthlyQuota
    db = os.path.join(tempfile.mkdtemp(), "q2.db")
    store = SqliteStore(db)
    q = MonthlyQuota(clock=lambda: 1_750_000_000.0, store=store)
    ok = {"n": 0}
    lock = threading.Lock()

    def burn():
        for _ in range(30):
            try:
                q.check("race", 50)
                with lock:
                    ok["n"] += 1
            except AuthError:
                return

    threads = [threading.Thread(target=burn) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert ok["n"] <= 50, f"kvotöverskott: {ok['n']} (tak 50)"
    store.close()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
