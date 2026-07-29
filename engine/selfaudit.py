"""Självrevision — systemet mäter sina egna spärrar.

Palantir-revisionen 2026-07-29 gjordes som en engångsläsning av hela
kodytan. De mätningar den byggde på ska inte åldras i en rapport: de
ligger här som rena funktioner, konsumerade av BÅDE testsviten (som
hindrar regression) och API-ytan (som visar transparensen utåt). En
implementation, två läsare — samma regel som api/surface_scan.py.

Vad en statisk skanning kan: bevisa att en vakt FINNS. Vad den inte
kan: bevisa att koden bakom vakten är korrekt. Varje kontroll här bär
den skillnaden i sin `cannot_en`.

Rent stdlib. Modulen importerar ALDRIG api/ — kontext som kräver
API-lagret (routade par, öppna vägar) injiceras av anroparen.
"""
from __future__ import annotations

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parent.parent

# ── Breda except utan OUR_BUGS-vakt ─────────────────────────────────────
# Allowlisten är DATA och varje rad bär sitt skäl. En rad utan skäl är
# ett hål med en kommentar på; en rad vars plats försvunnit är en död
# regel som ser ut som skydd — båda faller i testet.
DEFENSIBLE_BROAD_EXCEPTS: tuple[dict, ...] = (
    {"site": "engine/scheduler.py",
     "why_en": "The job runner records type(e).__name__ into the job "
               "record itself — the error surfaces in the registry, and "
               "the next job belongs to another customer."},
    {"site": "api/security.py",
     "why_en": "JWT parsing re-raises as typed ValueError immediately "
               "(malformed header/signature/payload), and the JWT sniff "
               "returns None to fall through to API-key auth. Nothing "
               "is swallowed silently."},
    {"site": "api/dev_server.py",
     "why_en": "The last-resort 500 net logs with request_id and must "
               "never leak a stacktrace to a client; the AAMOS "
               "self-registration is explicitly non-blocking."},
    {"site": "api/ticker.py",
     "why_en": "The scheduler thread records the error into its status "
               "surface (/v1/schedules) instead of dying — a dead "
               "ticker is silent, a recorded error is readable."},
)


def broad_except_sites(root: pathlib.Path | None = None) -> list[dict]:
    """Varje `except Exception` i engine/, integrations/ och api/ som
    varken föregås av `except OUR_BUGS: raise` eller står i den
    motiverade allowlisten.

    Regeln kommer ur engine/datasources/faults.py: ett brett except utan
    vakt gör nästa AttributeError i VÅR kod till "källan är nere", och
    revisionen fann fyra sådana — bl.a. ett som svalde ImportError, en
    medlem i själva OUR_BUGS.
    """
    rot = root or _ROOT
    tillatna = {r["site"] for r in DEFENSIBLE_BROAD_EXCEPTS}
    fynd = []
    filer = (sorted(rot.glob("engine/**/*.py"))
             + sorted(rot.glob("integrations/*.py"))
             + sorted(rot.glob("api/*.py")))
    for path in filer:
        rel = str(path.relative_to(rot))
        if path.name == "faults.py" or "__pycache__" in rel:
            continue
        rader = path.read_text(encoding="utf-8").split("\n")
        for i, rad in enumerate(rader):
            m = re.match(r"^(\s*)except Exception(\s+as\s+\w+)?:", rad)
            if not m:
                continue
            indrag = m.group(1)
            vaktad = False
            for back in range(i - 1, -1, -1):
                prev = rader[back]
                if prev.strip() and not prev.startswith(indrag):
                    break
                if prev == f"{indrag}except OUR_BUGS:":
                    vaktad = True
                    break
                if prev == f"{indrag}try:":
                    break
            if not vaktad and rel not in tillatna:
                fynd.append({"site": f"{rel}:{i + 1}",
                             "severity": "high",
                             "category": "unguarded_broad_except"})
    return fynd


def dead_allowlist_rows(root: pathlib.Path | None = None) -> list[str]:
    """Allowlist-rader vars fil inte längre har något brett except.

    En död undantagsrad är värre än ingen: den ser ut som en granskad
    risk och täcker ingenting.
    """
    rot = root or _ROOT
    doda = []
    for r in DEFENSIBLE_BROAD_EXCEPTS:
        path = rot / r["site"]
        if not path.exists() or "except Exception" not in path.read_text(
                encoding="utf-8"):
            doda.append(r["site"])
        if not r.get("why_en", "").strip():
            doda.append(f"{r['site']} (saknar skäl)")
    return doda
