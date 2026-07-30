"""LANDVEX Opportunity Engine – produktions-API (FastAPI).

Körs efter `pip install -r requirements.txt`:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Motorimporten är beroendefri; endast API-lagret kräver FastAPI.
För en beroendefri utvecklingsserver, se api/dev_server.py.
"""
from __future__ import annotations

import os
import sys
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
from engine.accountability import (all_decisions as accountability_all_decisions,
                                   commit as commit_decision, get_decision,
                                   ledger as accountability_ledger,
                                   resolve as resolve_decision,
                                   set_store as set_accountability_store)
from engine.correlate import cross_domain, cross_market, partial_correlation
from engine import inbox as inbox_engine
from engine.brief import catalog as brief_catalog, daily_brief, report as brief_report
from engine.provenance import parameters as provenance_parameters, summary as provenance_summary
from engine.offering import offering
from engine.chain import chain_overview
from engine.surface import surface
from engine.sensors import catalog as sensor_catalog
from engine.corroboration import (assess as corroboration_assess,
                                  catalog as corroboration_cat)
from engine.registers import RegisterClient, register_catalog
from engine.livability import HOUSEHOLDS
from engine.livability_scan import livability_ranking
from engine.merit_scan import market_merit, region_merit
from engine.saturation_scan import market_saturation
from engine import customer as customer_engine
from engine import visitor as visitor_engine
from engine import monitors as monitors_engine
from engine.monitors import set_store as set_monitors_store
from engine import inspections as _insp
from engine import scheduler as _sched
from engine import harvest as _harvest
from engine import news as _news
from engine import company as _company
from engine import connections as _connections
from engine import credentials as _credentials
from engine import deliveries as _deliveries
from engine import leads as _leads
from engine import sponsorship as _sponsorship
from engine import staff as _staff
from engine.scenario import project as scenario_project
from engine.eventstudy import before_after, diff_in_diff
from engine.benchmark import benchmark
from engine.sensitive import sensitive_association
from engine.wages import (compare as wage_compare, compensation_context, wage,
                          wage_catalog)
from engine.corrections import (adapt as adapt_correction,
                                consensus as correction_consensus,
                                set_store as set_corrections_store,
                                submit as submit_correction)
from engine.integrity import classify_query
from engine.compare import compare
from engine.gaps import gap_analysis
from engine.markets import DEFAULT_MARKET, market_catalog
from engine.indices import (city_assessment, index_catalog, index_families,
                            index_map)
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

