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
    payload           JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_geom ON reports USING GIST(geom);

CREATE TABLE IF NOT EXISTS profiles (
    id          TEXT PRIMARY KEY,
    created_at  DOUBLE PRECISION NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    vertical_id TEXT NOT NULL,
    payload     JSONB NOT NULL
);
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
"""


class PostgresStore(Store):

    def __init__(self, dsn: str):
        import psycopg  # lazy: engine/ ska vara importerbar utan psycopg
        self._conn = psycopg.connect(dsn, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute(_DDL)

    def save_report(self, report: dict[str, Any], created_at: float) -> str:
        report_id = uuid.uuid4().hex[:16]
        loc = report.get("location", {})
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reports (id, created_at, vertical_id, geom, "
                "address, opportunity_score, data_coverage, payload) VALUES "
                "(%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326), %s,%s,%s,%s)",
                (report_id, created_at, report["vertical_id"],
                 loc.get("lon", 0.0), loc.get("lat", 0.0),
                 loc.get("address", ""), report["opportunity_score"],
                 report["data_coverage"],
                 json.dumps(report, ensure_ascii=False)))
        return report_id

    def get_report(self, report_id: str) -> Optional[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, created_at FROM reports WHERE id = %s",
                        (report_id,))
            row = cur.fetchone()
        if row is None:
            return None
        doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        doc["report_id"] = report_id
        doc["created_at"] = row[1]
        return doc

    def list_reports(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, vertical_id, ST_Y(geom), ST_X(geom), "
                "address, opportunity_score, data_coverage FROM reports "
                "ORDER BY created_at DESC, id LIMIT %s", (limit,))
            rows = cur.fetchall()
        keys = ("report_id", "created_at", "vertical_id", "lat", "lon",
                "address", "opportunity_score", "data_coverage")
        return [dict(zip(keys, r)) for r in rows]

    def save_profile(self, profile: dict[str, Any], created_at: float) -> str:
        profile_id = uuid.uuid4().hex[:16]
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO profiles VALUES (%s,%s,%s,%s,%s)",
                (profile_id, created_at, profile.get("name", ""),
                 profile["vertical_id"],
                 json.dumps(profile, ensure_ascii=False)))
        return profile_id

    def get_profile(self, profile_id: str) -> Optional[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT payload, created_at FROM profiles WHERE id = %s",
                        (profile_id,))
            row = cur.fetchone()
        if row is None:
            return None
        doc = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        doc["profile_id"] = profile_id
        doc["created_at"] = row[1]
        return doc

    def list_profiles(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, name, vertical_id FROM profiles "
                "ORDER BY created_at DESC, id LIMIT %s", (limit,))
            rows = cur.fetchall()
        keys = ("profile_id", "created_at", "name", "vertical_id")
        return [dict(zip(keys, r)) for r in rows]

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
        assert self.get_report(rid) is not None
        self.put_cached_signals("scb", "selftest", {"income_index": (100.0, 0.7)}, time.time())
        assert "income_index" in self.get_cached_signals("scb", "selftest")
        print("PostgresStore selftest OK")
