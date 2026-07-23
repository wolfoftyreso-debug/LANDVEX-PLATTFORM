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
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
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
from engine.compare import compare
from engine.gaps import gap_analysis
from engine.markets import market_catalog
from engine.indices import city_assessment, index_catalog, index_map
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

from api.health import build_health, source_status
from api.security import AuthError, Gate

GATE = Gate()

_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

# Persistens: LANDVEX_DB = sökväg (default landvex.db) eller "off".
_DB = os.environ.get("LANDVEX_DB", "landvex.db")
STORE = SqliteStore(_DB) if _DB.lower() not in ("off", "0", "") else None

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

    _OPEN_PATHS = ("/", "/index.html", "/health")

    def _gated(self, method: str, route) -> None:
        """Auth → rate limit → routning → metrics + audit."""
        path = self.path
        if urlparse(path).path in self._OPEN_PATHS:
            return route()
        t0 = time.monotonic()
        principal, self._request_id, self._status = None, None, 500
        try:
            principal, self._request_id = GATE.enter(
                self.headers.get("X-API-Key"), method, path)
            self._principal = principal
            route()
        except AuthError as e:
            self._send(e.status, {"error": e.message_sv})
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
        if parsed.path == "/health":
            return self._send(200, build_health(RESOLVER, STORE))
        if parsed.path == "/v1/verticals":
            return self._send(200, [{"id": v.id, "label_sv": v.label_sv}
                                    for v in VERTICALS.values()])
        if parsed.path == "/v1/profile-options":
            return self._send(200, {**profile_options(),
                                    "scan_levels": SCAN_LEVEL_OPTIONS})
        if parsed.path == "/v1/catalog":
            from api.catalog import API_CATALOG
            return self._send(200, API_CATALOG)
        if parsed.path == "/v1/markets":
            return self._send(200, market_catalog())
        if parsed.path == "/v1/segments":
            return self._send(200, segment_catalog())
        if parsed.path == "/v1/products":
            return self._send(200, product_catalog())
        if parsed.path == "/v1/indices":
            return self._send(200, index_catalog())
        if parsed.path == "/v1/indices/map":
            q = parse_qs(parsed.query)
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
                return self._send(503, {"error": "Persistens avstängd (LANDVEX_DB=off)."})
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
            except ValueError:
                return self._send(422, {"error": "limit måste vara ett heltal"})
            return self._send(200, STORE.list_profiles(min(max(limit, 1), 200)))
        if parsed.path.startswith("/v1/profiles/"):
            if STORE is None:
                return self._send(503, {"error": "Persistens avstängd (LANDVEX_DB=off)."})
            doc = STORE.get_profile(parsed.path.rsplit("/", 1)[1])
            return self._send(200, doc) if doc is not None else \
                self._send(404, {"error": "Okänd profil."})
        if parsed.path == "/v1/reports":
            if STORE is None:
                return self._send(503, {"error": "Persistens avstängd (LANDVEX_DB=off)."})
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["20"])[0])
            except ValueError:
                return self._send(422, {"error": "limit måste vara ett heltal"})
            return self._send(200, STORE.list_reports(min(max(limit, 1), 200)))
        if parsed.path.startswith("/v1/reports/"):
            if STORE is None:
                return self._send(503, {"error": "Persistens avstängd (LANDVEX_DB=off)."})
            doc = STORE.get_report(parsed.path.rsplit("/", 1)[1])
            return self._send(200, doc) if doc is not None else \
                self._send(404, {"error": "Okänt rapport-id."})
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
                    return self._send(503, {"error": "Persistens avstängd (LANDVEX_DB=off)."})
                p = profile_from_dict(req)
                return self._send(200, {"profile_id": STORE.save_profile(
                    p.to_dict(), created_at=time.time())})
            if self.path == "/v1/ask":
                return self._send(200, ask(str(req.get("question", "")),
                                           resolver=RESOLVER))
            if self.path == "/v1/indices/assess":
                return self._send(200, city_assessment(
                    req["kommun_kod"], market=req.get("market", "se"),
                    resolver=RESOLVER))
            if self.path == "/v1/service/analyze":
                return self._send(200, service_analysis(
                    req["kommun_kod"], market=req.get("market", "se"),
                    target_year=int(req.get("target_year", 2031)),
                    resolver=RESOLVER))
            if self.path == "/v1/segments/analyze":
                return self._send(200, segment_analysis(
                    req["kommun_kod"], market=req.get("market", "se"),
                    resolver=RESOLVER))
            if self.path == "/v1/gaps":
                return self._send(200, gap_analysis(
                    req["vertical"], market=req.get("market", "se"),
                    resolver=RESOLVER,
                    top_n=min(max(int(req.get("top_n", 5)), 1), 20)))
            if self.path == "/v1/plan":
                return self._send(200, establishment_plan(
                    req["kommun_kod"], req["vertical"],
                    market=req.get("market", "se"),
                    team_size=req.get("team_size", "2-5"),
                    budget_band=req.get("budget_band", "500k-2m"),
                    resolver=RESOLVER))
            if self.path == "/v1/risk":
                loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                               address=req.get("address", ""),
                               radius_minutes=int(req.get("radius_minutes", 10)))
                return self._send(200, assess(loc, req["vertical"],
                                              resolver=RESOLVER))
            if self.path == "/v1/compare":
                return self._send(200, compare(req["locations"],
                                               req["vertical"],
                                               resolver=RESOLVER))
            if self.path == "/v1/workforce/forecast":
                return self._send(200, wf_forecast(
                    req["kommun_kod"], int(req.get("target_year", 2035)),
                    req.get("occupation_ids"), resolver=RESOLVER,
                    market=req.get("market", "se")))
            if self.path == "/v1/workforce/simulate":
                return self._send(200, wf_simulate(
                    req["kommun_kod"], req["occupation_id"],
                    float(req.get("extra_places_per_year", 0)),
                    int(req.get("target_year", 2035)), resolver=RESOLVER,
                    market=req.get("market", "se")))
            if self.path == "/v1/scan":
                raw = req.get("profile")
                if raw is None and req.get("profile_id"):
                    if STORE is None:
                        return self._send(503, {"error": "Persistens avstängd (LANDVEX_DB=off)."})
                    raw = STORE.get_profile(req["profile_id"])
                    if raw is None:
                        return self._send(404, {"error": "Okänd profil."})
                if raw is None:
                    return self._send(422, {"error": "Ange profile eller profile_id."})
                p = profile_from_dict(raw)
                top_n = min(max(int(req.get("top_n", 5)), 1), 20)
                return self._send(200, scan(p, resolver=RESOLVER, top_n=top_n,
                                            level=req.get("level", "oversikt"),
                                            market=req.get("market", "se")))
            self._send(404, {"error": "not found"})
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
            self._send(422, {"error": str(e)})

    def log_message(self, fmt, *args):  # tystare logg
        pass


def main(port: int = 8000) -> None:
    print(f"Opportunity Engine dev-server: http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
