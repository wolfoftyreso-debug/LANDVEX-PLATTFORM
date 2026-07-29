"""Tester för persistenslagret. Körs utan pytest:  python3 -m tests.test_storage

SqliteStore är referensimplementationen (in-memory här). PostgresStore
delar gränssnitt och verifieras separat mot riktig databas via
PostgresStore.selftest() vid driftsättning.
"""
from __future__ import annotations

import os
import tempfile

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
    rid = store.save_report(_report_dict(), created_at=1000.0, tenant='t1')
    doc = store.get_report(rid, tenant='t1')
    assert doc["report_id"] == rid
    assert doc["created_at"] == 1000.0
    assert doc["vertical_id"] == "frisor"
    assert doc["location"]["address"] == "Hornsgatan 52"
    assert store.get_report('finnsinte', tenant='t1') is None


def test_report_listing_order_and_limit():
    store = SqliteStore(":memory:")
    for i in range(5):
        store.save_report(_report_dict(score=50.0 + i), created_at=1000.0 + i,
                          tenant='t1')
    rows = store.list_reports(limit=3, tenant='t1')
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




# ── Tenant-isolering ─────────────────────────────────────────────────────
def test_two_tenants_never_see_each_others_data():
    """Bevisat läckage före rättelsen: två API-nycklar mot en körande
    server, och Konkurrent AB kunde lista OCH läsa Tyresö kommuns profil.
    Bara usage_meter hade en tenant-kolumn; auth läste tenant ur nyckeln,
    loggade den och kastade den innan lagret rördes."""
    store = SqliteStore(":memory:")
    a = store.save_profile({"name": "HEMLIG plan", "vertical_id": "frisor"},
                           created_at=1000.0, tenant="kommunen")
    b = store.save_profile({"name": "konkurrentens", "vertical_id": "frisor"},
                           created_at=1001.0, tenant="konkurrent")

    mina = store.list_profiles(tenant="kommunen")
    assert [r["profile_id"] for r in mina] == [a]
    andras = store.list_profiles(tenant="konkurrent")
    assert [r["profile_id"] for r in andras] == [b]

    # Även med rätt id i handen: fel tenant ⇒ inget dokument.
    assert store.get_profile(a, tenant="konkurrent") is None
    assert store.get_profile(a, tenant="kommunen") is not None


def test_reports_are_isolated_too():
    store = SqliteStore(":memory:")
    rid = store.save_report(_report_dict(), created_at=1000.0,
                            tenant="kommunen")
    assert store.get_report(rid, tenant="konkurrent") is None
    assert store.list_reports(tenant="konkurrent") == []
    assert store.get_report(rid, tenant="kommunen") is not None


def test_tenant_is_required_not_optional():
    """Ett argument man KAN glömma är en läcka som väntar. Det här testet
    faller om någon ger tenant ett default-värde."""
    import inspect
    for name in ("save_report", "get_report", "list_reports",
                 "save_profile", "get_profile", "list_profiles"):
        sig = inspect.signature(getattr(SqliteStore, name))
        p = sig.parameters.get("tenant")
        assert p is not None, f"{name} tog aldrig emot tenant"
        assert p.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert p.default is inspect.Parameter.empty, \
            f"{name} har default på tenant — då kan den glömmas"


def test_the_postgres_store_isolates_on_the_same_contract():
    """Ett lager som isolerar i SQLite men inte i produktion vore värre
    än inget: det ser säkert ut precis där ingen kund finns."""
    import inspect

    from engine.storage.postgres import PostgresStore
    for name in ("save_report", "get_report", "list_reports",
                 "save_profile", "get_profile", "list_profiles"):
        p = inspect.signature(getattr(PostgresStore, name)).parameters
        assert "tenant" in p, f"PostgresStore.{name} saknar tenant"
        assert p["tenant"].default is inspect.Parameter.empty, name
    src = inspect.getsource(PostgresStore)
    for frag in ("WHERE id = %s AND tenant = %s", "WHERE tenant = %s"):
        assert frag in src, f"postgres filtrerar inte: {frag!r} saknas"


