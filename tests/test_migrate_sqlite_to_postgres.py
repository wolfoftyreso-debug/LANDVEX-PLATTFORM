"""Tester för scripts/migrate_sqlite_to_postgres.py.

PostgresStore kräver psycopg (inte installerat här) — testerna
använder i stället två SqliteStore-instanser som källa/mål. Det
bevisar exakt samma sak: migrate() går bara via Store-gränssnittets
egna all_X()/save_X()-metoder, aldrig rå SQL, och gränssnittet är
identiskt oavsett vilken klass som ligger bakom.

Kör: python3 -m tests.test_migrate_sqlite_to_postgres
"""
from __future__ import annotations

from engine.storage.sqlite import SqliteStore
from scripts.migrate_sqlite_to_postgres import (_ENTITIES, SKIPPED, migrate,
                                                main)


def test_every_all_x_store_method_is_migrated_or_explicitly_skipped():
    """En ny all_X()-metod på Store-gränssnittet som varken migreras
    eller nämns som medvetet uteslutet försvinner tyst ur en framtida
    flytt utan att någon märker det."""
    alla_läsmetoder = {m for m in dir(SqliteStore)
                       if m.startswith("all_")
                       and callable(getattr(SqliteStore, m))}
    migrerade = {läs for _, läs, _, _ in _ENTITIES}
    saknas = alla_läsmetoder - migrerade
    assert not saknas, (
        f"nya all_X()-metoder som varken migreras eller är dokumenterat "
        f"uteslutna: {sorted(saknas)}")


def test_the_entity_table_only_names_real_store_methods():
    for label, läs, skriv, typ in _ENTITIES:
        assert hasattr(SqliteStore, läs), f"{label}: {läs} finns inte"
        assert hasattr(SqliteStore, skriv), f"{label}: {skriv} finns inte"
        assert typ in ("record", "rows"), f"{label}: okänd typ {typ!r}"


def test_reports_and_profiles_are_named_in_skipped_with_the_actual_reason():
    """En uteslutning utan skäl är ett hål med en kommentar på."""
    from scripts import migrate_sqlite_to_postgres as M
    assert "reports" in SKIPPED and "profiles" in SKIPPED
    assert "list_reports" in M.__doc__ and "tenant" in M.__doc__


def test_migrate_moves_every_row_via_the_store_interface(tmp_path=None):
    import tempfile
    from engine import inspections as I

    with tempfile.TemporaryDirectory() as d:
        src = SqliteStore(f"{d}/src.db")
        dst = SqliteStore(f"{d}/dst.db")
        try:
            asset = I.asset("fp-1", "flagpole", label_en="Test",
                            lat=59.3, lon=18.0, tenant="acme")
            src.save_asset(asset)
            routine = I.routine("r-1", "Weekly", "flagpole", 7,
                                checks=["present"], tenant="acme")
            src.save_routine(routine)
            src.save_check(I.record("fp-1", "r-1", "pass",
                                    performed_at="2026-07-01",
                                    mission_id="qz-test-1",
                                    tenant="acme"))
            src.save_harvested([{"source": "x", "region_code": "se-0180",
                                 "signal_id": "y", "value": 1.0,
                                 "harvested_at": "2026-07-01"}])

            resultat = migrate(src, dst)

            assert resultat["assets"] == 1
            assert resultat["routines"] == 1
            assert resultat["checks"] == 1
            assert resultat["harvested rows"] == 1
            assert len(dst.all_assets()) == 1
            assert dst.all_assets()[0]["id"] == "fp-1"
            assert len(dst.all_routines()) == 1
            assert len(dst.all_checks()) == 1
            assert len(dst.all_harvested()) == 1
        finally:
            src.close()
            dst.close()


def test_migrate_is_idempotent_on_a_second_run():
    """Att köra flytten två gånger (t.ex. efter ett avbrutet första
    försök) ska inte dubblera rader eller krascha."""
    import tempfile
    from engine import inspections as I

    with tempfile.TemporaryDirectory() as d:
        src = SqliteStore(f"{d}/src.db")
        dst = SqliteStore(f"{d}/dst.db")
        try:
            src.save_asset(I.asset("fp-1", "flagpole", label_en="Test",
                                   lat=59.3, lon=18.0, tenant="acme"))
            migrate(src, dst)
            migrate(src, dst)
            assert len(dst.all_assets()) == 1, "andra körningen dubblerade raden"
        finally:
            src.close()
            dst.close()


def test_dry_run_writes_nothing():
    import tempfile
    from engine import inspections as I

    with tempfile.TemporaryDirectory() as d:
        src = SqliteStore(f"{d}/src.db")
        dst = SqliteStore(f"{d}/dst.db")
        try:
            src.save_asset(I.asset("fp-1", "flagpole", label_en="Test",
                                   lat=59.3, lon=18.0, tenant="acme"))
            resultat = migrate(src, dst, dry_run=True)
            assert resultat["assets"] == 1, "räkningen ska ändå stämma"
            assert dst.all_assets() == [], "dry-run skrev ändå något"
        finally:
            src.close()
            dst.close()


def test_main_refuses_without_a_dsn(monkeypatch=None):
    import os
    import tempfile

    tidigare = os.environ.pop("LANDVEX_PG_DSN", None)
    try:
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/src.db"
            SqliteStore(path).close()
            assert main(["prog", path]) == 2
    finally:
        if tidigare is not None:
            os.environ["LANDVEX_PG_DSN"] = tidigare


def test_main_refuses_a_missing_sqlite_file():
    import os
    os.environ["LANDVEX_PG_DSN"] = "postgresql://irrelevant"
    try:
        assert main(["prog", "/does/not/exist.db"]) == 2
    finally:
        del os.environ["LANDVEX_PG_DSN"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
