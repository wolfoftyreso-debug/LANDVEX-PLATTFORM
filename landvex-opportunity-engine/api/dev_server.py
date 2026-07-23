"""Beroendefri utvecklingsserver (endast stdlib).

    python3 -m api.dev_server   # startar på http://localhost:8000

Samma endpoints som produktions-API:t:
    GET  /health
    GET  /v1/verticals
    GET  /v1/reports?limit=20
    GET  /v1/reports/<id>
    POST /v1/analyze   {"lat":..,"lon":..,"vertical":"frisor","radius_minutes":10}

Endast för lokal utveckling/demo – i AWS körs api/main.py (FastAPI).
"""
from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from engine.datasources.adapters import production_sources
from engine.datasources.base import Resolver
from engine.datasources.cache import CachedSource
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.scoring import analyze
from engine.storage.sqlite import SqliteStore
from engine.verticals import VERTICALS

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
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._send(200, {"status": "ok"})
        if parsed.path == "/v1/verticals":
            return self._send(200, [{"id": v.id, "label_sv": v.label_sv}
                                    for v in VERTICALS.values()])
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

    def do_POST(self):
        if self.path != "/v1/analyze":
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            loc = Location(lat=float(req["lat"]), lon=float(req["lon"]),
                           address=req.get("address", ""),
                           radius_minutes=int(req.get("radius_minutes", 10)))
            report = analyze(loc, req["vertical"], resolver=RESOLVER).to_dict()
            if STORE is not None:
                report["report_id"] = STORE.save_report(report, created_at=time.time())
            self._send(200, report)
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self._send(422, {"error": str(e)})

    def log_message(self, fmt, *args):  # tystare logg
        pass


def main(port: int = 8000) -> None:
    print(f"Opportunity Engine dev-server: http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