def test_legacy_rows_are_invisible_rather_than_guessed():
    """Rader från före migrationen får tenant ''. Att gissa vem de tillhör
    vore att gissa fel för någon. Fail closed."""
    store = SqliteStore(":memory:")
    store._conn.execute(
        "INSERT INTO profiles (id, created_at, name, vertical_id, payload, "
        "tenant) VALUES ('gammal', 1.0, 'förmigrering', 'frisor', '{}', '')")
    store._conn.commit()
    assert store.list_profiles(tenant="kommunen") == []
    assert store.get_profile("gammal", tenant="kommunen") is None


def test_inspections_survive_a_restart_and_stay_per_tenant():
    """Ett efterlevnadsregister som bara finns i processminnet är inget
    register: det som ska visas för en nämnd ett år senare måste finnas
    kvar efter en omstart."""
    from engine import inspections as I

    path = os.path.join(tempfile.mkdtemp(), "kontroller.db")
    store = SqliteStore(path)
    I.set_store(store)
    try:
        I.save_asset(I.asset("fp1", "flagpole", lat=59.3, lon=18.0,
                             tenant="flaggab"))
        I.save_asset(I.asset("boj1", "lifebuoy", lat=59.4, lon=18.1,
                             tenant="kommunen"))
        I.save_routine(I.routine("vecka", "Weekly flag check", "flagpole", 7,
                                 checks=["present"], tenant="flaggab"))
        I.save_check(I.record("fp1", "vecka", "pass", mission_id="qz-1",
                              performed_at="2026-07-20", tenant="flaggab"))
        store.close()

        igen = SqliteStore(path)          # omstart: nytt lager, samma fil
        I.set_store(igen)
        assert [a["id"] for a in I.all_assets("flaggab")] == ["fp1"]
        assert [a["id"] for a in I.all_assets("kommunen")] == ["boj1"]
        assert I.all_routines("kommunen") == []
        assert [c["asset_id"] for c in I.all_checks("flaggab")] == ["fp1"]
        assert I.all_checks("kommunen") == []
        igen.close()
    finally:
        I.set_store(None)
        I.reset()


def test_no_stored_check_carries_the_photo_itself():
    """En fältbild på en badplats innehåller människor. Landvex lagrar
    domen och referensen; bilden stannar hos quiXzoom, som har samtycket.
    Kolumnen finns inte, och den ska inte kunna smyga in."""
    store = SqliteStore(":memory:")
    kolumner = {r[1] for r in
                store._conn.execute("PRAGMA table_info(checks)").fetchall()}
    for förbjuden in ("image", "photo", "media", "image_data", "blob",
                      "thumbnail"):
        assert förbjuden not in kolumner, förbjuden
    store.close()


def test_both_stores_offer_the_inspection_contract():
    """Samma sak som för rapporter: ett lager som bär registret lokalt men
    inte i produktion ser säkert ut precis där ingen kund finns."""
    import inspect

    from engine.storage.postgres import PostgresStore
    for klass in (SqliteStore, PostgresStore):
        for name in ("save_asset", "all_assets", "save_routine",
                     "all_routines", "save_check", "all_checks"):
            assert callable(getattr(klass, name, None)), \
                f"{klass.__name__}.{name} saknas"
    src = inspect.getsource(PostgresStore)
    assert "ON CONFLICT (tenant, id)" in src, \
        "postgres skriver över fel kunds objekt vid id-krock"


class _FejkCursor:
    """Loggar exekverad SQL och svarar på versionsfrågan — mer behövs
    inte för att bevisa kedjelogiken utan psycopg."""

    def __init__(self, versioner: list[int], logg: list):
        self._versioner, self._logg = versioner, logg
        self._svar = None

    def execute(self, sql, params=None):
        self._logg.append((sql.strip(), params))
        if "SELECT MAX(version)" in sql:
            self._svar = (max(self._versioner) if self._versioner else None,)
        elif "INSERT INTO schema_meta" in sql:
            self._versioner.append(params[0])

    def fetchone(self):
        return self._svar

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FejkConn:
    def __init__(self, versioner: list[int] | None = None):
        self.versioner = list(versioner or [])
        self.logg: list = []

    def cursor(self):
        return _FejkCursor(self.versioner, self.logg)


