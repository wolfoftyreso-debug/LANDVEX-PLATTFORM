"""SQLite-implementation av Store (endast stdlib).

Referensimplementation och default lokalt/i test. I Lambda pekas den
mot /tmp (flyktig) eller ersätts av PostgresStore. Trådsäker via lås –
tillräckligt för dev-servern och FastAPI:s trådpool.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from typing import Any, Optional

from .base import Store

# Migrationshantering: basschemat (_DDL) är version 1 och idempotent.
# Senare schemaändringar läggs som (version, DDL) här och körs i
# ordning; aktuell version lagras i schema_meta. Ändra aldrig en
# redan utrullad migration – lägg en ny.
_SCHEMA_VERSION = 1
_MIGRATIONS: list[tuple[int, str]] = [
    (2, """
    CREATE TABLE IF NOT EXISTS outcomes (
        id              TEXT PRIMARY KEY,
        created_at      REAL NOT NULL,
        vertical        TEXT NOT NULL DEFAULT '',
        predicted_score REAL NOT NULL,
        survived        INTEGER NOT NULL,
        payload         TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_outcomes_score ON outcomes(predicted_score);
    """),
    (3, """
    CREATE TABLE IF NOT EXISTS decisions (
        id           TEXT PRIMARY KEY,
        committed_at REAL NOT NULL,
        owner        TEXT NOT NULL DEFAULT '',
        payload      TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS resolutions (
        id          TEXT PRIMARY KEY,
        decision_id TEXT NOT NULL,
        resolved_at REAL NOT NULL,
        met         INTEGER NOT NULL,
        payload     TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_resolutions_dec ON resolutions(decision_id);
    """),
    (4, """
    CREATE TABLE IF NOT EXISTS corrections (
        id           TEXT PRIMARY KEY,
        created_at   REAL NOT NULL,
        region       TEXT NOT NULL,
        target_key   TEXT NOT NULL,
        submitter_id TEXT NOT NULL,
        payload      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_corrections_tgt ON corrections(target_key, region);
    """),
    (5, """
    CREATE TABLE IF NOT EXISTS monitors (
        id      TEXT PRIMARY KEY,
        owner   TEXT NOT NULL DEFAULT '',
        metric  TEXT NOT NULL DEFAULT '',
        payload TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS findings (
        checksum   TEXT NOT NULL,
        monitor_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        triggered  INTEGER NOT NULL,
        payload    TEXT NOT NULL,
        PRIMARY KEY (monitor_id, checksum)
    );
    CREATE INDEX IF NOT EXISTS idx_findings_mon ON findings(monitor_id);
    """),
    # Tenant-isolering. Innan den här migrationen bar BARA usage_meter en
    # tenant-kolumn: auth-lagret läste tenant ur nyckeln, loggade den, och
    # kastade den innan lagret rördes. Två kunder i samma databas såg
    # därför varandras rapporter och profiler — bevisat med två API-nycklar
    # mot en körande server.
    #
    # Befintliga rader får tenant '' och blir därmed OSYNLIGA för alla
    # riktiga tenants. Det är med flit: att gissa vem gamla rader tillhör
    # vore att gissa fel för någon. Fail closed.
    (6, """
    ALTER TABLE reports  ADD COLUMN tenant TEXT NOT NULL DEFAULT '';
    ALTER TABLE profiles ADD COLUMN tenant TEXT NOT NULL DEFAULT '';
    CREATE INDEX IF NOT EXISTS idx_reports_tenant  ON reports(tenant);
    CREATE INDEX IF NOT EXISTS idx_profiles_tenant ON profiles(tenant);
    """),
    # Återkommande kontroller av kundens egna objekt. Tenant är en KOLUMN
    # här och inte bara ett fält i nyttolasten: registret är det som visas
    # för en nämnd eller en försäkringsgivare efter en olycka, och då ska
    # det gå att se i databasen vem raden tillhör utan att packa upp JSON.
    #
    # `checks` bär INTE media. Bilden stannar hos quiXzoom, som har
    # samtycket; här ligger domen och en referens (mission_id/evidence_ref).
    # En fältbild på en badplats innehåller människor — den kolumnen ska
    # aldrig läggas till.
    (7, """
    CREATE TABLE IF NOT EXISTS assets (
        id      TEXT NOT NULL,
        tenant  TEXT NOT NULL DEFAULT '',
        kind    TEXT NOT NULL DEFAULT '',
        payload TEXT NOT NULL,
        PRIMARY KEY (tenant, id)
    );
    CREATE TABLE IF NOT EXISTS routines (
        id      TEXT NOT NULL,
        tenant  TEXT NOT NULL DEFAULT '',
        payload TEXT NOT NULL,
        PRIMARY KEY (tenant, id)
    );
    CREATE TABLE IF NOT EXISTS checks (
        id           TEXT PRIMARY KEY,
        tenant       TEXT NOT NULL DEFAULT '',
        asset_id     TEXT NOT NULL,
        routine_id   TEXT NOT NULL DEFAULT '',
        performed_at TEXT NOT NULL DEFAULT '',
        verdict      TEXT NOT NULL DEFAULT '',
        payload      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_checks_tenant ON checks(tenant, asset_id);
    """),
    # Schemalagda körningar. `last_run` är en KOLUMN och inte bara ett
    # fält i nyttolasten, för det är den som villkoret i claim_job läser:
    # två processer som kör samma jobb ger kunden två beställda fältuppdrag
    # för samma objekt.
    (8, """
    CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id       TEXT NOT NULL,
        tenant   TEXT NOT NULL DEFAULT '',
        kind     TEXT NOT NULL DEFAULT '',
        enabled  INTEGER NOT NULL DEFAULT 1,
        last_run REAL NOT NULL DEFAULT 0,
        payload  TEXT NOT NULL,
        PRIMARY KEY (tenant, id)
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON scheduled_jobs(tenant);
    """),
    # Skördad öppen data. INGEN tenant-kolumn, med flit: hur många
    # frisörer OpenStreetMap känner till i Nacka är samma sak för varje
    # kund, och att skopa raden per kund vore att lagra samma sanning
    # femtio gånger — och antyda att en kund kan ha en egen. Det skiljer
    # sig från assets/routines/checks, som ÄR kundens egna objekt.
    #
    # `observed_at` är en KOLUMN eftersom åldern avgör om raden får
    # användas alls: äldre än källans max_age_days läses som frånvarande.
    (9, """
    CREATE TABLE IF NOT EXISTS harvested (
        source      TEXT NOT NULL,
        region_code TEXT NOT NULL,
        signal_id   TEXT NOT NULL,
        market      TEXT NOT NULL DEFAULT '',
        value       REAL,
        unit        TEXT NOT NULL DEFAULT '',
        lat         REAL,
        lon         REAL,
        observed_at REAL NOT NULL DEFAULT 0,
        payload     TEXT NOT NULL,
        PRIMARY KEY (source, region_code, signal_id)
    );
    CREATE INDEX IF NOT EXISTS idx_harvested_src
        ON harvested(source, observed_at);
    """),
    # Nyhetsposter. De passar INTE i `harvested`, som är
    # (källa, region, signal, VÄRDE): en rubrik är ingen signal med ett
    # värde, och att trycka in den där hade krävt ett signal_id som inte
    # är en signal.
    #
    # Ingen tenant: publicerad text är densamma för alla, precis som
    # skördad öppen data.
    (10, """
    CREATE TABLE IF NOT EXISTS news_items (
        checksum     TEXT PRIMARY KEY,
        outlet       TEXT NOT NULL DEFAULT '',
        owner        TEXT NOT NULL DEFAULT '',
        market       TEXT NOT NULL DEFAULT '',
        region_code  TEXT NOT NULL DEFAULT '',
        title        TEXT NOT NULL DEFAULT '',
        summary      TEXT NOT NULL DEFAULT '',
        link         TEXT NOT NULL DEFAULT '',
        published    TEXT NOT NULL DEFAULT '',
        harvested_at REAL NOT NULL DEFAULT 0,
        payload      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_news_region
        ON news_items(region_code, harvested_at);
    """),
    # Sponsrade uppdrag. Kampanjer och fullbordanden är KUNDENS egna
    # (tenant-kolumn, motorn filtrerar — samma mönster som assets).
    # Fullbordanden bär dom, region och avräkningsreferens — ALDRIG
    # person: zoomern, plånboken och samtycket bor hos quiXzoom, och
    # att kolumnerna inte finns är spärren som inte kan glömmas.
    (11, """
    CREATE TABLE IF NOT EXISTS sponsor_campaigns (
        id         TEXT NOT NULL,
        tenant     TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL DEFAULT 0,
        status     TEXT NOT NULL DEFAULT 'active',
        payload    TEXT NOT NULL,
        PRIMARY KEY (tenant, id)
    );
    CREATE TABLE IF NOT EXISTS sponsor_completions (
        id           TEXT PRIMARY KEY,
        tenant       TEXT NOT NULL DEFAULT '',
        campaign_id  TEXT NOT NULL,
        mission_id   TEXT NOT NULL,
        region_code  TEXT NOT NULL DEFAULT '',
        completed_at REAL NOT NULL DEFAULT 0,
        payload      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sponsor_completions
        ON sponsor_completions(tenant, campaign_id, completed_at);
    """),
    # Infrastrukturobservationer. Egen tabell och inte `checks`: en
    # kontroll är en DOM (godkänd/underkänd), en observation är MÄTTA
    # VÄRDEN med färskhet. Att trycka in värden i en domtabell hade
    # krävt en dom som inte fanns — och åldersregeln hade gällt fel sak.
    (12, """
    CREATE TABLE IF NOT EXISTS observations (
        id           TEXT PRIMARY KEY,
        tenant       TEXT NOT NULL DEFAULT '',
        object_id    TEXT NOT NULL,
        kind         TEXT NOT NULL DEFAULT '',
        mission_id   TEXT NOT NULL DEFAULT '',
        observed_at  REAL NOT NULL DEFAULT 0,
        payload      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_observations
        ON observations(tenant, object_id, observed_at);
    """),
    # Kundens egna kopplingar (LLM-nycklar, webhooks). payload bär
    # hemligheten OKRYPTERAD i lagret — samma skyddsnivå som resten av
    # databasen (kryptering i vila är infrastrukturens ansvar, KMS på
    # Aurora); det som ALDRIG händer är att den lämnar systemet
    # omaskerad, och den regeln bor i engine/connections.masked().
    # En koppling per (tenant, provider) — att byta nyckel är att
    # skriva över, inte att samla gamla nycklar på hög.
    (13, """
    CREATE TABLE IF NOT EXISTS connections (
        tenant     TEXT NOT NULL DEFAULT '',
        provider   TEXT NOT NULL,
        created_at REAL NOT NULL DEFAULT 0,
        payload    TEXT NOT NULL,
        PRIMARY KEY (tenant, provider)
    );
    """),
    # Företagsprofilen (varumärket som rider på uppdragen) och
    # credential-hemligheterna. Hemligheten lämnar ALDRIG systemet —
    # den har ingen läsväg utåt alls, inte ens maskerad: den används
    # för att signera och verifiera, punkt.
    (14, """
    CREATE TABLE IF NOT EXISTS company_profiles (
        tenant     TEXT PRIMARY KEY,
        updated_at REAL NOT NULL DEFAULT 0,
        payload    TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS credential_secrets (
        tenant     TEXT PRIMARY KEY,
        secret     TEXT NOT NULL,
        created_at REAL NOT NULL DEFAULT 0
    );
    """),
    # Kundens egna zoomers: kontoreferenser och inbjudningskoder —
    # aldrig namn, aldrig e-post. Motorn (engine/staff.py) vägrar dem
    # vid dörren; att kolumnerna inte finns är spärren som består.
    (15, """
    CREATE TABLE IF NOT EXISTS staff (
        tenant   TEXT NOT NULL DEFAULT '',
        id       TEXT NOT NULL,
        added_at REAL NOT NULL DEFAULT 0,
        payload  TEXT NOT NULL,
        PRIMARY KEY (tenant, id)
    );
    """),
    # Leveransloggen: varje utgående försök med mottagarens svar.
    # payload bär loggposten — kroppens SHA-256, ALDRIG kroppen själv.
    (16, """
    CREATE TABLE IF NOT EXISTS deliveries (
        id         TEXT PRIMARY KEY,
        tenant     TEXT NOT NULL DEFAULT '',
        kind       TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL DEFAULT 0,
        payload    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_deliveries
        ON deliveries(tenant, created_at);
    """),
    # Uppladdade logotyper: en per tenant (samma mönster som
    # company_profiles). Byten själva ligger base64:ade INUTI payload —
    # ingen egen BLOB-kolumn behövs, samma "allt är payload"-form som
    # varenda annan tabell här.
    (17, """
    CREATE TABLE IF NOT EXISTS company_logos (
        tenant      TEXT PRIMARY KEY,
        uploaded_at REAL NOT NULL DEFAULT 0,
        payload     TEXT NOT NULL
    );
    """),
]

_DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    version    INTEGER NOT NULL,
    applied_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id                TEXT PRIMARY KEY,
    created_at        REAL NOT NULL,
    vertical_id       TEXT NOT NULL,
    lat               REAL NOT NULL,
    lon               REAL NOT NULL,
    address           TEXT NOT NULL DEFAULT '',
    opportunity_score REAL NOT NULL,
    data_coverage     REAL NOT NULL,
    payload           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);

CREATE TABLE IF NOT EXISTS profiles (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    vertical_id TEXT NOT NULL,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profiles_created ON profiles(created_at DESC);

CREATE TABLE IF NOT EXISTS signal_cache (
    source    TEXT NOT NULL,
    loc_key   TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    value     REAL NOT NULL,
    quality   REAL NOT NULL,
    stored_at REAL NOT NULL,
    PRIMARY KEY (source, loc_key, signal_id)
);

CREATE TABLE IF NOT EXISTS extras_cache (
    source    TEXT NOT NULL,
    loc_key   TEXT NOT NULL,
    payload   TEXT NOT NULL,
    stored_at REAL NOT NULL,
    PRIMARY KEY (source, loc_key)
);

CREATE TABLE IF NOT EXISTS usage_meter (
    tenant TEXT NOT NULL,
    month  TEXT NOT NULL,
    n      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant, month)
);
"""


class SqliteStore(Store):

    def __init__(self, path: str = "landvex.db"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_DDL)
            self._migrate()

    def _migrate(self) -> None:
        import time
        row = self._conn.execute(
            "SELECT MAX(version) FROM schema_meta").fetchone()
        current = row[0] or 0
        if current == 0:
            self._conn.execute("INSERT INTO schema_meta VALUES (?, ?)",
                               (_SCHEMA_VERSION, time.time()))
            current = _SCHEMA_VERSION
        for version, ddl in _MIGRATIONS:
            if version > current:
                self._conn.executescript(ddl)
                self._conn.execute("INSERT INTO schema_meta VALUES (?, ?)",
                                   (version, time.time()))

    def schema_version(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(version) FROM schema_meta").fetchone()
        return row[0] or 0

    # ── Rapporter ────────────────────────────────────────────────────

    def save_report(self, report: dict[str, Any], created_at: float, *,
                    tenant: str) -> str:
        report_id = uuid.uuid4().hex[:16]
        loc = report.get("location", {})
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO reports (id, created_at, vertical_id, lat, lon, "
                "address, opportunity_score, data_coverage, payload, tenant) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (report_id, created_at, report["vertical_id"],
                 loc.get("lat", 0.0), loc.get("lon", 0.0),
                 loc.get("address", ""), report["opportunity_score"],
                 report["data_coverage"],
                 json.dumps(report, ensure_ascii=False), tenant))
        return report_id

    def get_report(self, report_id: str, *,
                   tenant: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, created_at FROM reports "
                "WHERE id = ? AND tenant = ?",
                (report_id, tenant)).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        doc["report_id"] = report_id
        doc["created_at"] = row[1]
        return doc

    def list_reports(self, limit: int = 20, *,
                     tenant: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, vertical_id, lat, lon, address, "
                "opportunity_score, data_coverage FROM reports "
                "WHERE tenant = ? "
                "ORDER BY created_at DESC, id LIMIT ?",
                (tenant, limit)).fetchall()
        keys = ("report_id", "created_at", "vertical_id", "lat", "lon",
                "address", "opportunity_score", "data_coverage")
        return [dict(zip(keys, r, strict=True)) for r in rows]

    # ── Affärsprofiler ───────────────────────────────────────────────

    def save_profile(self, profile: dict[str, Any], created_at: float, *,
                     tenant: str) -> str:
        profile_id = uuid.uuid4().hex[:16]
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO profiles (id, created_at, name, vertical_id, "
                "payload, tenant) VALUES (?,?,?,?,?,?)",
                (profile_id, created_at, profile.get("name", ""),
                 profile["vertical_id"],
                 json.dumps(profile, ensure_ascii=False), tenant))
        return profile_id

    def get_profile(self, profile_id: str, *,
                    tenant: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, created_at FROM profiles "
                "WHERE id = ? AND tenant = ?",
                (profile_id, tenant)).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        doc["profile_id"] = profile_id
        doc["created_at"] = row[1]
        return doc

    def list_profiles(self, limit: int = 50, *,
                      tenant: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, name, vertical_id FROM profiles "
                "WHERE tenant = ? "
                "ORDER BY created_at DESC, id LIMIT ?",
                (tenant, limit)).fetchall()
        keys = ("profile_id", "created_at", "name", "vertical_id")
        return [dict(zip(keys, r, strict=True)) for r in rows]

    # ── Signalcache ──────────────────────────────────────────────────

    def get_cached_signals(self, source: str, loc_key: str
                           ) -> dict[str, tuple[float, float, float]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT signal_id, value, quality, stored_at FROM signal_cache "
                "WHERE source = ? AND loc_key = ?", (source, loc_key)).fetchall()
        return {sid: (v, q, ts) for sid, v, q, ts in rows}

    def put_cached_signals(self, source: str, loc_key: str,
                           signals: dict[str, tuple[float, float]],
                           stored_at: float) -> None:
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO signal_cache VALUES (?,?,?,?,?,?)",
                [(source, loc_key, sid, v, q, stored_at)
                 for sid, (v, q) in signals.items()])

    def get_cached_extras(self, source: str, loc_key: str
                          ) -> Optional[tuple[dict[str, Any], float]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, stored_at FROM extras_cache "
                "WHERE source = ? AND loc_key = ?", (source, loc_key)).fetchone()
        return (json.loads(row[0]), row[1]) if row else None

    def put_cached_extras(self, source: str, loc_key: str,
                          extras: dict[str, Any], stored_at: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO extras_cache VALUES (?,?,?,?)",
                (source, loc_key, json.dumps(extras, ensure_ascii=False),
                 stored_at))

    def bump_usage(self, tenant: str, month: str, quota: int) -> bool:
        """Atomiskt: släpp igenom och räkna upp om under kvot, annars
        neka utan att räkna upp. True = tillåtet, False = kvot nådd.
        Persistent över omstarter (till skillnad från in-memory)."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT n FROM usage_meter WHERE tenant = ? AND month = ?",
                (tenant, month)).fetchone()
            n = row[0] if row else 0
            if n >= quota:
                return False
            self._conn.execute(
                "INSERT INTO usage_meter (tenant, month, n) VALUES (?,?,1) "
                "ON CONFLICT(tenant, month) DO UPDATE SET n = n + 1",
                (tenant, month))
            return True

    # ── Utfall (kalibrering) ─────────────────────────────────────────

    def save_outcome(self, record: dict[str, Any]) -> str:
        """Append-only, idempotent på record['id'] (INSERT OR IGNORE)."""
        import time
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO outcomes "
                "(id, created_at, vertical, predicted_score, survived, payload) "
                "VALUES (?,?,?,?,?,?)",
                (record["id"], time.time(), record.get("vertical", ""),
                 float(record.get("predicted_score", 0.0)),
                 1 if record.get("survived") else 0,
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_outcomes(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM outcomes ORDER BY created_at, id").fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Ansvarsloop ──────────────────────────────────────────────────

    def save_decision(self, record: dict[str, Any]) -> str:
        import time
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO decisions (id, committed_at, owner, "
                "payload) VALUES (?,?,?,?)",
                (record["id"], time.time(),
                 record.get("owners", {}).get("formellt", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_decisions(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM decisions ORDER BY committed_at, id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def save_resolution(self, record: dict[str, Any]) -> str:
        import time
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO resolutions (id, decision_id, "
                "resolved_at, met, payload) VALUES (?,?,?,?,?)",
                (record["id"], record["decision_id"], time.time(),
                 1 if record.get("met") else 0,
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_resolutions(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM resolutions ORDER BY resolved_at, id").fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Wiki-rättelser ───────────────────────────────────────────────

    def save_correction(self, record: dict[str, Any]) -> str:
        import time
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO corrections (id, created_at, region, "
                "target_key, submitter_id, payload) VALUES (?,?,?,?,?,?)",
                (record["id"], time.time(), record["region"],
                 record["target_key"], record["submitter_id"],
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_corrections(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM corrections ORDER BY created_at, id").fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Bevakningar (kontroll-infrastruktur / cron) ──────────────────
    def save_monitor(self, record: dict[str, Any]) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO monitors (id, owner, metric, payload) "
                "VALUES (?,?,?,?)",
                (record["id"], record.get("owner", ""),
                 record.get("metric", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_monitors(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM monitors ORDER BY id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def save_finding(self, record: dict[str, Any]) -> str:
        import time
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO findings (checksum, monitor_id, "
                "created_at, triggered, payload) VALUES (?,?,?,?,?)",
                (record["checksum"], record["monitor_id"], time.time(),
                 1 if record.get("triggered") else 0,
                 json.dumps(record, ensure_ascii=False)))
        return record["checksum"]

    def all_findings(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM findings ORDER BY created_at, checksum"
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Återkommande kontroller ──────────────────────────────────────
    def save_asset(self, record: dict[str, Any]) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO assets (id, tenant, kind, payload) "
                "VALUES (?,?,?,?)",
                (record["id"], record.get("tenant", ""),
                 record.get("kind", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_assets(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM assets ORDER BY tenant, id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def save_routine(self, record: dict[str, Any]) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO routines (id, tenant, payload) "
                "VALUES (?,?,?)",
                (record["id"], record.get("tenant", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_routines(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM routines ORDER BY tenant, id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def save_check(self, record: dict[str, Any]) -> str:
        # Append-only: ett utfall skrivs aldrig över. En kontroll som
        # gjordes om samma dag är en NY rad — det är två observationer,
        # och registret ska visa båda.
        cid = record.get("id") or str(uuid.uuid4())
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO checks (id, tenant, asset_id, "
                "routine_id, performed_at, verdict, payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (cid, record.get("tenant", ""), record["asset_id"],
                 record.get("routine_id", ""),
                 record.get("performed_at", ""), record.get("verdict", ""),
                 json.dumps(record, ensure_ascii=False)))
        return cid

    def all_checks(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM checks ORDER BY performed_at, id"
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    # ── Schemalagda körningar ────────────────────────────────────────
    def save_job(self, record: dict[str, Any]) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO scheduled_jobs (id, tenant, kind, "
                "enabled, last_run, payload) VALUES (?,?,?,?,?,?)",
                (record["id"], record.get("tenant", ""),
                 record.get("kind", ""),
                 1 if record.get("enabled", True) else 0,
                 float(record.get("last_run") or 0.0),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload, last_run FROM scheduled_jobs "
                "ORDER BY tenant, id").fetchall()
        # last_run läses ur KOLUMNEN, inte ur nyttolasten: det är kolumnen
        # claim_job uppdaterar, och en nyttolast som hunnit bli gammal
        # skulle annars säga att jobbet är förfallet igen.
        ut = []
        for payload, last_run in rows:
            d = json.loads(payload)
            d["last_run"] = last_run
            ut.append(d)
        return ut

    def claim_job(self, job_id: str, tenant: str, now: float,
                  gap_seconds: float) -> bool:
        """Atomiskt: ta jobbet om det inte körts inom `gap_seconds`.

        Villkoret ligger i UPDATE-satsen, inte i Python: en läsning följd
        av en skrivning är ett tidsfönster där två processer båda ser
        'inte körd' och båda kör.
        """
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE scheduled_jobs SET last_run = ? "
                "WHERE id = ? AND tenant = ? AND last_run <= ?",
                (now, job_id, tenant, now - gap_seconds))
            return cur.rowcount > 0

    # ── Skördad öppen data ───────────────────────────────────────────
    def save_harvested(self, rows: list[dict[str, Any]]) -> int:
        """Skriv över raden för samma (källa, region, signal).

        En skörd ERSÄTTER föregående i stället för att lägga till: det
        här är det senaste kända läget, inte en tidsserie. Vill man ha
        historik är det en annan tabell och ett annat beslut — och att
        låta den här växa obemärkt vore att fatta det beslutet av misstag.
        """
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO harvested (source, region_code, "
                "signal_id, market, value, unit, lat, lon, observed_at, "
                "payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(r["source"], r["region_code"], r["signal_id"],
                  r.get("market", ""), r.get("value"), r.get("unit", ""),
                  r.get("lat"), r.get("lon"),
                  float(r.get("observed_at") or 0),
                  json.dumps(r, ensure_ascii=False)) for r in rows])
        return len(rows)

    def all_harvested(self) -> list[dict[str, Any]]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload, observed_at FROM harvested "
                "ORDER BY source, region_code, signal_id").fetchall()
        ut = []
        for payload, observed_at in rader:
            d = json.loads(payload)
            d["observed_at"] = observed_at      # kolumnen är sanningen
            ut.append(d)
        return ut

    # ── Nyhetsposter ─────────────────────────────────────────────────
    def save_news(self, rows: list[dict[str, Any]]) -> int:
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO news_items (checksum, outlet, "
                "owner, market, region_code, title, summary, link, "
                "published, harvested_at, payload) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(r["checksum"], r.get("outlet", ""), r.get("owner", ""),
                  r.get("market", ""), r.get("region_code", ""),
                  r.get("title", ""), r.get("summary", ""),
                  r.get("link", ""), r.get("published", ""),
                  float(r.get("harvested_at") or 0),
                  json.dumps(r, ensure_ascii=False)) for r in rows])
        return len(rows)

    def all_news(self) -> list[dict[str, Any]]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload, harvested_at FROM news_items "
                "ORDER BY harvested_at DESC, checksum").fetchall()
        ut = []
        for payload, harvested_at in rader:
            d = json.loads(payload)
            d["harvested_at"] = harvested_at
            ut.append(d)
        return ut

    # ── Infrastrukturobservationer ──────────────────────────────────
    def save_observation(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO observations (id, tenant, "
                "object_id, kind, mission_id, observed_at, payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (rec["id"], rec.get("tenant", ""), rec["object_id"],
                 rec.get("kind", ""), rec.get("mission_id", ""),
                 float(rec.get("observed_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["id"]

    def all_observations(self) -> list[dict]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload FROM observations "
                "ORDER BY observed_at DESC, id").fetchall()
        return [json.loads(r[0]) for r in rader]

    # ── Sponsrade uppdrag ───────────────────────────────────────────
    def save_campaign(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO sponsor_campaigns "
                "(id, tenant, created_at, status, payload) "
                "VALUES (?,?,?,?,?)",
                (rec["id"], rec.get("tenant", ""),
                 float(rec.get("created_at") or 0),
                 rec.get("status", "active"),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["id"]

    def all_campaigns(self) -> list[dict]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload FROM sponsor_campaigns "
                "ORDER BY created_at DESC, id").fetchall()
        return [json.loads(r[0]) for r in rader]

    def save_completion(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO sponsor_completions "
                "(id, tenant, campaign_id, mission_id, region_code, "
                "completed_at, payload) VALUES (?,?,?,?,?,?,?)",
                (rec["id"], rec.get("tenant", ""), rec["campaign_id"],
                 rec["mission_id"], rec.get("region_code", ""),
                 float(rec.get("completed_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["id"]

    def all_completions(self) -> list[dict]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload FROM sponsor_completions "
                "ORDER BY completed_at DESC, id").fetchall()
        return [json.loads(r[0]) for r in rader]

    # ── Kundens kopplingar ──────────────────────────────────────────
    def save_connection(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO connections "
                "(tenant, provider, created_at, payload) VALUES (?,?,?,?)",
                (rec.get("tenant", ""), rec["provider"],
                 float(rec.get("created_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["provider"]

    def all_connections(self) -> list[dict]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload FROM connections "
                "ORDER BY created_at DESC, provider").fetchall()
        return [json.loads(r[0]) for r in rader]

    def delete_connection(self, provider: str, tenant: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM connections WHERE tenant = ? AND provider = ?",
                (tenant, provider))
        return cur.rowcount > 0

    # ── Företagsprofil + credential-hemlighet ───────────────────────
    def save_company_profile(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO company_profiles "
                "(tenant, updated_at, payload) VALUES (?,?,?)",
                (rec["tenant"], float(rec.get("updated_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["tenant"]

    def get_company_profile(self, tenant: str) -> dict | None:
        with self._lock:
            rad = self._conn.execute(
                "SELECT payload FROM company_profiles WHERE tenant = ?",
                (tenant,)).fetchone()
        return json.loads(rad[0]) if rad else None

    def save_company_logo(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO company_logos "
                "(tenant, uploaded_at, payload) VALUES (?,?,?)",
                (rec["tenant"], float(rec.get("uploaded_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["tenant"]

    def get_company_logo(self, tenant: str) -> dict | None:
        with self._lock:
            rad = self._conn.execute(
                "SELECT payload FROM company_logos WHERE tenant = ?",
                (tenant,)).fetchone()
        return json.loads(rad[0]) if rad else None

    def delete_company_logo(self, tenant: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM company_logos WHERE tenant = ?", (tenant,))
        return cur.rowcount > 0

    def credential_secret(self, tenant: str) -> bytes:
        """Hämta-eller-skapa: hemligheten genereras första gången den
        behövs och har därefter INGEN läsväg utanför signering."""
        import secrets as _s
        import time as _t
        with self._lock, self._conn:
            rad = self._conn.execute(
                "SELECT secret FROM credential_secrets WHERE tenant = ?",
                (tenant,)).fetchone()
            if rad:
                return bytes.fromhex(rad[0])
            ny = _s.token_bytes(32)
            self._conn.execute(
                "INSERT INTO credential_secrets (tenant, secret, "
                "created_at) VALUES (?,?,?)",
                (tenant, ny.hex(), _t.time()))
        return ny

    # ── Kundens egna zoomers ────────────────────────────────────────
    def save_staff(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO staff "
                "(tenant, id, added_at, payload) VALUES (?,?,?,?)",
                (rec.get("tenant", ""), rec["id"],
                 float(rec.get("added_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["id"]

    def all_staff(self) -> list[dict]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload FROM staff "
                "ORDER BY added_at, id").fetchall()
        return [json.loads(r[0]) for r in rader]

    def delete_staff(self, row_id: str, tenant: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM staff WHERE tenant = ? AND id = ?",
                (tenant, row_id))
        return cur.rowcount > 0

    # ── Leveransloggen ──────────────────────────────────────────────
    def save_delivery(self, rec: dict) -> str:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO deliveries "
                "(id, tenant, kind, created_at, payload) "
                "VALUES (?,?,?,?,?)",
                (rec["id"], rec.get("tenant", ""), rec.get("kind", ""),
                 float(rec.get("created_at") or 0),
                 json.dumps(rec, ensure_ascii=False)))
        return rec["id"]

    def all_deliveries(self) -> list[dict]:
        with self._lock:
            rader = self._conn.execute(
                "SELECT payload FROM deliveries "
                "ORDER BY created_at DESC, id LIMIT 2000").fetchall()
        return [json.loads(r[0]) for r in rader]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