_OPEN_PATHS = ("/", "/console", "/demo", "/explore", "/index.html", "/sandbox",
               "/health", "/docs", "/openapi.json", "/v1/plans",
               "/v1/company/logo/raw")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Auth → rate limit → routning → metrics + audit (se api/security.py)."""
    path = request.url.path
    if path in _OPEN_PATHS:
        # Öppna vägar går utanför Gate — auth och kvot på "/" hade brutit
        # dörren. Men METRIKEN ska se dem: före den här raden fanns tio
        # vägar som inte lämnade något spår alls i /metrics, och en
        # driftbild där startsidan inte existerar är gladare än
        # verkligheten. Ingen audit-rad: anonym HTML är brus i en
        # säkerhetslogg, och det är ett medvetet val, inte ett hål.
        t0 = time.monotonic()
        response = await call_next(request)
        GATE.metrics.observe(path, response.status_code,
                             (time.monotonic() - t0) * 1000)
        return response
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


def _tenant(request: Request) -> str:
    """Vilken kund frågan kommer från. Lagret KRÄVER den — ett argument
    man kan glömma är en läcka som väntar på att hända."""
    p = getattr(request.state, "principal", None)
    return p.tenant if p is not None else "dev"


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

# Backa utfallskalibreringen + ansvarsloopen med lagret (överlever omstart +
# delas över workers). Utan store faller de ärligt tillbaka på process-minne.
set_outcome_store(STORE)
set_accountability_store(STORE)
set_corrections_store(STORE)
set_monitors_store(STORE)
# Kontrollregistret måste ligga i lagret här också, inte bara i
# dev-servern: det är produktionsvägen, och ett efterlevnadsregister som
# bara finns i processminnet är borta vid nästa omstart — precis det
# register som ska gå att visa ett år senare.
_insp.set_store(STORE)
# Schemalagda jobb överlever omstart OCH claimas i lagret — utan det
# kör två workers samma jobb och kunden får två beställda uppdrag för
# samma objekt.
_sched.set_store(STORE)
# Skörden och frågan måste dela lager, annars läser
# förfrågningsvägen en tom tabell och svarar mock.
_harvest.set_store(STORE)
_news.set_store(STORE)
# Budget som nollställs vid omstart är en budget som kan överskridas.
_sponsorship.set_store(STORE)
_connections.set_store(STORE)
_company.set_store(STORE)
_credentials.set_store(STORE)
_staff.set_store(STORE)
_deliveries.set_store(STORE)
_leads.set_store(STORE)


def _med_credential(rec: dict, kind: str, subject: dict, *,
                    tenant: str, mission_id: str) -> dict:
    """Samma regel som dev-servern: godkänt utfall får sitt signerade
    kvitto + leveransförsöket till kundens system, båda redovisade;
    en vägran redovisas i stället för att fälla anropet."""
    from engine import connections as CN
    from integrations import feedback
    ut = dict(rec)
    try:
        cred = _credentials.issue(kind, subject, tenant=tenant,
                                  mission_id=mission_id)
    except _credentials.CredentialRefused as e:
        ut["credential"] = None
        ut["credential_refused_en"] = str(e)
        return ut
    ut["credential"] = cred
    ut["feedback"] = feedback.forward(cred, CN.feedback_target(tenant))
    return ut

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


@app.on_event("startup")
def _start_scheduler() -> None:
    """Väck schemaläggaren vid uppstart, inte vid import.

    Uvicorn importerar modulen i varje worker. Startade tråden vid import
    skulle N workers köra samma jobb — jobbet claimas visserligen i lagret,
    men en tråd per worker som väcks av en modulimport är fel ordning på
    orsak och verkan. Avstängd om inte LANDVEX_SCHEDULER=on.
    """
    warning = GATE.auth.open_mode_warning(
        os.environ.get("LANDVEX_HOST", "0.0.0.0"))
    if warning:
        print(warning, file=sys.stderr)
    from api.ticker import start
    start()


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
def analyze_location(req: AnalyzeRequest, request: Request):
    if req.vertical not in VERTICALS:
        raise HTTPException(status_code=422,
                            detail=f"Unknown vertical: {req.vertical}")
    loc = Location(lat=req.lat, lon=req.lon, address=req.address,
                   radius_minutes=req.radius_minutes)
    report = analyze(loc, req.vertical, resolver=RESOLVER).to_dict()
    if STORE is not None:
        report["report_id"] = STORE.save_report(
            report, created_at=time.time(), tenant=_tenant(request))
    return report


class ScanRequest(BaseModel):
    profile: dict | None = None      # inline-profil ...
    profile_id: str | None = None    # ... eller sparad profil
    top_n: int = Field(5, ge=1, le=20)
    level: str = "oversikt"
    market: str = DEFAULT_MARKET


_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
_SANDBOX = Path(__file__).resolve().parent.parent / "frontend" / "sandbox.html"
# Dörren. Konsolen med nio flikar ligger kvar oförändrad på /console.
_START = Path(__file__).resolve().parent.parent / "frontend" / "start.html"
# Demosystemet: sex bevis, alla hämtade från det körande API:t.
_DEMO = Path(__file__).resolve().parent.parent / "frontend" / "demo.html"
# Ytan för den som INTE kan området: riktiga platser, riktiga tal.
_EXPLORE = Path(__file__).resolve().parent.parent / "frontend" / "explore.html"


@app.get("/", include_in_schema=False)
def front_door():
    """En fråga och fyra löften. Konsolen ligger på /console."""
    return FileResponse(_START, media_type="text/html")


@app.get("/explore", include_in_schema=False)
def explore_page():
    """Riktiga platser och tal, för den som inte kan området."""
    return FileResponse(_EXPLORE, media_type="text/html")


@app.get("/demo", include_in_schema=False)
def demo_page():
    """Sex bevis, alla hämtade live. Se frontend/demo.html."""
    return FileResponse(_DEMO, media_type="text/html")


@app.get("/console", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def frontend():
    return FileResponse(_FRONTEND, media_type="text/html")


@app.get("/sandbox", include_in_schema=False)
def sandbox_page():
    return FileResponse(_SANDBOX, media_type="text/html")


@app.get("/v1/profile-options")
def get_profile_options():
    return {**profile_options(), "scan_levels": SCAN_LEVEL_OPTIONS}


@app.post("/v1/profiles")
def save_profile(profile: dict, request: Request):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    try:
        p = profile_from_dict(profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"profile_id": STORE.save_profile(
        p.to_dict(), created_at=time.time(), tenant=_tenant(request))}


@app.get("/v1/profiles")
def list_profiles(request: Request, limit: int = 50):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    return STORE.list_profiles(min(max(limit, 1), 200),
                               tenant=_tenant(request))


@app.get("/v1/profiles/{profile_id}")
def get_profile(profile_id: str, request: Request):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    doc = STORE.get_profile(profile_id, tenant=_tenant(request))
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown profile.")
    return doc


@app.post("/v1/scan")
def scan_sweden(req: ScanRequest, request: Request):
    if req.profile is None and req.profile_id is None:
        raise HTTPException(status_code=422,
                            detail="Provide profile (inline) or profile_id (saved).")
    raw = req.profile
    if raw is None:
        if STORE is None:
            raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
        raw = STORE.get_profile(req.profile_id, tenant=_tenant(request))
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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/risk")
def risk_profile(req: RiskRequest):
    try:
        return assess(Location(lat=req.lat, lon=req.lon, address=req.address,
                               radius_minutes=req.radius_minutes),
                      req.vertical, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/compare")
def compare_locations(req: CompareRequest):
    try:
        return compare(req.locations, req.vertical, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/plan")
def plan(req: PlanRequest):
    try:
        return establishment_plan(req.kommun_kod, req.vertical,
                                  market=req.market, team_size=req.team_size,
                                  budget_band=req.budget_band,
                                  resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"entity": ent, "jsonld": to_jsonld(ent),
            "citations": {s: strim_cite(ent, s) for s in ("text", "apa", "bibtex")}}


@app.get("/v1/sources")
def sources():
    from api.sources import sources_status
    return sources_status()


@app.get("/v1/entrypoints")
def entrypoints_ep():
    from engine.entrypoints import entrypoints
    return entrypoints()


@app.get("/v1/admin")
def admin_ep(country: str = "", level: int = 1, parent: str = ""):
    from engine.admin import admin_countries, admin_units
    if country:
        try:
            return admin_units(country, level=level, parent=parent)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    return admin_countries()


class FlowsRequest(BaseModel):
    costs: list[dict] = Field(default_factory=list)
    benefits: list[dict] = Field(default_factory=list)
    horizon_years: int = 1
    decision: str = ""
    currency: str = "USD"


@app.post("/v1/flows/expected-value")
def flows_expected_value(req: FlowsRequest):
    from engine.flows import expected_value
    return expected_value(req.costs, req.benefits,
                          horizon_years=req.horizon_years,
                          decision=req.decision, currency=req.currency)


class MonitorDefineRequest(BaseModel):
    metric: str
    scope: str
    rule: str
    owner: str
    params: dict = Field(default_factory=dict)
    cadence: dict = Field(default_factory=dict)
    label: str = ""


class MonitorEvaluateRequest(BaseModel):
    monitor_id: str = ""
    monitor: dict | None = None
    series: list[float] = Field(default_factory=list)
    evaluated_at: float | str = ""


class MonitorRunRequest(BaseModel):
    now: float | str
    series_by_id: dict = Field(default_factory=dict)


class MonitorEscalateRequest(BaseModel):
    finding: dict
    owners: dict = Field(default_factory=dict)
    expected: dict = Field(default_factory=dict)
    committed_at: str = ""
    horizon_months: int = 0


class SubscribeRequest(BaseModel):
    subscriber: str
    role: str = "citizen"
    stakes: list[dict] = Field(default_factory=list)
    min_severity: str = "medium"
    threshold: float = 50.0


class RouteRequest(BaseModel):
    events: list[dict] = Field(default_factory=list)
    findings: list[dict] = Field(default_factory=list)
    feed_events: list[dict] = Field(default_factory=list)
    subscriber: str = ""
    now: float | str = ""


def _collect_events(req) -> list[dict]:
    """Feed-händelser och bevakningsfynd blir samma händelseform."""
    evs = list(req.events)
    evs += [inbox_engine.from_feed_event(e) for e in req.feed_events]
    evs += [inbox_engine.from_finding(f) for f in req.findings]
    return evs


class VisitorRequest(BaseModel):
    payload: dict = Field(default_factory=dict)


@app.get("/v1/visitor/contract")
def visitor_contract():
    return visitor_engine.contract()


@app.post("/v1/visitor")
def visitor_ingest(req: VisitorRequest):
    """Onboarding-post in → besökarprofil, kännedomsnivå och nästa steg."""
    try:
        prof = visitor_engine.from_onboarding(req.payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"profile": prof, "guide": visitor_engine.guide(prof)}


@app.get("/v1/customer/journey")
def customer_journey():
    return customer_engine.journey()


@app.post("/v1/customer/stage")
def customer_stage(req: VisitorRequest):
    """Var i kedjan KYC → onboarding → uppsättning → aktiv kunden står."""
    try:
        return customer_engine.stage(req.payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class SaturationRequest(BaseModel):
    vertical: str
    region: str
    market: str = "se"
    peer_limit: int = 25


class MeritRequest(BaseModel):
    market: str = "se"
    region: str = ""
    top_n: int = 10


@app.post("/v1/merit")
def merit_ep(req: MeritRequest):
    """Which places perform measurably well — and how, and why."""
    try:
        if req.region:
            return region_merit(req.region, market=req.market,
                                resolver=RESOLVER)
        return market_merit(req.market, top_n=min(max(req.top_n, 1), 40),
                            resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


class LivabilityRequest(BaseModel):
    occupation: str
    household: str = "single"
    markets: list[str] = Field(default_factory=lambda: ["se"])
    top_n: int = 10
    per_market: int = 12
    citizenship: str = "eu"


@app.get("/v1/households")
def households_catalog():
    return {"households": [{"id": k, **{x: v[x] for x in
                                        ("label_en", "means_en")},
                            "weights": v["weights"]}
                           for k, v in HOUSEHOLDS.items()]}


@app.post("/v1/livability")
def livability_ep(req: LivabilityRequest):
    """Where can THIS household build a good life — barrier stated first."""
    try:
        return livability_ranking(
            req.occupation, req.household, markets=req.markets,
            top_n=min(max(req.top_n, 1), 40),
            per_market=min(max(req.per_market, 1), 40),
            citizenship=req.citizenship, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class BriefRequest(BaseModel):
    reports: list[dict] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    limit: int = 20
    date: str = ""
    plan: str = ""            # Explorer/Professional/Enterprise – styr scope
    own_assets: bool = False  # endast Enterprise Intelligence


class BriefReportRequest(BaseModel):
    kind: str
    title: str
    summary_en: str
    areas: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    confidence_inputs: dict = Field(default_factory=dict)
    snapshot: dict = Field(default_factory=dict)
    discrepancy_en: str = ""
    options: list[str] = Field(default_factory=list)
    observed_at: str = ""


@app.get("/v1/brief")
def brief_kinds():
    return brief_catalog()


@app.post("/v1/brief")
def brief_ep(req: BriefRequest):
    """Today's brief, scoped and sorted by decision value."""
    try:
        return daily_brief(req.reports, areas=req.areas, sectors=req.sectors,
                           limit=min(max(req.limit, 1), 100), date=req.date,
                           plan=req.plan, own_assets=req.own_assets)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/brief/report")