def test_a_fresh_postgres_schema_is_stamped_at_the_sqlite_baseline():
    """Mätt före fixen: postgres hade INGEN schema_meta, ingen _migrate,
    ingen schema_version — bara platt CREATE TABLE IF NOT EXISTS vid
    varje start. Det lägger aldrig en kolumn på en befintlig tabell, så
    nästa schemaändring hade tyst uteblivit i produktion medan sqlite
    fick den via sin kedja. Färskt schema ska stämplas på sqlite-kedjans
    max, så att de två liggarna talar samma nummer."""
    from engine.storage.postgres import _baseline_version, _migrate
    from engine.storage.sqlite import _MIGRATIONS as SQ

    conn = _FejkConn()
    _migrate(conn)
    assert conn.versioner == [max(v for v, _ in SQ)]
    assert _baseline_version() == max(v for v, _ in SQ)
    # sqlite-referensen ska rapportera samma tal ur sin riktiga databas
    s = SqliteStore(":memory:")
    assert s.schema_version() == _baseline_version()
    s.close()


def test_pending_postgres_migrations_run_in_order_and_stamp_each_step():
    from engine.storage import postgres as P

    orig = P._MIGRATIONS
    P._MIGRATIONS = [(11, "ALTER TABLE reports ADD COLUMN a TEXT"),
                     (12, "ALTER TABLE reports ADD COLUMN b TEXT")]
    try:
        conn = _FejkConn(versioner=[10])
        P._migrate(conn)
        assert conn.versioner == [10, 11, 12]
        ddl = [sql for sql, _ in conn.logg if sql.startswith("ALTER")]
        assert ddl == ["ALTER TABLE reports ADD COLUMN a TEXT",
                       "ALTER TABLE reports ADD COLUMN b TEXT"]
        # redan ikapp → ingenting körs igen
        conn2 = _FejkConn(versioner=[12])
        P._migrate(conn2)
        assert not [s for s, _ in conn2.logg if s.startswith("ALTER")]
    finally:
        P._MIGRATIONS = orig


def test_the_two_stores_describe_the_same_tables_and_columns():
    """Drifttestet revisionen saknade: sqlite är den testade referensen,
    postgres är vad produktionen kör, och INGET jämförde dem. Sqlite
    läses ur en riktig databas (PRAGMA), postgres ur DDL-texten —
    kolumnNAMN jämförs, aldrig typer (REAL↔DOUBLE PRECISION är samma
    beslut i två dialekter). Undantagen är datarader med skäl.

    Implementationen bor i engine/selfaudit och konsumeras av BÅDE det
    här testet och /v1/integrity/audit — en jämförare, två läsare. Att
    den biter är bevisat i tests/test_selfaudit och via mutation
    (news_items bortdöpt → tabellen namnges)."""
    from engine.selfaudit import SCHEMA_EXCEPTIONS, store_schema_drift

    assert store_schema_drift() == []
    for tabell, u in SCHEMA_EXCEPTIONS.items():
        assert u.get("why_en"), f"{tabell}: undantag utan skäl"


def test_the_selftest_honours_the_tenant_contract_it_runs_under():
    """Mätt före fixen: selftest() anropade save_report/get_report UTAN
    tenant= — TypeError vid första raden, så driftsättningsverifieringen
    har ALDRIG kunnat köras mot en riktig databas. Ett självtest som
    inte kan starta ser i en runbook ut som ett självtest som inte
    behövdes. Källskanning i stället för körning: psycopg finns inte
    här, och ett test som kräver produktionsdriver för att upptäcka en
    TypeError hade aldrig körts det heller."""
    import inspect
    import re

    from engine.storage.postgres import PostgresStore

    src = inspect.getsource(PostgresStore.selftest)
    anrop = re.findall(r"self\.(?:save_report|get_report)\((?:[^()]|\([^)]*\))*\)",
                       src, re.DOTALL)
    assert len(anrop) >= 2, "selftest anropar inte längre rapportvägen"
    for a in anrop:
        assert "tenant=" in a, a


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
