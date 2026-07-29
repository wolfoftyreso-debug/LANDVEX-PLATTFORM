"""Läser API-ytan ur källkoden — EN implementation, flera konsumenter.

Parsarna föddes i tests/test_contract.py. När licenssvepet behövde samma
läsning var alternativet att kopiera dem dit, och två kopior av en
parser är två sanningar om vad ytan är: den dag den ena lär sig ett nytt
routningsmönster och den andra inte, godkänner de olika kontrakt.
Därför bor läsningen här och konsumeras av kontraktstestet,
licenssvepet och självrevisionsytan.

Läsningen är STATISK — reguljära uttryck över källtexten, aldrig import
av apparna. Det är ett medvetet val: kontraktet ska kunna prövas utan
fastapi installerat, och en parser som importerar det den granskar kan
fällas av just det fel den letar efter.

Vad den inte kan: den bevisar att en väg FINNS, inte att handlern bakom
den är korrekt, och den ser bara mönster den lärt sig. Ett nytt
routningssätt i dev-servern måste läras in här — och testet
`test_no_unparseable_verbs` ser till att nya verb inte kan smyga förbi.
"""
from __future__ import annotations

import pathlib
import re

_API = pathlib.Path(__file__).resolve().parent


def norm(path: str) -> str:
    """Normaliserar path-parametrar: {id}/<id> → *."""
    path = re.sub(r"\{[^}]+\}", "*", path)
    path = re.sub(r"<[^>]+>", "*", path)
    return path.split("?")[0].rstrip("/") or "/"


def _src(namn: str) -> str:
    return (_API / namn).read_text(encoding="utf-8")


def fastapi_pairs() -> set[tuple[str, str]]:
    """(METOD, väg) ur dekoratorerna i main.py."""
    return {(m.upper(), norm(p)) for m, p in
            re.findall(r'@app\.(get|post|put|delete)\("([^"]+)"',
                       _src("main.py"))}


def devserver_pairs() -> set[tuple[str, str]]:
    """(METOD, väg) ur dev-servern.

    Metoden avgörs av vilken router vägen står i: `_route_get` respektive
    `_route_post`. Att bara jämföra vägar dolde riktig drift — en endpoint
    som finns som POST i den ena servern och GET i den andra har samma väg
    och gick därför igenom kontraktstestet.
    """
    src = _src("dev_server.py")
    cut = src.index("def _route_post")
    pairs = set()
    for method, part in (("GET", src[:cut]), ("POST", src[cut:])):
        for p in re.findall(r'(?:parsed\.path|self\.path)\s*==\s*"([^"]+)"',
                            part):
            pairs.add((method, norm(p)))
        for s in re.findall(
                r'(?:parsed\.path|self\.path)\.startswith\("([^"]+)"', part):
            pairs.add((method, norm(s.rstrip("/") + "/*")))
        # `parsed.path in ("/", "/console", ...)` — en route som serveras av
        # ett medlemskapstest är lika mycket en route som en likhetsjämförelse.
        # Utan det här läste kontraktet dem som obefintliga.
        for grupp in re.findall(
                r'(?:parsed\.path|self\.path)\s+in\s+\(([^)]*)\)', part):
            for p in re.findall(r'"([^"]+)"', grupp):
                pairs.add((method, norm(p)))
    return pairs


def open_paths(layer: str) -> set[str]:
    """`_OPEN_PATHS`-tupeln ur ett lagers källa, statiskt läst.

    Öppna vägar är den enda punkt där de två lagren FÅR skilja sig utan
    att kontraktstestet ser det via routningen — därför måste själva
    tupeln kunna jämföras. `layer` ∈ {"main.py", "dev_server.py"}.
    """
    src = _src(layer)
    m = re.search(r'_OPEN_PATHS\s*=\s*\(([^)]*)\)', src)
    if not m:
        raise ValueError(f"{layer}: hittar ingen _OPEN_PATHS-tupel")
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def selfaudit_context() -> dict:
    """Kontexten självrevisionens grindkontroll behöver — byggd HÄR,
    för motorn importerar aldrig api/. En körning utan den här
    kontexten redovisar grindkontrollen som refused."""
    from api.licensing import required_capability

    return {"pairs": fastapi_pairs() | devserver_pairs(),
            "open_paths": open_paths("main.py") | open_paths("dev_server.py"),
            "required_capability": required_capability}


def unparseable_verbs() -> list[str]:
    """Verb i main.py som dev-parsern inte kan känna igen.

    `devserver_pairs` förstår exakt GET och POST. Införs en @app.put
    utan att parsern byggs ut skulle kontraktet rapportera vägen som
    saknad i dev — och den kunde aldrig bli grön. Det här ger felet ett
    namn i förväg i stället för en gåta i efterhand.
    """
    return re.findall(r'@app\.(put|delete|patch)\(', _src("main.py"))
