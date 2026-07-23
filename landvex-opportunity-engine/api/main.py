"""LANDVEX Opportunity Engine – produktions-API (FastAPI).

Körs efter `pip install -r requirements.txt`:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Motorimporten är beroendefri; endast API-lagret kräver FastAPI.
För en beroendefri utvecklingsserver, se api/dev_server.py.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from api.security import AuthError, Gate

from engine.datasources.adapters import production_sources
from engine.datasources.base import Resolver
from engine.datasources.cache import CachedSource
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.profile import profile_from_dict, profile_options
from engine.scan import SCAN_LEVEL_OPTIONS, SCAN_LEVELS, scan
from engine.scoring import analyze
from engine.ask import ask
from engine.compare import compare
from engine.gaps import gap_analysis
from engine.markets import market_catalog
from engine.installed_base import (product_catalog, service_analysis,
                                   service_demand_map)
from engine.plan import establishment_plan
from engine.risk import assess
from engine.segments import segment_analysis, segment_catalog, segment_map
from engine.storage.sqlite import SqliteStore
from engine.verticals import VERTICALS
from engine.workforce import (forecast as wf_forecast, global_map,
                              national_map, occupation_catalog,
                              simulate as wf_simulate)

app = FastAPI(title="LANDVEX Opportunity Engine", version="0.9.0")

GATE = Gate()
_OPEN_PATHS = ("/", "/index.html", "/health", "/docs", "/openapi.json")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Auth → rate limit → routning → metrics + audit (se api/security.py)."""
    path = request.url.path
    if path in _OPEN_PATHS:
        return await call_next(request)
    t0 = time.monotonic()
    principal, request_id, status = None, "-", 500
    try:
        principal, request_id = GATE.enter(
            request.headers.get("X-API-Key"), request.method, path)
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except AuthError as e:
        status = e.status
        return JSONResponse({"error": e.message_sv}, status_code=e.status,
                            headers={"X-Request-ID": request_id})
    finally:
        GATE.exit(principal, request_id, request.method, path,
                  status, (time.monotonic() - t0) * 1000)


@app.get("/metrics")
def metrics():
    snap = GATE.metrics.snapshot()
    snap["rate_limit_per_min"] = GATE.limiter.capacity
    return snap

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
    level: str = "oversikt"
    market: str = "se"


_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(_FRONTEND, media_type="text/html")


@app.get("/v1/profile-options")
def get_profile_options():
    return {**profile_options(), "scan_levels": SCAN_LEVEL_OPTIONS}


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
    if req.level not in SCAN_LEVELS:
        raise HTTPException(status_code=422,
                            detail=f"Okänd analysnivå: {req.level}.")
    try:
        p = profile_from_dict(raw)
        return scan(p, resolver=RESOLVER, top_n=req.top_n, level=req.level,
                    market=req.market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class ForecastRequest(BaseModel):
    kommun_kod: str
    target_year: int = 2035
    occupation_ids: list[str] | None = None
    market: str = "se"


class SimulateRequest(BaseModel):
    kommun_kod: str
    occupation_id: str
    extra_places_per_year: float = Field(..., ge=0)
    target_year: int = 2035
    market: str = "se"


class RiskRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    vertical: str
    address: str = ""
    radius_minutes: int = Field(10, ge=1, le=60)


class CompareRequest(BaseModel):
    vertical: str
    locations: list[dict]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


@app.post("/v1/ask")
def ask_landvex(req: AskRequest):
    try:
        return ask(req.question, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/risk")
def risk_profile(req: RiskRequest):
    try:
        return assess(Location(lat=req.lat, lon=req.lon, address=req.address,
                               radius_minutes=req.radius_minutes),
                      req.vertical, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/compare")
def compare_locations(req: CompareRequest):
    try:
        return compare(req.locations, req.vertical, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class GapRequest(BaseModel):
    vertical: str
    market: str = "se"
    top_n: int = Field(5, ge=1, le=20)


class PlanRequest(BaseModel):
    kommun_kod: str
    vertical: str
    market: str = "se"
    team_size: str = "2-5"
    budget_band: str = "500k-2m"


@app.post("/v1/gaps")
def gaps(req: GapRequest):
    try:
        return gap_analysis(req.vertical, market=req.market,
                            resolver=RESOLVER, top_n=req.top_n)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/plan")
def plan(req: PlanRequest):
    try:
        return establishment_plan(req.kommun_kod, req.vertical,
                                  market=req.market, team_size=req.team_size,
                                  budget_band=req.budget_band,
                                  resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class SegmentAnalyzeRequest(BaseModel):
    kommun_kod: str
    market: str = "se"


class ServiceAnalyzeRequest(BaseModel):
    kommun_kod: str
    market: str = "se"
    target_year: int = 2031


@app.get("/v1/products")
def products():
    return product_catalog()


@app.post("/v1/service/analyze")
def service_analyze(req: ServiceAnalyzeRequest):
    try:
        return service_analysis(req.kommun_kod, market=req.market,
                                target_year=req.target_year,
                                resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/v1/service/map")
def service_map(product_id: str, market: str = "se",
                target_year: int = 2031):
    try:
        return service_demand_map(product_id, market=market,
                                  target_year=target_year, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/v1/segments")
def segments():
    return segment_catalog()


@app.post("/v1/segments/analyze")
def segments_analyze(req: SegmentAnalyzeRequest):
    try:
        return segment_analysis(req.kommun_kod, market=req.market,
                                resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/v1/segments/map")
def segments_map(segment_id: str, market: str = "se"):
    try:
        return segment_map(segment_id, market=market, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/v1/markets")
def markets():
    return market_catalog()


@app.get("/v1/workforce/occupations")
def workforce_occupations():
    return occupation_catalog()


@app.post("/v1/workforce/forecast")
def workforce_forecast(req: ForecastRequest):
    try:
        return wf_forecast(req.kommun_kod, req.target_year,
                           req.occupation_ids, resolver=RESOLVER,
                           market=req.market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/workforce/simulate")
def workforce_simulate(req: SimulateRequest):
    try:
        return wf_simulate(req.kommun_kod, req.occupation_id,
                           req.extra_places_per_year, req.target_year,
                           resolver=RESOLVER, market=req.market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/v1/workforce/map")
def workforce_map(occupation_id: str, target_year: int = 2035,
                  market: str = "se"):
    try:
        return national_map(occupation_id, target_year, resolver=RESOLVER,
                            market=market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/v1/workforce/global-map")
def workforce_global_map(occupation_id: str, target_year: int = 2035,
                         group: str = "eu"):
    try:
        return global_map(occupation_id, target_year, group=group,
                          resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
