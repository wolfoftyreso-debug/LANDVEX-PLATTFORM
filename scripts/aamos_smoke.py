"""AAMOS Core live-handshake smoke test — run in a NETWORKED environment.

Pre-flight diagnostic before wiring Landvex to the real AAMOS Capability
Platform. It exercises the integration end-to-end against a running AAMOS
Core and prints a clear per-endpoint report: what connected, what returned
JSON vs XML/RSS, the quiXzoom mission shape, and which candidate route
actually answers (the exact quiXzoom path is still marked unconfirmed in
integrations/aamos.py).

    AAMOS_CORE_URL=http://127.0.0.1:3100 python3 -m scripts.aamos_smoke
    # AAMOS Core gates every endpoint — set ONE of these if you get 401s:
    AAMOS_TOKEN=<jwt>      # sent as Authorization: Bearer <jwt>
    AAMOS_API_KEY=<key>    # sent as X-API-Key: <key>
    # optional overrides:
    AAMOS_QUIXZOOM_PATH=/api/qz/missions  LAT=59.33 LON=18.06 RADIUS_KM=10 ...

Nothing here mutates state except an optional best-effort service
registration (POST /api/services/register) — pass --no-register to skip.
Exit code is 0 if AAMOS Core answered at all, 1 if it was unreachable.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from integrations.aamos import AamosClient, AamosUnavailable, _decode_body

CORE = os.environ.get("AAMOS_CORE_URL", "http://127.0.0.1:3100")
LAT = float(os.environ.get("LAT", "59.33"))
LON = float(os.environ.get("LON", "18.06"))
RADIUS_KM = float(os.environ.get("RADIUS_KM", "10"))
TIMEOUT = float(os.environ.get("AAMOS_TIMEOUT", "5"))

# Candidate quiXzoom routes to probe (the exact one is unconfirmed).
QZ_CANDIDATES = [
    os.environ.get("AAMOS_QUIXZOOM_PATH", "/api/aamos/quixzoom/missions"),
    "/api/qz/missions",
    "/api/quixzoom/missions",
    "/api/missions",
]

_OK, _WARN, _FAIL = "PASS", "PARTIAL", "FAIL"

# Same auth as the client (env AAMOS_TOKEN / AAMOS_API_KEY), so route
# discovery is authenticated too — AAMOS Core gates every endpoint.
_AUTH = AamosClient(base_url=CORE).auth_headers()


def _raw_get(path: str) -> tuple[int, str, dict | None]:
    """Low-level GET returning (http_status, content_type, parsed|None)."""
    url = CORE.rstrip("/") + path
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", **_AUTH}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace")
            ct = r.headers.get("Content-Type", "")
            try:
                parsed = _decode_body(body)
            except Exception:
                parsed = None
            return r.status, ct, parsed
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), None
    except Exception as e:  # noqa: BLE001 - diagnostics
        return 0, f"error: {e}", None


def _shape(obj) -> str:
    if isinstance(obj, dict):
        return "{" + ", ".join(list(obj)[:6]) + ("…}" if len(obj) > 6 else "}")
    if isinstance(obj, list):
        return f"[{len(obj)} items]" + (f" e.g. {_shape(obj[0])}" if obj else "")
    return type(obj).__name__


def _line(status: str, name: str, detail: str) -> None:
    mark = {"PASS": "  ✓", "PARTIAL": "  ~", "FAIL": "  ✗"}[status]
    print(f"{mark} {name:34} {detail}")


def main() -> int:
    register = "--no-register" not in sys.argv
    auth = ("Bearer token" if os.environ.get("AAMOS_TOKEN") else
            "X-API-Key" if os.environ.get("AAMOS_API_KEY") else
            "NONE — set AAMOS_TOKEN or AAMOS_API_KEY (Core returns 401 "
            "without it)")
    print(f"AAMOS Core smoke test → {CORE}")
    print(f"  auth: {auth}\n")
    client = AamosClient(base_url=CORE, timeout=TIMEOUT)
    reached = False

    # 1. Health / status
    for name, fn in (("health_summary", client.health_summary),
                     ("control_plane_services", client.control_plane_services)):
        try:
            r = fn(); reached = True
            _line(_OK, name, _shape(r))
        except AamosUnavailable as e:
            _line(_FAIL, name, str(e)[:80])

    # 2. quiXzoom route discovery — probe each candidate
    print("\n  quiXzoom mission route discovery:")
    winner = None
    for path in dict.fromkeys(QZ_CANDIDATES):        # dedupe, keep order
        full = f"{path}?lat={LAT}&lon={LON}&radius_km={RADIUS_KM}"
        code, ct, parsed = _raw_get(full)
        if code == 200:
            reached = True
            kind = "json" if "json" in ct.lower() else \
                   "xml/rss" if parsed else "unparsed"
            _line(_OK, f"  {path}", f"200 · {kind} · {_shape(parsed)}")
            if winner is None:
                winner = (path, parsed)
        elif code:
            _line(_WARN if code < 500 else _FAIL, f"  {path}", f"HTTP {code}")
        else:
            _line(_FAIL, f"  {path}", ct[:60])
    if winner:
        path, parsed = winner
        print(f"\n  → quiXzoom answers on: {path}")
        missions = parsed if isinstance(parsed, list) else \
            (parsed.get("missions") or parsed.get("contents") or []) \
            if isinstance(parsed, dict) else []
        if missions:
            m = missions[0]
            loc = m.get("location", {}) if isinstance(m, dict) else {}
            has_lnglat = bool(loc) and ("lng" in loc or "lon" in loc)
            _line(_OK if has_lnglat else _WARN, "  mission[0] shape",
                  _shape(m) + (f" location={_shape(loc)}" if loc else
                               " (no location field)"))
        else:
            _line(_WARN, "  missions", "route answered but returned 0 missions")
    else:
        _line(_WARN, "quiXzoom", "no candidate route returned 200 — confirm "
              "the path with AAMOS-dev and set AAMOS_QUIXZOOM_PATH")

    # 3. Client-level quiXzoom (uses the configured path + parsing)
    try:
        r = client.quixzoom_missions(LAT, LON, radius_km=RADIUS_KM)
        reached = True
        _line(_OK, "client.quixzoom_missions", _shape(r))
    except AamosUnavailable as e:
        _line(_WARN, "client.quixzoom_missions", str(e)[:70])

    # 4. Cognition / agents / alerts
    for name, call in (("identity_agents", lambda: client.identity_agents()),
                       ("cognition_brief", lambda: client.cognition_brief("landvex")),
                       ("alerts", lambda: client.alerts())):
        try:
            r = call(); reached = True
            _line(_OK, name, _shape(r))
        except AamosUnavailable as e:
            _line(_WARN, name, str(e)[:70])

    # 5. Best-effort service registration (mutating — opt-out with --no-register)
    if register:
        try:
            r = client.register_service("landvex-opportunity-engine", 8087,
                                        ["/v1/opportunities", "/v1/scan"])
            reached = True
            _line(_OK, "register_service", _shape(r))
        except AamosUnavailable as e:
            _line(_WARN, "register_service", str(e)[:70])
    else:
        _line(_WARN, "register_service", "skipped (--no-register)")

    print()
    if reached:
        print("RESULT: AAMOS Core is reachable. Review PARTIAL lines above — "
              "they show routes/shapes to confirm with AAMOS-dev before "
              "flipping LANDVEX to live.")
        return 0
    print("RESULT: AAMOS Core was NOT reachable at "
          f"{CORE}. Check the URL, that Core is running, and network egress.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
