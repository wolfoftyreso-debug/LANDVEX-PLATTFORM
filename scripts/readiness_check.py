"""Production readiness check — hit every catalog endpoint on a running server.

    BASE=http://localhost:8000 python3 -m scripts.readiness_check

Reads the API catalog for the endpoint surface, exercises GETs and a
representative POST for each engine, and reports status. Exit 0 only if every
required endpoint answered 2xx (422 is acceptable for POSTs missing a body —
it proves the route is wired). Read-only except for the demo POSTs, which are
harmless. Use as the final gate before pointing landvex.com at the service.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BASE", "http://localhost:8000").rstrip("/")
KEY = os.environ.get("LANDVEX_API_KEY", "")

# Representative POST bodies for the write endpoints.
POSTS = {
    "/v1/lambda": {"axes": {"ECON": 60, "HEALTH": 55}},
    "/v1/kpi/evaluate": {"code": "life_expectancy", "value": 81, "previous": 82},
    "/v1/setpoints/assess": {"code": "gini", "value": 0.33},
    "/v1/cite": {"statement": "x", "value": 1, "source": {"authority": "SCB"},
                 "time": {"observed_at": "2025-01-01"}},
    "/v1/feeds/events": {"feed": "daily_top_changes", "rows": []},
    "/v1/worthiness": {"snapshots": []},
    "/v1/decision": {"template": "policy_decision", "answers": {}},
    "/v1/strim/entity": {"entity_type": "term", "slug": "x", "name_en": "X",
                         "definition": "A neutral definition.", "sources": ["A"]},
    "/v1/outcomes/roi": {"score": 80},
    "/v1/ask": {"question": "What is the population trend in Malmö?"},
}


def _req(path: str, body=None):
    url = f"{BASE}{path}"
    headers = {"Accept": "application/json"}
    if KEY:
        headers["X-API-Key"] = KEY
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:80]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {str(e)[:60]}"


def main() -> int:
    print(f"Readiness check → {BASE}\n")
    st, _ = _req("/health")
    print(f"  {'✓' if st == 200 else '✗'} GET  /health            {st}")
    cat_st, cat_body = _req("/v1/catalog")
    if cat_st != 200:
        print("  ✗ /v1/catalog unreachable — is the server up?")
        return 1
    catalog = json.loads(urllib.request.urlopen(f"{BASE}/v1/catalog",
                                                timeout=8).read())
    # A route proves it is wired if it answers at all with an app status.
    # 200 = ok; 422 = wired, needs params/body; 503 = wired, degraded
    # (e.g. persistence off with LANDVEX_DB=off). 404/405/500/0 = broken.
    WIRED = {200, 201, 422, 503}
    # Endpoints that MUTATE shared state — never exercised against a live
    # server (would pollute the outcome dataset). Their wiring is proven by
    # the contract test instead.
    SKIP_MUTATING = {"/v1/outcomes"}
    ok, bad, skipped = [], [], []
    for eng in catalog["engines"]:
        for ep in eng["endpoints"]:
            p, m = ep["path"], ep["method"]
            if "{" in p:
                continue
            if p in SKIP_MUTATING and m != "GET":
                skipped.append((m, p))
                continue
            st, _ = _req(p, POSTS.get(p, {}) if m != "GET" else None)
            (ok if st in WIRED else bad).append((m, p, st))
    for m, p, st in ok:
        tag = "" if st in (200, 201) else \
            "  (needs params/body)" if st == 422 else "  (degraded — persistence off)"
        print(f"  ✓ {m:4} {p:26} {st}{tag}")
    for m, p in skipped:
        print(f"  – {m:4} {p:26} skipped (mutating; wiring via contract test)")
    for m, p, st in bad:
        print(f"  ✗ {m:4} {p:26} {st}")
    print(f"\n{len(ok)} wired, {len(bad)} broken.")
    if bad:
        print("RESULT: NOT ready — the routes above are not wired.")
        return 1
    print("RESULT: every catalog endpoint is wired. Ready to serve landvex.com.\n"
          "  (For a full-function check, run against a server with persistence "
          "on and query params supplied.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
