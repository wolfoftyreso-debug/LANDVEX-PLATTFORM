"""Beroendefri utvecklingsserver (endast stdlib).

    python3 -m api.dev_server   # startar på http://localhost:8000

Samma endpoints som produktions-API:t:
    GET  /health
    GET  /v1/verticals
    POST /v1/analyze   {"lat":..,"lon":..,"vertical":"frisor","radius_minutes":10}

Endast för lokal utveckling/demo – i AWS körs api/main.py (FastAPI).
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from engine.models import Location
from engine.scoring import analyze
from engine.verticals import VERTICALS


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if self.path == "/v1/verticals":
            return self._send(200, [{"id": v.id, "label_sv": v.label_sv}
                                    for v in VERTICALS.values()])
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
            report = analyze(loc, req["vertical"])
            self._send(200, report.to_dict())
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self._send(422, {"error": str(e)})

    def log_message(self, fmt, *args):  # tystare logg
        pass


def main(port: int = 8000) -> None:
    print(f"Opportunity Engine dev-server: http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
