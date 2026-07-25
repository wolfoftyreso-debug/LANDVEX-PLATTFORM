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
from engine.registers import RegisterClient, register_catalog
from engine.saturation_scan import market_saturation
from engine import customer as customer_engine
from engine import visitor as visitor_engine
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

# Persistens: LANDVEX_DB = sökväg (default landvex.db) eller "off".
_DB = os.environ.get("LANDVEX_DB", "landvex.db")
STORE = SqliteStore(_DB) if _DB.lower() not in ("off", "0", "") else None
# Utfallskalibrering + ansvarsloop backas av lagret (överlever omstart).
set_outcome_store(STORE)
set_accountability_store(STORE)
set_corrections_store(STORE)
set_monitors_store(STORE)

# Gate delar lagret så månadskvoten överlever omstarter (om DB på).
GATE = Gate(store=STORE)

# Samma källkedja som produktions-API:t; LANDVEX_LIVE=0 → endast mock.
_LIVE = os.environ.get("LANDVEX_LIVE", "1") != "0"
_sources = production_sources() if _LIVE else []
if STORE is not None:
    _sources = [CachedSource(s, STORE) for s in _sources]
RESOLVER = Resolver(_sources + [MockSource()])


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict | list) -> None:
        self._status = code
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if getattr(self, "_request_id", None):
            self.send_header("X-Request-ID", self._request_id)
        self.end_headers()
        self.wfile.write(body)

    _OPEN_PATHS = ("/", "/index.html", "/sandbox", "/health", "/v1/plans",
                   "/openapi.json")

    def _live_locked(self) -> bool:
        p = getattr(self, "_principal", None)
        return p is not None and "intelligence_map_live" not in p.capabilities

    def _gated(self, method: str, route) -> None:
        """Auth → rate limit → routning → metrics + audit."""
        path = self.path
        if urlparse(path).path in self._OPEN_PATHS:
            return route()
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
        if parsed.path in ("/", "/index.html"):
            self._status = 200
            body = _FRONTEND.read_bytes()
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
            return self._send(200, [{"id": v.id, "label_en": v.label_en}
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
            return self._send(200, accountability_ledger())
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
            return self._send(200, STORE.list_profiles(min(max(limit, 1), 200)))
        if parsed.path.startswith("/v1/profiles/"):
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            doc = STORE.get_profile(parsed.path.rsplit("/", 1)[1])
            return self._send(200, doc) if doc is not None else \
                self._send(404, {"error": "Unknown profile."})
        if parsed.path == "/v1/reports":
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["20"])[0])
            except ValueError:
                return self._send(422, {"error": "limit must be an integer"})
            return self._send(200, STORE.list_reports(min(max(limit, 1), 200)))
        if parsed.path.startswith("/v1/reports/"):
            if STORE is None:
                return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
            doc = STORE.get_report(parsed.path.rsplit("/", 1)[1])
            return self._send(200, doc) if doc is not None else \
                self._send(404, {"error": "Unknown report id."})
        self._send(404, {"error": "not found"})

    def _route_post(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/v1/analyze":
                loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                               address=req.get("address", ""),
                               radius_minutes=int(req.get("radius_minutes", 10)))
                report = analyze(loc, req["vertical"], resolver=RESOLVER).to_dict()
                if STORE is not None:
                    report["report_id"] = STORE.save_report(report, created_at=time.time())
                return self._send(200, report)
            if self.path == "/v1/profiles":
                if STORE is None:
                    return self._send(503, {"error": "Persistence disabled (LANDVEX_DB=off)."})
                p = profile_from_dict(req)
                return self._send(200, {"profile_id": STORE.save_profile(
                    p.to_dict(), created_at=time.time())})
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
                    committed_at=str(req.get("committed_at", ""))))
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
                decisions = accountability_all_decisions()
                who = str(req.get("subscriber", ""))
                if who:
                    return self._send(200, inbox_engine.brief(
                        who, evs, decisions=decisions, now=req.get("now", "")))
                return self._send(200, inbox_engine.route(
                    evs, decisions=decisions, now=req.get("now", "")))
            if self.path == "/v1/monitors":
                return self._send(200, monitors_engine.define(
                    str(req["metric"]), str(req["scope"]), str(req["rule"]),
                    str(req.get("owner", "")), params=req.get("params") or {},
                    cadence=req.get("cadence") or None,
                    label=str(req.get("label", ""))))
            if self.path == "/v1/monitors/evaluate":
                mon = req.get("monitor") or monitors_engine.get_monitor(
                    str(req.get("monitor_id", "")))
                if mon is None:
                    return self._send(404, {"error": "unknown monitor"})
                return self._send(200, monitors_engine.evaluate(
                    mon, req.get("series") or [],
                    evaluated_at=req.get("evaluated_at", "")))
            if self.path == "/v1/monitors/run":
                return self._send(200, monitors_engine.run_due(
                    monitors_engine.all_monitors(), req["now"],
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
                    raw = STORE.get_profile(req["profile_id"])
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
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
            self._send(422, {"error": str(e)})

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
    # Flertrådad + större accept-kö: tål burst-last utan att droppa
    # anslutningar (red-team: 200 samtidiga anrop). Produktionsvägen är
    # uvicorn/FastAPI, men denna server deployas också (systemd).
    class _Server(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 256
    _Server((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
