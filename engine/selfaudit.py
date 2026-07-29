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


# ── Lagergränserna ──────────────────────────────────────────────────────
# Motorkärnan är beroendefri och importerar inte api/ eller
# integrations/ — UTOM vid namngivna sömmar, lazy, med skäl. Regeln
# fanns som absolut prosa ("importerar ALDRIG härifrån") och var osann:
# revisionen mätte fyra sömmar mot integrations/ och en mot api/. En
# regel som inte stämmer med koden skyddar ingenting; sömmarna står nu
# som data, och en NY smygväg faller i stället för att glida in.
LAYER_SEAMS: tuple[dict, ...] = (
    {"site": "engine/datasources/adapters.py",
     "imports": "integrations.aamos",
     "why_en": "The quiXzoom adapter's default transport is AAMOS Core; "
               "lazy import at construction, only when no client is "
               "injected."},
    {"site": "engine/datasources/quixzoom_direct.py",
     "imports": "integrations.aamos",
     "why_en": "Shares AAMOS's fault vocabulary (AamosUnavailable) so "
               "the two quiXzoom paths degrade identically."},
    {"site": "engine/scheduler.py",
     "imports": "integrations.quixzoom_dispatch",
     "why_en": "The dispatch job kind orders field missions; lazy import "
               "inside the job runner, never at engine import time."},
    {"site": "engine/scheduler.py",
     "imports": "integrations.feedback",
     "why_en": "The exception_report job kind files tickets in the "
               "customer's system; lazy import inside the job runner, "
               "never at engine import time."},
    {"site": "engine/surface.py", "imports": "api.catalog",
     "why_en": "The surface counts endpoints per promise; API_CATALOG is "
               "data about the API, read lazily. No engine number "
               "depends on it."},
)


def layer_violations(root: pathlib.Path | None = None) -> list[dict]:
    """Importer från engine/ in i api/ eller integrations/ som inte står
    som söm. Lagerregeln är plattformens ryggrad: motorn ska kunna
    importeras och räkna utan att API-sidan ens finns."""
    import ast

    rot = root or _ROOT
    somnar = {(r["site"], r["imports"]) for r in LAYER_SEAMS}
    fynd = []
    for path in sorted(rot.glob("engine/**/*.py")):
        rel = str(path.relative_to(rot))
        if "__pycache__" in rel:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            moduler = []
            if isinstance(n, ast.Import):
                moduler = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                moduler = [n.module or ""]
            for m in moduler:
                bas = m.split(".")[0]
                if bas in ("api", "integrations") and \
                        (rel, m) not in somnar:
                    fynd.append({"site": f"{rel}:{n.lineno}",
                                 "imports": m, "severity": "critical",
                                 "category": "layer_violation"})
    return fynd


def nonstdlib_top_imports(root: pathlib.Path | None = None) -> list[dict]:
    """Toppnivåimporter i engine/ utanför stdlib. Beroendefriheten är
    ett produktlöfte (`pip install ingenting`); fastapi/pydantic hör
    till api/, psycopg importeras lazy i postgres-lagret."""
    import ast
    import sys

    rot = root or _ROOT
    std = set(sys.stdlib_module_names)
    fynd = []
    for path in sorted(rot.glob("engine/**/*.py")):
        rel = str(path.relative_to(rot))
        if "__pycache__" in rel:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in tree.body:                  # ENDAST toppnivån — lazy är
            moduler = []                     # lagerfrågan ovan
            if isinstance(n, ast.Import):
                moduler = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                moduler = [n.module or ""]
            for m in moduler:
                bas = m.split(".")[0]
                if bas and bas not in std and bas not in ("engine",):
                    fynd.append({"site": f"{rel}:{n.lineno}",
                                 "imports": m, "severity": "critical",
                                 "category": "nonstdlib_import"})
    return fynd


