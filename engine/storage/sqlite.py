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

    def save_report(self, report: dict[str, Any], created_at: float) -> str:
        report_id = uuid.uuid4().hex[:16]
        loc = report.get("location", {})
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?)",
                (report_id, created_at, report["vertical_id"],
                 loc.get("lat", 0.0), loc.get("lon", 0.0),
                 loc.get("address", ""), report["opportunity_score"],
                 report["data_coverage"],
                 json.dumps(report, ensure_ascii=False)))
        return report_id

    def get_report(self, report_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, created_at FROM reports WHERE id = ?",
                (report_id,)).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        doc["report_id"] = report_id
        doc["created_at"] = row[1]
        return doc

    def list_reports(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, vertical_id, lat, lon, address, "
                "opportunity_score, data_coverage FROM reports "
                "ORDER BY created_at DESC, id LIMIT ?", (limit,)).fetchall()
        keys = ("report_id", "created_at", "vertical_id", "lat", "lon",
                "address", "opportunity_score", "data_coverage")
        return [dict(zip(keys, r)) for r in rows]

    # ── Affärsprofiler ───────────────────────────────────────────────

    def save_profile(self, profile: dict[str, Any], created_at: float) -> str:
        profile_id = uuid.uuid4().hex[:16]
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO profiles VALUES (?,?,?,?,?)",
                (profile_id, created_at, profile.get("name", ""),
                 profile["vertical_id"],
                 json.dumps(profile, ensure_ascii=False)))
        return profile_id

    def get_profile(self, profile_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, created_at FROM profiles WHERE id = ?",
                (profile_id,)).fetchone()
        if row is None:
            return None
        doc = json.loads(row[0])
        doc["profile_id"] = profile_id
        doc["created_at"] = row[1]
        return doc

    def list_profiles(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, name, vertical_id FROM profiles "
                "ORDER BY created_at DESC, id LIMIT ?", (limit,)).fetchall()
        keys = ("profile_id", "created_at", "name", "vertical_id")
        return [dict(zip(keys, r)) for r in rows]

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

    def close(self) -> None:
        with self._lock:
            self._conn.close()
