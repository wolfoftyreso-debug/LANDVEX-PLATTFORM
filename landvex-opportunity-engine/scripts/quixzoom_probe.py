"""Direct quiXzoom (:3209) probe — run in a NETWORKED environment.

Answers the open question "is direct access to quiXzoom on :3209 possible?"
without touching AAMOS Core auth. It hits quiXzoom's own API directly,
probes candidate mission paths, and reports status (200 / 401 / shape) — so
you can tell whether field_observation_density can go live via :3209 while
the Core service token is still being issued.

    LANDVEX_QUIXZOOM_URL=http://127.0.0.1:3209 python3 -m scripts.quixzoom_probe
    # if :3209 needs its own credential:
    LANDVEX_QUIXZOOM_KEY=<key>  LANDVEX_QUIXZOOM_AUTH_HEADER=X-Api-Key ...

A 401 here means :3209 needs its own credential (from quiXzoom, never
forged). Exit 0 if a route returned 200, 1 otherwise. Read-only.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

from engine.datasources.quixzoom_direct import DirectQuixzoomClient

BASE = os.environ.get("LANDVEX_QUIXZOOM_URL", "http://127.0.0.1:3209")
LAT = float(os.environ.get("LAT", "59.33"))
LON = float(os.environ.get("LON", "18.06"))
CANDIDATES = [
    os.environ.get("LANDVEX_QUIXZOOM_PATH", "/api/missions"),
    "/missions", "/api/qz/missions", "/api/quixzoom/missions", "/v1/missions",
]


def main() -> int:
    client = DirectQuixzoomClient(base_url=BASE)
    auth = "set" if client.key else "NONE"
    print(f"Direct quiXzoom probe → {BASE}\n  auth: {auth} "
          f"(header {client.auth_header})\n")
    reached = False
    for path in dict.fromkeys(CANDIDATES):
        url = (f"{BASE.rstrip('/')}{path}?lat={LAT}&lon={LON}&radius_km=10")
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", **client.auth_headers()})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                body = r.read().decode("utf-8", "replace")[:120]
                reached = True
                print(f"  ✓ {path:26} 200 · {body!r}")
        except urllib.error.HTTPError as e:
            reached = True
            hint = " (needs its own credential from quiXzoom)" if e.code == 401 else ""
            print(f"  ~ {path:26} HTTP {e.code}{hint}")
        except Exception as e:  # noqa: BLE001 - diagnostics
            print(f"  ✗ {path:26} {type(e).__name__}: {str(e)[:50]}")
    print()
    if reached:
        print("RESULT: :3209 is reachable. A ✓ 200 means quiXzoom can go live "
              "directly — set LANDVEX_QUIXZOOM_URL (+ its path/key) and the "
              "engine uses it automatically, no Core token needed. A 401 means "
              "it needs its own credential from quiXzoom.")
        return 0
    print(f"RESULT: :3209 not reachable at {BASE}. Check the port and egress.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
