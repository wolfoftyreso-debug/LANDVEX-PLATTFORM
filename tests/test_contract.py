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


def _fastapi_pairs() -> set[tuple[str, str]]:
    """(METOD, väg) ur dekoratorerna i main.py."""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    return {(m.upper(), _norm(p)) for m, p in
            re.findall(r'@app\.(get|post|put|delete)\("([^"]+)"', src)}


def _devserver_pairs() -> set[tuple[str, str]]:
    """(METOD, väg) ur dev-servern.

    Metoden avgörs av vilken router vägen står i: `_route_get` respektive
    `_route_post`. Att bara jämföra vägar dolde riktig drift — en endpoint
    som finns som POST i den ena servern och GET i den andra har samma väg
    och gick därför igenom kontraktstestet.
    """
    src = (_ROOT / "dev_server.py").read_text(encoding="utf-8")
    cut = src.index("def _route_post")
    pairs = set()
    for method, part in (("GET", src[:cut]), ("POST", src[cut:])):
        for p in re.findall(r'(?:parsed\.path|self\.path)\s*==\s*"([^"]+)"',
                            part):
            pairs.add((method, _norm(p)))
        for s in re.findall(
                r'(?:parsed\.path|self\.path)\.startswith\("([^"]+)"', part):
            pairs.add((method, _norm(s.rstrip("/") + "/*")))
        # `parsed.path in ("/", "/console", ...)` — en route som serveras av
        # ett medlemskapstest är lika mycket en route som en likhetsjämförelse.
        # Utan det här läste kontraktet dem som obefintliga.
        for grupp in re.findall(
                r'(?:parsed\.path|self\.path)\s+in\s+\(([^)]*)\)', part):
            for p in re.findall(r'"([^"]+)"', grupp):
                pairs.add((method, _norm(p)))
    return pairs


def _fastapi_routes() -> set[str]:
    return {p for _, p in _fastapi_pairs()}


def _devserver_routes() -> set[str]:
    return {p for _, p in _devserver_pairs()}


# Sedan dörren infördes serverar BÅDA servrarna "/", "/console" och
# "/index.html" — de HTML-vägarna är alltså inte längre undantag utan
# kontrakt, och undantagsmängderna är tomma. De står kvar som tomma i
# stället för att tas bort: nästa sida som bara finns i ett lager ska
# behöva skrivas in här medvetet, inte glida in.
_DEV_ONLY: set[str] = set()
_FASTAPI_ONLY: set[str] = set()
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


def test_the_same_path_answers_the_same_methods_in_both_servers():
    """Samma väg måste svara på samma verb i båda lagren.

    Ett kontrakt som bara jämför vägar godkänner att /v1/x är POST i den
    ena servern och GET i den andra. Klienten som byter miljö får då 404
    eller 405 på en endpoint katalogen påstår finns.
    """
    fapi = _fastapi_pairs() - {("GET", p) for p in _FASTAPI_ONLY}
    dev = _devserver_pairs() - {("GET", p) for p in _DEV_ONLY | _FRAMEWORK}
    only_fapi = fapi - dev
    only_dev = dev - fapi
    assert not only_fapi, \
        f"Metod/väg i FastAPI men inte dev_server: {sorted(only_fapi)}"
    assert not only_dev, \
        f"Metod/väg i dev_server men inte FastAPI: {sorted(only_dev)}"


def test_catalog_declares_the_method_each_endpoint_actually_answers():
    """Katalogen är det agenter och kunder läser. Står fel verb där är
    den en instruktion som inte fungerar."""
    both = _fastapi_pairs() & _devserver_pairs()
    for eng in API_CATALOG["engines"]:
        for ep in eng["endpoints"]:
            pair = (ep["method"].upper(), _norm(ep["path"]))
            if pair[1] in _FRAMEWORK or pair[1] == "/health":
                continue
            assert pair in both, \
                f"Katalogen säger {pair[0]} {pair[1]} – det svarar inte " \
                f"båda servrarna på"


def test_both_layers_back_the_same_engines_with_the_store():
    """Samma yta räcker inte om bara den ena servern persisterar.

    dev-servern hade `inspections.set_store(STORE)`; FastAPI-lagret hade
    det inte. Ytan var identisk och kontraktstestet grönt — men i
    produktion låg efterlevnadsregistret i processminnet och var borta vid
    nästa omstart. Det är den sortens drift som bara syns om något läser
    båda filerna.
    """
    fapi = (_ROOT / "main.py").read_text(encoding="utf-8")
    dev = (_ROOT / "dev_server.py").read_text(encoding="utf-8")
    for modul in ("outcome", "accountability", "corrections", "monitors"):
        for namn, src in (("main.py", fapi), ("dev_server.py", dev)):
            assert f"set_{modul}_store(STORE)" in src, f"{namn}: {modul}"
    for namn, src in (("main.py", fapi), ("dev_server.py", dev)):
        assert re.search(r"\w+\.set_store\(STORE\)", src), \
            f"{namn} kopplar inte kontrollregistret till lagret"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
