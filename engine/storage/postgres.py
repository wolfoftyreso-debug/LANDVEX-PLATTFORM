"""PostgreSQL/PostGIS-implementation av Store (Aurora i produktion).

Kräver psycopg (se requirements.txt) – importeras lazy så att engine/
förblir importerbar utan installation. Samma gränssnitt och semantik
som SqliteStore, som är den testade referensen; denna implementation
ska verifieras mot en riktig PostgreSQL innan produktionssättning
(ingen databas fanns i utvecklingsmiljön vid implementationen):

    python3 -c "from engine.storage.postgres import PostgresStore; \\
                PostgresStore('postgresql://...').selftest()"

Platser lagras som PostGIS-punkter (SRID 4326) → radie-/närhetsfrågor
("alla rapporter inom 2 km") blir enkla när geodatafasen börjar.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from .base import Store

_DDL = """
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS reports (
    id                TEXT PRIMARY KEY,
    created_at        DOUBLE PRECISION NOT NULL,
    vertical_id       TEXT NOT NULL,
    geom              geometry(Point, 4326) NOT NULL,
    address           TEXT NOT NULL DEFAULT '',
    opportunity_score DOUBLE PRECISION NOT NULL,
    data_coverage     DOUBLE PRECISION NOT NULL,
    payload           JSONB NOT NULL,
    tenant            TEXT NOT NULL DEFAULT ''
);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS tenant TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_reports_tenant ON reports(tenant);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_geom ON reports USING GIST(geom);

CREATE TABLE IF NOT EXISTS profiles (
    id          TEXT PRIMARY KEY,
    created_at  DOUBLE PRECISION NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    vertical_id TEXT NOT NULL,
    payload     JSONB NOT NULL,
    tenant      TEXT NOT NULL DEFAULT ''
);
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS tenant TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_profiles_tenant ON profiles(tenant);
CREATE INDEX IF NOT EXISTS idx_profiles_created ON profiles(created_at DESC);

CREATE TABLE IF NOT EXISTS signal_cache (
    source    TEXT NOT NULL,
    loc_key   TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    value     DOUBLE PRECISION NOT NULL,
    quality   DOUBLE PRECISION NOT NULL,
    stored_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (source, loc_key, signal_id)
);

CREATE TABLE IF NOT EXISTS extras_cache (
    source    TEXT NOT NULL,
    loc_key   TEXT NOT NULL,
    payload   JSONB NOT NULL,
    stored_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (source, loc_key)
);

CREATE TABLE IF NOT EXISTS usage_meter (
    tenant TEXT NOT NULL,
    month  TEXT NOT NULL,
    n      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant, month)
);

