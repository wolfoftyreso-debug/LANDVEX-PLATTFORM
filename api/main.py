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
from typing import Any
from pydantic import BaseModel, Field

from api.health import build_health, source_status
from api.licensing import plans_catalog, upgrade_hint_en
from api.security import AuthError, Gate
from integrations.aamos import (AamosClient, agent_chat_safe,
                                agents as aamos_agents,
                                cognition_brief_safe,
                                platform_status, watch)

from engine.datasources.adapters import production_sources
from engine.datasources.base import Resolver
from engine.datasources.cache import CachedSource
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.profile import profile_from_dict, profile_options
from engine.scan import SCAN_LEVEL_OPTIONS, SCAN_LEVELS, scan
from engine.scoring import analyze
from engine.ask import ask
from engine.kpi import evaluate as evaluate_kpi, kpi_catalog
from engine.lambda_index import lambda_score
from engine.setpoints import assess_zone, catalog as setpoints_catalog
from engine.claims import build_claim, cite, validate_governance, verify as verify_claim
from engine.feeds import catalog as feeds_catalog, generate as generate_feed
from engine.worthiness import select_for_wrap
from engine.decision import (crisis_scan, evaluate as decision_evaluate,
                             templates as decision_templates)
from engine.strim import (build_entity, cite as strim_cite, entity_types,
                          to_jsonld)
from engine.datasources.kolada import KoladaClient
from engine.datasources.svk import SvkClient
from engine.outcomes import (calibration as outcome_calibration,
                             expected_roi, log_outcome, record as record_outcome,
                             set_store as set_outcome_store)
from engine.integrity import classify_query
from engine.compare import compare
from engine.gaps import gap_analysis
from engine.markets import DEFAULT_MARKET, market_catalog
from engine.indices import city_assessment, index_catalog, index_map
from engine.installed_base import (product_catalog, service_analysis,
                                   service_demand_map)
from engine.plan import establishment_plan
from engine.report import decision_report
from engine.opportunity_intel import opportunity_intel
from engine.risk import assess
from engine.risk_intel import risk_intelligence
from engine.segments import segment_analysis, segment_catalog, segment_map
from engine.storage.sqlite import SqliteStore
from engine.verticals import VERTICALS
from engine.workforce import (forecast as wf_forecast, global_map,
                              national_map, occupation_catalog,
                              simulate as wf_simulate)

app = FastAPI(title="LANDVEX Opportunity Engine", version="1.1.0")

# CORS only when the frontend is served from a different origin than the API.
# Same-origin deploys (nginx serves both) leave LANDVEX_CORS_ORIGINS unset.
_CORS = [o.strip() for o in os.environ.get("LANDVEX_CORS_ORIGINS", "").split(",")
         if o.strip()]
if _CORS:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=_CORS,
                       allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-API-Key",
                                      "Authorization"])

_OPEN_PATHS = ("/", "/index.html", "/health", "/docs", "/openapi.json",
               "/v1/plans")


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
            request.headers.get("X-API-Key")
            or request.headers.get("Authorization"), request.method, path)
        request.state.principal = principal
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except AuthError as e:
        status = e.status
        return JSONResponse({"error": e.message_en}, status_code=e.status,
                            headers={"X-Request-ID": request_id})
    finally:
        GATE.exit(principal, request_id, request.method, path,
                  status, (time.monotonic() - t0) * 1000)


@app.get("/metrics")
def metrics(format: str = "json"):
    kallor = source_status(RESOLVER)
    if format == "prometheus":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(GATE.metrics.to_prometheus(kallor))
    snap = GATE.metrics.snapshot()
    snap["rate_limit_per_min"] = GATE.limiter.capacity
    snap["kallor"] = kallor
    return snap


@app.get("/v1/audit")
def audit(limit: int = 100):
    return GATE.audit.tail(limit)


@app.get("/v1/agent-manifest")
def agent_manifest():
    from api.agent_manifest import AGENT_MANIFEST
    return AGENT_MANIFEST

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

# Backa utfallskalibreringen med lagret (överlever omstart + delas över
# workers). Utan store faller den ärligt tillbaka på process-minne.
set_outcome_store(STORE)

# Gate delar lagret så månadskvoten överlever omstarter (om DB på).
GATE = Gate(store=STORE)