# ── Tenantkontraktet ────────────────────────────────────────────────────
def tenant_contract_violations() -> list[dict]:
    """De kundskopade lagerfunktionerna ska kräva tenant som keyword-only
    UTAN default — ett argument man kan glömma är en läcka som väntar."""
    import inspect

    from engine.storage.base import Store

    fynd = []
    for namn in ("save_report", "get_report", "list_reports",
                 "save_profile", "get_profile", "list_profiles"):
        fn = getattr(Store, namn, None)
        if fn is None:
            fynd.append({"site": f"Store.{namn}", "severity": "critical",
                         "category": "tenant_contract",
                         "detail_en": "method missing"})
            continue
        p = inspect.signature(fn).parameters.get("tenant")
        if p is None or p.kind is not inspect.Parameter.KEYWORD_ONLY \
                or p.default is not inspect.Parameter.empty:
            fynd.append({"site": f"Store.{namn}", "severity": "critical",
                         "category": "tenant_contract",
                         "detail_en": "tenant must be keyword-only with "
                                      "no default"})
    return fynd


# ── Lagerdrift sqlite ↔ postgres ────────────────────────────────────────
# Undantag som är representationsval, inte drift.
SCHEMA_EXCEPTIONS: dict[str, dict] = {
    "reports": {"sqlite_only": {"lat", "lon"}, "postgres_only": {"geom"},
                "why_en": "Postgres stores the point as PostGIS geometry; "
                          "sqlite as two REAL columns. Same decision, two "
                          "representations."},
}

_DDL_KEYWORDS = {"PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"}


def store_schema_drift() -> list[dict]:
    """Sqlite (referensen, läst ur en riktig databas) mot postgres
    (produktionen, läst ur DDL-texten). KolumnNAMN jämförs, aldrig
    typer. Revisionens fynd: inget jämförde dem alls, och produktionens
    lager var otestat per konstruktion."""
    from engine.storage import postgres as P
    from engine.storage.sqlite import SqliteStore

    s = SqliteStore(":memory:")
    try:
        sq_tab = {r[0] for r in s._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        sq = {t: {r[1] for r in
                  s._conn.execute(f"PRAGMA table_info({t})").fetchall()}
              for t in sq_tab}
    finally:
        s.close()

    pg_ddl = P._DDL + "".join(ddl for _, ddl in P._MIGRATIONS)
    pg: dict[str, set] = {}
    for tabell, kropp in re.findall(
            r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\);", pg_ddl,
            re.DOTALL):
        kol = set()
        for rad in kropp.split("\n"):
            m = re.match(r"\s*([a-z_]\w*)\s", rad)
            if m and m.group(1).upper() not in _DDL_KEYWORDS:
                kol.add(m.group(1))
        pg[tabell] = kol
    for tabell, kolumn in re.findall(
            r"ALTER TABLE (\w+) ADD COLUMN(?: IF NOT EXISTS)? (\w+)",
            pg_ddl):
        pg.setdefault(tabell, set()).add(kolumn)

    fynd = []
    for t in sorted(set(sq) - set(pg)):
        fynd.append({"site": t, "severity": "critical",
                     "category": "schema_drift",
                     "detail_en": "table exists only in sqlite"})
    for t in sorted(set(pg) - set(sq)):
        fynd.append({"site": t, "severity": "critical",
                     "category": "schema_drift",
                     "detail_en": "table exists only in postgres"})
    for t in sorted(set(sq) & set(pg)):
        u = SCHEMA_EXCEPTIONS.get(t, {})
        a = sq[t] - u.get("sqlite_only", set())
        b = pg[t] - u.get("postgres_only", set())
        if a != b:
            fynd.append({"site": t, "severity": "critical",
                         "category": "schema_drift",
                         "detail_en": f"only sqlite {sorted(a - b)}, "
                                      f"only postgres {sorted(b - a)}"})
    return fynd


# ── Ärlighetsfältens närvaro ────────────────────────────────────────────
# Vilka svarsbyggande moduler som MÅSTE bära sitt täcknings-/ärlighets-
# fält i källan. Rader, inte grenar: nästa motor är en rad till.
HONESTY_MARKERS: tuple[tuple[str, str], ...] = (
    ("engine/scoring.py", "data_coverage"),
    ("engine/risk.py", "data_coverage"),
    ("engine/workforce.py", "data_coverage"),
    ("engine/indices.py", "data_coverage"),
    ("engine/segments.py", "data_coverage"),
    ("engine/installed_base.py", "data_coverage"),
    ("engine/livability.py", "coverage"),
    ("engine/mrai.py", "refusal_en"),
    ("engine/analysis.py", "cannot_en"),
    ("engine/corroboration.py", "SINGLE_SOURCE_CEILING"),
)