CREATE TABLE IF NOT EXISTS outcomes (
    id              TEXT PRIMARY KEY,
    created_at      DOUBLE PRECISION NOT NULL,
    vertical        TEXT NOT NULL DEFAULT '',
    predicted_score DOUBLE PRECISION NOT NULL,
    survived        BOOLEAN NOT NULL,
    payload         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcomes_score ON outcomes(predicted_score);

CREATE TABLE IF NOT EXISTS decisions (
    id           TEXT PRIMARY KEY,
    committed_at DOUBLE PRECISION NOT NULL,
    owner        TEXT NOT NULL DEFAULT '',
    payload      JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS resolutions (
    id          TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    resolved_at DOUBLE PRECISION NOT NULL,
    met         BOOLEAN NOT NULL,
    payload     JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_resolutions_dec ON resolutions(decision_id);

CREATE TABLE IF NOT EXISTS corrections (
    id           TEXT PRIMARY KEY,
    created_at   DOUBLE PRECISION NOT NULL,
    region       TEXT NOT NULL,
    target_key   TEXT NOT NULL,
    submitter_id TEXT NOT NULL,
    payload      JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corrections_tgt ON corrections(target_key, region);

CREATE TABLE IF NOT EXISTS monitors (
    id      TEXT PRIMARY KEY,
    owner   TEXT NOT NULL DEFAULT '',
    metric  TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    checksum   TEXT NOT NULL,
    monitor_id TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    triggered  BOOLEAN NOT NULL,
    payload    JSONB NOT NULL,
    PRIMARY KEY (monitor_id, checksum)
);
CREATE INDEX IF NOT EXISTS idx_findings_mon ON findings(monitor_id);

-- Återkommande kontroller av kundens egna objekt. Motsvarar migration 7
-- i SQLite-lagret; de två får inte glida isär (tests/test_storage.py).
-- `checks` bär ALDRIG media: bilden stannar hos quiXzoom, som har
-- samtycket. Här ligger domen och en referens till uppdraget.
CREATE TABLE IF NOT EXISTS assets (
    id      TEXT NOT NULL,
    tenant  TEXT NOT NULL DEFAULT '',
    kind    TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL,
    PRIMARY KEY (tenant, id)
);

CREATE TABLE IF NOT EXISTS routines (
    id      TEXT NOT NULL,
    tenant  TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL,
    PRIMARY KEY (tenant, id)
);

CREATE TABLE IF NOT EXISTS checks (
    id           TEXT PRIMARY KEY,
    tenant       TEXT NOT NULL DEFAULT '',
    asset_id     TEXT NOT NULL,
    routine_id   TEXT NOT NULL DEFAULT '',
    performed_at TEXT NOT NULL DEFAULT '',
    verdict      TEXT NOT NULL DEFAULT '',
    payload      JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checks_tenant ON checks(tenant, asset_id);

-- Schemalagda körningar (migration 8 i SQLite-lagret). last_run är en
-- kolumn eftersom claim_job villkorar på den: två processer som kör samma
-- jobb ger kunden två beställda fältuppdrag för samma objekt.
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id       TEXT NOT NULL,
    tenant   TEXT NOT NULL DEFAULT '',
    kind     TEXT NOT NULL DEFAULT '',
    enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    last_run DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload  JSONB NOT NULL,
    PRIMARY KEY (tenant, id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON scheduled_jobs(tenant);

-- Skördad öppen data (migration 9 i SQLite-lagret). Ingen tenant-kolumn
-- med flit: öppen referensdata är densamma för alla kunder.
CREATE TABLE IF NOT EXISTS harvested (
    source      TEXT NOT NULL,
    region_code TEXT NOT NULL,
    signal_id   TEXT NOT NULL,
    market      TEXT NOT NULL DEFAULT '',
    value       DOUBLE PRECISION,
    unit        TEXT NOT NULL DEFAULT '',
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    observed_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload     JSONB NOT NULL,
    PRIMARY KEY (source, region_code, signal_id)
);
CREATE INDEX IF NOT EXISTS idx_harvested_src ON harvested(source, observed_at);

-- Nyhetsposter (migration 10 i SQLite-lagret). En rubrik är ingen signal
-- med ett värde, så de bor för sig. Ingen tenant.
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
    harvested_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload      JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_region ON news_items(region_code, harvested_at);
"""


class PostgresStore(Store):

    def __init__(self, dsn: str):
        import psycopg  # lazy: engine/ ska vara importerbar utan psycopg
        self._conn = psycopg.connect(dsn, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute(_DDL)

    def save_report(self, report: dict[str, Any], created_at: float, *,
                    tenant: str) -> str:
        report_id = uuid.uuid4().hex[:16]
        loc = report.get("location", {})
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reports (id, created_at, vertical_id, geom, "
                "address, opportunity_score, data_coverage, payload, tenant) "
                "VALUES (%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326), "
                "%s,%s,%s,%s,%s)",
                (report_id, created_at, report["vertical_id"],
                 loc.get("lon", 0.0), loc.get("lat", 0.0),
                 loc.get("address", ""), report["opportunity_score"],
                 report["data_coverage"],
                 json.dumps(report, ensure_ascii=False), tenant))
        return report_id

    def get_report(self, report_id: str, *,
                   tenant: str) -> Optional[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, created_at FROM reports "
                        "WHERE id = %s AND tenant = %s",
                        (report_id, tenant))
            row = cur.fetchone()
        if row is None:
            return None
        doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        doc["report_id"] = report_id
        doc["created_at"] = row[1]
        return doc

    def list_reports(self, limit: int = 20, *,
                     tenant: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, vertical_id, ST_Y(geom), ST_X(geom), "
                "address, opportunity_score, data_coverage FROM reports "
                "WHERE tenant = %s "
                "ORDER BY created_at DESC, id LIMIT %s", (tenant, limit))
            rows = cur.fetchall()
        keys = ("report_id", "created_at", "vertical_id", "lat", "lon",
                "address", "opportunity_score", "data_coverage")
        return [dict(zip(keys, r, strict=True)) for r in rows]

    def save_profile(self, profile: dict[str, Any], created_at: float, *,
                     tenant: str) -> str:
        profile_id = uuid.uuid4().hex[:16]
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO profiles (id, created_at, name, vertical_id, "
                "payload, tenant) VALUES (%s,%s,%s,%s,%s,%s)",
                (profile_id, created_at, profile.get("name", ""),
                 profile["vertical_id"],
                 json.dumps(profile, ensure_ascii=False), tenant))
        return profile_id

    def get_profile(self, profile_id: str, *,
                    tenant: str) -> Optional[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, created_at FROM profiles "
                        "WHERE id = %s AND tenant = %s",
                        (profile_id, tenant))
            row = cur.fetchone()
        if row is None:
            return None
        doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        doc["profile_id"] = profile_id
        doc["created_at"] = row[1]
        return doc

    def list_profiles(self, limit: int = 50, *,
                      tenant: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, name, vertical_id FROM profiles "
                "WHERE tenant = %s "
                "ORDER BY created_at DESC, id LIMIT %s", (tenant, limit))
            rows = cur.fetchall()
        keys = ("profile_id", "created_at", "name", "vertical_id")
        return [dict(zip(keys, r, strict=True)) for r in rows]

    def get_cached_signals(self, source: str, loc_key: str
                           ) -> dict[str, tuple[float, float, float]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT signal_id, value, quality, stored_at FROM signal_cache "
                "WHERE source = %s AND loc_key = %s", (source, loc_key))
            rows = cur.fetchall()
        return {sid: (v, q, ts) for sid, v, q, ts in rows}

    def put_cached_signals(self, source: str, loc_key: str,
                           signals: dict[str, tuple[float, float]],
                           stored_at: float) -> None:
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO signal_cache VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (source, loc_key, signal_id) DO UPDATE SET "
                "value = EXCLUDED.value, quality = EXCLUDED.quality, "
                "stored_at = EXCLUDED.stored_at",
                [(source, loc_key, sid, v, q, stored_at)
                 for sid, (v, q) in signals.items()])

    def get_cached_extras(self, source: str, loc_key: str
                          ) -> Optional[tuple[dict[str, Any], float]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT payload, stored_at FROM extras_cache "
                "WHERE source = %s AND loc_key = %s", (source, loc_key))
            row = cur.fetchone()
        if row is None:
            return None
        doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return doc, row[1]

    def put_cached_extras(self, source: str, loc_key: str,
                          extras: dict[str, Any], stored_at: float) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO extras_cache VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (source, loc_key) DO UPDATE SET "
                "payload = EXCLUDED.payload, stored_at = EXCLUDED.stored_at",
                (source, loc_key, json.dumps(extras, ensure_ascii=False),
                 stored_at))

    def bump_usage(self, tenant: str, month: str, quota: int) -> bool:
        """Atomisk villkorad upsert: räkna upp endast om under kvot.
        RETURNING ger en rad ⇒ tillåtet; tom ⇒ kvot nådd. DB:n
        serialiserar samtidiga anrop."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usage_meter (tenant, month, n) VALUES (%s,%s,1) "
                "ON CONFLICT (tenant, month) DO UPDATE SET n = usage_meter.n "
                "+ 1 WHERE usage_meter.n < %s RETURNING n",
                (tenant, month, quota))
            return cur.fetchone() is not None

    def save_outcome(self, record: dict[str, Any]) -> str:
        import json
        import time
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO outcomes "
                "(id, created_at, vertical, predicted_score, survived, payload) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                (record["id"], time.time(), record.get("vertical", ""),
                 float(record.get("predicted_score", 0.0)),
                 bool(record.get("survived")),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_outcomes(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM outcomes ORDER BY created_at, id")
            return [r[0] for r in cur.fetchall()]

    def save_decision(self, record: dict[str, Any]) -> str:
        import json
        import time
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO decisions (id, committed_at, owner, payload) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                (record["id"], time.time(),
                 record.get("owners", {}).get("formellt", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_decisions(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM decisions ORDER BY committed_at, id")
            return [r[0] for r in cur.fetchall()]

    def save_resolution(self, record: dict[str, Any]) -> str:
        import json
        import time
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO resolutions (id, decision_id, resolved_at, met, "
                "payload) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                (record["id"], record["decision_id"], time.time(),
                 bool(record.get("met")),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_resolutions(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM resolutions ORDER BY resolved_at, id")
            return [r[0] for r in cur.fetchall()]

    def save_correction(self, record: dict[str, Any]) -> str:
        import json
        import time
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO corrections (id, created_at, region, target_key, "
                "submitter_id, payload) VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO NOTHING",
                (record["id"], time.time(), record["region"],
                 record["target_key"], record["submitter_id"],
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_corrections(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM corrections ORDER BY created_at, id")
            return [r[0] for r in cur.fetchall()]

    # ── Bevakningar (kontroll-infrastruktur / cron) ──────────────────
    def save_monitor(self, record: dict[str, Any]) -> str:
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO monitors (id, owner, metric, payload) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE "
                "SET owner=EXCLUDED.owner, metric=EXCLUDED.metric, "
                "payload=EXCLUDED.payload",
                (record["id"], record.get("owner", ""),
                 record.get("metric", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_monitors(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM monitors ORDER BY id")
            return [r[0] for r in cur.fetchall()]

    def save_finding(self, record: dict[str, Any]) -> str:
        import json
        import time
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO findings (checksum, monitor_id, created_at, "
                "triggered, payload) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (monitor_id, checksum) DO NOTHING",
                (record["checksum"], record["monitor_id"], time.time(),
                 bool(record.get("triggered")),
                 json.dumps(record, ensure_ascii=False)))
        return record["checksum"]

    def all_findings(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM findings "
                        "ORDER BY created_at, checksum")
            return [r[0] for r in cur.fetchall()]

    # ── Återkommande kontroller ──────────────────────────────────────
    def save_asset(self, record: dict[str, Any]) -> str:
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assets (id, tenant, kind, payload) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (tenant, id) DO UPDATE "
                "SET kind=EXCLUDED.kind, payload=EXCLUDED.payload",
                (record["id"], record.get("tenant", ""),
                 record.get("kind", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_assets(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM assets ORDER BY tenant, id")
            return [r[0] for r in cur.fetchall()]

    def save_routine(self, record: dict[str, Any]) -> str:
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO routines (id, tenant, payload) "
                "VALUES (%s,%s,%s) ON CONFLICT (tenant, id) DO UPDATE "
                "SET payload=EXCLUDED.payload",
                (record["id"], record.get("tenant", ""),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_routines(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM routines ORDER BY tenant, id")
            return [r[0] for r in cur.fetchall()]

    def save_check(self, record: dict[str, Any]) -> str:
        import json
        import uuid as _uuid
        cid = record.get("id") or str(_uuid.uuid4())
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO checks (id, tenant, asset_id, routine_id, "
                "performed_at, verdict, payload) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload",
                (cid, record.get("tenant", ""), record["asset_id"],
                 record.get("routine_id", ""),
                 record.get("performed_at", ""), record.get("verdict", ""),
                 json.dumps(record, ensure_ascii=False)))
        return cid

    def all_checks(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload FROM checks "
                        "ORDER BY performed_at, id")
            return [r[0] for r in cur.fetchall()]

    # ── Schemalagda körningar ────────────────────────────────────────
    def save_job(self, record: dict[str, Any]) -> str:
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scheduled_jobs (id, tenant, kind, enabled, "
                "last_run, payload) VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant, id) DO UPDATE SET kind=EXCLUDED.kind, "
                "enabled=EXCLUDED.enabled, last_run=EXCLUDED.last_run, "
                "payload=EXCLUDED.payload",
                (record["id"], record.get("tenant", ""),
                 record.get("kind", ""), bool(record.get("enabled", True)),
                 float(record.get("last_run") or 0.0),
                 json.dumps(record, ensure_ascii=False)))
        return record["id"]

    def all_jobs(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, last_run FROM scheduled_jobs "
                        "ORDER BY tenant, id")
            ut = []
            for payload, last_run in cur.fetchall():
                d = dict(payload)
                d["last_run"] = last_run
                ut.append(d)
            return ut

    def claim_job(self, job_id: str, tenant: str, now: float,
                  gap_seconds: float) -> bool:
        """Atomiskt i databasen — villkoret ligger i UPDATE-satsen, inte i
        Python. En läsning följd av en skrivning är ett tidsfönster där två
        processer båda ser 'inte körd' och båda kör."""
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE scheduled_jobs SET last_run = %s "
                "WHERE id = %s AND tenant = %s AND last_run <= %s",
                (now, job_id, tenant, now - gap_seconds))
            return cur.rowcount > 0

    # ── Skördad öppen data ───────────────────────────────────────────
    def save_harvested(self, rows: list[dict[str, Any]]) -> int:
        import json
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO harvested (source, region_code, signal_id, "
                "market, value, unit, lat, lon, observed_at, payload) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (source, region_code, signal_id) DO UPDATE SET "
                "value=EXCLUDED.value, unit=EXCLUDED.unit, "
                "observed_at=EXCLUDED.observed_at, payload=EXCLUDED.payload",
                [(r["source"], r["region_code"], r["signal_id"],
                  r.get("market", ""), r.get("value"), r.get("unit", ""),
                  r.get("lat"), r.get("lon"),
                  float(r.get("observed_at") or 0),
                  json.dumps(r, ensure_ascii=False)) for r in rows])
        return len(rows)

    def all_harvested(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, observed_at FROM harvested "
                        "ORDER BY source, region_code, signal_id")
            ut = []
            for payload, observed_at in cur.fetchall():
                d = dict(payload)
                d["observed_at"] = observed_at
                ut.append(d)
            return ut

    # ── Nyhetsposter ─────────────────────────────────────────────────
    def save_news(self, rows: list[dict[str, Any]]) -> int:
        import json
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO news_items (checksum, outlet, owner, market, "
                "region_code, title, summary, link, published, "
                "harvested_at, payload) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (checksum) DO UPDATE SET "
                "region_code=EXCLUDED.region_code, "
                "harvested_at=EXCLUDED.harvested_at, "
                "payload=EXCLUDED.payload",
                [(r["checksum"], r.get("outlet", ""), r.get("owner", ""),
                  r.get("market", ""), r.get("region_code", ""),
                  r.get("title", ""), r.get("summary", ""),
                  r.get("link", ""), r.get("published", ""),
                  float(r.get("harvested_at") or 0),
                  json.dumps(r, ensure_ascii=False)) for r in rows])
        return len(rows)

    def all_news(self) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, harvested_at FROM news_items "
                        "ORDER BY harvested_at DESC, checksum")
            ut = []
            for payload, harvested_at in cur.fetchall():
                d = dict(payload)
                d["harvested_at"] = harvested_at
                ut.append(d)
            return ut

    def close(self) -> None:
        self._conn.close()

    def selftest(self) -> None:
        """Minimal rundtur mot riktig databas – kör vid driftsättning."""
        import time
        rid = self.save_report(
            {"vertical_id": "frisor", "opportunity_score": 50.0,
             "data_coverage": 0.0,
             "location": {"lat": 59.33, "lon": 18.06, "address": "selftest"}},
            created_at=time.time())
        # assert stryks av `python -O`: självtestet hade då "passerat"
        # utan att kontrollera någonting. En kontroll som kan optimeras
        # bort är ingen kontroll.
        if self.get_report(rid) is None:
            raise RuntimeError("selftest: saved report could not be read back")
        self.put_cached_signals("scb", "selftest", {"income_index": (100.0, 0.7)}, time.time())
        if "income_index" not in self.get_cached_signals("scb", "selftest"):
            raise RuntimeError("selftest: cached signal did not survive a "
                               "write/read round trip")
        print("PostgresStore selftest OK")   # noqa: T201 – CLI-självtest