# Verkliga källor först (cachade med TTL per källa om persistens finns),
# mock som fallback per signal. LANDVEX_LIVE=0 stänger av live-källor.
_LIVE = os.environ.get("LANDVEX_LIVE", "1") != "0"
_sources = production_sources() if _LIVE else []
if STORE is not None:
    _sources = [CachedSource(s, STORE) for s in _sources]
RESOLVER = Resolver(_sources + [MockSource()])
from engine.datasources.programs import ProgramsClient
PROGRAMS = ProgramsClient()   # connected only if LANDVEX_PROGRAMS_URL is set


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    vertical: str
    address: str = ""
    radius_minutes: int = Field(10, ge=1, le=60)


@app.get("/health")
def health():
    return build_health(RESOLVER, STORE)


@app.get("/v1/verticals")
def verticals():
    return [{"id": v.id, "label_en": v.label_en,
             "factors": [{"id": f.id, "label_en": f.label_en, "weight": f.weight}
                         for f in v.factors]}
            for v in VERTICALS.values()]


@app.post("/v1/analyze")
def analyze_location(req: AnalyzeRequest):
    if req.vertical not in VERTICALS:
        raise HTTPException(status_code=422,
                            detail=f"Unknown vertical: {req.vertical}")
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
    market: str = DEFAULT_MARKET


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
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    try:
        p = profile_from_dict(profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"profile_id": STORE.save_profile(p.to_dict(), created_at=time.time())}


@app.get("/v1/profiles")
def list_profiles(limit: int = 50):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    return STORE.list_profiles(min(max(limit, 1), 200))