def missing_honesty_markers(root: pathlib.Path | None = None) -> list[dict]:
    rot = root or _ROOT
    fynd = []
    for rel, markor in HONESTY_MARKERS:
        path = rot / rel
        if not path.exists() or markor not in path.read_text(
                encoding="utf-8"):
            fynd.append({"site": rel, "severity": "critical",
                         "category": "honesty_field_missing",
                         "detail_en": f"expected marker '{markor}'"})
    return fynd


def modules_without_tests(root: pathlib.Path | None = None) -> list[dict]:
    """Motor-moduler som ingen testfil ens nämner. Revisionen fann tre
    (glossary, specialization, commission — intäktsmodellen); efter den
    ska listan vara tom, och en NY modul utan test faller här."""
    rot = root or _ROOT
    testkalla = "".join(p.read_text(encoding="utf-8")
                        for p in sorted(rot.glob("tests/test_*.py")))
    fynd = []
    for p in sorted(rot.glob("engine/*.py")):
        namn = p.stem
        if namn == "__init__":
            continue
        if f"engine.{namn}" not in testkalla and not re.search(
                rf"from engine import [^\n]*\b{namn}\b", testkalla):
            fynd.append({"site": f"engine/{namn}.py", "severity": "high",
                         "category": "module_without_test"})
    return fynd


# ── Grindkontrollen (kräver API-kontext) ────────────────────────────────
def ungated_endpoints(context: dict) -> list[dict]:
    """Routade vägar som varken är öppna eller bär kapabilitet.
    Kontexten (par, öppna vägar, uppslag) byggs av API-lagret —
    motorn importerar aldrig api/."""
    vagar = {p for _, p in context["pairs"]}
    oppna = set(context["open_paths"])
    slags = context["required_capability"]
    return [{"site": p, "severity": "critical",
             "category": "ungated_endpoint"}
            for p in sorted(vagar)
            if p not in oppna and p != "/health" and slags(p) is None]


# ── Katalogen och körningen ─────────────────────────────────────────────
def _check(id_, what_en, cannot_en, run):
    return {"id": id_, "what_en": what_en, "cannot_en": cannot_en,
            "run": run}


