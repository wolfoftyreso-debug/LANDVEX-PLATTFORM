"""Beroendefri utvecklingsserver (endast stdlib).

    python3 -m api.dev_server   # startar på http://localhost:8000

Samma endpoints som produktions-API:t:
    GET  /health
    GET  /v1/verticals
    GET  /v1/profile-options
    GET  /v1/profiles          ·  POST /v1/profiles
    GET  /v1/profiles/<id>
    GET  /v1/reports?limit=20  ·  GET /v1/reports/<id>
    POST /v1/analyze   {"lat":..,"lon":..,"vertical":"frisor","radius_minutes":10}
    POST /v1/scan      {"profile":{...}} eller {"profile_id":"..."}
    POST /v1/ask       {"question":"Var är behovet av elektriker störst?"}
    POST /v1/risk      {"lat":..,"lon":..,"vertical":"frisor"}
    POST /v1/compare   {"vertical":"frisor","locations":[{...},{...}]}
    GET  /v1/workforce/occupations
    GET  /v1/workforce/map?occupation_id=elektriker&target_year=2035
    POST /v1/workforce/forecast  {"kommun_kod":"0180","target_year":2035}
    POST /v1/workforce/simulate  {"kommun_kod":"0180","occupation_id":"elektriker",
                                  "extra_places_per_year":30}

Endast för lokal utveckling/demo – i AWS körs api/main.py (FastAPI).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from engine.datasources.adapters import production_sources
from engine.datasources.base import Resolver
from engine.datasources.cache import CachedSource
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.profile import profile_from_dict, profile_options
from engine.scan import SCAN_LEVEL_OPTIONS, scan
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
from engine import inspections as insp_engine
from engine import scheduler
from engine import analysis as analysis_engine
from engine import mrai as mrai_engine
from engine import harvest as harvest_engine
from engine import news as news_engine
from engine import company as company_engine
from engine import connections as connections_engine
from engine import credentials as credentials_engine
from engine import deliveries as deliveries_engine
from engine import leads as leads_engine
from engine import sponsorship as sponsorship_engine
from engine import staff as staff_engine
from engine.coverage import compare_markets, coverage
from engine.export import catalog as export_catalog, export as export_data
from api.ticker import start as start_ticker, status as ticker_status
from engine import monitors as monitors_engine
from engine.monitors import set_store as set_monitors_store
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

from api.health import build_health, source_status
from api.licensing import plans_catalog, upgrade_hint_en
from api.security import AuthError, Gate
from integrations.aamos import (AamosClient, AamosUnavailable,
                                agent_chat_safe,
                                agents as aamos_agents,
                                cognition_brief_safe,
                                platform_status, watch)

AAMOS = AamosClient()
from engine.datasources.programs import ProgramsClient
PROGRAMS = ProgramsClient()   # connected only if LANDVEX_PROGRAMS_URL is set

_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
_SANDBOX = Path(__file__).resolve().parent.parent / "frontend" / "sandbox.html"
# Dörren: en fråga och fyra löften. Konsolen med nio flikar finns kvar
# oförändrad på /console — den är vad man hittar EFTER sin första fråga.
_START = Path(__file__).resolve().parent.parent / "frontend" / "start.html"
# Demosystemet: sex bevis, alla hämtade från det körande API:t.
_DEMO = Path(__file__).resolve().parent.parent / "frontend" / "demo.html"
# Ytan för den som INTE kan området: riktiga platser, riktiga tal.
_EXPLORE = Path(__file__).resolve().parent.parent / "frontend" / "explore.html"

# Persistens: LANDVEX_DB = sökväg (default landvex.db) eller "off".
_DB = os.environ.get("LANDVEX_DB", "landvex.db")
STORE = SqliteStore(_DB) if _DB.lower() not in ("off", "0", "") else None
# Utfallskalibrering + ansvarsloop backas av lagret (överlever omstart).
set_outcome_store(STORE)
set_accountability_store(STORE)
set_corrections_store(STORE)
set_monitors_store(STORE)
insp_engine.set_store(STORE)
# Schemalagda jobb måste ligga i lagret av två skäl: de ska överleva en
# omstart (annars slutar en veckorunda tyst att köras), och claimet som
# hindrar två processer från att köra samma jobb sitter i databasen.
scheduler.set_store(STORE)
# Skörden och frågan MÅSTE dela lager: utan den här raden
# skördar make harvest till en databas som API:t inte läser,
# och varje svar blir mock fast rader finns.
harvest_engine.set_store(STORE)
news_engine.set_store(STORE)
# Kampanjer och fullbordanden är kundens egna och måste överleva en
# omstart: en budget som nollställs vid omstart är en budget som kan
# överskridas obegränsat.
sponsorship_engine.set_store(STORE)
connections_engine.set_store(STORE)
company_engine.set_store(STORE)
credentials_engine.set_store(STORE)
staff_engine.set_store(STORE)
deliveries_engine.set_store(STORE)
leads_engine.set_store(STORE)


def _med_credential(rec: dict, kind: str, subject: dict, *,
                    tenant: str, mission_id: str) -> dict:
    """Godkänt utfall ⇒ signerat kvitto + leveransförsök till kundens
    system, båda REDOVISADE på svaret. En vägran (underkänd dom, saknad
    uppdragsreferens) redovisas också i stället för att fälla anropet:
    domen är giltig även när kvittot inte kan utfärdas — men den får
    aldrig se ut att ha certifierats."""
    from engine import connections as CN
    from integrations import feedback
    ut = dict(rec)
    try:
        cred = credentials_engine.issue(kind, subject, tenant=tenant,
                                        mission_id=mission_id)
    except credentials_engine.CredentialRefused as e:
        ut["credential"] = None
        ut["credential_refused_en"] = str(e)
        return ut
    ut["credential"] = cred
    ut["feedback"] = feedback.forward(cred, CN.feedback_target(tenant))
    return ut

# Gate delar lagret så månadskvoten överlever omstarter (om DB på).
GATE = Gate(store=STORE)

# CORS — SAMMA variabel och samma tre headers som FastAPI-lagret
# (api/main.py). Dev-servern hade ingen CORS alls: en frontend som
# fungerade mot produktionslagret fick tysta preflight-fel mot det här,
# och skillnaden stod inte dokumenterad någonstans. Osatt variabel =
# samma origin = inga CORS-headers, precis som i main.
_CORS = tuple(o.strip()
              for o in os.environ.get("LANDVEX_CORS_ORIGINS", "").split(",")
              if o.strip())

# Samma källkedja som produktions-API:t; LANDVEX_LIVE=0 → endast mock.
_LIVE = os.environ.get("LANDVEX_LIVE", "1") != "0"
_sources = production_sources() if _LIVE else []
if STORE is not None:
    _sources = [CachedSource(s, STORE) for s in _sources]
RESOLVER = Resolver(_sources + [MockSource()])


def _field_error(e: Exception) -> str:
    """Ett fältfel som går att åtgärda utan att läsa källkoden.

    `str(KeyError("lat"))` är `"'lat'"` — vilket för klienten bara är ett
    ord inom apostrofer. Vilket fält, och att det SAKNAS, sägs inte.
    """
    if isinstance(e, KeyError):
        return (f"Missing required field: {e.args[0]!r}."
                if e.args else "Missing a required field.")
    return str(e)


class _BadRequest(Exception):
    """Klientens kropp går inte att tolka — 400, aldrig 500."""


class _TooLarge(Exception):
    """Kroppen är större än taket — 413."""


class Handler(BaseHTTPRequestHandler):
    def _cors_origin(self) -> str:
        """Anroparens origin OM den står i listan — annars tomt.

        Origin ekas aldrig tillbaka oprövad: `Access-Control-Allow-
        Origin: <vad som helst>` hade gjort listan till dekoration.
        """
        origin = self.headers.get("Origin", "")
        return origin if origin and origin in _CORS else ""

    def _send(self, code: int, payload: dict | list) -> None:
        self._status = code
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if getattr(self, "_request_id", None):
            self.send_header("X-Request-ID", self._request_id)
        tillaten = self._cors_origin()
        if tillaten:
            self.send_header("Access-Control-Allow-Origin", tillaten)
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, code: int, content_type: str, body: bytes) -> None:
        """Rå kropp, inte JSON — för loggans egna byte (samma väg som
        /metrics?format=prometheus redan tar förbi _send)."""
        self._status = code
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if getattr(self, "_request_id", None):
            self.send_header("X-Request-ID", self._request_id)
        tillaten = self._cors_origin()
        if tillaten:
            self.send_header("Access-Control-Allow-Origin", tillaten)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):                                # noqa: N802
        """Preflight. Samma verb och headers som FastAPI-lagrets
        CORSMiddleware svarar med — skillnaden mellan lagren var
        odokumenterad och syntes först som tysta fetch-fel i en
        frontend som fungerade mot produktion."""
        tillaten = self._cors_origin()
        self._status = 204
        self.send_response(204)
        if tillaten:
            self.send_header("Access-Control-Allow-Origin", tillaten)
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, X-API-Key, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # Samma tupel som api/main.py — kontraktstestet jämför dem numera
    # statiskt. En väg som är öppen i ena lagret och grindad i det andra
    # ger olika svar på samma nyckel beroende på miljö.
    _OPEN_PATHS = ("/", "/console", "/demo", "/explore", "/index.html",
                   "/sandbox", "/health", "/docs", "/openapi.json",
                   "/v1/plans", "/v1/company/logo/raw")

    def _tenant(self) -> str:
        """Vilken kund frågan kommer från. Lagret KRÄVER den — ett argument
        man kan glömma är en läcka som väntar på att hända."""
        p = getattr(self, "_principal", None)
        return p.tenant if p is not None else "dev"

    def _live_locked(self) -> bool:
        p = getattr(self, "_principal", None)
        return p is not None and "intelligence_map_live" not in p.capabilities

    def _har(self, capability: str) -> bool:
        """Bär nyckeln kapabiliteten? I öppet läge (ingen auth) finns
        ingen principal, och då gäller inget paket att bryta mot."""
        p = getattr(self, "_principal", None)
        return p is None or capability in p.capabilities

    def _gated(self, method: str, route) -> None:
        """Auth → rate limit → routning → metrics + audit."""
        path = self.path
        if urlparse(path).path in self._OPEN_PATHS:
            # Utanför Gate men INTE utanför metriken — samma regel som
            # FastAPI-lagret: en driftbild där startsidan aldrig hänt är
            # gladare än verkligheten. Ingen audit-rad, medvetet.
            t0 = time.monotonic()
            try:
                return route()
            finally:
                GATE.metrics.observe(
                    urlparse(path).path, getattr(self, "_status", 200),
                    (time.monotonic() - t0) * 1000)
        t0 = time.monotonic()
        principal, self._request_id, self._status = None, None, 500
        try:
            principal, self._request_id = GATE.enter(
                self.headers.get("X-API-Key")
                or self.headers.get("Authorization"), method, path)
            self._principal = principal
            route()
        except AuthError as e:
            self._send(e.status, {"error": e.message_en})
        except Exception:
            # Sista skyddsnät: en oväntad bugg får aldrig läcka en
            # stacktrace eller lämna klienten utan svar. Logga med
            # request_id för korrelation, returnera ren 500.
            rid = self._request_id or "-"
            traceback.print_exc(file=sys.stderr)
            print(f'{{"level":"error","request_id":"{rid}",'
                  f'"path":"{urlparse(path).path}"}}', file=sys.stderr,
                  flush=True)
            self._send(500, {"error": "Internal error.", "request_id": rid})
        finally:
            GATE.exit(principal, self._request_id or "-", method, path,
                      self._status, (time.monotonic() - t0) * 1000)

    def do_GET(self):
        self._gated("GET", self._route_get)

    def do_POST(self):
        self._gated("POST", self._route_post)

    def _route_get(self):
        """Frågesträngen är också indata.

        POST-vägen mappade sedan länge fältfel till 422; GET gjorde det
        inte, så `?market=atlantis` blev "Internal error" med ett
        request-id — medan FastAPI-lagret svarade 422 med vilka
        marknader som finns. Två servrar som beter sig olika på samma
        felstavning är samma sorts drift som en saknad endpoint, bara
        svårare att upptäcka.
        """
        try:
            return self._route_get_inner()
        except (KeyError, ValueError, TypeError) as e:
            return self._send(422, {"error": _field_error(e)})

    def _route_get_inner(self):
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            kallor = source_status(RESOLVER)
            if parse_qs(parsed.query).get("format", [""])[0] == "prometheus":
                body = GATE.metrics.to_prometheus(kallor).encode("utf-8")
                self._status = 200
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            snap = GATE.metrics.snapshot()
            snap["rate_limit_per_min"] = GATE.limiter.capacity
            snap["kallor"] = kallor
            return self._send(200, snap)
        if parsed.path == "/v1/audit":
            limit = int(parse_qs(parsed.query).get("limit", ["100"])[0])
            return self._send(200, GATE.audit.tail(limit))
        if parsed.path == "/v1/agent-manifest":
            from api.agent_manifest import AGENT_MANIFEST
            return self._send(200, AGENT_MANIFEST)
        if parsed.path in ("/", "/console", "/index.html", "/demo", "/explore"):
            self._status = 200
            body = {"/": _START, "/demo": _DEMO,
                    "/explore": _EXPLORE}.get(parsed.path,
                                              _FRONTEND).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if parsed.path == "/sandbox":
            self._status = 200
            body = _SANDBOX.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if parsed.path == "/health":
            return self._send(200, build_health(RESOLVER, STORE))
        if parsed.path == "/v1/verticals":
            # Samma form som FastAPI-lagret, med faktornedbrytningen.
            # Utan den svarade samma väg med OLIKA nyttolast i de två
            # lagren — kontraktstestet låser vägar, inte svar, så driften
            # var osynlig tills någon jämförde svaren.
            return self._send(200, [
                {"id": v.id, "label_en": v.label_en,
                 "factors": [{"id": f.id, "label_en": f.label_en,
                              "weight": f.weight} for f in v.factors]}
                for v in VERTICALS.values()])
        if parsed.path == "/v1/profile-options":
            return self._send(200, {**profile_options(),
                                    "scan_levels": SCAN_LEVEL_OPTIONS})
        if parsed.path == "/v1/catalog":
            from api.catalog import API_CATALOG
            return self._send(200, API_CATALOG)
        if parsed.path == "/openapi.json":
            from api.catalog import openapi_spec
            return self._send(200, openapi_spec())
        if parsed.path == "/docs":
            # FastAPI genererar en Swagger-sida här. Dev-servern gjorde
            # INGENTING — medan kontraktstestets _FRAMEWORK-kommentar
            # påstod att "båda serverar dem". En omdirigering till
            # specifikationen är inte Swagger, men den är sann: samma
            # väg svarar i båda lagren, och svaret leder rätt.
            self._status = 307
            self.send_response(307)
            self.send_header("Location", "/openapi.json")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if parsed.path == "/v1/markets":
            return self._send(200, market_catalog())
        if parsed.path == "/v1/kpi":
            return self._send(200, kpi_catalog())
        if parsed.path == "/v1/setpoints":
            return self._send(200, setpoints_catalog())
        if parsed.path == "/v1/feeds":
            return self._send(200, feeds_catalog())
        if parsed.path == "/v1/decision":
            return self._send(200, decision_templates())
        if parsed.path == "/v1/strim":
            return self._send(200, entity_types())
        if parsed.path == "/v1/sources":
            from api.sources import sources_status
            return self._send(200, sources_status())
        if parsed.path == "/v1/entrypoints":
            from engine.entrypoints import entrypoints
            return self._send(200, entrypoints())
        if parsed.path == "/v1/admin":
            from engine.admin import admin_countries, admin_units
            qs = parse_qs(parsed.query)
            country = qs.get("country", [""])[0]
            if country:
                try:
                    return self._send(200, admin_units(
                        country, level=int(qs.get("level", ["1"])[0]),
                        parent=qs.get("parent", [""])[0]))
                except ValueError as e:
                    return self._send(404, {"error": str(e)})
            return self._send(200, admin_countries())
        if parsed.path == "/v1/households":
            return self._send(200, {"households": [
                {"id": k, "label_en": v["label_en"],
                 "means_en": v["means_en"], "weights": v["weights"]}
                for k, v in HOUSEHOLDS.items()]})
        if parsed.path == "/v1/brief":
            return self._send(200, brief_catalog())
        if parsed.path == "/v1/provenance":
            cls = parse_qs(parsed.query).get("cls", [""])[0]
            try:
                return self._send(200, {**provenance_summary(),
                                        "parameters": provenance_parameters(cls)})
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/corroboration":
            return self._send(200, corroboration_cat())
        if parsed.path == "/v1/sensors":
            return self._send(200, sensor_catalog())
        if parsed.path == "/v1/surface":
            detail = parse_qs(parsed.query).get("detail", [""])[0]
            return self._send(200, surface(detail.lower() in ("1", "true")))
        if parsed.path == "/v1/chain":
            return self._send(200, chain_overview())
        if parsed.path == "/v1/infrastructure":
            from engine.infrastructure import catalog as infra_catalog
            return self._send(200, infra_catalog())
        if parsed.path == "/v1/infrastructure/due":
            from engine import infrastructure as I
            t = self._tenant()
            return self._send(200, I.due(
                insp_engine.all_assets(t),
                insp_engine.all_observations(t)))
        if parsed.path == "/v1/reality-kpi":
            from engine.reality_kpi import reality_kpi
            t = self._tenant()
            return self._send(200, reality_kpi(
                insp_engine.all_assets(t), insp_engine.all_routines(t),
                insp_engine.all_checks(t), insp_engine.all_observations(t)))
        if parsed.path == "/v1/land":
            from engine.land import catalog as land_catalog
            return self._send(200, land_catalog())
        if parsed.path == "/v1/housing-market":
            from engine.housing_market import catalog as hm_catalog
            return self._send(200, hm_catalog())
        if parsed.path == "/v1/leads":
            from engine import leads as LD
            return self._send(200, {**LD.catalog(),
                                    "surveys": LD.all_surveys(self._tenant())})
        if parsed.path == "/v1/leads/results":
            from engine import leads as LD
            q = parse_qs(parsed.query)
            try:
                return self._send(200, LD.leads(
                    q.get("survey_id", [""])[0],
                    min_severity=q.get("min_severity", ["light"])[0],
                    tenant=self._tenant()))
            except LD.SurveyRefused as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/sponsorship":
            from engine import sponsorship as SP
            return self._send(200, {
                **SP.catalog(),
                "campaigns": SP.all_campaigns(self._tenant())})
        if parsed.path == "/v1/sponsorship/stats":
            from engine import sponsorship as SP
            q = parse_qs(parsed.query)
            try:
                return self._send(200, SP.stats(
                    q.get("campaign_id", [""])[0], tenant=self._tenant()))
            except SP.SponsorshipRefused as e:
                return self._send(404, {"error": str(e)})
        if parsed.path == "/v1/company":
            return self._send(200, {
                **company_engine.catalog(),
                "profile": company_engine.get_profile(self._tenant())})
        if parsed.path == "/v1/company/logo":
            return self._send(200, {
                "logo": company_engine.get_logo(self._tenant())})
        if parsed.path == "/v1/company/logo/raw":
            q = parse_qs(parsed.query)
            tenant = q.get("tenant", [""])[0]
            if not tenant:
                return self._send(422, {
                    "error": "tenant query parameter is required"})
            ut = company_engine.get_logo_bytes(tenant)
            if ut is None:
                return self._send(404, {
                    "error": "no logo uploaded for this tenant"})
            content, content_type = ut
            return self._send_bytes(200, content_type, content)
        if parsed.path == "/v1/staff":
            return self._send(200, {
                **staff_engine.catalog(),
                "staff": staff_engine.all_staff(self._tenant())})
        if parsed.path == "/v1/credentials":
            return self._send(200, credentials_engine.catalog())
        if parsed.path == "/v1/deliveries":
            q = parse_qs(parsed.query)
            return self._send(200, {
                **deliveries_engine.catalog(),
                "deliveries": deliveries_engine.all_deliveries(
                    self._tenant(),
                    limit=int(q.get("limit", ["100"])[0]))})
        if parsed.path == "/v1/deliveries/streaks":
            return self._send(200, {
                "streaks": deliveries_engine.failure_streaks(
                    self._tenant())})
        if parsed.path == "/v1/connections":
            from engine import connections as CN
            return self._send(200, {
                **CN.catalog(),
                # Läsvägen går genom masked() — nyckeln lagras för att
                # användas, aldrig för att ekas tillbaka.
                "connections": [CN.masked(r) for r in
                                CN.all_connections(self._tenant())]})
        if parsed.path == "/v1/pushes":
            from engine.pushes import catalog as pushes_catalog
            return self._send(200, pushes_catalog())
        if parsed.path == "/v1/commercial":
            from engine.commercial import catalog as _kommersiell
            return self._send(200, _kommersiell())
        if parsed.path == "/v1/offering":
            plan = parse_qs(parsed.query).get("plan", [""])[0]
            try:
                return self._send(200, offering(plan))
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/registers":
            return self._send(200, {**register_catalog(),
                                    "client": RegisterClient().status()})
        if parsed.path == "/v1/customer/journey":
            return self._send(200, customer_engine.journey())
        if parsed.path == "/v1/visitor/contract":
            return self._send(200, visitor_engine.contract())
        if parsed.path == "/v1/inbox":
            sub = parse_qs(parsed.query).get("subscriber", [""])[0]
            return self._send(200, {
                "subscriptions": inbox_engine.subscriptions(sub),
                "stake_kinds": list(inbox_engine.STAKE_WEIGHT)})
        if parsed.path == "/v1/assets":
            return self._send(200, {"assets": insp_engine.all_assets(
                self._tenant()), "source": "customer"})
        if parsed.path == "/v1/routines":
            return self._send(200, {"routines": insp_engine.all_routines(
                self._tenant()), **insp_engine.catalog()})
        if parsed.path == "/v1/inspections/due":
            return self._send(200, insp_engine.due_now(self._tenant()))
        if parsed.path == "/v1/inspections/compliance":
            return self._send(200, insp_engine.report(self._tenant()))
        if parsed.path == "/v1/inspections/exceptions":
            return self._send(200,
                              insp_engine.exception_feed(self._tenant()))
        if parsed.path == "/v1/mrai/compare":
            q = parse_qs(parsed.query)
            m = [x for x in q.get("markets", [""])[0].split(",") if x]
            return self._send(200, mrai_engine.compare(m or None))
        if parsed.path == "/v1/mrai":
            q = parse_qs(parsed.query)
            marknad = q.get("market", [""])[0]
            if not marknad:
                return self._send(200, mrai_engine.catalog())
            return self._send(200, mrai_engine.mrai(marknad))
        if parsed.path == "/v1/integrity/audit":
            from api.surface_scan import selfaudit_context
            from engine.selfaudit import run_audit
            return self._send(200, run_audit(selfaudit_context()))
        if parsed.path == "/v1/analysis":
            q = parse_qs(parsed.query)
            return self._send(200, {
                **analysis_engine.register(q.get("kind", [""])[0],
                                           q.get("market", [""])[0]),
                **analysis_engine.catalog()})
        if parsed.path == "/v1/coverage/markets":
            q = parse_qs(parsed.query)
            marknader = [m for m in q.get("markets", [""])[0].split(",") if m]
            return self._send(200, compare_markets(marknader or None))
        if parsed.path == "/v1/coverage":
            q = parse_qs(parsed.query)
            return self._send(200, coverage(q.get("market", [""])[0]))
        if parsed.path == "/v1/export":
            return self._send(200, export_catalog())
        if parsed.path == "/v1/schedules":
            return self._send(200, {
                "jobs": scheduler.all_jobs(self._tenant()),
                **scheduler.catalog(), **ticker_status()})
        if parsed.path == "/v1/monitors":
            return self._send(200, monitors_engine.catalog())
        if parsed.path == "/v1/kolada":
            return self._send(200, KoladaClient().status())
        if parsed.path == "/v1/svk":
            return self._send(200, SvkClient().status())
        if parsed.path == "/v1/wages":
            return self._send(200, wage_catalog())
        if parsed.path == "/v1/outcomes/calibration":
            return self._send(200, outcome_calibration())
        if parsed.path == "/v1/decisions/ledger":
            return self._send(200,
                              accountability_ledger(tenant=self._tenant()))
        if parsed.path == "/v1/segments":
            return self._send(200, segment_catalog())
        if parsed.path == "/v1/products":
            return self._send(200, product_catalog())
        if parsed.path == "/v1/plans":
            return self._send(200, plans_catalog())
        if parsed.path == "/v1/entitlements":
            p = self._principal
            return self._send(200, {"tenant": p.tenant, "roll": p.role,
                                    "plan": p.plan, "tillagg": list(p.addons),
                                    "capabilities": sorted(p.capabilities)})
        if parsed.path == "/v1/platform/status":
            return self._send(200, platform_status(
                AAMOS, RESOLVER, STORE, build_health, source_status))
        if parsed.path == "/v1/watch":
            return self._send(200, watch(AAMOS, RESOLVER, source_status))
        if parsed.path == "/v1/agents":
            return self._send(200, aamos_agents(AAMOS))
        if parsed.path == "/v1/indices":
            kat = index_catalog()
            if self._live_locked():
                for ix in kat:
                    if ix["niva"] == "live":
                        ix["last"] = True
                        ix["las_notis_en"] = upgrade_hint_en(
                            "intelligence_map_live")
            return self._send(200, kat)
        if parsed.path == "/v1/indices/families":
            return self._send(200, index_families())
        if parsed.path == "/v1/indices/map":
            q = parse_qs(parsed.query)
            from engine.indices import INDEX_TYPES
            ix = INDEX_TYPES.get(q.get("index_id", [""])[0])
            if ix and ix.niva == "live" and self._live_locked():
                return self._send(403, {"error": "Live layers require a "
                                        "subscription. " + upgrade_hint_en(
                                            "intelligence_map_live")})
            try:
                return self._send(200, index_map(
                    q.get("index_id", [""])[0],
                    market=q.get("market", ["se"])[0], resolver=RESOLVER))
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/service/map":
            q = parse_qs(parsed.query)
            try:
                return self._send(200, service_demand_map(
                    q.get("product_id", [""])[0],
                    market=q.get("market", ["se"])[0],
                    target_year=int(q.get("target_year", ["2031"])[0]),
                    resolver=RESOLVER))
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/segments/map":
            q = parse_qs(parsed.query)
            try:
                return self._send(200, segment_map(
                    q.get("segment_id", [""])[0],
                    market=q.get("market", ["se"])[0], resolver=RESOLVER))
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/workforce/occupations":
            return self._send(200, occupation_catalog())
        if parsed.path == "/v1/workforce/map":
            q = parse_qs(parsed.query)
            try:
                return self._send(200, national_map(
                    q.get("occupation_id", [""])[0],
                    int(q.get("target_year", ["2035"])[0]), resolver=RESOLVER,
                    market=q.get("market", ["se"])[0]))
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/workforce/global-map":
            q = parse_qs(parsed.query)
            try:
                return self._send(200, global_map(
                    q.get("occupation_id", [""])[0],
                    int(q.get("target_year", ["2035"])[0]),
                    group=q.get("group", ["eu"])[0], resolver=RESOLVER))
            except ValueError as e:
                return self._send(422, {"error": str(e)})
        if parsed.path == "/v1/profiles":
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
            except ValueError:
                return self._send(422, {"error": "limit must be an integer"})
            return self._send(200, STORE.list_profiles(
                min(max(limit, 1), 200), tenant=self._tenant()))
        if parsed.path.startswith("/v1/profiles/"):
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            doc = STORE.get_profile(parsed.path.rsplit("/", 1)[1],
                                    tenant=self._tenant())
            return self._send(200, doc) if doc is not None else \
                self._send(404, {"error": "Unknown profile."})
        if parsed.path == "/v1/reports":
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["20"])[0])
            except ValueError:
                return self._send(422, {"error": "limit must be an integer"})
            return self._send(200, STORE.list_reports(
                min(max(limit, 1), 200), tenant=self._tenant()))
        if parsed.path.startswith("/v1/reports/"):
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            doc = STORE.get_report(parsed.path.rsplit("/", 1)[1],
                                   tenant=self._tenant())
            return self._send(200, doc) if doc is not None else \
                self._send(404, {"error": "Unknown report id."})
        self._send(404, {"error": "not found"})

    def _route_post(self):
        try:
            req = self._read_body()
            if self.path == "/v1/analyze":
                loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                               address=req.get("address", ""),
                               radius_minutes=int(req.get("radius_minutes", 10)))
                report = analyze(loc, req["vertical"], resolver=RESOLVER).to_dict()
                if STORE is not None:
                    report["report_id"] = STORE.save_report(
                        report, created_at=time.time(),
                        tenant=self._tenant())
                return self._send(200, report)
            if self.path == "/v1/profiles":
                if STORE is None:
                    return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
                p = profile_from_dict(req)
                return self._send(200, {"profile_id": STORE.save_profile(
                    p.to_dict(), created_at=time.time(),
                    tenant=self._tenant())})
            if self.path == "/v1/kpi/evaluate":
                return self._send(200, evaluate_kpi(
                    str(req["code"]), float(req["value"]),
                    None if req.get("previous") is None
                    else float(req["previous"])))
            if self.path == "/v1/lambda":
                return self._send(200, lambda_score(
                    {str(k): float(v) for k, v in
                     (req.get("axes") or {}).items()}))
            if self.path == "/v1/setpoints/assess":
                return self._send(200, assess_zone(
                    str(req["code"]), float(req["value"])))
            if self.path == "/v1/cite":
                claim = build_claim(
                    str(req.get("statement", "")), req.get("value"),
                    req.get("source") or {}, req.get("jurisdiction") or {},
                    req.get("time") or {}, unit=req.get("unit", ""),
                    method=req.get("method", "observed"),
                    uncertainty=req.get("uncertainty", ""),
                    owners=req.get("owners") or {})
                ok, missing = validate_governance(claim)
                return self._send(200, {
                    "claim": claim,
                    "citations": {s: cite(claim, s)
                                  for s in ("text", "apa", "bibtex")},
                    "governance": {"ok": ok, "missing": missing},
                    "verified": verify_claim(claim)})
            if self.path == "/v1/feeds/events":
                return self._send(200, {"events": generate_feed(
                    str(req["feed"]), req.get("rows") or [])})
            if self.path == "/v1/worthiness":
                return self._send(200, select_for_wrap(
                    req.get("snapshots") or []))
            if self.path == "/v1/decision":
                return self._send(200, decision_evaluate(
                    str(req["template"]), req.get("answers") or {}))
            if self.path == "/v1/outcomes":
                rec = log_outcome(
                    req.get("location") or {}, str(req["vertical"]),
                    float(req["predicted_score"]), bool(req["survived"]),
                    months_active=int(req.get("months_active", 0)),
                    revenue_index=req.get("revenue_index"),
                    established_at=str(req.get("established_at", "")))
                return self._send(200, {"id": record_outcome(rec),
                                        "calibration": outcome_calibration()})
            if self.path == "/v1/outcomes/roi":
                return self._send(200, expected_roi(float(req["score"])))
            if self.path == "/v1/decisions/commit":
                return self._send(200, commit_decision(
                    str(req["decision"]), req.get("owners") or {},
                    req.get("expected") or {}, kpi_ids=req.get("kpi_ids") or [],
                    horizon_months=int(req.get("horizon_months", 0)),
                    committed_at=str(req.get("committed_at", "")),
                    tenant=self._tenant()))
            if self.path == "/v1/decisions/resolve":
                dcn = get_decision(str(req["decision_id"]))
                if dcn is None:
                    return self._send(404, {"error": "unknown decision_id"})
                return self._send(200, resolve_decision(
                    dcn, float(req["actual_value"]),
                    baseline=req.get("baseline"),
                    resolved_at=str(req.get("resolved_at", ""))))
            if self.path == "/v1/flows/expected-value":
                from engine.flows import expected_value
                return self._send(200, expected_value(
                    req.get("costs") or [], req.get("benefits") or [],
                    horizon_years=int(req.get("horizon_years", 1)),
                    decision=str(req.get("decision", "")),
                    currency=str(req.get("currency", "USD"))))
            if self.path == "/v1/livability":
                return self._send(200, livability_ranking(
                    str(req["occupation"]),
                    str(req.get("household", "single")),
                    markets=req.get("markets") or ["se"],
                    top_n=min(max(int(req.get("top_n", 10)), 1), 40),
                    per_market=min(max(int(req.get("per_market", 12)), 1), 40),
                    citizenship=str(req.get("citizenship", "eu")),
                    resolver=RESOLVER))
            if self.path == "/v1/merit":
                try:
                    if req.get("region"):
                        return self._send(200, region_merit(
                            str(req["region"]), market=str(req.get("market", "se")),
                            resolver=RESOLVER))
                    return self._send(200, market_merit(
                        str(req.get("market", "se")),
                        top_n=min(max(int(req.get("top_n", 10)), 1), 40),
                        resolver=RESOLVER))
                except ValueError as e:
                    return self._send(404, {"error": str(e)})
            if self.path == "/v1/corroboration":
                return self._send(200, corroboration_assess(
                    req.get("sources") or []))
            if self.path == "/v1/brief":
                try:
                    return self._send(200, daily_brief(
                        req.get("reports") or [], areas=req.get("areas") or [],
                        sectors=req.get("sectors") or [],
                        limit=min(max(int(req.get("limit", 20)), 1), 100),
                        date=str(req.get("date", "")),
                        plan=str(req.get("plan", "")),
                        own_assets=bool(req.get("own_assets", False))))
                except ValueError as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/brief/report":
                return self._send(200, brief_report(
                    str(req["kind"]), title=str(req.get("title", "")),
                    summary_en=str(req.get("summary_en", "")),
                    areas=req.get("areas") or [],
                    sectors=req.get("sectors") or None,
                    evidence=req.get("evidence") or [],
                    confidence_inputs=req.get("confidence_inputs") or {},
                    snapshot=req.get("snapshot") or {},
                    discrepancy_en=str(req.get("discrepancy_en", "")),
                    options=req.get("options") or None,
                    observed_at=str(req.get("observed_at", ""))))
            if self.path == "/v1/saturation":
                try:
                    return self._send(200, market_saturation(
                        str(req["vertical"]), str(req["region"]),
                        market=str(req.get("market", "se")), resolver=RESOLVER,
                        peer_limit=min(max(int(req.get("peer_limit", 25)), 5), 60)))
                except ValueError as e:
                    return self._send(404, {"error": str(e)})
            if self.path == "/v1/customer/stage":
                return self._send(200, customer_engine.stage(
                    req.get("payload") or {}))
            if self.path == "/v1/visitor":
                prof = visitor_engine.from_onboarding(req.get("payload") or {})
                return self._send(200, {"profile": prof,
                                        "guide": visitor_engine.guide(prof)})
            if self.path == "/v1/inbox/subscribe":
                return self._send(200, inbox_engine.subscribe(
                    str(req.get("subscriber", "")), str(req.get("role", "citizen")),
                    req.get("stakes") or [],
                    min_severity=str(req.get("min_severity", "medium")),
                    threshold=float(req.get("threshold", 50.0))))
            if self.path == "/v1/inbox/route":
                evs = list(req.get("events") or [])
                evs += [inbox_engine.from_feed_event(e)
                        for e in (req.get("feed_events") or [])]
                evs += [inbox_engine.from_finding(f)
                        for f in (req.get("findings") or [])]
                decisions = accountability_all_decisions(self._tenant())
                who = str(req.get("subscriber", ""))
                if who:
                    return self._send(200, inbox_engine.brief(
                        who, evs, decisions=decisions, now=req.get("now", "")))
                return self._send(200, inbox_engine.route(
                    evs, decisions=decisions, now=req.get("now", "")))
            if self.path == "/v1/assets":
                rec = insp_engine.asset(
                    req["id"], req["kind"],
                    label_en=req.get("label_en", ""),
                    lat=req.get("lat"), lon=req.get("lon"),
                    address=req.get("address", ""),
                    installed_at=req.get("installed_at", ""),
                    tenant=self._tenant())
                insp_engine.save_asset(rec)
                return self._send(201, rec)
            if self.path == "/v1/routines":
                rec = insp_engine.routine(
                    req["id"], req["label_en"],
                    req["applies_to"],
                    int(req["every_days"]),
                    checks=tuple(req.get("checks") or ()),
                    weekday=req.get("weekday"),
                    season=tuple(req["season"]) if req.get("season") else None,
                    owners=req.get("owners"), expected=req.get("expected"),
                    audience_=req.get("audience"),
                    tenant=self._tenant())
                insp_engine.save_routine(rec)
                return self._send(201, rec)
            if self.path == "/v1/inspections/verdict":
                rec = insp_engine.record(
                    req["asset_id"], req["routine_id"],
                    req["verdict"],
                    performed_at=req.get("performed_at", ""),
                    mission_id=req.get("mission_id", ""),
                    evidence_ref=req.get("evidence_ref", ""),
                    observed_by=req.get("observed_by", ""),
                    note_en=req.get("note_en", ""),
                    tenant=self._tenant())
                insp_engine.save_check(rec)
                # Godkänt utfall ⇒ signerat kvitto ⇒ in i kundens
                # system. Underkänt certifieras inte (motorn vägrar),
                # och en misslyckad leverans redovisas — aldrig döljs.
                return self._send(201, _med_credential(
                    rec, "check_passed",
                    {"asset_id": rec["asset_id"],
                     "routine_id": rec["routine_id"],
                     "verdict": rec["verdict"],
                     "performed_at": rec.get("performed_at", ""),
                     "evidence_ref": rec.get("evidence_ref", "")},
                    tenant=self._tenant(),
                    mission_id=rec.get("mission_id", "")))
            if self.path == "/v1/analysis/run":
                return self._send(200, analysis_engine.run(
                    req.get("market") or DEFAULT_MARKET,
                    resolver=RESOLVER,
                    limit=int(req.get("limit", 0)),
                    as_of=str(req.get("as_of", ""))))
            if self.path == "/v1/schedules":
                kinds = scheduler.JOB_KINDS
                k = kinds.get(req.get("kind", ""))
                if k and not self._har(k["capability"]):
                    return self._send(403, {"error": (
                        f"Scheduling {req['kind']!r} needs the "
                        f"{k['capability']} package. See /v1/plans.")})
                if req.get("kind") == "push":
                    # Datamängdens egen kapabilitet — samma grind som
                    # /v1/export, annars är pushen en väg runt paketet.
                    d = {x["id"]: x for x in
                         export_catalog()["datasets"]}.get(
                        (req.get("params") or {}).get("dataset", ""))
                    if d and not self._har(d["capability"]):
                        return self._send(403, {"error": (
                            f"Pushing {d['id']!r} needs the same package "
                            f"as {d['answers_from']} ({d['capability']}). "
                            f"See /v1/plans.")})
                rec = scheduler.job(
                    req["id"], req["kind"],
                    cadence=req.get("cadence"), params=req.get("params"),
                    enabled=bool(req.get("enabled", True)),
                    tenant=self._tenant())
                scheduler.save_job(rec)
                return self._send(201, rec)
            if self.path == "/v1/schedules/run":
                return self._send(200, scheduler.run_due(
                    self._tenant(), req.get("now"),
                    {k for k, v in scheduler.JOB_KINDS.items()
                     if self._har(v["capability"])}))
            if self.path == "/v1/infrastructure/observe":
                from engine import infrastructure as I
                try:
                    rec = I.observe(
                        req.get("object_id", ""), req.get("kind", ""),
                        req.get("values") or {},
                        mission_id=req.get("mission_id", ""),
                        observer_network=req.get("observer_network",
                                                 "quixzoom"),
                        tenant=self._tenant())
                except I.ObservationRefused as e:
                    return self._send(422, {"error": str(e)})
                insp_engine.save_observation(rec)
                return self._send(201, rec)
            if self.path == "/v1/infrastructure/status":
                from engine import infrastructure as I
                try:
                    return self._send(200, I.status(
                        req.get("object_id", ""), req.get("kind", ""),
                        insp_engine.all_observations(self._tenant())))
                except I.ObservationRefused as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/infrastructure/freshness":
                from engine import infrastructure as I
                try:
                    return self._send(200, I.freshness_record(
                        req.get("object_id", ""), req.get("kind", ""),
                        insp_engine.all_observations(self._tenant())))
                except I.ObservationRefused as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/infrastructure/sla":
                from engine import infrastructure as I
                t = self._tenant()
                try:
                    return self._send(200, I.sla_report(
                        insp_engine.all_assets(t),
                        insp_engine.all_observations(t),
                        promised_minutes=float(
                            req.get("promised_minutes", 0)),
                        window_hours=float(req.get("window_hours", 168))))
                except (I.ObservationRefused, ValueError) as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/land/assess":
                from engine.land import assess as land_assess
                try:
                    return self._send(200, land_assess(
                        req.get("region_code", ""),
                        req.get("market", "se"), resolver=RESOLVER))
                except ValueError as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/land/compare":
                from engine.land import LandRefused
                from engine.land import compare as land_compare
                try:
                    return self._send(200, land_compare(
                        req.get("region_codes") or [],
                        req.get("market", "se"), resolver=RESOLVER))
                except (LandRefused, ValueError) as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/housing-market/price":
                from engine.housing_market import price as hm_price
                try:
                    return self._send(200, hm_price(
                        req.get("market", "se"), req.get("region_code", "")))
                except ValueError as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/housing-market/standard":
                from engine.housing_market import standard as hm_standard
                try:
                    return self._send(200, hm_standard(
                        req.get("region_code", ""),
                        req.get("market", "se"), resolver=RESOLVER))
                except ValueError as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/housing-market/compare":
                from engine.housing_market import price_vs_standard as hm_pvs
                try:
                    return self._send(200, hm_pvs(
                        req.get("market", "se"), req.get("region_code", ""),
                        resolver=RESOLVER))
                except ValueError as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/housing-market/master-plans":
                from engine.housing_market import master_plans as hm_plans
                try:
                    return self._send(200, hm_plans(
                        req.get("market", "se"), req.get("region_code", "")))
                except ValueError as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/leads/survey":
                from engine import leads as LD
                try:
                    rec = LD.survey(req.get("id", ""),
                                    req.get("label_en", ""),
                                    req.get("condition", ""),
                                    req.get("addresses") or [],
                                    tenant=self._tenant())
                except LD.SurveyRefused as e:
                    return self._send(422, {"error": str(e)})
                LD.save_survey(rec)
                return self._send(201, rec)
            if self.path == "/v1/leads/dispatch":
                from engine import leads as LD
                surv = next((s for s in LD.all_surveys(self._tenant())
                            if s["id"] == req.get("survey_id", "")), None)
                if surv is None:
                    return self._send(404, {
                        "error": "no such survey for this tenant"})
                return self._send(200, LD.dispatch_survey(surv))
            if self.path == "/v1/leads/verdict":
                from engine import leads as LD
                try:
                    rec = LD.verdict(req.get("survey_id", ""),
                                     req.get("address_id", ""),
                                     req.get("severity", ""),
                                     mission_id=req.get("mission_id", ""),
                                     evidence_ref=req.get("evidence_ref", ""),
                                     note_en=req.get("note_en", ""),
                                     tenant=self._tenant())
                except LD.SurveyRefused as e:
                    return self._send(422, {"error": str(e)})
                LD.save_verdict(rec)
                return self._send(201, rec)
            if self.path == "/v1/sponsorship/campaigns":
                from engine import sponsorship as SP
                try:
                    rec = SP.campaign(
                        req.get("id", ""),
                        req.get("sponsor_visible_en", ""),
                        req.get("mission_class", ""),
                        req.get("brief_en", ""),
                        budget=float(req.get("budget", 0)),
                        currency=req.get("currency", "SEK"),
                        rewards=tuple(req.get("rewards") or ()),
                        market=req.get("market", "se"),
                        region_codes=tuple(req.get("region_codes") or ()),
                        max_per_day=int(req.get("max_per_day", 0)),
                        rights_agreement_ref=req.get(
                            "rights_agreement_ref", ""),
                        co_sponsors=tuple(req.get("co_sponsors") or ()),
                        tenant=self._tenant())
                except (SP.SponsorshipRefused, ValueError, TypeError) as e:
                    return self._send(422, {"error": str(e)})
                SP.save_campaign(rec)
                return self._send(201, rec)
            if self.path == "/v1/sponsorship/mission":
                from engine import sponsorship as SP
                kamp = next((k for k in SP.all_campaigns(self._tenant())
                             if k["id"] == req.get("campaign_id")), None)
                if kamp is None:
                    return self._send(404, {"error": (
                        f"unknown campaign {req.get('campaign_id')!r}")})
                grind = SP.can_order(
                    kamp, today_count=int(req.get("today_count", 0)))
                if not grind["allowed"]:
                    return self._send(409, {"error": grind["why_en"]})
                return self._send(200, SP.mission_body(
                    kamp, region_code=req.get("region_code", ""),
                    lat=req.get("lat"), lon=req.get("lon")))
            if self.path == "/v1/sponsorship/completion":
                from engine import sponsorship as SP
                try:
                    rec = SP.completion(
                        req.get("campaign_id", ""),
                        req.get("mission_id", ""),
                        region_code=req.get("region_code", ""),
                        quality_band=req.get("quality_band", ""),
                        verdicts=req.get("verdicts"),
                        settlement_ref=req.get("settlement_ref", ""),
                        tenant=self._tenant())
                except SP.SponsorshipRefused as e:
                    return self._send(422, {"error": str(e)})
                SP.save_completion(rec)
                return self._send(201, _med_credential(
                    rec, "sponsored_completion",
                    {"campaign_id": rec["campaign_id"],
                     "region_code": rec.get("region_code", ""),
                     "quality_band": rec.get("quality_band", ""),
                     "verdicts": rec.get("verdicts", {})},
                    tenant=self._tenant(),
                    mission_id=rec.get("mission_id", "")))
            if self.path == "/v1/sponsorship/order":
                from engine import sponsorship as SP
                if not any(k["id"] == req.get("campaign_id")
                           for k in SP.all_campaigns(self._tenant())):
                    return self._send(404, {"error": (
                        f"unknown campaign {req.get('campaign_id')!r}")})
                try:
                    # 409, inte 422: kampanjen finns men grinden säger
                    # nej — budgettaket eller pacingen ÄR svaret.
                    return self._send(201, SP.order_mission(
                        req.get("campaign_id", ""),
                        tenant=self._tenant(),
                        region_code=req.get("region_code", ""),
                        lat=req.get("lat"), lon=req.get("lon"),
                        today_count=int(req.get("today_count", 0))))
                except SP.SponsorshipRefused as e:
                    return self._send(409, {"error": str(e)})
            if self.path == "/v1/sponsorship/status":
                from engine import sponsorship as SP
                try:
                    return self._send(200, SP.set_status(
                        req.get("campaign_id", ""),
                        req.get("status", ""), tenant=self._tenant()))
                except SP.SponsorshipRefused as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/company":
                try:
                    rec = company_engine.profile(
                        self._tenant(),
                        name=req.get("name", ""),
                        about_en=req.get("about_en", ""),
                        logo_url=req.get("logo_url", ""),
                        website=req.get("website", ""),
                        brand_color=req.get("brand_color", ""),
                        org_ref=req.get("org_ref", ""))
                except company_engine.ProfileRefused as e:
                    return self._send(422, {"error": str(e)})
                company_engine.save_profile(rec)
                return self._send(201, rec)
            if self.path == "/v1/company/logo":
                try:
                    rec = company_engine.save_logo(
                        self._tenant(), req.get("filename", ""),
                        req.get("content_b64", ""))
                except company_engine.ProfileRefused as e:
                    return self._send(422, {"error": str(e)})
                return self._send(201, rec)
            if self.path == "/v1/company/logo/remove":
                borta = company_engine.delete_logo(self._tenant())
                return self._send(200, {"deleted": borta})
            if self.path == "/v1/staff":
                try:
                    rec = staff_engine.member(
                        req.get("zoomer_ref", ""),
                        tenant=self._tenant(),
                        role_label_en=req.get("role_label_en", ""))
                except staff_engine.StaffRefused as e:
                    return self._send(422, {"error": str(e)})
                staff_engine.save_staff(rec)
                return self._send(201, rec)
            if self.path == "/v1/staff/invite":
                try:
                    rec = staff_engine.invite(
                        tenant=self._tenant(),
                        role_label_en=req.get("role_label_en", ""))
                except staff_engine.StaffRefused as e:
                    return self._send(422, {"error": str(e)})
                staff_engine.save_staff(rec)
                return self._send(201, rec)
            if self.path == "/v1/staff/claim":
                try:
                    return self._send(201, staff_engine.claim_invite(
                        req.get("invite_id", ""),
                        req.get("zoomer_ref", ""),
                        tenant=self._tenant()))
                except staff_engine.StaffRefused as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/staff/remove":
                borta = staff_engine.remove_staff(
                    req.get("id", ""), tenant=self._tenant())
                return self._send(200, {"deleted": borta})
            if self.path == "/v1/inspections/exceptions/report":
                from engine import connections as CN
                from integrations import feedback
                t = self._tenant()
                if req.get("connection"):
                    try:
                        kopp = CN.get_connection(req["connection"],
                                                 tenant=t)
                    except CN.ConnectionRefused as e:
                        return self._send(404, {"error": str(e)})
                else:
                    kopp = CN.feedback_target(t)
                return self._send(200, feedback.report_exceptions(
                    insp_engine.exception_feed(t, req.get("today", "")),
                    kopp))
            if self.path == "/v1/credentials/verify":
                return self._send(200, credentials_engine.verify(
                    req.get("credential") or {}, tenant=self._tenant()))
            if self.path == "/v1/deliveries/verify":
                return self._send(200, deliveries_engine.verify_delivery(
                    req.get("delivery_id", ""),
                    req.get("body_sha256", ""),
                    tenant=self._tenant()))
            if self.path == "/v1/deliveries/retry":
                from integrations.redelivery import retry
                return self._send(200, retry(
                    req.get("delivery_id", ""), tenant=self._tenant()))
            if self.path == "/v1/connections":
                from engine import connections as CN
                try:
                    rec = CN.connection(req.get("provider", ""),
                                        req.get("config") or {},
                                        tenant=self._tenant())
                except CN.ConnectionRefused as e:
                    return self._send(422, {"error": str(e)})
                CN.save_connection(rec)
                return self._send(201, CN.masked(rec))
            if self.path == "/v1/connections/delete":
                from engine import connections as CN
                borta = CN.delete_connection(req.get("provider", ""),
                                             tenant=self._tenant())
                return self._send(200, {
                    "deleted": borta,
                    "note_en": "" if borta else (
                        "nothing to delete — no such connection for "
                        "this tenant, which is a state, not an error")})
            if self.path == "/v1/connections/test":
                from engine import connections as CN
                from integrations import llm
                try:
                    rec = CN.get_connection(req.get("provider", ""),
                                            tenant=self._tenant())
                except CN.ConnectionRefused as e:
                    return self._send(404, {"error": str(e)})
                resultat = llm.probe(rec)
                if resultat["verified"]:
                    rec = dict(rec)
                    rec["status"] = "verified"
                    rec["verified_at"] = resultat["probed_at"]
                    CN.save_connection(rec)
                return self._send(200, resultat)
            if self.path == "/v1/connections/narrate":
                from engine import connections as CN
                from integrations import llm
                try:
                    rec = CN.get_connection(
                        req.get("provider", "anthropic"),
                        tenant=self._tenant())
                    return self._send(200, llm.narrate(
                        rec, req.get("analysis") or {},
                        question=req.get("question", "")))
                except CN.ConnectionRefused as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/pushes/preview":
                from engine.pushes import PushRefused, preview
                d = {x["id"]: x for x in
                     export_catalog()["datasets"]}.get(
                    req.get("dataset", ""))
                # Samma grind som /v1/export: förhandsvisningen får inte
                # bli en väg runt paketet.
                if d and not self._har(d["capability"]):
                    return self._send(403, {"error": (
                        f"Previewing {d['id']!r} needs the same package "
                        f"as its engine ({d['capability']}). "
                        f"See /v1/plans.")})
                try:
                    return self._send(200, preview(
                        req.get("dataset", ""), req.get("format", "csv"),
                        req.get("params") or {}, tenant=self._tenant()))
                except PushRefused as e:
                    return self._send(422, {"error": str(e)})
            if self.path == "/v1/export":
                # Datamängdens EGEN kapabilitet gäller också: annars vore
                # exporten en väg runt paketet — köp export, läs allt.
                d = {x["id"]: x for x in export_catalog()["datasets"]}.get(
                    req.get("dataset", ""))
                if d and not self._har(d["capability"]):
                    return self._send(403, {"error": (
                        f"Exporting {d['id']!r} needs the same package as "
                        f"{d['answers_from']} ({d['capability']}). "
                        f"See /v1/plans.")})
                return self._send(200, export_data(
                    req.get("dataset", ""), req.get("format", "csv"),
                    req.get("params") or {}, tenant=self._tenant()))
            if self.path == "/v1/inspections/dispatch":
                from integrations.quixzoom_dispatch import dispatch_due
                return self._send(200, dispatch_due(self._tenant()))
            if self.path == "/v1/monitors":
                return self._send(200, monitors_engine.define(
                    str(req["metric"]), str(req["scope"]), str(req["rule"]),
                    str(req.get("owner", "")), params=req.get("params") or {},
                    cadence=req.get("cadence") or None,
                    label=str(req.get("label", "")),
                    tenant=self._tenant()))
            if self.path == "/v1/monitors/evaluate":
                mon = req.get("monitor") or monitors_engine.get_monitor(
                    str(req.get("monitor_id", "")), self._tenant())
                if mon is None:
                    return self._send(404, {"error": "unknown monitor"})
                return self._send(200, monitors_engine.evaluate(
                    mon, req.get("series") or [],
                    evaluated_at=req.get("evaluated_at", "")))
            if self.path == "/v1/monitors/run":
                return self._send(200, monitors_engine.run_due(
                    monitors_engine.all_monitors(self._tenant()), req["now"],
                    req.get("series_by_id") or {}))
            if self.path == "/v1/monitors/escalate":
                return self._send(200, monitors_engine.escalate(
                    req["finding"], req.get("owners") or {},
                    req.get("expected") or {},
                    committed_at=str(req.get("committed_at", "")),
                    horizon_months=int(req.get("horizon_months", 0))))
            if self.path == "/v1/correlate":
                out = cross_domain(req.get("a") or [], req.get("b") or [],
                                   label_a=req.get("label_a", "A"),
                                   label_b=req.get("label_b", "B"))
                if req.get("control"):
                    out["partial"] = partial_correlation(
                        req["a"], req["b"], req["control"],
                        label_a=req.get("label_a", "A"),
                        label_b=req.get("label_b", "B"),
                        label_c=req.get("label_c", "C"))
                return self._send(200, out)
            if self.path == "/v1/correlate/cross-market":
                return self._send(200, cross_market(
                    req.get("markets") or [], label_a=req.get("label_a", "A"),
                    label_b=req.get("label_b", "B")))
            if self.path == "/v1/scenario":
                return self._send(200, scenario_project(
                    req.get("series") or [], req.get("sources") or [],
                    horizon=int(req.get("horizon", 3)),
                    coverage=float(req.get("coverage", 1.0)),
                    metric=str(req.get("metric", "indicator"))))
            if self.path == "/v1/event-study":
                if req.get("treated_pre") is not None:
                    return self._send(200, diff_in_diff(
                        req["treated_pre"], req.get("treated_post") or [],
                        req.get("control_pre") or [], req.get("control_post") or [],
                        metric=str(req.get("metric", "indicator")),
                        event=str(req.get("event", "intervention"))))
                if req.get("series") is not None and req.get("split_index") is not None:
                    return self._send(200, before_after(
                        req["series"], int(req["split_index"]),
                        metric=str(req.get("metric", "indicator")),
                        event=str(req.get("event", "intervention"))))
                return self._send(422, {"error": "provide series+split_index or the four DiD arrays"})
            if self.path == "/v1/benchmark":
                return self._send(200, benchmark(
                    float(req["value"]), req.get("peers") or [],
                    label=str(req.get("label", "unit")),
                    metric=str(req.get("metric", "ratio")),
                    higher_is_better=req.get("higher_is_better"),
                    sources=req.get("sources") or []))
            if self.path == "/v1/sensitive-association":
                return self._send(200, sensitive_association(
                    req.get("a") or [], req.get("b") or [], req.get("control") or [],
                    category=str(req.get("category", "")),
                    group_sizes=req.get("group_sizes") or [],
                    sources=req.get("sources") or [],
                    confounders=req.get("confounders") or [],
                    label_a=str(req.get("label_a", "attribute")),
                    label_b=str(req.get("label_b", "outcome")),
                    label_c=str(req.get("label_c", "confounder"))))
            if self.path == "/v1/wages/lookup":
                return self._send(200, wage(
                    str(req["occupation"]), str(req.get("market", DEFAULT_MARKET))))
            if self.path == "/v1/wages/compare":
                return self._send(200, wage_compare(
                    str(req["occupation"]), req.get("markets") or []))
            if self.path == "/v1/wages/context":
                return self._send(200, compensation_context(
                    str(req["occupation"]), str(req["region"])))
            if self.path == "/v1/corrections/submit":
                return self._send(200, submit_correction(
                    str(req["region"]), str(req["target_key"]),
                    float(req["proposed_value"]), str(req.get("source", "")),
                    str(req.get("submitter_id", "")),
                    current_value=req.get("current_value"),
                    note=str(req.get("note", ""))))
            if self.path == "/v1/corrections/consensus":
                return self._send(200, correction_consensus(
                    str(req["target_key"]), str(req["region"])))
            if self.path == "/v1/corrections/adapt":
                return self._send(200, adapt_correction(
                    str(req["target_key"]), str(req["region"])))
            if self.path == "/v1/strim/entity":
                ent = build_entity(
                    str(req["entity_type"]), str(req["slug"]),
                    str(req.get("name_en", "")), name_sv=req.get("name_sv", ""),
                    definition=req.get("definition", ""),
                    sources=req.get("sources") or [],
                    fields=req.get("fields") or {})
                return self._send(200, {
                    "entity": ent, "jsonld": to_jsonld(ent),
                    "citations": {s: strim_cite(ent, s)
                                  for s in ("text", "apa", "bibtex")}})
            if self.path == "/v1/ask":
                q = str(req.get("question", ""))
                kris = crisis_scan(q)   # autodetekterar språk/land
                if kris:
                    return self._send(200, kris)
                svar = ask(q, resolver=RESOLVER)
                block = classify_query(q)
                if block:
                    svar["neutrality"] = block
                if AAMOS.connected:
                    # Berikning i API-lagret – aldrig i kärnan, aldrig
                    # blockerande: kognitiv not utöver motorsvaret.
                    try:
                        svar["aamos_cognition"] = AAMOS.cognition_analysis(
                            str(req.get("question", "")))
                    except AamosUnavailable:
                        pass
                return self._send(200, svar)
            if self.path == "/v1/indices/assess":
                res = city_assessment(req["kommun_kod"],
                                      market=req.get("market", DEFAULT_MARKET),
                                      resolver=RESOLVER)
                if self._live_locked():
                    for row in res["index"]:
                        if row["niva"] == "live":
                            row.update({"varde": None, "band": None,
                                        "band_en": None, "drivare": [],
                                        "last": True,
                                        "narrativ_en": "Live layer – requires "
                                        "a subscription. " + upgrade_hint_en(
                                            "intelligence_map_live")})
                return self._send(200, res)
            if self.path == "/v1/service/analyze":
                return self._send(200, service_analysis(
                    req["kommun_kod"], market=req.get("market", DEFAULT_MARKET),
                    target_year=int(req.get("target_year", 2031)),
                    resolver=RESOLVER))
            if self.path == "/v1/segments/analyze":
                return self._send(200, segment_analysis(
                    req["kommun_kod"], market=req.get("market", DEFAULT_MARKET),
                    resolver=RESOLVER))
            if self.path == "/v1/report":
                rep = decision_report(
                    req["kommun_kod"], req["vertical"],
                    market=req.get("market", DEFAULT_MARKET),
                    resolver=RESOLVER)
                p = getattr(self, "_principal", None)
                if (p is not None
                        and "demand_intelligence" not in p.capabilities):
                    rep["service"] = {
                        "status": "locked",
                        "notis_en": upgrade_hint_en("demand_intelligence")}
                return self._send(200, rep)
            if self.path == "/v1/gaps":
                return self._send(200, gap_analysis(
                    req["vertical"], market=req.get("market", DEFAULT_MARKET),
                    resolver=RESOLVER,
                    top_n=min(max(int(req.get("top_n", 5)), 1), 20)))
            if self.path == "/v1/agents/chat":
                return self._send(200, agent_chat_safe(
                    AAMOS, str(req.get("message", "")),
                    req.get("agent_id")))
            if self.path == "/v1/cognition/brief":
                return self._send(200, cognition_brief_safe(
                    AAMOS, str(req.get("topic", ""))))
            if self.path == "/v1/plan":
                return self._send(200, establishment_plan(
                    req["kommun_kod"], req["vertical"],
                    market=req.get("market", DEFAULT_MARKET),
                    team_size=req.get("team_size", "2-5"),
                    budget_band=req.get("budget_band", "500k-2m"),
                    resolver=RESOLVER))
            if self.path == "/v1/risk":
                loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                               address=req.get("address", ""),
                               radius_minutes=int(req.get("radius_minutes", 10)))
                return self._send(200, assess(loc, req["vertical"],
                                              resolver=RESOLVER))
            if self.path == "/v1/opportunities":
                loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                               address=req.get("address", ""))
                return self._send(200, opportunity_intel(
                    loc, req["vertical"], resolver=RESOLVER,
                    specialization=req.get("specialization"),
                    team_size=req.get("team_size", "1"),
                    company_form=req.get("company_form", "aktiebolag"),
                    market=req.get("market", DEFAULT_MARKET),
                    programs_client=PROGRAMS))
            if self.path == "/v1/risk-intelligence":
                loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                               address=req.get("address", ""))
                return self._send(200, risk_intelligence(
                    loc, req["vertical"], resolver=RESOLVER,
                    specialization=req.get("specialization"),
                    market=req.get("market", DEFAULT_MARKET)))
            if self.path == "/v1/compare":
                return self._send(200, compare(req["locations"],
                                               req["vertical"],
                                               resolver=RESOLVER))
            if self.path == "/v1/workforce/forecast":
                return self._send(200, wf_forecast(
                    req["kommun_kod"], int(req.get("target_year", 2035)),
                    req.get("occupation_ids"), resolver=RESOLVER,
                    market=req.get("market", DEFAULT_MARKET)))
            if self.path == "/v1/workforce/simulate":
                return self._send(200, wf_simulate(
                    req["kommun_kod"], req["occupation_id"],
                    float(req.get("extra_places_per_year", 0)),
                    int(req.get("target_year", 2035)), resolver=RESOLVER,
                    market=req.get("market", DEFAULT_MARKET)))
            if self.path == "/v1/scan":
                raw = req.get("profile")
                if raw is None and req.get("profile_id"):
                    if STORE is None:
                        return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
                    raw = STORE.get_profile(req["profile_id"],
                                            tenant=self._tenant())
                    if raw is None:
                        return self._send(404, {"error": "Unknown profile."})
                if raw is None:
                    return self._send(422, {"error": "Provide profile or profile_id."})
                p = profile_from_dict(raw)
                top_n = min(max(int(req.get("top_n", 5)), 1), 20)
                return self._send(200, scan(p, resolver=RESOLVER, top_n=top_n,
                                            level=req.get("level", "oversikt"),
                                            market=req.get("market", DEFAULT_MARKET)))
            self._send(404, {"error": "not found"})
        except _BadRequest as e:
            self._send(400, {"error": str(e)})
        except _TooLarge as e:
            self._send(413, {"error": str(e)})
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
            self._send(422, {"error": _field_error(e)})

    # Största POST-kropp som läses. En Content-Length utan tak låter en
    # klient hålla en tråd (och godtyckligt mycket minne) genom att lova
    # byte den aldrig skickar — ThreadingHTTPServer ger en tråd per
    # anslutning, så några få sådana räcker för att tömma servern.
    MAX_BODY_BYTES = 1 << 20        # 1 MiB; största riktiga kroppen är ~50 kB

    def _read_body(self) -> dict:
        """Läs och tolka JSON-kroppen med tak, timeout och ärliga koder.

        Tre fel som tidigare blev 500 eller en hängd tråd:
          * Content-Length som inte är ett tal      → 400
          * Content-Length över taket               → 413
          * färre byte än utlovat (klienten ljuger) → 400, aldrig en hängning
        """
        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            return {}
        try:
            length = int(raw_len)
        except (TypeError, ValueError):
            raise _BadRequest("Content-Length must be an integer.") from None
        if length < 0:
            raise _BadRequest("Content-Length must not be negative.")
        if length > self.MAX_BODY_BYTES:
            raise _TooLarge(f"Request body exceeds "
                            f"{self.MAX_BODY_BYTES} bytes.")
        if length == 0:
            return {}
        body = self.rfile.read(length)
        if len(body) < length:
            # Utlovade fler byte än den skickade. Att vänta vidare är att
            # låta en klient hålla tråden hur länge den vill.
            raise _BadRequest(f"Incomplete request body: declared {length} "
                              f"bytes, received {len(body)}.")
        try:
            parsed = json.loads(body or b"{}")
        except json.JSONDecodeError as e:
            raise _BadRequest(f"Body is not valid JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise _BadRequest("Body must be a JSON object.")
        return parsed

    def log_message(self, fmt, *args):  # tystare logg
        pass


def _register_with_aamos(port: int) -> None:
    """Best-effort self-registrering i AAMOS service registry. Får aldrig
    hindra uppstart – ett fel loggas och ignoreras."""
    if not AAMOS.connected:
        return
    try:
        AAMOS.register_service(
            "landvex-opportunity-engine", port,
            endpoints=[e["path"] for eng in _catalog_engines()
                       for e in eng["endpoints"]])
        print("Registered with AAMOS service registry.")
    except Exception as e:                       # aldrig blockerande
        print(f"AAMOS registration skipped: {e}")


def _catalog_engines():
    from api.catalog import API_CATALOG
    return API_CATALOG["engines"]


def main(port: int | None = None) -> None:
    port = port or int(os.environ.get("LANDVEX_PORT", "8000"))
    # LANDVEX_HOST styr bindningen. Default 0.0.0.0 (deploy bakom nginx).
    # Sandlådan sätter 127.0.0.1 – på Windows slipper man då brandväggs-
    # dialogen som annars dyker upp vid bindning mot alla gränssnitt.
    host = os.environ.get("LANDVEX_HOST", "0.0.0.0")
    print(f"Opportunity Engine dev server: http://localhost:{port}")
    _register_with_aamos(port)
    # Schemaläggaren startas HÄR och inte vid import: en bakgrundstråd som
    # börjar beställa fältuppdrag bara för att någon importerat modulen är
    # en dyr överraskning. Avstängd om inte LANDVEX_SCHEDULER=on.
    if start_ticker():
        print(f"scheduler: on, every {ticker_status()['scheduler']['interval_s']:.0f}s")
    # Flertrådad + större accept-kö: tål burst-last utan att droppa
    # anslutningar (red-team: 200 samtidiga anrop). Produktionsvägen är
    # uvicorn/FastAPI, men denna server deployas också (systemd).
    class _Server(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 256
    _Server((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