@app.get("/v1/profiles/{profile_id}")
def get_profile(profile_id: str):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    doc = STORE.get_profile(profile_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown profile.")
    return doc


@app.post("/v1/scan")
def scan_sweden(req: ScanRequest):
    if req.profile is None and req.profile_id is None:
        raise HTTPException(status_code=422,
                            detail="Provide profile (inline) or profile_id (saved).")
    raw = req.profile
    if raw is None:
        if STORE is None:
            raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
        raw = STORE.get_profile(req.profile_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Unknown profile.")
    if req.level not in SCAN_LEVELS:
        raise HTTPException(status_code=422,
                            detail=f"Unknown analysis level: {req.level}.")
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
    market: str = DEFAULT_MARKET


class SimulateRequest(BaseModel):
    kommun_kod: str
    occupation_id: str
    extra_places_per_year: float = Field(..., ge=0)
    target_year: int = 2035
    market: str = DEFAULT_MARKET


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
        # Krisgrind går FÖRE motordata: suicid/självskada → nödresurser.
        kris = crisis_scan(req.question)   # autodetekterar språk/land
        if kris:
            return kris
        svar = ask(req.question, resolver=RESOLVER)
        # Integritetsgrind (skördat lager E): flagga icke-neutrala frågor
        # ärligt utan att blockera motorsvaret – förklarbarhet, inte censur.
        block = classify_query(req.question)
        if block:
            svar["neutrality"] = block
        return svar
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


class OpportunitiesRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    vertical: str
    address: str = ""
    specialization: str | None = None
    team_size: str = "1"
    company_form: str = "aktiebolag"
    market: str = DEFAULT_MARKET


@app.post("/v1/opportunities")
def opportunities(req: OpportunitiesRequest):
    try:
        return opportunity_intel(
            Location(lat=req.lat, lon=req.lon, address=req.address),
            req.vertical, resolver=RESOLVER,
            specialization=req.specialization, team_size=req.team_size,
            company_form=req.company_form, market=req.market,
            programs_client=PROGRAMS)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class RiskIntelRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    vertical: str
    address: str = ""
    specialization: str | None = None
    market: str = DEFAULT_MARKET


@app.post("/v1/risk-intelligence")
def risk_intel_ep(req: RiskIntelRequest):
    try:
        return risk_intelligence(
            Location(lat=req.lat, lon=req.lon, address=req.address),
            req.vertical, resolver=RESOLVER,
            specialization=req.specialization, market=req.market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class GapRequest(BaseModel):
    vertical: str
    market: str = DEFAULT_MARKET
    top_n: int = Field(5, ge=1, le=20)


class PlanRequest(BaseModel):
    kommun_kod: str
    vertical: str
    market: str = DEFAULT_MARKET
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


# --- Skördade lager: KPI-motor + Lambda-index -----------------------------
class KpiEvalRequest(BaseModel):
    code: str
    value: float
    previous: float | None = None


class LambdaRequest(BaseModel):
    axes: dict[str, float]


@app.get("/v1/kpi")
def kpi_registry():
    return kpi_catalog()


@app.post("/v1/kpi/evaluate")
def kpi_evaluate(req: KpiEvalRequest):
    try:
        return evaluate_kpi(req.code, req.value, req.previous)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/lambda")
def lambda_ep(req: LambdaRequest):
    return lambda_score(req.axes)


class SetpointRequest(BaseModel):
    code: str
    value: float


@app.get("/v1/setpoints")
def setpoints_registry():
    return setpoints_catalog()


@app.post("/v1/setpoints/assess")
def setpoints_assess(req: SetpointRequest):
    try:
        return assess_zone(req.code, req.value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class CiteRequest(BaseModel):
    statement: str
    value: Any = None
    unit: str = ""
    source: dict = Field(default_factory=dict)
    jurisdiction: dict = Field(default_factory=dict)
    time: dict = Field(default_factory=dict)
    owners: dict = Field(default_factory=dict)
    method: str = "observed"
    uncertainty: str = ""


def _cite_response(req: "CiteRequest") -> dict:
    claim = build_claim(req.statement, req.value, req.source, req.jurisdiction,
                        req.time, unit=req.unit, method=req.method,
                        uncertainty=req.uncertainty, owners=req.owners)
    ok, missing = validate_governance(claim)
    return {"claim": claim,
            "citations": {s: cite(claim, s) for s in ("text", "apa", "bibtex")},
            "governance": {"ok": ok, "missing": missing},
            "verified": verify_claim(claim)}


@app.post("/v1/cite")
def cite_ep(req: CiteRequest):
    return _cite_response(req)


class FeedEventsRequest(BaseModel):
    feed: str
    rows: list[dict] = Field(default_factory=list)


class WorthinessRequest(BaseModel):
    snapshots: list[dict] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    template: str
    answers: dict = Field(default_factory=dict)


@app.get("/v1/feeds")
def feeds_registry():
    return feeds_catalog()


@app.post("/v1/feeds/events")
def feeds_events(req: FeedEventsRequest):
    try:
        return {"events": generate_feed(req.feed, req.rows)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/worthiness")
def worthiness_ep(req: WorthinessRequest):
    return select_for_wrap(req.snapshots)


@app.get("/v1/decision")
def decision_registry():
    return decision_templates()


@app.post("/v1/decision")
def decision_ep(req: DecisionRequest):
    try:
        return decision_evaluate(req.template, req.answers)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class StrimEntityRequest(BaseModel):
    entity_type: str
    slug: str
    name_en: str
    name_sv: str = ""
    definition: str = ""
    sources: list = Field(default_factory=list)
    fields: dict = Field(default_factory=dict)


@app.get("/v1/strim")
def strim_registry():
    return entity_types()


@app.post("/v1/strim/entity")
def strim_entity(req: StrimEntityRequest):
    try:
        ent = build_entity(req.entity_type, req.slug, req.name_en,
                           name_sv=req.name_sv, definition=req.definition,
                           sources=req.sources, fields=req.fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"entity": ent, "jsonld": to_jsonld(ent),
            "citations": {s: strim_cite(ent, s) for s in ("text", "apa", "bibtex")}}


@app.get("/v1/kolada")
def kolada_status():
    return KoladaClient().status()


@app.get("/v1/svk")
def svk_status():
    return SvkClient().status()


class OutcomeRequest(BaseModel):
    location: dict = Field(default_factory=dict)
    vertical: str
    predicted_score: float
    survived: bool
    months_active: int = 0
    revenue_index: float | None = None
    established_at: str = ""


class RoiRequest(BaseModel):
    score: float


@app.post("/v1/outcomes")
def outcomes_log(req: OutcomeRequest):
    rec = log_outcome(req.location, req.vertical, req.predicted_score,
                      req.survived, months_active=req.months_active,
                      revenue_index=req.revenue_index,
                      established_at=req.established_at)
    return {"id": record_outcome(rec), "calibration": outcome_calibration()}


@app.get("/v1/outcomes/calibration")
def outcomes_calibration():
    return outcome_calibration()


@app.post("/v1/outcomes/roi")
def outcomes_roi(req: RoiRequest):
    return expected_roi(req.score)


class SegmentAnalyzeRequest(BaseModel):
    kommun_kod: str
    market: str = DEFAULT_MARKET


class ServiceAnalyzeRequest(BaseModel):
    kommun_kod: str
    market: str = DEFAULT_MARKET
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
def service_map(product_id: str, market: str = DEFAULT_MARKET,
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
def segments_map(segment_id: str, market: str = DEFAULT_MARKET):
    try:
        return segment_map(segment_id, market=market, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class AssessRequest(BaseModel):
    kommun_kod: str
    market: str = DEFAULT_MARKET


@app.get("/v1/plans")
def plans():
    return plans_catalog()


@app.get("/v1/entitlements")
def entitlements(request: Request):
    p = request.state.principal
    return {"tenant": p.tenant, "roll": p.role, "plan": p.plan,
            "tillagg": list(p.addons),
            "capabilities": sorted(p.capabilities)}


AAMOS = AamosClient()


@app.get("/v1/platform/status")
def platform_status_ep():
    return platform_status(AAMOS, RESOLVER, STORE,
                           build_health, source_status)


@app.get("/v1/watch")
def watch_ep():
    return watch(AAMOS, RESOLVER, source_status)


@app.get("/v1/agents")
def agents_ep():
    return aamos_agents(AAMOS)


class AgentChatIn(BaseModel):
    message: str
    agent_id: str | None = None


@app.post("/v1/agents/chat")
def agents_chat_ep(body: AgentChatIn):
    return agent_chat_safe(AAMOS, body.message, body.agent_id)


class BriefIn(BaseModel):
    topic: str


class ReportIn(BaseModel):
    kommun_kod: str
    vertical: str
    market: str = DEFAULT_MARKET


@app.post("/v1/report")
def report_ep(body: ReportIn, request: Request):
    rep = decision_report(body.kommun_kod, body.vertical,
                          market=body.market, resolver=RESOLVER)
    p = getattr(request.state, "principal", None)
    if p is not None and "demand_intelligence" not in p.capabilities:
        rep["service"] = {"status": "locked",
                          "notis_en": upgrade_hint_en("demand_intelligence")}
    return rep


@app.post("/v1/cognition/brief")
def cognition_brief_ep(body: BriefIn):
    return cognition_brief_safe(AAMOS, body.topic)


def _live_locked(request: Request) -> bool:
    p = getattr(request.state, "principal", None)
    return p is not None and "intelligence_map_live" not in p.capabilities


@app.get("/v1/indices")
def indices(request: Request):
    kat = index_catalog()
    if _live_locked(request):
        for ix in kat:
            if ix["niva"] == "live":
                ix["last"] = True
                ix["las_notis_en"] = upgrade_hint_en("intelligence_map_live")
    return kat


@app.get("/v1/indices/map")
def indices_map(request: Request, index_id: str, market: str = DEFAULT_MARKET):
    from engine.indices import INDEX_TYPES
    ix = INDEX_TYPES.get(index_id)
    if ix and ix.niva == "live" and _live_locked(request):
        raise HTTPException(status_code=403,
                            detail="Live layers require a subscription. "
                                   + upgrade_hint_en("intelligence_map_live"))
    try:
        return index_map(index_id, market=market, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/v1/indices/assess")
def indices_assess(request: Request, req: AssessRequest):
    try:
        res = city_assessment(req.kommun_kod, market=req.market,
                              resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if _live_locked(request):
        for row in res["index"]:
            if row["niva"] == "live":
                row.update({"varde": None, "band": None, "band_en": None,
                            "drivare": [], "last": True,
                            "narrativ_en": "Live layer – requires a subscription. "
                            + upgrade_hint_en("intelligence_map_live")})
    return res


@app.get("/v1/catalog")
def api_catalog():
    from api.catalog import API_CATALOG
    return API_CATALOG


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
                  market: str = DEFAULT_MARKET):
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
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    return STORE.list_reports(min(max(limit, 1), 200))


@app.get("/v1/reports/{report_id}")
def get_report(report_id: str):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    doc = STORE.get_report(report_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown report id.")
    return doc