CHECKS: tuple[dict, ...] = (
    _check(
        "ungated_endpoints",
        "Every routed path in both API layers is either deliberately "
        "open (named in _OPEN_PATHS) or carries a capability. The audit "
        "measured three paths that were neither — valid key required, "
        "every plan admitted.",
        "A static sweep proves the gate EXISTS, not that the handler "
        "behind it is correct. It also cannot see gates enforced "
        "in-handler (export datasets, schedule kinds).",
        None),                    # kräver kontext — sätts i run_audit
    _check(
        "tenant_contract",
        "Customer-scoped store methods require tenant as a keyword-only "
        "argument with no default. An argument you can forget is a leak "
        "waiting to happen.",
        "Signature inspection proves the argument is required, not that "
        "every SQL statement filters on it. The tenancy tests cover the "
        "behaviour; this check keeps the contract's shape.",
        lambda ctx: tenant_contract_violations()),
    _check(
        "unguarded_broad_excepts",
        "Every `except Exception` in engine/, integrations/ and api/ is "
        "preceded by `except OUR_BUGS: raise` or sits in a justified "
        "allowlist. The audit found four unguarded — one swallowed "
        "ImportError, a member of OUR_BUGS itself.",
        "It proves the guard exists, not that the degradation below it "
        "is honest. A dead allowlist row (site gone, or reason too "
        "thin) is reported as a finding, not silently kept.",
        lambda ctx: broad_except_sites()
        + [{"site": s, "severity": "high",
            "category": "dead_allowlist_row"} for s in dead_allowlist_rows()]),
    _check(
        "store_schema_drift",
        "Sqlite (the tested reference) and postgres (production) "
        "describe the same tables and column names, exceptions named "
        "with reasons. Before the audit nothing compared them at all.",
        "Column NAMES only — types are dialect choices, and the "
        "postgres side is read from DDL text, not a live database. A "
        "live-database diff needs `PostgresStore.selftest()` at deploy.",
        lambda ctx: store_schema_drift()),
    _check(
        "layer_boundaries",
        "engine/ imports api/ or integrations/ only at the named, "
        "justified seams in LAYER_SEAMS. The old rule said 'never' and "
        "was false; a rule that disagrees with the code protects "
        "nothing.",
        "It cannot judge whether a seam SHOULD exist — only that no "
        "unnamed one appears. Removing a seam requires editing the "
        "data row, which is the point.",
        lambda ctx: layer_violations()),
    _check(
        "stdlib_only_core",
        "Top-level imports in engine/ are stdlib or engine-internal. "
        "Zero dependencies is a product promise, not a preference.",
        "Lazy imports inside functions are the layer check's concern; "
        "this one keeps `import engine` working on a bare Python.",
        lambda ctx: nonstdlib_top_imports()),
    _check(
        "honesty_fields_present",
        "Every response-building engine carries its honesty marker "
        "(data_coverage, coverage, refusal_en …) in source. The audit "
        "found the flagship index engine without one.",
        "Presence of the string, not correctness of the number. The "
        "per-engine tests prove the arithmetic; this catches the next "
        "engine shipped without the field.",
        lambda ctx: missing_honesty_markers()),
    _check(
        "modules_without_tests",
        "Every engine module is at least mentioned by some test file. "
        "The audit found the revenue model itself untested.",
        "Mention is not coverage — a module can be imported by a test "
        "and still have untested functions. It catches total silence, "
        "nothing subtler.",
        lambda ctx: modules_without_tests()),
)


def run_audit(context: dict | None = None) -> dict:
    """Kör hela katalogen. Utan API-kontext REDOVISAS grindkontrollen
    som refused i stället för att gissas — samma regel som överallt:
    vägran med skäl slår ett fabricerat resultat."""
    from engine.claims import canonical_hash
    from engine.integrity import integrity_score

    resultat = []
    alla_fynd: list[dict] = []
    for c in CHECKS:
        rad = {"id": c["id"], "what_en": c["what_en"],
               "cannot_en": c["cannot_en"]}
        if c["id"] == "ungated_endpoints":
            if context and "pairs" in context:
                fynd = ungated_endpoints(context)
            else:
                rad.update(status="refused", findings=[], refusal_en=(
                    "Needs the API layer's context (routed pairs, open "
                    "paths, capability lookup) — the engine never imports "
                    "api/, so without it this check refuses rather than "
                    "guesses."))
                resultat.append(rad)
                continue
        else:
            fynd = c["run"](context or {})
        rad.update(status="computed", findings=fynd)
        alla_fynd.extend(fynd)
        resultat.append(rad)

    score = integrity_score([{"severity": f["severity"],
                              "category": f.get("category", ""),
                              "description": f.get("detail_en", ""),
                              "index": i}
                             for i, f in enumerate(alla_fynd)])
    korda = [r for r in resultat if r["status"] == "computed"]
    return {
        "audit_id": canonical_hash({"findings": alla_fynd,
                                    "checks": [r["id"] for r in resultat]}),
        "checks": resultat,
        "checks_computed": len(korda),
        "checks_refused": len(resultat) - len(korda),
        "finding_count": len(alla_fynd),
        "passed": score["passed"] and not alla_fynd,
        "integrity": score,
        "what_en": (
            "The platform auditing its own guardrails: gates, tenant "
            "contract, fault doctrine, schema parity, layer boundaries, "
            "dependency promise, honesty fields, test presence. Grown "
            "out of the 2026-07-29 revision — these are the measurements "
            "that found the defects, kept running."),
        "cannot_en": (
            "Static self-inspection proves structure, never behaviour: "
            "a present guard can still guard the wrong thing, and a "
            "passing audit is not a correctness proof. It also cannot "
            "see what only a live environment shows — network reach, "
            "real databases, real load."),
    }


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
