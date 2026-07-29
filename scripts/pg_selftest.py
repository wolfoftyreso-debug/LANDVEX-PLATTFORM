"""Driftsättningsverifiering mot riktig Postgres/Aurora.

    LANDVEX_PG_DSN=postgresql://... python3 -m scripts.pg_selftest

Kör `PostgresStore.selftest()` — spara/läs en rapport och en cachad
signal mot den RIKTIGA databasen — och skriver ut migrationsläget ur
`schema_meta`. Det är runbook-steget i backlog #2: provisionera Aurora,
kör det här, läs utskriften.

Utan DSN vägrar skriptet med skälet i stället för att "passera": en
driftsättningsverifiering som blir grön utan databas är ett falskt
kvitto, och det upptäcks först den dag databasen faktiskt är trasig.
"""
from __future__ import annotations

import os


def main() -> int:
    dsn = os.environ.get("LANDVEX_PG_DSN", "")
    if not dsn:
        print("REFUSED: LANDVEX_PG_DSN is not set. This check proves a "
              "real database round-trip; without a DSN there is nothing "
              "to prove, and a green run would be a false receipt.")
        return 2
    from engine.storage.postgres import PostgresStore

    store = PostgresStore(dsn)
    try:
        store.selftest()
    except Exception as e:                    # noqa: BLE001 — CLI-randen:
        # varje fel HÄR är resultatet skriptet finns för att visa.
        print(f"SELFTEST FAILED: {type(e).__name__}: {e}")
        return 1
    print(f"schema_meta version: {store.schema_version()}")
    from engine.storage.sqlite import SqliteStore

    ref = SqliteStore(":memory:")
    if store.schema_version() != ref.schema_version():
        print(f"WARNING: postgres is at version {store.schema_version()} "
              f"but the sqlite reference chain ends at "
              f"{ref.schema_version()} — the stores have drifted.")
        return 1
    print("PostgresStore matches the reference migration chain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
