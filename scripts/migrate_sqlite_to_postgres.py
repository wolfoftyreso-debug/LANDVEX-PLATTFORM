"""Migrerar en SqliteStore till en PostgresStore, tabell för tabell.

    LANDVEX_PG_DSN=postgresql://... python3 -m scripts.migrate_sqlite_to_postgres <sqlite-path>
    LANDVEX_PG_DSN=postgresql://... python3 -m scripts.migrate_sqlite_to_postgres <sqlite-path> --dry-run

Varje rad LÄSES via källagrets `all_X()` och SKRIVS via mållagrets
`save_X()` — aldrig rå SQL mot någotdera lagret, så migreringen går
genom exakt samma kod applikationen själv skriver med (samma
validering, samma ON CONFLICT-hantering, samma tenant-doktrin).

Skäl filen finns: 2026-07-30-infrastrukturinventeringen visade att
skarp drift kör SqliteStore (`/var/lib/landvex/landvex.db`), och
`docs/aws.md`/`docs/k8s.md` säger båda att SQLite är fel val bortom EN
replik — flera repliker (K8s, ECS-repliker >1) delar inte en fil. Det
här är verktyget för steget "byt lager", inte en generell
databasklon.

VAD SOM MIGRERAS: alla poster med rent (spara en post, läs alla poster)-
kontrakt — assets, routines, checks, check-granskningar, schemalagda
jobb, observationer, sponsrade kampanjer/genomföranden, dataleverantörs-
kopplingar, spaningar, lead-verdikter, lead-granskningar, personal,
leveranser, samt de äldre lärandeposterna (outcomes/decisions/
resolutions/corrections/monitors/findings) och skördade rader
(harvested, news).

VAD SOM INTE MIGRERAS, och varför:
  - `reports`/`profiles` — Store-gränssnittet exponerar bara
    tenant-listning (`list_reports(tenant=...)`), aldrig en global
    "alla tenanter"-lista (tenancy-doktrinen: ingen tvärtenant-vy ska
    kunna byggas av misstag). Migrera dessa per tenant för hand om det
    behövs, med en känd tenantlista.
  - `cached_signals`/`cached_extras` — cache, byggs om av sig själv.
  - `company_profile`/`company_logo` — nycklade per tenant utan en
    global "alla tenanter"-lista, av samma skäl som reports/profiles.

Rent stdlib. Ingen import av psycopg här — PostgresStore importerar den
lazy, så det här skriptet är läsbart och testbart utan den.
"""
from __future__ import annotations

import os
import sys

# (etikett, läsmetod, skrivmetod, typ) — typ "record" anropar
# skriv(post) en post i taget; "rows" anropar skriv(alla_poster) i ett
# svep, som harvested/news redan gör i sina egna Store-metoder.
_ENTITIES: tuple[tuple[str, str, str, str], ...] = (
    ("assets", "all_assets", "save_asset", "record"),
    ("routines", "all_routines", "save_routine", "record"),
    ("checks", "all_checks", "save_check", "record"),
    ("check reviews", "all_reviews", "save_review", "record"),
    ("scheduled jobs", "all_jobs", "save_job", "record"),
    ("observations", "all_observations", "save_observation", "record"),
    ("sponsor campaigns", "all_campaigns", "save_campaign", "record"),
    ("sponsor completions", "all_completions", "save_completion", "record"),
    ("provider connections", "all_connections", "save_connection", "record"),
    ("surveys", "all_surveys", "save_survey", "record"),
    ("lead verdicts", "all_lead_verdicts", "save_lead_verdict", "record"),
    ("lead reviews", "all_lead_reviews", "save_lead_review", "record"),
    ("staff", "all_staff", "save_staff", "record"),
    ("deliveries", "all_deliveries", "save_delivery", "record"),
    ("outcomes", "all_outcomes", "save_outcome", "record"),
    ("decisions", "all_decisions", "save_decision", "record"),
    ("resolutions", "all_resolutions", "save_resolution", "record"),
    ("corrections", "all_corrections", "save_correction", "record"),
    ("monitors", "all_monitors", "save_monitor", "record"),
    ("findings", "all_findings", "save_finding", "record"),
    ("harvested rows", "all_harvested", "save_harvested", "rows"),
    ("news items", "all_news", "save_news", "rows"),
)

# Store-metoder som medvetet INTE migreras — se moduldocstringen för
# varför. Namngivna här så att en framtida läsare ser att det är ett
# beslut, inte ett förbiseende, om de letar efter dem i _ENTITIES.
SKIPPED = ("reports", "profiles", "cached_signals", "cached_extras",
          "company_profile", "company_logo")


def migrate(source, target, *, dry_run: bool = False) -> dict[str, int]:
    """Ren funktion över två Store-objekt — testbar med två SqliteStore,
    eftersom PostgresStore delar exakt samma gränssnitt."""
    flyttat: dict[str, int] = {}
    for label, läs, skriv, typ in _ENTITIES:
        poster = getattr(source, läs)()
        if typ == "record":
            if not dry_run:
                for post in poster:
                    getattr(target, skriv)(post)
            flyttat[label] = len(poster)
        else:  # "rows" — hela listan i ett anrop, precis som applikationen gör
            if not dry_run and poster:
                getattr(target, skriv)(poster)
            flyttat[label] = len(poster)
    return flyttat


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in argv
    if not args:
        print("USAGE: python3 -m scripts.migrate_sqlite_to_postgres "
              "<sqlite-path> [--dry-run]")
        return 2
    sqlite_path = args[0]
    if not os.path.exists(sqlite_path):
        print(f"REFUSED: {sqlite_path} does not exist.")
        return 2
    dsn = os.environ.get("LANDVEX_PG_DSN", "")
    if not dsn:
        print("REFUSED: LANDVEX_PG_DSN is not set. Nothing to migrate to.")
        return 2

    from engine.storage.postgres import PostgresStore
    from engine.storage.sqlite import SqliteStore

    source = SqliteStore(sqlite_path)
    target = PostgresStore(dsn)
    try:
        flyttat = migrate(source, target, dry_run=dry_run)
    except Exception as e:                    # noqa: BLE001 — CLI-randen
        print(f"MIGRATION FAILED: {type(e).__name__}: {e}")
        return 1
    finally:
        source.close()
        target.close()

    verb = "would move" if dry_run else "moved"
    for label, n in flyttat.items():
        print(f"  {verb} {n:>6} {label}")
    print(f"\nNOT migrated (see module docstring for why): "
          f"{', '.join(SKIPPED)}")
    if dry_run:
        print("\nDRY RUN — nothing was written. Re-run without --dry-run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
