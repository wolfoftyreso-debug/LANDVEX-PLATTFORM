"""Kontraktstest: de två API-lagren (FastAPI + stdlib) måste exponera
SAMMA endpoint-yta, och varje katalog-/manifest-endpoint måste finnas i
båda. Fångar drift (en route läggs till i en server men glöms i den
andra). Läser källkoden statiskt – körs utan fastapi/pytest:
python3 -m tests.test_contract"""
from __future__ import annotations

import pathlib
import re

from api.catalog import API_CATALOG

_ROOT = pathlib.Path(__file__).resolve().parent.parent / "api"


def _norm(path: str) -> str:
    """Normaliserar path-parametrar: {id}/<id> → *."""
    path = re.sub(r"\{[^}]+\}", "*", path)
    path = re.sub(r"<[^>]+>", "*", path)
    return path.split("?")[0].rstrip("/") or "/"


def _fastapi_routes() -> set[str]:
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    return {_norm(p) for _, p in
            re.findall(r'@app\.(get|post|put|delete)\("([^"]+)"', src)}


def _devserver_routes() -> set[str]:
    src = (_ROOT / "dev_server.py").read_text(encoding="utf-8")
    routes = set()
    for p in re.findall(r'(?:parsed\.path|self\.path)\s*==\s*"([^"]+)"', src):
        routes.add(_norm(p))
    # startswith-prefix (t.ex. /v1/reports/<id>) → normaliserad *-form
    for s in re.findall(r'(?:parsed\.path|self\.path)\.startswith\("([^"]+)"',
                        src):
        routes.add(_norm(s.rstrip("/") + "/*"))
    return routes


# Statiska/HTML-vägar som bara dev-servern serverar direkt (FastAPI
# monterar frontenden på annat sätt) – utanför kontraktet.
_DEV_ONLY = {"/", "/index.html"}
# FastAPI serverar "/" som frontend; dev-servern har "/" + "/index.html".
_FASTAPI_ONLY = {"/"}
# Ramverksgenererade i FastAPI (auto, syns ej i källan) men explicita i
# dev-servern – båda serverar dem, alltså ingen drift.
_FRAMEWORK = {"/openapi.json", "/docs"}


def test_both_servers_expose_the_same_surface():
    fapi = _fastapi_routes() - _FASTAPI_ONLY
    dev = _devserver_routes() - _DEV_ONLY - _FRAMEWORK
    saknas_i_dev = fapi - dev
    saknas_i_fastapi = dev - fapi
    assert not saknas_i_dev, \
        f"Routes i FastAPI men inte dev_server: {sorted(saknas_i_dev)}"
    assert not saknas_i_fastapi, \
        f"Routes i dev_server men inte FastAPI: {sorted(saknas_i_fastapi)}"


def test_every_catalog_endpoint_exists_in_both_servers():
    fapi = _fastapi_routes()
    dev = _devserver_routes()
    for eng in API_CATALOG["engines"]:
        for ep in eng["endpoints"]:
            p = _norm(ep["path"])
            assert p in fapi, f"Katalog-endpoint saknas i FastAPI: {p}"
            assert p in dev, f"Katalog-endpoint saknas i dev_server: {p}"


def test_agent_manifest_tools_are_routable():
    from api.agent_manifest import AGENT_MANIFEST
    fapi = _fastapi_routes()
    dev = _devserver_routes()
    for tool in AGENT_MANIFEST["tools"]:
        p = _norm(tool["path"])
        assert p in fapi and p in dev, \
            f"Manifest-verktyg {tool['name']} pekar på oroutbar väg: {p}"


def test_new_aamos_and_report_endpoints_are_present():
    both = _fastapi_routes() & _devserver_routes()
    for p in ("/v1/report", "/v1/platform/status", "/v1/watch",
              "/v1/agents", "/v1/agents/chat", "/v1/cognition/brief"):
        assert p in both, f"{p} finns inte i BÅDA servrarna"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