def brief_report_ep(req: BriefReportRequest):
    """Build one report — rejects a detection kind that has no declared limits."""
    try:
        return brief_report(req.kind, title=req.title,
                            summary_en=req.summary_en, areas=req.areas,
                            sectors=req.sectors or None, evidence=req.evidence,
                            confidence_inputs=req.confidence_inputs,
                            snapshot=req.snapshot,
                            discrepancy_en=req.discrepancy_en,
                            options=req.options or None,
                            observed_at=req.observed_at)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/provenance")
def provenance_ep(cls: str = ""):
    """Where the platform's own numbers come from."""
    try:
        return {**provenance_summary(), "parameters": provenance_parameters(cls)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class CorroborationRequest(BaseModel):
    sources: list[dict] = Field(default_factory=list)


@app.get("/v1/corroboration")
def corroboration_catalog():
    """How independence is judged, and why it is a band not a percentage."""
    return corroboration_cat()


@app.post("/v1/corroboration")
def corroboration_ep(req: CorroborationRequest):
    """How well supported a claim is. Disagreement is its own outcome."""
    return corroboration_assess(req.sources)


@app.get("/v1/sensors")
def sensors_ep():
    """What could measure what — and what a measurement never settles."""
    return sensor_catalog()


@app.get("/v1/surface")
def surface_ep(detail: bool = False):
    """Four promises. The full catalogue stays at /v1/catalog."""
    return surface(detail)


@app.get("/v1/chain")
def chain_ep():
    """Four intents, and the two real chains behind them — never a
    fabricated shared pipeline. The full catalogue stays at /v1/catalog."""
    return chain_overview()


@app.get("/v1/assets")
def assets_ep(request: Request):
    """The customer's own physical objects."""
    from engine import inspections as I
    return {"assets": I.all_assets(_tenant(request)), "source": "customer"}


@app.post("/v1/assets", status_code=201)
def assets_create_ep(request: Request, body: dict):
    from engine import inspections as I
    try:
        rec = I.asset(body["id"], body["kind"],
                      label_en=body.get("label_en", ""),
                      lat=body.get("lat"), lon=body.get("lon"),
                      address=body.get("address", ""),
                      installed_at=body.get("installed_at", ""),
                      tenant=_tenant(request))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    I.save_asset(rec)
    return rec


@app.get("/v1/routines")
def routines_ep(request: Request):
    """What must be checked, how often, and what counts as a pass."""
    from engine import inspections as I
    return {"routines": I.all_routines(_tenant(request)), **I.catalog()}


@app.post("/v1/routines", status_code=201)
def routines_create_ep(request: Request, body: dict):
    from engine import inspections as I
    try:
        rec = I.routine(body["id"], body["label_en"], body["applies_to"],
                        int(body["every_days"]),
                        checks=tuple(body.get("checks") or ()),
                        weekday=body.get("weekday"),
                        season=tuple(body["season"]) if body.get("season")
                        else None,
                        owners=body.get("owners"),
                        expected=body.get("expected"),
                        audience_=body.get("audience"),
                        tenant=_tenant(request))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    I.save_routine(rec)
    return rec


@app.get("/v1/inspections/due")
def inspections_due_ep(request: Request):
    """What a dispatch run would order today."""
    from engine import inspections as I
    return I.due_now(_tenant(request))


@app.post("/v1/inspections/dispatch")
def inspections_dispatch_ep(request: Request):
    """Order field missions for everything that falls due."""
    from integrations.quixzoom_dispatch import dispatch_due
    return dispatch_due(_tenant(request))


@app.post("/v1/inspections/verdict", status_code=201)
def inspections_verdict_ep(request: Request, body: dict):
    """Record an outcome. Evidence required for anything but 'unclear'."""
    from engine import inspections as I
    try:
        rec = I.record(body["asset_id"], body["routine_id"],
                       body["verdict"],
                       performed_at=body.get("performed_at", ""),
                       mission_id=body.get("mission_id", ""),
                       evidence_ref=body.get("evidence_ref", ""),
                       observed_by=body.get("observed_by", ""),
                       note_en=body.get("note_en", ""),
                       tenant=_tenant(request))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    I.save_check(rec)
    return _med_credential(
        rec, "check_passed",
        {"asset_id": rec["asset_id"], "routine_id": rec["routine_id"],
         "verdict": rec["verdict"],
         "performed_at": rec.get("performed_at", ""),
         "evidence_ref": rec.get("evidence_ref", "")},
        tenant=_tenant(request), mission_id=rec.get("mission_id", ""))


@app.post("/v1/inspections/review", status_code=201)
def inspections_review_ep(request: Request, body: dict):
    """A second, named person reads the same evidence and confirms,
    disputes, or says the basis is not enough to tell."""
    from engine import inspections as I
    t = _tenant(request)
    check = next((c for c in I.all_checks(t)
                 if c.get("asset_id") == body.get("asset_id")
                 and c.get("routine_id") == body.get("routine_id")
                 and c.get("performed_at") == body.get("performed_at")), None)
    if check is None:
        raise HTTPException(status_code=404,
                            detail="no such check for this tenant")
    try:
        rec = I.review(check, reviewer=body["reviewer"],
                       outcome=body["outcome"],
                       note_en=body.get("note_en", ""), tenant=t)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    I.save_review(rec)
    return rec


@app.get("/v1/inspections/compliance")
def inspections_compliance_ep(request: Request):
    """Every object, last seen, next due — what you show afterwards."""
    from engine import inspections as I
    return I.report(_tenant(request))


@app.get("/v1/inspections/exceptions")
def inspections_exceptions_ep(request: Request):
    """Only what needs someone."""
    from engine import inspections as I
    return I.exception_feed(_tenant(request))


@app.get("/v1/inspections/reviews")
def inspections_reviews_ep(request: Request):
    """Every second-person review recorded for this tenant."""
    from engine import inspections as I
    return {"reviews": I.all_reviews(_tenant(request))}


@app.get("/v1/objects/{object_id}")
def object_view_ep(request: Request, object_id: str):
    """One object, everything currently known — compliance, condition,
    full history and every second-person review, composed from the
    engines that already compute each piece."""
    from engine import inspections as I
    from engine.object_view import ObjectNotFound, object_view
    t = _tenant(request)
    try:
        return object_view(
            object_id, I.all_assets(t), I.all_routines(t), I.all_checks(t),
            I.all_observations(t), I.all_reviews(t))
    except ObjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/v1/schedules")
def schedules_ep(request: Request):
    """Registered jobs, what can be scheduled, and whether it is awake."""
    from api.ticker import status as ticker_status
    from engine import scheduler
    return {"jobs": scheduler.all_jobs(_tenant(request)),
            **scheduler.catalog(), **ticker_status()}


@app.post("/v1/schedules")
def schedules_create_ep(request: Request, body: dict):
    """Register a job that runs without anyone asking."""
    from engine import scheduler
    k = scheduler.JOB_KINDS.get(body.get("kind", ""))
    p = getattr(request.state, "principal", None)
    if k and p is not None and k["capability"] not in p.capabilities:
        raise HTTPException(
            status_code=403,
            detail=(f"Scheduling {body['kind']!r} needs the "
                    f"{k['capability']} package. See /v1/plans."))
    if body.get("kind") == "push" and p is not None:
        # Pushens DATAMÄNGD bär sin egen kapabilitet — samma grind som
        # /v1/export, annars vore en schemalagd push en väg runt paketet.
        from engine.export import catalog as _exkat
        d = {x["id"]: x for x in _exkat()["datasets"]}.get(
            (body.get("params") or {}).get("dataset", ""))
        if d and d["capability"] not in p.capabilities:
            raise HTTPException(
                status_code=403,
                detail=(f"Pushing {d['id']!r} needs the same package as "
                        f"{d['answers_from']} ({d['capability']}). "
                        f"See /v1/plans."))
    try:
        rec = scheduler.job(body["id"], body["kind"],
                            cadence=body.get("cadence"),
                            params=body.get("params"),
                            enabled=bool(body.get("enabled", True)),
                            tenant=_tenant(request))
    except (KeyError, scheduler.ScheduleRefused) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    scheduler.save_job(rec)
    return JSONResponse(status_code=201, content=rec)


@app.post("/v1/schedules/run")
def schedules_run_ep(request: Request, body: dict | None = None):
    """Run everything due. The path EventBridge or cron points at."""
    from engine import scheduler
    p = getattr(request.state, "principal", None)
    tillatna = None if p is None else {
        k for k, v in scheduler.JOB_KINDS.items()
        if v["capability"] in p.capabilities}
    return scheduler.run_due(_tenant(request), (body or {}).get("now"),
                             tillatna)


@app.get("/v1/integrity/audit")
def integrity_audit_ep():
    """The platform auditing its own guardrails, on demand."""
    from api.surface_scan import selfaudit_context
    from engine.selfaudit import run_audit
    return run_audit(selfaudit_context())


@app.get("/v1/mrai")
def mrai_ep(market: str = ""):
    """Media Reality Alignment Index — or why there is none."""
    from engine import mrai as M
    if not market:
        return M.catalog()
    try:
        return M.mrai(market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/mrai/compare")
def mrai_compare_ep(markets: str = ""):
    """Several markets — with the unscorable listed, not dropped."""
    from engine import mrai as M
    return M.compare([m for m in markets.split(",") if m] or None)


@app.get("/v1/analysis")
def analysis_register_ep(kind: str = "", market: str = ""):
    """What the sweep has found — contradictions and relationships."""
    from engine import analysis
    return {**analysis.register(kind, market), **analysis.catalog()}


@app.post("/v1/analysis/run")
def analysis_run_ep(body: dict | None = None):
    """Sweep a market and add what is new to the register."""
    from engine import analysis
    b = body or {}
    try:
        return analysis.run(b.get("market") or DEFAULT_MARKET,
                            resolver=RESOLVER,
                            limit=int(b.get("limit", 0)),
                            as_of=str(b.get("as_of", "")))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/coverage")
def coverage_ep(market: str = ""):
    """What the platform can actually answer for in a given market."""
    from engine.coverage import coverage
    try:
        return coverage(market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/coverage/markets")
def coverage_markets_ep(markets: str = ""):
    """The same number across markets — the honest answer to 'do you cover X?'."""
    from engine.coverage import compare_markets
    return compare_markets([m for m in markets.split(",") if m] or None)


@app.get("/v1/export")
def export_catalog_ep():
    """What can be taken into your own tools — and what cannot."""
    from engine.export import catalog
    return catalog()


@app.post("/v1/export")
def export_ep(request: Request, body: dict):
    """Export a dataset as CSV, NDJSON or GeoJSON, caveats included."""
    from engine.export import ExportRefused, catalog, export
    d = {x["id"]: x for x in catalog()["datasets"]}.get(
        body.get("dataset", ""))
    # Datamängdens egen kapabilitet gäller också — annars vore exporten en
    # väg runt paketet: köp export, läs allt.
    p = getattr(request.state, "principal", None)
    if d and p is not None and d["capability"] not in p.capabilities:
        raise HTTPException(
            status_code=403,
            detail=(f"Exporting {d['id']!r} needs the same package as "
                    f"{d['answers_from']} ({d['capability']}). "
                    f"See /v1/plans."))
    try:
        return export(body.get("dataset", ""), body.get("format", "csv"),
                      body.get("params") or {}, tenant=_tenant(request))
    except ExportRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/infrastructure")
def infrastructure_catalog_ep():
    """Object types, what each observation means, and how fast it ages."""
    from engine.infrastructure import catalog
    return catalog()


@app.post("/v1/infrastructure/observe")
def infrastructure_observe_ep(request: Request, body: dict):
    """Record a verified field observation."""
    from engine import infrastructure as I
    from engine import inspections as INS
    try:
        rec = I.observe(body.get("object_id", ""), body.get("kind", ""),
                        body.get("values") or {},
                        mission_id=body.get("mission_id", ""),
                        observer_network=body.get("observer_network",
                                                  "quixzoom"),
                        tenant=_tenant(request))
    except I.ObservationRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    INS.save_observation(rec)
    return JSONResponse(status_code=201, content=rec)


@app.post("/v1/infrastructure/status")
def infrastructure_status_ep(request: Request, body: dict):
    """State field by field — an expired perishable is history, not status."""
    from engine import infrastructure as I
    from engine import inspections as INS
    try:
        return I.status(body.get("object_id", ""), body.get("kind", ""),
                        INS.all_observations(_tenant(request)))
    except I.ObservationRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/infrastructure/freshness")
def infrastructure_freshness_ep(request: Request, body: dict):
    """Reality Freshness for one object."""
    from engine import infrastructure as I
    from engine import inspections as INS
    try:
        return I.freshness_record(body.get("object_id", ""),
                                  body.get("kind", ""),
                                  INS.all_observations(_tenant(request)))
    except I.ObservationRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/infrastructure/due")
def infrastructure_due_ep(request: Request):
    """What needs seeing again — driven by the fastest-perishing field."""
    from engine import infrastructure as I
    from engine import inspections as INS
    t = _tenant(request)
    return I.due(INS.all_assets(t), INS.all_observations(t))


@app.get("/v1/reality-kpi")
def reality_kpi_ep(request: Request):
    """Coverage, Freshness and Confidence, rolled up per object class."""
    from engine import inspections as INS
    from engine.reality_kpi import reality_kpi
    t = _tenant(request)
    return reality_kpi(INS.all_assets(t), INS.all_routines(t),
                       INS.all_checks(t), INS.all_observations(t))


@app.post("/v1/infrastructure/sla")
def infrastructure_sla_ep(request: Request, body: dict):
    """Did the promised verification frequency hold? From history."""
    from engine import infrastructure as I
    from engine import inspections as INS
    t = _tenant(request)
    try:
        return I.sla_report(
            INS.all_assets(t), INS.all_observations(t),
            promised_minutes=float(body.get("promised_minutes", 0)),
            window_hours=float(body.get("window_hours", 168)))
    except (I.ObservationRefused, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/land")
def land_catalog_ep():
    """What drives the land-value position, and what it is not."""
    from engine.land import catalog
    return catalog()


@app.post("/v1/land/assess")
def land_assess_ep(body: dict):
    """Relative land-value position for a region — or a refusal."""
    from engine.land import assess
    try:
        return assess(body.get("region_code", ""),
                      body.get("market", "se"), resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/land/compare")
def land_compare_ep(body: dict):
    """Several regions side by side; the unplaceable stay in the list."""
    from engine.land import LandRefused, compare
    try:
        return compare(body.get("region_codes") or [],
                       body.get("market", "se"), resolver=RESOLVER)
    except (LandRefused, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/housing-market")
def housing_market_catalog_ep():
    """What the price, the standard and the plans can and cannot say."""
    from engine.housing_market import catalog
    return catalog()


@app.post("/v1/housing-market/price")
def housing_market_price_ep(body: dict):
    """Price per m² — measured=True only from a real transaction register."""
    from engine.housing_market import price
    try:
        return price(body.get("market", "se"), body.get("region_code", ""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/housing-market/standard")
def housing_market_standard_ep(body: dict):
    """Relative housing-standard position — never a currency."""
    from engine.housing_market import standard
    try:
        return standard(body.get("region_code", ""),
                        body.get("market", "se"), resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/housing-market/compare")
def housing_market_compare_ep(body: dict):
    """Price divided by standard — arithmetic, never a valuation."""
    from engine.housing_market import price_vs_standard
    try:
        return price_vs_standard(body.get("market", "se"),
                                 body.get("region_code", ""),
                                 resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/housing-market/master-plans")
def housing_market_plans_ep(body: dict):
    """The municipality's own planning documents — or an honest 'not connected'."""
    from engine.housing_market import master_plans
    try:
        return master_plans(body.get("market", "se"),
                            body.get("region_code", ""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/leads")
def leads_catalog_ep(request: Request):
    """What a survey can ask for, and this tenant's surveys."""
    from engine import leads as LD
    return {**LD.catalog(), "surveys": LD.all_surveys(_tenant(request))}


@app.post("/v1/leads/survey", status_code=201)
def leads_survey_ep(request: Request, body: dict):
    """Create a survey order over named third-party addresses."""
    from engine import leads as LD
    try:
        rec = LD.survey(body.get("id", ""), body.get("label_en", ""),
                        body.get("condition", ""),
                        body.get("addresses") or [],
                        tenant=_tenant(request))
    except LD.SurveyRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    LD.save_survey(rec)
    return rec


@app.post("/v1/leads/dispatch")
def leads_dispatch_ep(request: Request, body: dict):
    """Order one field mission per address — refusals are answers."""
    from engine import leads as LD
    surv = next((s for s in LD.all_surveys(_tenant(request))
                if s["id"] == body.get("survey_id", "")), None)
    if surv is None:
        raise HTTPException(status_code=404,
                            detail="no such survey for this tenant")
    return LD.dispatch_survey(surv)


@app.post("/v1/leads/verdict", status_code=201)
def leads_verdict_ep(request: Request, body: dict):
    """Record a severity — refused without evidence, same rule as inspections."""
    from engine import leads as LD
    try:
        rec = LD.verdict(body.get("survey_id", ""),
                         body.get("address_id", ""),
                         body.get("severity", ""),
                         mission_id=body.get("mission_id", ""),
                         evidence_ref=body.get("evidence_ref", ""),
                         note_en=body.get("note_en", ""),
                         tenant=_tenant(request))
    except LD.SurveyRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    LD.save_verdict(rec)
    return rec


@app.post("/v1/leads/review", status_code=201)
def leads_review_ep(request: Request, body: dict):
    """A second, named person reads the same evidence reference."""
    from engine import leads as LD
    t = _tenant(request)
    verdict_rec = next((v for v in LD.all_verdicts(t)
                        if v["id"] == body.get("verdict_id", "")), None)
    if verdict_rec is None:
        raise HTTPException(status_code=404,
                            detail="no such verdict for this tenant")
    try:
        rec = LD.review(verdict_rec, reviewer=body.get("reviewer", ""),
                        outcome=body.get("outcome", ""),
                        note_en=body.get("note_en", ""), tenant=t)
    except LD.SurveyRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    LD.save_review(rec)
    return rec


@app.get("/v1/leads/results")
def leads_results_ep(request: Request, survey_id: str = "",
                     min_severity: str = "light"):
    """The addresses that met the threshold — verdict + mission reference, never the photo."""
    from engine import leads as LD
    try:
        return LD.leads(survey_id, min_severity=min_severity,
                        tenant=_tenant(request))
    except LD.SurveyRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/leads/reviews")
def leads_reviews_ep(request: Request):
    """Every second-person review recorded for this tenant."""
    from engine import leads as LD
    return {"reviews": LD.all_reviews(_tenant(request))}


@app.get("/v1/sponsorship")
def sponsorship_catalog_ep(request: Request):
    """Sponsored missions: the option space and this tenant's campaigns."""
    from engine import sponsorship as SP
    return {**SP.catalog(),
            "campaigns": SP.all_campaigns(_tenant(request))}


@app.post("/v1/sponsorship/campaigns")
def sponsorship_create_ep(request: Request, body: dict):
    """Create a campaign, or refuse with a reason that can be acted on."""
    from engine import sponsorship as SP
    try:
        rec = SP.campaign(
            body.get("id", ""), body.get("sponsor_visible_en", ""),
            body.get("mission_class", ""), body.get("brief_en", ""),
            budget=float(body.get("budget", 0)),
            currency=body.get("currency", "SEK"),
            rewards=tuple(body.get("rewards") or ()),
            market=body.get("market", "se"),
            region_codes=tuple(body.get("region_codes") or ()),
            max_per_day=int(body.get("max_per_day", 0)),
            rights_agreement_ref=body.get("rights_agreement_ref", ""),
            co_sponsors=tuple(body.get("co_sponsors") or ()),
            tenant=_tenant(request))
    except (SP.SponsorshipRefused, ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    SP.save_campaign(rec)
    return JSONResponse(status_code=201, content=rec)


@app.post("/v1/sponsorship/mission")
def sponsorship_mission_ep(request: Request, body: dict):
    """The mission body a zoomer would see — budget cap and pacing
    decide whether one may be generated at all."""
    from engine import sponsorship as SP
    kamp = next((k for k in SP.all_campaigns(_tenant(request))
                 if k["id"] == body.get("campaign_id")), None)
    if kamp is None:
        raise HTTPException(status_code=404,
                            detail=f"unknown campaign "
                                   f"{body.get('campaign_id')!r}")
    grind = SP.can_order(kamp, today_count=int(body.get("today_count", 0)))
    if not grind["allowed"]:
        raise HTTPException(status_code=409, detail=grind["why_en"])
    return SP.mission_body(kamp, region_code=body.get("region_code", ""),
                           lat=body.get("lat"), lon=body.get("lon"))


@app.post("/v1/sponsorship/completion")
def sponsorship_completion_ep(request: Request, body: dict):
    """Record a completion: verdict and region — never a person."""
    from engine import sponsorship as SP
    try:
        rec = SP.completion(
            body.get("campaign_id", ""), body.get("mission_id", ""),
            region_code=body.get("region_code", ""),
            quality_band=body.get("quality_band", ""),
            verdicts=body.get("verdicts"),
            settlement_ref=body.get("settlement_ref", ""),
            tenant=_tenant(request))
    except SP.SponsorshipRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    SP.save_completion(rec)
    return JSONResponse(status_code=201, content=_med_credential(
        rec, "sponsored_completion",
        {"campaign_id": rec["campaign_id"],
         "region_code": rec.get("region_code", ""),
         "quality_band": rec.get("quality_band", ""),
         "verdicts": rec.get("verdicts", {})},
        tenant=_tenant(request), mission_id=rec.get("mission_id", "")))


@app.post("/v1/sponsorship/order")
def sponsorship_order_ep(request: Request, body: dict):
    """Order ONE mission and commit its cost — through the gate.

    Ordering is the only way `ordered` and `spent` move; a refusal from
    the budget cap or the pacing is the answer, not an error to retry.
    """
    from engine import sponsorship as SP
    if not any(k["id"] == body.get("campaign_id")
               for k in SP.all_campaigns(_tenant(request))):
        raise HTTPException(status_code=404,
                            detail=f"unknown campaign "
                                   f"{body.get('campaign_id')!r}")
    try:
        return JSONResponse(status_code=201, content=SP.order_mission(
            body.get("campaign_id", ""), tenant=_tenant(request),
            region_code=body.get("region_code", ""),
            lat=body.get("lat"), lon=body.get("lon"),
            today_count=int(body.get("today_count", 0))))
    except SP.SponsorshipRefused as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.post("/v1/sponsorship/status")
def sponsorship_status_ep(request: Request, body: dict):
    """Pause, resume or close a campaign — transitions are data."""
    from engine import sponsorship as SP
    try:
        return SP.set_status(body.get("campaign_id", ""),
                             body.get("status", ""),
                             tenant=_tenant(request))
    except SP.SponsorshipRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/sponsorship/stats")
def sponsorship_stats_ep(request: Request, campaign_id: str = ""):
    """Aggregates only — cells under the k-floor are suppressed and counted."""
    from engine import sponsorship as SP
    try:
        return SP.stats(campaign_id, tenant=_tenant(request))
    except SP.SponsorshipRefused as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/v1/company")
def company_get_ep(request: Request):
    """The tenant's company profile — the brand that rides on missions."""
    return {**_company.catalog(),
            "profile": _company.get_profile(_tenant(request))}


@app.post("/v1/company", status_code=201)
def company_save_ep(request: Request, body: dict):
    """Save the profile; every field is validated at the door."""
    try:
        rec = _company.profile(
            _tenant(request), name=body.get("name", ""),
            about_en=body.get("about_en", ""),
            logo_url=body.get("logo_url", ""),
            website=body.get("website", ""),
            brand_color=body.get("brand_color", ""),
            org_ref=body.get("org_ref", ""))
    except _company.ProfileRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _company.save_profile(rec)
    return rec


@app.get("/v1/company/logo")
def company_logo_get_ep(request: Request):
    """Metadata about the stored logo — never the bytes themselves."""
    return {"logo": _company.get_logo(_tenant(request))}


@app.post("/v1/company/logo", status_code=201)
def company_logo_save_ep(request: Request, body: dict):
    """Upload a logo file as base64 — sniffed, measured, judged, and
    adapted to a suitable format where that can be done losslessly."""
    try:
        rec = _company.save_logo(_tenant(request),
                                 body.get("filename", ""),
                                 body.get("content_b64", ""))
    except _company.ProfileRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return rec


@app.post("/v1/company/logo/remove")
def company_logo_remove_ep(request: Request, body: dict):
    return {"deleted": _company.delete_logo(_tenant(request))}


@app.get("/v1/company/logo/raw")
def company_logo_raw_ep(tenant: str = ""):
    """The logo's actual bytes — public and unauthenticated on purpose:
    quiXzoom's map (and any phone rendering a mission pin) fetches this
    with no Landvex credentials, the same openness the platform already
    requires of an externally-hosted logo_url."""
    from fastapi.responses import Response
    if not tenant:
        raise HTTPException(status_code=422,
                            detail="tenant query parameter is required")
    ut = _company.get_logo_bytes(tenant)
    if ut is None:
        raise HTTPException(status_code=404,
                            detail="no logo uploaded for this tenant")
    content, content_type = ut
    return Response(content=content, media_type=content_type)


@app.post("/v1/inspections/exceptions/report")
def exceptions_report_ep(request: Request, body: dict):
    """File the exception feed as tickets in the customer's own system."""
    from engine import connections as CN
    from engine import inspections as I
    from integrations import feedback
    t = _tenant(request)
    if body.get("connection"):
        try:
            kopp = CN.get_connection(body["connection"], tenant=t)
        except CN.ConnectionRefused as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    else:
        kopp = CN.feedback_target(t)
    return feedback.report_exceptions(
        I.exception_feed(t, body.get("today", "")), kopp)


@app.get("/v1/credentials")
def credentials_catalog_ep():
    """What a credential certifies — and what it cannot."""
    return _credentials.catalog()


@app.get("/v1/deliveries")
def deliveries_list_ep(request: Request, limit: int = 100):
    """The outbound audit log — attempts and answers, never bodies."""
    return {**_deliveries.catalog(),
            "deliveries": _deliveries.all_deliveries(_tenant(request),
                                                     limit=limit)}


@app.post("/v1/deliveries/verify")
def deliveries_verify_ep(request: Request, body: dict):
    """Does this delivery id belong to this body? The log answers."""
    return _deliveries.verify_delivery(body.get("delivery_id", ""),
                                       body.get("body_sha256", ""),
                                       tenant=_tenant(request))


@app.get("/v1/deliveries/streaks")
def deliveries_streaks_ep(request: Request):
    """Consecutive-failure streaks per target, straight from the log."""
    return {"streaks": _deliveries.failure_streaks(_tenant(request))}


@app.post("/v1/deliveries/retry")
def deliveries_retry_ep(request: Request, body: dict):
    """Rebuild a failed delivery from its source — never from a saved body."""
    from integrations.redelivery import retry
    return retry(body.get("delivery_id", ""), tenant=_tenant(request))


@app.post("/v1/credentials/verify")
def credentials_verify_ep(request: Request, body: dict):
    """Recompute the signature — one changed byte fails it."""
    return _credentials.verify(body.get("credential") or {},
                               tenant=_tenant(request))


@app.get("/v1/staff")
def staff_list_ep(request: Request):
    """The tenant's own zoomers — account references, never persons."""
    return {**_staff.catalog(),
            "staff": _staff.all_staff(_tenant(request))}


@app.post("/v1/staff", status_code=201)
def staff_add_ep(request: Request, body: dict):
    """Link an existing quiXzoom account by its reference."""
    try:
        rec = _staff.member(body.get("zoomer_ref", ""),
                            tenant=_tenant(request),
                            role_label_en=body.get("role_label_en", ""))
    except _staff.StaffRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _staff.save_staff(rec)
    return rec


@app.post("/v1/staff/invite", status_code=201)
def staff_invite_ep(request: Request, body: dict):
    """Create an invite code — identity and consent live with quiXzoom."""
    try:
        rec = _staff.invite(tenant=_tenant(request),
                            role_label_en=body.get("role_label_en", ""))
    except _staff.StaffRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _staff.save_staff(rec)
    return rec


@app.post("/v1/staff/claim", status_code=201)
def staff_claim_ep(request: Request, body: dict):
    """Redeem an invite code for the account reference that came back."""
    try:
        return _staff.claim_invite(body.get("invite_id", ""),
                                   body.get("zoomer_ref", ""),
                                   tenant=_tenant(request))
    except _staff.StaffRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/staff/remove")
def staff_remove_ep(request: Request, body: dict):
    """Stop future targeting; the person's quiXzoom account is untouched."""
    return {"deleted": _staff.remove_staff(body.get("id", ""),
                                           tenant=_tenant(request))}


@app.get("/v1/connections")
def connections_catalog_ep(request: Request):
    """The customer's own integrations — secrets masked on every read."""
    from engine import connections as CN
    return {**CN.catalog(),
            "connections": [CN.masked(r) for r in
                            CN.all_connections(_tenant(request))]}


@app.post("/v1/connections")
def connections_create_ep(request: Request, body: dict):
    """Connect a provider — validated at creation, echoed back masked."""
    from engine import connections as CN
    try:
        rec = CN.connection(body.get("provider", ""),
                            body.get("config") or {},
                            tenant=_tenant(request))
    except CN.ConnectionRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    CN.save_connection(rec)
    return JSONResponse(status_code=201, content=CN.masked(rec))


@app.post("/v1/connections/delete")
def connections_delete_ep(request: Request, body: dict):
    """Remove a connection; a missing one is a state, not an error."""
    from engine import connections as CN
    borta = CN.delete_connection(body.get("provider", ""),
                                 tenant=_tenant(request))
    return {"deleted": borta,
            "note_en": "" if borta else (
                "nothing to delete — no such connection for this "
                "tenant, which is a state, not an error")}


@app.post("/v1/connections/test")
def connections_test_ep(request: Request, body: dict):
    """Probe the real provider — only a real answer sets 'verified'."""
    from engine import connections as CN
    from integrations import llm
    try:
        rec = CN.get_connection(body.get("provider", ""),
                                tenant=_tenant(request))
    except CN.ConnectionRefused as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    resultat = llm.probe(rec)
    if resultat["verified"]:
        rec = dict(rec)
        rec["status"] = "verified"
        rec["verified_at"] = resultat["probed_at"]
        CN.save_connection(rec)
    return resultat


@app.post("/v1/connections/narrate")
def connections_narrate_ep(request: Request, body: dict):
    """The customer's own model interprets an analysis — marked as such."""
    from engine import connections as CN
    from integrations import llm
    try:
        rec = CN.get_connection(body.get("provider", "anthropic"),
                                tenant=_tenant(request))
        return llm.narrate(rec, body.get("analysis") or {},
                           question=body.get("question", ""))
    except CN.ConnectionRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/pushes")
def pushes_catalog_ep():
    """The push generator's option space: datasets × formats × rules."""
    from engine.pushes import catalog
    return catalog()


@app.post("/v1/pushes/preview")
def pushes_preview_ep(request: Request, body: dict):
    """Exactly what WOULD be delivered — nothing is sent."""
    from engine.export import catalog as _exkat
    from engine.pushes import PushRefused, preview
    d = {x["id"]: x for x in _exkat()["datasets"]}.get(
        body.get("dataset", ""))
    # Samma grind som /v1/export: datamängdens kapabilitet gäller —
    # annars vore förhandsvisningen en väg runt paketet.
    p = getattr(request.state, "principal", None)
    if d and p is not None and d["capability"] not in p.capabilities:
        raise HTTPException(
            status_code=403,
            detail=(f"Previewing {d['id']!r} needs the same package as "
                    f"its engine ({d['capability']}). See /v1/plans."))
    try:
        return preview(body.get("dataset", ""),
                       body.get("format", "csv"),
                       body.get("params") or {},
                       tenant=_tenant(request))
    except PushRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/commercial")
def commercial_ep():
    """How a customer buys. Five packagings, because customers differ."""
    from engine.commercial import catalog as _kommersiell
    return _kommersiell()


@app.get("/v1/offering")
def offering_ep(plan: str = ""):
    """What each tier lets you decide. Built and planned kept apart."""
    try:
        return offering(plan)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/registers")
def registers_catalog():
    return {**register_catalog(), "client": RegisterClient().status()}


@app.post("/v1/saturation")
def saturation_ep(req: SaturationRequest):
    """How saturated is the market for a trade in a place?"""
    try:
        return market_saturation(req.vertical, req.region, market=req.market,
                                 resolver=RESOLVER,
                                 peer_limit=min(max(req.peer_limit, 5), 60))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/v1/inbox")
def inbox_subscriptions(subscriber: str = ""):
    return {"subscriptions": inbox_engine.subscriptions(subscriber),
            "stake_kinds": list(inbox_engine.STAKE_WEIGHT)}


@app.post("/v1/inbox/subscribe")
def inbox_subscribe(req: SubscribeRequest):
    try:
        return inbox_engine.subscribe(req.subscriber, req.role, req.stakes,
                                      min_severity=req.min_severity,
                                      threshold=req.threshold)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/inbox/route")
def inbox_route(req: RouteRequest, request: Request):
    decisions = accountability_all_decisions(_tenant(request))
    evs = _collect_events(req)
    if req.subscriber:
        return inbox_engine.brief(req.subscriber, evs, decisions=decisions,
                                  now=req.now)
    return inbox_engine.route(evs, decisions=decisions, now=req.now)


@app.get("/v1/monitors")
def monitors_catalog():
    return monitors_engine.catalog()


@app.post("/v1/monitors")
def monitors_define(req: MonitorDefineRequest, request: Request):
    try:
        return monitors_engine.define(
            req.metric, req.scope, req.rule, req.owner,
            params=req.params, cadence=req.cadence or None,
            label=req.label, tenant=_tenant(request))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/monitors/evaluate")
def monitors_evaluate(req: MonitorEvaluateRequest, request: Request):
    mon = req.monitor or monitors_engine.get_monitor(
        req.monitor_id, _tenant(request))
    if mon is None:
        raise HTTPException(status_code=404, detail="unknown monitor")
    return monitors_engine.evaluate(mon, req.series, evaluated_at=req.evaluated_at)


@app.post("/v1/monitors/run")
def monitors_run(req: MonitorRunRequest, request: Request):
    mons = monitors_engine.all_monitors(_tenant(request))
    return monitors_engine.run_due(mons, req.now, req.series_by_id)


@app.post("/v1/monitors/escalate")
def monitors_escalate(req: MonitorEscalateRequest):
    try:
        return monitors_engine.escalate(
            req.finding, req.owners, req.expected,
            committed_at=req.committed_at, horizon_months=req.horizon_months)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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


class DecisionCommitRequest(BaseModel):
    decision: str
    owners: dict = Field(default_factory=dict)
    expected: dict = Field(default_factory=dict)
    kpi_ids: list = Field(default_factory=list)
    horizon_months: int = 0
    committed_at: str = ""


class DecisionResolveRequest(BaseModel):
    decision_id: str
    actual_value: float
    baseline: float | None = None
    resolved_at: str = ""


@app.post("/v1/decisions/commit")
def decisions_commit(req: DecisionCommitRequest, request: Request):
    try:
        return commit_decision(req.decision, req.owners, req.expected,
                               kpi_ids=req.kpi_ids,
                               horizon_months=req.horizon_months,
                               committed_at=req.committed_at,
                               tenant=_tenant(request))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/decisions/resolve")
def decisions_resolve(req: DecisionResolveRequest):
    dcn = get_decision(req.decision_id)
    if dcn is None:
        raise HTTPException(status_code=404, detail="unknown decision_id")
    return resolve_decision(dcn, req.actual_value, baseline=req.baseline,
                            resolved_at=req.resolved_at)


@app.get("/v1/decisions/ledger")
def decisions_ledger(request: Request):
    return accountability_ledger(tenant=_tenant(request))


class CorrelateRequest(BaseModel):
    a: list[float]
    b: list[float]
    control: list[float] | None = None
    label_a: str = "A"
    label_b: str = "B"
    label_c: str = "C"


class CrossMarketRequest(BaseModel):
    markets: list[dict] = Field(default_factory=list)
    label_a: str = "A"
    label_b: str = "B"


@app.post("/v1/correlate")
def correlate_ep(req: CorrelateRequest):
    out = cross_domain(req.a, req.b, label_a=req.label_a, label_b=req.label_b)
    if req.control:
        out["partial"] = partial_correlation(
            req.a, req.b, req.control, label_a=req.label_a,
            label_b=req.label_b, label_c=req.label_c)
    return out


@app.post("/v1/correlate/cross-market")
def correlate_cross_market(req: CrossMarketRequest):
    return cross_market(req.markets, label_a=req.label_a, label_b=req.label_b)


class ScenarioRequest(BaseModel):
    series: list[float]
    sources: list = Field(default_factory=list)
    horizon: int = 3
    coverage: float = 1.0
    metric: str = "indicator"


class EventStudyRequest(BaseModel):
    series: list[float] | None = None
    split_index: int | None = None
    treated_pre: list[float] | None = None
    treated_post: list[float] | None = None
    control_pre: list[float] | None = None
    control_post: list[float] | None = None
    metric: str = "indicator"
    event: str = "intervention"


class BenchmarkRequest(BaseModel):
    value: float
    peers: list[float] = Field(default_factory=list)
    label: str = "unit"
    metric: str = "ratio"
    higher_is_better: bool | None = None
    sources: list = Field(default_factory=list)


@app.post("/v1/scenario")
def scenario_ep(req: ScenarioRequest):
    return scenario_project(req.series, req.sources, horizon=req.horizon,
                            coverage=req.coverage, metric=req.metric)


@app.post("/v1/event-study")
def event_study_ep(req: EventStudyRequest):
    try:
        if req.treated_pre is not None:
            return diff_in_diff(req.treated_pre, req.treated_post or [],
                                req.control_pre or [], req.control_post or [],
                                metric=req.metric, event=req.event)
        if req.series is not None and req.split_index is not None:
            return before_after(req.series, req.split_index, metric=req.metric,
                                event=req.event)
        raise HTTPException(status_code=422,
                            detail="provide series+split_index or the four DiD arrays")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/benchmark")
def benchmark_ep(req: BenchmarkRequest):
    return benchmark(req.value, req.peers, label=req.label, metric=req.metric,
                     higher_is_better=req.higher_is_better, sources=req.sources)


class SensitiveRequest(BaseModel):
    a: list[float]
    b: list[float]
    control: list[float]
    category: str
    group_sizes: list[int] = Field(default_factory=list)
    sources: list = Field(default_factory=list)
    confounders: list = Field(default_factory=list)
    label_a: str = "attribute"
    label_b: str = "outcome"
    label_c: str = "confounder"


@app.post("/v1/sensitive-association")
def sensitive_ep(req: SensitiveRequest):
    return sensitive_association(
        req.a, req.b, req.control, category=req.category,
        group_sizes=req.group_sizes, sources=req.sources,
        confounders=req.confounders, label_a=req.label_a,
        label_b=req.label_b, label_c=req.label_c)


class WageLookupRequest(BaseModel):
    occupation: str
    market: str = DEFAULT_MARKET


class WageCompareRequest(BaseModel):
    occupation: str
    markets: list[str] = Field(default_factory=list)


@app.get("/v1/wages")
def wages_registry():
    return wage_catalog()


@app.post("/v1/wages/lookup")
def wages_lookup(req: WageLookupRequest):
    try:
        return wage(req.occupation, req.market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/wages/compare")
def wages_compare(req: WageCompareRequest):
    try:
        return wage_compare(req.occupation, req.markets)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class WageContextRequest(BaseModel):
    occupation: str
    region: str


@app.post("/v1/wages/context")
def wages_context(req: WageContextRequest):
    return compensation_context(req.occupation, req.region)


class CorrectionSubmitRequest(BaseModel):
    region: str
    target_key: str
    proposed_value: float
    source: str
    submitter_id: str
    current_value: float | None = None
    note: str = ""


class CorrectionQueryRequest(BaseModel):
    region: str
    target_key: str


@app.post("/v1/corrections/submit")
def corrections_submit(req: CorrectionSubmitRequest):
    try:
        return submit_correction(req.region, req.target_key, req.proposed_value,
                                 req.source, req.submitter_id,
                                 current_value=req.current_value, note=req.note)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/corrections/consensus")
def corrections_consensus(req: CorrectionQueryRequest):
    return correction_consensus(req.target_key, req.region)


@app.post("/v1/corrections/adapt")
def corrections_adapt(req: CorrectionQueryRequest):
    return adapt_correction(req.target_key, req.region)


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
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/service/map")
def service_map(product_id: str, market: str = DEFAULT_MARKET,
                target_year: int = 2031):
    try:
        return service_demand_map(product_id, market=market,
                                  target_year=target_year, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/segments")
def segments():
    return segment_catalog()


@app.post("/v1/segments/analyze")
def segments_analyze(req: SegmentAnalyzeRequest):
    try:
        return segment_analysis(req.kommun_kod, market=req.market,
                                resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/segments/map")
def segments_map(segment_id: str, market: str = DEFAULT_MARKET):
    try:
        return segment_map(segment_id, market=market, resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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


@app.get("/v1/indices/families")
def indices_families():
    return index_families()


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
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/indices/assess")
def indices_assess(request: Request, req: AssessRequest):
    try:
        res = city_assessment(req.kommun_kod, market=req.market,
                              resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
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
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/workforce/simulate")
def workforce_simulate(req: SimulateRequest):
    try:
        return wf_simulate(req.kommun_kod, req.occupation_id,
                           req.extra_places_per_year, req.target_year,
                           resolver=RESOLVER, market=req.market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/workforce/map")
def workforce_map(occupation_id: str, target_year: int = 2035,
                  market: str = DEFAULT_MARKET):
    try:
        return national_map(occupation_id, target_year, resolver=RESOLVER,
                            market=market)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/workforce/global-map")
def workforce_global_map(occupation_id: str, target_year: int = 2035,
                         group: str = "eu"):
    try:
        return global_map(occupation_id, target_year, group=group,
                          resolver=RESOLVER)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/v1/reports")
def list_reports(request: Request, limit: int = 20):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    return STORE.list_reports(min(max(limit, 1), 200),
                              tenant=_tenant(request))


@app.get("/v1/reports/{report_id}")
def get_report(report_id: str, request: Request):
    if STORE is None:
        raise HTTPException(status_code=503, detail="Persistence disabled (LANDVEX_DB=off).")
    doc = STORE.get_report(report_id, tenant=_tenant(request))
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown report id.")
    return doc
