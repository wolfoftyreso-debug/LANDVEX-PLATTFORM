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

_DDL = """
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
"""


class SqliteStore(Store):

    def __init__(self, path: str = "landvex.db"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_DDL)

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

    def close(self) -> None:
        with self._lock:
            self._conn.close()
