"""Kontraktstest: de två API-lagren (FastAPI + stdlib) måste exponera
SAMMA endpoint-yta, och varje katalog-/manifest-endpoint måste finnas i
båda. Fångar drift (en route läggs till i en server men glöms i den
andra). Läser källkoden statiskt – körs utan fastapi/pytest:
python3 -m tests.test_contract"""
from __future__ import annotations

import pathlib
import re

from api.catalog import API_CATALOG
# Parsarna föddes här men bor numera i api/surface_scan.py: licenssvepet
# och självrevisionsytan läser SAMMA implementation. Två kopior av en
# parser är två sanningar om vad ytan är.
from api.surface_scan import (devserver_pairs as _devserver_pairs,
                              fastapi_pairs as _fastapi_pairs,
                              norm as _norm, open_paths as _open_paths,
                              unparseable_verbs as _unparseable_verbs)

_ROOT = pathlib.Path(__file__).resolve().parent.parent / "api"


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
# dev-servern – båda serverar dem, alltså ingen drift. Kommentaren var
# en gång en LÖGN: dev-servern serverade inte /docs alls, och eftersom
# mängden EXKLUDERAR vägarna ur jämförelsen kunde ingen se det. Numera
# verifierar test_framework_paths_are_actually_served att varje väg här
# faktiskt routas i dev-servern — en undantagsrad måste förtjäna sig.
_FRAMEWORK = {"/openapi.json", "/docs"}


def test_framework_paths_are_actually_served_not_just_excluded():
    """En väg i _FRAMEWORK tas bort ur jämförelsen. Serverar dev-servern
    den inte, är undantaget ett hål med en kommentar på. Mätt före
    fixen: /docs fanns i mängden, och `grep '"/docs"' dev_server.py` gav
    noll träffar — klienten som bytte lager fick 404 på en väg
    kontraktet kallade ramverksstandard."""
    dev = _devserver_routes()
    for p in sorted(_FRAMEWORK):
        assert p in dev, (
            f"{p} står i _FRAMEWORK men routas inte av dev-servern — "
            f"undantaget döljer ett hål i stället för en ramverksdetalj")


def test_open_paths_are_identical_in_both_layers():
    """De öppna vägarna är den enda punkt där lagren får skilja sig utan
    att routningsjämförelsen ser det — alltså måste tuplarna själva
    jämföras. Mätt före fixen: main hade /docs öppen, dev hade den inte
    (och serverade den inte heller); samma nyckel gav olika svar på
    samma väg beroende på miljö."""
    assert _open_paths("main.py") == _open_paths("dev_server.py")


def test_no_verbs_the_devserver_parser_cannot_see():
    """_devserver_pairs känner igen exakt GET och POST. En @app.put i
    main.py skulle rapporteras som "saknas i dev" utan att dev NÅGONSIN
    kan bli grön — parsern måste byggas ut FÖRST. Det här testet ger
    felet ett namn i förväg i stället för en gåta i efterhand."""
    verb = _unparseable_verbs()
    assert not verb, (
        f"main.py använder {sorted(set(verb))} — utöka "
        f"surface_scan.devserver_pairs innan verbet införs")


def test_verticals_answers_with_the_same_shape_in_both_layers():
    """Kontraktet låser vägar, inte nyttolaster — så /v1/verticals
    svarade med faktornedbrytning i FastAPI och bara id/label i dev.
    Ett fullständigt nyttolastkontrakt vore ett annat verktyg; det här
    låser den ENA uppmätta driften: båda lagren ska bygga
    factors-nedbrytningen."""
    fapi = (_ROOT / "main.py").read_text(encoding="utf-8")
    dev = (_ROOT / "dev_server.py").read_text(encoding="utf-8")
    # Sök på ROUTNINGSuttrycket, inte på vägsträngen: den nämns även i
    # moduldocstringen, och ett test som läser fel förekomst godkänner
    # vad som helst.
    for namn, src, mark in (
            ("main.py", fapi, '@app.get("/v1/verticals")'),
            ("dev_server.py", dev, 'parsed.path == "/v1/verticals"')):
        i = src.index(mark)
        utsnitt = src[i:i + 700]
        assert '"factors"' in utsnitt, (
            f"{namn}: /v1/verticals bygger ingen factors-nedbrytning")


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


def test_both_layers_hand_every_market_engine_the_real_resolver():
    """Motorernas default är numera produktionskedjan, men API-lagren
    ska ändå skicka SIN resolver uttryckligen: den bär cache-lagret
    (CachedSource), och en handler som glömmer argumentet ger rätt
    källor utan cache — långsammare för varje kund, synligt för ingen.
    Källskanning: varje anrop av marknadsmotorerna i båda lagren bär
    resolver=RESOLVER."""
    def _anrop(src: str, fn: str) -> list[str]:
        """Varje fullständigt `fn(...)`-anrop, avgränsat med
        parentesräkning — ett teckenfönster hade kunnat 'låna' nästa
        anrops resolver-argument och godkänna ett anrop utan eget."""
        ut = []
        i = 0
        while True:
            i = src.find(f"{fn}(", i)
            if i < 0:
                return ut
            radstart = src.rfind("\n", 0, i) + 1
            if "import" in src[radstart:src.find("\n", i)]:
                i += 1
                continue
            djup, j = 0, i + len(fn)
            while j < len(src):
                if src[j] == "(":
                    djup += 1
                elif src[j] == ")":
                    djup -= 1
                    if djup == 0:
                        break
                j += 1
            ut.append(src[i:j + 1])
            i = j

    fapi = (_ROOT / "main.py").read_text(encoding="utf-8")
    dev = (_ROOT / "dev_server.py").read_text(encoding="utf-8")
    for fn in ("city_assessment", "index_map", "segment_analysis",
               "segment_map", "service_analysis", "service_demand_map"):
        for namn, src in (("main.py", fapi), ("dev_server.py", dev)):
            anrop = _anrop(src, fn)
            assert anrop, f"{namn}: {fn} anropas aldrig"
            for a in anrop:
                assert "resolver=RESOLVER" in a, f"{namn}: {a[:120]}"


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
    # Modulerna räknas var för sig. Ett test som bara krävde "någon
    # .set_store(STORE)" var grönt när dev-servern kopplade in
    # kontrollregistret men inte schemaläggaren — och då låg jobben i
    # processminnet: en veckorunda slutade tyst köras vid omstart, och
    # claimet som hindrar dubbelkörning fanns inte.
    for modul, vad in (("inspections", "kontrollregistret"),
                       ("scheduler", "schemalagda jobb"),
                       ("harvest", "skördad öppen data"),
                       ("news", "nyhetsposter")):
        for namn, src in (("main.py", fapi), ("dev_server.py", dev)):
            # Modulen importeras under olika alias i de två filerna; leta
            # upp aliaset i stället för att gissa det.
            alias = re.findall(rf"from engine import {modul} as (\w+)", src)
            alias += ([modul] if f"from engine import {modul}\n" in src
                      else [])
            assert alias, f"{namn} importerar inte engine.{modul}"
            assert any(f"{a}.set_store(STORE)" in src for a in alias), \
                f"{namn} kopplar inte {vad} till lagret"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
