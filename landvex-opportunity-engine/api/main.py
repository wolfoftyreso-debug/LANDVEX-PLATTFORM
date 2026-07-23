"""LANDVEX Opportunity Engine – produktions-API (FastAPI).

Körs efter `pip install -r requirements.txt`:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Motorimporten är beroendefri; endast API-lagret kräver FastAPI.
För en beroendefri utvecklingsserver, se api/dev_server.py.
"""
from __future__ import annotations

import os
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine.datasources.adapters import production_sources
from engine.datasources.base import Resolver
from engine.datasources.cache import CachedSource
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.profile import profile_from_dict, profile_options
from engine.scan import scan
from engine.scoring import analyze
from engine.storage.sqlite import SqliteStore
from engine.verticals import VERTICALS

app = FastAPI(title="LANDVEX Opportunity Engine", version="0.4.0")

# Persistens: LANDVEX_DB = sökväg (default landvex.db) eller "off".
# I produktion ersätts SqliteStore av PostgresStore (Aurora + PostGIS)
# via LANDVEX_PG_DSN – samma gränssnitt.
_DB = os.environ.get("LANDVEX_DB", "landvex.db")
_PG_DSN = os.environ.get("LANDVEX_PG_DSN", "")
if _PG_DSN:
    from engine.storage.postgres import PostgresStore
    STORE = PostgresStore(_PG_DSN)
elif _DB.lower() not in ("off", "0", ""):
    STORE = SqliteStore(_DB)
else:
    STORE = None

# Verkliga källor först (cachade med TTL per källa om persistens finns),
# mock som fallback per signal. LANDVEX_LIVE=0 stänger av live-källor.
_LIVE = os.environ.get("LANDVEX_LIVE", "1") != "0"
_sources = production_sources() if _LIVE else []
if STORE is not None:
    _sources = [CachedSource(s, STORE) for s in _sources]
RESOLVER = Resolver(_sources + [MockSource()])


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    vertical: str
    address: str = ""
    radius_minutes: int = Field(10, ge=1, le=60)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/verticals")
def verticals():
    return [{"id": v.id, "label_sv": v.label_sv,
             "factors": [{"id": f.id, "label_sv": f.label_sv, "weight": f.weight}
                         for f in v.factors]}
            for v in VERTICALS.values()]


@app.post("/v1/analyze")
def analyze_location(req: AnalyzeRequest):
    if req.vertical not in VERTICALS:
        raise HTTPException(status_code=422,
                            detail=f"Okänd vertikal: {req.vertical}")
    loc = Location(lat=req.lat, lon=req.lon, address=req.address,
                   radius_minutes=req.radius_minutes)
    report = analyze(loc, req.vertical, resolver=RESOLVER).to_dict()
    if STORE is not None:
        report["report_id"] = STORE.save_report(report, created_at=time.time())
    return report


class ScanRequest(BaseModel):
    profile: dict | None = None      # inline-profil ...
    profile_id: str | None = None    # ... eller sparad profil
    top_n: int = Field(5, ge=1, le=20)


@app.get("/v1/profile-options")
def get_profile_options():
    return profile_options()


@app.post("/v1/profiles")
def save_profile(profile: dict):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistens avstängd (LANDVEX_DB=off).")
    try:
        p = profile_from_dict(profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"profile_id": STORE.save_profile(p.to_dict(), created_at=time.time())}


@app.get("/v1/profiles")
def list_profiles(limit: int = 50):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistens avstängd (LANDVEX_DB=off).")
    return STORE.list_profiles(min(max(limit, 1), 200))


@app.get("/v1/profiles/{profile_id}")
def get_profile(profile_id: str):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistens avstängd (LANDVEX_DB=off).")
    doc = STORE.get_profile(profile_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Okänd profil.")
    return doc


@app.post("/v1/scan")
def scan_sweden(req: ScanRequest):
    if req.profile is None and req.profile_id is None:
        raise HTTPException(status_code=422,
                            detail="Ange profile (inline) eller profile_id (sparad).")
    raw = req.profile
    if raw is None:
        if STORE is None:
            raise HTTPException(status_code=503, detail="Persistens avstängd (LANDVEX_DB=off).")
        raw = STORE.get_profile(req.profile_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Okänd profil.")
    try:
        p = profile_from_dict(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return scan(p, resolver=RESOLVER, top_n=req.top_n)


@app.get("/v1/reports")
def list_reports(limit: int = 20):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistens avstängd (LANDVEX_DB=off).")
    return STORE.list_reports(min(max(limit, 1), 200))


@app.get("/v1/reports/{report_id}")
def get_report(report_id: str):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistens avstängd (LANDVEX_DB=off).")
    doc = STORE.get_report(report_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Okänt rapport-id.")
    return doc
