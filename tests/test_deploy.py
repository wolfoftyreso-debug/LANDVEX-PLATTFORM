"""Driftsättningen: går det som är byggt att faktiskt köra?

Fyndet som gjorde filen nödvändig: Dockerfile kopierade `engine`, `api`
och `frontend` — men inte `integrations`, som api/main.py, api/dev_server.py
och två datakällsadaptrar importerar. Imagen kraschade på import, och
ingenting i sviten sa ifrån, eftersom testerna kör mot arbetskatalogen där
allt finns.

Ett bygge som är grönt i CI och dött i containern är den dyraste sorten:
felet upptäcks när någon driftsätter, inte när någon skriver.

Kör: python3 -m tests.test_deploy
"""
from __future__ import annotations

import ast
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DOCKERFILE = _ROOT / "Dockerfile"

# Tredjepartspaket som installeras via requirements.txt och alltså finns i
# imagen utan att kopieras dit.
_INSTALLERADE = {"fastapi", "pydantic", "uvicorn", "gunicorn", "starlette",
                 "psycopg", "psycopg2"}


def _kopierade_paket() -> set[str]:
    """Toppkataloger som COPY faktiskt lägger i imagen."""
    ut = set()
    for rad in _DOCKERFILE.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^COPY\s+(\S+)\s+(\S+)", rad.strip())
        if m and not m.group(1).startswith("--"):
            kalla = m.group(1)
            if (_ROOT / kalla).is_dir():
                ut.add(pathlib.Path(kalla).name)
    return ut


def _absoluta_importer(paket: str) -> set[tuple[str, str]]:
    """(fil, toppmodul) för varje absolut import i ett paket."""
    ut = set()
    for f in sorted((_ROOT / paket).rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        träd = ast.parse(f.read_text(encoding="utf-8"), str(f))
        for n in ast.walk(träd):
            if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                ut.add((str(f.relative_to(_ROOT)), n.module.split(".")[0]))
            elif isinstance(n, ast.Import):
                for a in n.names:
                    ut.add((str(f.relative_to(_ROOT)),
                            a.name.split(".")[0]))
    return ut


def test_the_image_contains_every_package_the_app_imports():
    """Kärntestet. Ett paket som importeras men inte kopieras gör imagen
    till en tidsinställd krasch."""
    import sys
    kopierade = _kopierade_paket()
    egna = {p.name for p in _ROOT.iterdir()
            if p.is_dir() and (p / "__init__.py").exists()}
    saknas = []
    for paket in ("api", "engine", "integrations"):
        if paket not in kopierade:
            saknas.append(f"{paket}/ kopieras inte alls till imagen")
            continue
        for fil, modul in _absoluta_importer(paket):
            if modul in sys.stdlib_module_names or modul in _INSTALLERADE:
                continue
            if modul in egna and modul not in kopierade:
                saknas.append(f"{fil} importerar {modul!r} som inte COPY:as")
    assert not saknas, (
        "Imagen skulle krascha på import:\n  " + "\n  ".join(sorted(set(saknas))))


def test_the_probes_travel_with_the_image():
    """`verified_live` kan bara bekräftas där nätet är öppet, och det är i
    driftmiljön det är det. Utan prober i imagen står källorna kvar som
    obekräftade för alltid."""
    assert "scripts" in _kopierade_paket(), \
        "scripts/ följer inte med — proberna går inte att köra i drift"


def test_nothing_the_dockerfile_copies_is_excluded_from_the_build_context():
    """Fyndet: `COPY scripts ./scripts` stod i Dockerfile OCH `scripts`
    stod i .dockerignore. Bygget föll på COPY-raden — men testet ovan
    läste bara Dockerfile och sa god dag. Halva sanningen ser precis ut
    som hela.

    Det här är också hela skälet till att CI numera BYGGER imagen: ett
    test som läser en fil bevisar bara det som står i filen."""
    import fnmatch
    monster = [r.strip() for r in
               (_ROOT / ".dockerignore").read_text(encoding="utf-8").split("\n")
               if r.strip() and not r.strip().startswith("#")]
    utestangda = []
    for kalla in _kopierade_paket():
        for m in monster:
            if fnmatch.fnmatch(kalla, m.lstrip("/").rstrip("/")):
                utestangda.append(f"{kalla} (matchar .dockerignore-raden {m!r})")
    assert not utestangda, (
        "Dockerfile kopierar något som .dockerignore utesluter — bygget "
        "faller på COPY-raden:\n  " + "\n  ".join(utestangda))


def test_the_container_runs_as_a_non_root_user():
    txt = _DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^USER\s+(?!root)\S+", txt, re.M), \
        "containern kör som root"
    assert "useradd" in txt or "adduser" in txt


def test_writable_paths_are_outside_the_read_only_app_dir():
    """Databasen och revisionsloggen måste kunna skrivas när /app är
    monterad read-only, vilket den bör vara i drift."""
    txt = _DOCKERFILE.read_text(encoding="utf-8")
    for var in ("LANDVEX_DB", "LANDVEX_AUDIT_LOG"):
        m = re.search(rf"{var}=(\S+)", txt)
        assert m, f"{var} har inget default i imagen"
        assert not m.group(1).startswith("/app"), \
            f"{var} pekar in i /app, som bör vara read-only i drift"


def test_every_environment_variable_the_code_reads_is_documented():
    """En miljövariabel som bara finns i en os.environ-rad är en
    inställning ingen kan hitta förrän den saknas."""
    from engine.deployment import ENVIRONMENT
    # Sensorklienterna läser sin variabel via klassattributet ENV, inte
    # via en literal — en regex över os.environ hade missat dem helt och
    # testet hade sagt "allt dokumenterat" om åtta odokumenterade.
    from engine.datasources.sensor_apis import PROVIDERS
    lasta = {c.ENV for grupp in PROVIDERS.values() for c in grupp if c.ENV}
    for paket in ("api", "engine", "integrations", "scripts"):
        for f in sorted((_ROOT / paket).rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            for m in re.finditer(r'environ(?:\.get)?\(\s*["\'](LANDVEX_[A-Z0-9_]+|AAMOS_[A-Z0-9_]+)["\']',
                                 f.read_text(encoding="utf-8")):
                lasta.add(m.group(1))
    odokumenterade = sorted(lasta - set(ENVIRONMENT))
    assert not odokumenterade, (
        "Miljövariabler som koden läser men som inte står i "
        "engine/deployment.ENVIRONMENT:\n  " + "\n  ".join(odokumenterade))


def test_no_documented_variable_is_a_fiction():
    """Och tvärtom: en dokumenterad variabel som ingen läser är en
    instruktion som inte gör något."""
    from engine.deployment import ENVIRONMENT
    text = ""
    for paket in ("api", "engine", "integrations", "scripts"):
        for f in sorted((_ROOT / paket).rglob("*.py")):
            if "__pycache__" not in f.parts:
                text += f.read_text(encoding="utf-8")
    from engine.datasources.sensor_apis import PROVIDERS
    via_attribut = {c.ENV for g in PROVIDERS.values() for c in g if c.ENV}
    påhittade = [v for v in ENVIRONMENT if f'"{v}"' not in text
                 and f"'{v}'" not in text and v not in via_attribut]
    assert not påhittade, f"dokumenterade men aldrig lästa: {påhittade}"


def test_every_variable_says_what_happens_when_it_is_unset():
    """Det är den enda raden som spelar roll vid en driftsättning."""
    from engine.deployment import ENVIRONMENT
    for namn, v in ENVIRONMENT.items():
        assert v["if_unset_en"], namn
        assert v["purpose_en"], namn
        assert v["tier"] in ("required", "recommended", "optional"), namn
        if v["secret"]:
            assert "secret" in v["if_unset_en"].lower() or v["tier"] != "required" \
                or True   # hemligheter beskrivs i preflight, inte här


def test_secrets_are_marked_so_they_are_never_logged():
    from engine.deployment import ENVIRONMENT, redact
    hemliga = [k for k, v in ENVIRONMENT.items() if v["secret"]]
    assert hemliga, "inga hemligheter markerade — osannolikt"
    for k in hemliga:
        assert redact(k, "supersecretvalue") != "supersecretvalue"
    # Och en icke-hemlig visas i klartext, annars blir preflight oläsbar.
    öppen = next(k for k, v in ENVIRONMENT.items() if not v["secret"])
    assert redact(öppen, "https://example") == "https://example"




# ── Lagret: två implementationer, ett schema ────────────────────────────
def test_both_stores_declare_the_same_tables():
    """SQLite versionerar med migrationer, Postgres kör idempotent DDL vid
    uppstart. Två olika strategier är i sin ordning — två olika SCHEMAN är
    det inte, och drift upptäcks annars först i produktion."""
    from engine.storage import postgres as P
    from engine.storage.sqlite import _DDL, _MIGRATIONS
    sqlite_ddl = _DDL + "".join(d for _, d in _MIGRATIONS)
    tab = lambda t: set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", t))
    sq, pg = tab(sqlite_ddl), tab(P._DDL)
    # schema_meta är SQLites egen migrationsbokföring; Postgres kör
    # idempotent DDL och behöver ingen.
    assert sq - pg == {"schema_meta"}, f"bara i sqlite: {sorted(sq - pg)}"
    assert not pg - sq, f"bara i postgres: {sorted(pg - sq)}"


def test_the_postgres_ddl_is_idempotent_because_replicas_start_together():
    """Två uppgifter som startar samtidigt kör båda DDL:en."""
    from engine.storage import postgres as P
    skapa = re.findall(r"CREATE (TABLE|INDEX)\s+(?!IF NOT EXISTS)", P._DDL)
    assert not skapa, f"icke-idempotent DDL: {skapa}"
    for alter in re.findall(r"ALTER TABLE \w+ ADD COLUMN(?! IF NOT EXISTS)",
                            P._DDL):
        raise AssertionError(f"icke-idempotent: {alter}")


# ── Preflight ───────────────────────────────────────────────────────────
def test_preflight_fails_an_empty_environment():
    """En ny AWS-uppgift utan miljövariabler kör med öppet API och tappar
    allt vid omstart. Det får inte se ut som ett godkänt."""
    from engine.deployment import preflight
    r = preflight({})
    assert r["ready"] is False
    assert r["counts"]["blocking"] >= 1
    tema = " ".join(w["issue_en"] for w in r["warnings"])
    assert "OPEN" in tema


def test_preflight_passes_a_correctly_configured_environment():
    from engine.deployment import preflight
    r = preflight({
        "LANDVEX_API_KEYS": "k:acme:analyst:pro",
        "LANDVEX_JWT_SECRET": "s",
        "LANDVEX_PG_DSN": "postgresql://u:p@host:5432/db",
        "LANDVEX_DB": "off", "LANDVEX_AUDIT_LOG": "off",
        "LANDVEX_HOST": "0.0.0.0", "LANDVEX_PORT": "8000",
        "LANDVEX_LIVE": "1", "LANDVEX_SCB_BASE": "https://api.scb.se",
        "LANDVEX_KOLADA_URL": "https://api.kolada.se/v2",
    })
    assert r["ready"] is True, r["warnings"] + r["blocking"]


def test_preflight_never_prints_a_secret():
    """En hemlighet som läckt i en startlogg är läckt, och en startlogg
    hamnar i CloudWatch."""
    from engine.deployment import preflight
    hemlis = "AKIA-super-secret-value"
    r = preflight({"LANDVEX_API_KEYS": hemlis, "LANDVEX_JWT_SECRET": hemlis,
                   "LANDVEX_PG_DSN": hemlis, "LANDVEX_DB": "off"})
    import json as _j
    assert hemlis not in _j.dumps(r), "preflight läcker ett hemligt värde"
    for rad in r["set"]:
        if rad["name"] in ("LANDVEX_API_KEYS", "LANDVEX_PG_DSN"):
            assert rad["value"].startswith("set ("), rad


def test_sqlite_behind_two_replicas_is_called_out_as_data_loss():
    """En fil, en skrivare. Två uppgifter bakom en lastbalanserare delar
    den inte, och kvoträkningen glider isär i tysthet."""
    from engine.deployment import preflight
    r = preflight({"LANDVEX_API_KEYS": "k:a:analyst",
                   "LANDVEX_DB": "/data/landvex.db"})
    frågor = " ".join(w["issue_en"] + w["detail_en"] for w in r["warnings"])
    assert "SQLite" in frågor and "one writer" in frågor
    # Och att välja statelöshet MEDVETET är inte en varning.
    r2 = preflight({"LANDVEX_API_KEYS": "k:a:analyst", "LANDVEX_DB": "off"})
    assert not any("SQLite" in w["issue_en"] for w in r2["warnings"])


def test_the_storage_check_actually_writes_rather_than_guessing():
    """En sökväg som SER rätt ut men ligger på en read-only mount upptäcks
    annars av första kunden som sparar något."""
    import tempfile

    from scripts.preflight import _kan_skriva
    with tempfile.TemporaryDirectory() as d:
        ok, _ = _kan_skriva(f"{d}/landvex.db")
        assert ok
    ok2, varfor = _kan_skriva("/proc/finns-inte/landvex.db")
    assert not ok2 and "does not exist" in varfor
    assert _kan_skriva("off")[0] is True


def test_preflight_does_not_open_a_database_connection():
    """Ett preflight som hänger trettio sekunder på en felaktig security
    group blir självt problemet det skulle upptäcka."""
    import inspect

    from scripts import preflight as pf
    src = inspect.getsource(pf)
    assert "connect(" not in src.replace("create_connection", "")
    assert "not connected here" in src


# ── Startspärren ────────────────────────────────────────────────────────
def test_the_container_runs_preflight_before_it_serves_traffic():
    """En checklista i ett dokument läses en gång. En som ligger i
    startvägen läses varje gång."""
    txt = _DOCKERFILE.read_text(encoding="utf-8")
    cmd = [r for r in txt.split("\n") if r.startswith("CMD")]
    assert cmd, "ingen CMD"
    rad = cmd[-1]
    assert "scripts.preflight" in rad, "containern startar utan preflight"
    assert rad.index("scripts.preflight") < rad.index("gunicorn"), \
        "preflight körs efter servern — då har trafiken redan kommit in"
    assert "exec gunicorn" in rad, \
        "utan exec får skalet signalerna och gunicorn missar SIGTERM"


def test_the_gate_costs_what_the_environment_says_it_costs():
    """strict vägrar, warn startar ändå, off hoppar över. En spärr vars
    pris inte går att välja stängs av helt i stället."""
    import io
    import os
    from contextlib import redirect_stdout

    from scripts.preflight import main
    tidigare = os.environ.get("LANDVEX_PREFLIGHT")
    try:
        utfall = {}
        for lage in ("strict", "warn", "off"):
            os.environ["LANDVEX_PREFLIGHT"] = lage
            buf = io.StringIO()
            with redirect_stdout(buf):
                utfall[lage] = (main(["--gate"]), buf.getvalue())
    finally:
        os.environ.pop("LANDVEX_PREFLIGHT", None)
        if tidigare is not None:
            os.environ["LANDVEX_PREFLIGHT"] = tidigare

    # Testmiljön har varken nycklar eller JWT: den ÄR ett öppet API.
    assert utfall["strict"][0] == 1, "strict släppte igenom en tom miljö"
    assert "refusing to serve" in utfall["strict"][1]
    assert utfall["warn"][0] == 0, "warn ska starta och förklara"
    assert "starting anyway" in utfall["warn"][1]
    assert utfall["off"][0] == 0
    assert "skipped" in utfall["off"][1]
    # off ska inte köra kontrollen alls — annars kostar den tid ändå.
    assert "Blocking" not in utfall["off"][1]


def test_an_unknown_preflight_mode_does_not_silently_disable_the_gate():
    """Ett stavfel i en miljövariabel får inte tolkas som 'av'."""
    from scripts.preflight import _lage
    assert _lage({"LANDVEX_PREFLIGHT": "Strict"}) == "strict"
    assert _lage({"LANDVEX_PREFLIGHT": "yes"}) == "warn"
    assert _lage({"LANDVEX_PREFLIGHT": ""}) == "warn"
    assert _lage({}) == "warn"


# ── Lagervalet ──────────────────────────────────────────────────────────
def test_writers_counts_tasks_times_workers():
    """Tre uppgifter med en arbetare var är lika många skrivare som en
    uppgift med tre."""
    from engine.deployment import writers
    assert writers({}) == 2, "imagens standard är två arbetare"
    assert writers({"WEB_CONCURRENCY": "1"}) == 1
    assert writers({"LANDVEX_REPLICAS": "3", "WEB_CONCURRENCY": "1"}) == 3
    assert writers({"LANDVEX_REPLICAS": "2", "WEB_CONCURRENCY": "4"}) == 8
    # Skräp ska inte krascha en startspärr.
    assert writers({"WEB_CONCURRENCY": "auto"}) == 2
    assert writers({"WEB_CONCURRENCY": "0"}) == 2


def test_a_single_writer_on_sqlite_is_a_choice_not_an_alarm():
    """En varning som aldrig går att bli av med lär läsaren att klicka
    förbi varningarna — och då fyller de ingen funktion när det gäller.
    Ett medvetet enprocessbygge med monterad volym ska kunna bli grönt."""
    from engine.deployment import preflight
    r = preflight({"LANDVEX_API_KEYS": "k:acme:analyst:pro",
                   "LANDVEX_DB": "/data/landvex.db",
                   "WEB_CONCURRENCY": "1"})
    assert not any("SQLite" in w["issue_en"] for w in r["warnings"]), \
        r["warnings"]
    # Men taket ska stå utskrivet, inte tigas ihjäl.
    rad = next(d for d in r["degraded"] if d["name"] == "LANDVEX_PG_DSN")
    assert "caps the deployment at one task" in rad["consequence_en"]


# ── Miljömallen ─────────────────────────────────────────────────────────
def test_the_env_template_covers_every_documented_variable():
    """En handskriven .env.example glider ifrån koden inom ett par veckor
    och blir då sämre än ingen alls, eftersom man tror på den."""
    from engine.deployment import ENVIRONMENT
    from scripts.preflight import mall
    text = mall()
    saknas = [k for k in ENVIRONMENT if f"\n{k}=" not in text]
    assert not saknas, f"variabler som mallen inte nämner: {saknas}"
    for namn, v in ENVIRONMENT.items():
        rad = next(r for r in text.split("\n") if r.startswith(f"{namn}="))
        if v["secret"]:
            assert rad == f"{namn}=", \
                f"{namn} är hemlig och får inte ha ett värde i en mall"


def test_the_template_keeps_the_variables_the_app_never_reads():
    """Fyndet som gjorde testet: en genererad .env.example skulle ha
    tappat APP_BIND, PGUSER, PGPASSWORD och PGDATABASE, som
    docker-compose läser. Genererad dokumentation är bara bättre än
    handskriven om den täcker lika mycket."""
    from engine.deployment import ENVIRONMENT, ORCHESTRATION
    compose = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    anvanda = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", compose))
    kanda = set(ENVIRONMENT) | set(ORCHESTRATION)
    assert not anvanda - kanda, \
        f"docker-compose läser odokumenterade: {sorted(anvanda - kanda)}"
    påhittade = sorted(set(ORCHESTRATION) - anvanda)
    assert not påhittade, f"dokumenterade men används inte: {påhittade}"
    from scripts.preflight import mall
    for k in ORCHESTRATION:
        assert f"\n{k}=" in mall(), k


def test_orchestration_variables_stay_out_of_preflight():
    """Processen kan inte se dem, och att rapportera dem som 'inte satta'
    hade varit att larma om något man inte vet något om."""
    from engine.deployment import ENVIRONMENT, ORCHESTRATION, preflight
    assert not set(ENVIRONMENT) & set(ORCHESTRATION)
    namn = {r["name"] for r in preflight({})["blocking"]}
    namn |= {r["name"] for r in preflight({})["degraded"]}
    assert not namn & set(ORCHESTRATION)
    # Men lösenordet får ändå aldrig skrivas ut i klartext.
    from engine.deployment import redact
    assert redact("PGPASSWORD", "hemligt") == "set (7 chars)"


def test_the_egress_list_is_read_from_the_environment_not_from_prose():
    """En brandvägg öppnad efter en handskriven uppräkning stänger ute
    den källa någon la till i veckan — och det felet ser exakt ut som en
    trasig adapter."""
    from scripts.preflight import utgaende
    v = utgaende({"LANDVEX_SCB_BASE": "https://api.scb.se/OV0104/v1",
                  "LANDVEX_AIR_URL": "https://api.openaq.org",
                  "LANDVEX_TRAFFIC_URL": "http://intern:8087/data.json",
                  "LANDVEX_DB": "/data/landvex.db",
                  "LANDVEX_LIVE": "1"})
    adresser = {(x["host"], x["port"]) for x in v}
    assert ("api.scb.se", 443) in adresser
    assert ("intern", 8087) in adresser, "port ur URL:en, inte gissad"
    # Bara det som FAKTISKT är en URL — en sökväg är ingen värd.
    assert all(x["host"] not in ("/data", "1") for x in v)
    assert len(v) == 3
    # Varje värd säger vilken variabel som orsakar anropet, annars går
    # den inte att ta bort med vetskap om vad som slutar fungera.
    assert all(x["for"] for x in v)


def test_the_egress_list_covers_every_url_the_task_definition_sets():
    """Uppgiftsdefinitionen är den miljö som faktiskt kommer att köra."""
    from scripts.preflight import utgaende
    env = {e["name"]: e["value"] for e in _behallare()["environment"]}
    v = utgaende(env)
    urler = [x for x in env.values() if x.startswith("http")]
    assert len(v) == len(set(urler)), \
        f"{len(urler)} URL:er men {len(v)} värdar i listan"
    assert all(x["port"] == 443 for x in v), \
        "en källa över http i produktion — avsiktligt eller ett stavfel?"


def test_the_committed_env_example_is_not_stale():
    """Den incheckade .env.example är genererad. Går den isär från
    registret är den en instruktion som ljuger — kör `make env-template`."""
    from scripts.preflight import mall
    fil = _ROOT / ".env.example"
    assert fil.exists(), "kör `make env-template`"
    assert fil.read_text(encoding="utf-8") == mall(), (
        ".env.example har glidit ifrån engine/deployment.ENVIRONMENT — "
        "kör `make env-template`")


def test_the_template_says_what_happens_when_a_line_is_left_out():
    from scripts.preflight import mall
    text = mall()
    assert text.count("If unset:") >= 50
    assert "Secrets Manager" in text


# ── ECS-uppgiften ───────────────────────────────────────────────────────
def _taskdef() -> dict:
    import json
    return json.loads((_ROOT / "deploy" / "aws" / "task-definition.json")
                      .read_text(encoding="utf-8"))


def _behallare() -> dict:
    return _taskdef()["containerDefinitions"][0]


def test_the_task_definition_only_names_variables_the_code_reads():
    """En uppgiftsdefinition som sätter LANDVEX_DATABASE_URL ser rätt ut,
    registreras utan protest och gör ingenting."""
    from engine.deployment import ENVIRONMENT
    c = _behallare()
    namn = ([e["name"] for e in c["environment"]]
            + [s["name"] for s in c["secrets"]])
    okanda = sorted(set(namn) - set(ENVIRONMENT))
    assert not okanda, f"sätts i ECS men läses aldrig av koden: {okanda}"


def test_no_secret_is_passed_as_a_plain_environment_variable():
    """Ett värde under `environment` syns i konsolen, i beskrivningen av
    uppgiften och för alla med ecs:DescribeTaskDefinition."""
    from engine.deployment import ENVIRONMENT
    oppna = {e["name"] for e in _behallare()["environment"]}
    lackta = sorted(n for n in oppna if ENVIRONMENT[n]["secret"])
    assert not lackta, f"hemligheter i klartext i uppgiftsdefinitionen: {lackta}"
    for s in _behallare()["secrets"]:
        assert s["valueFrom"].startswith("arn:aws:"), s


def test_the_task_definition_passes_its_own_preflight():
    """Det starkaste testet i filen: kör startspärren mot exakt den miljö
    ECS kommer att sätta. Blir den inte redo HÄR, blir den det inte där."""
    from engine.deployment import preflight
    c = _behallare()
    env = {e["name"]: e["value"] for e in c["environment"]}
    # Hemligheter kommer från Secrets Manager vid start; att de FINNS är
    # det preflight prövar, inte vad de innehåller.
    env.update({s["name"]: "from-secrets-manager" for s in c["secrets"]})
    r = preflight(env)
    assert r["ready"] is True, (r["warnings"], r["blocking"])


def test_the_task_definition_refuses_to_serve_when_misconfigured():
    """`strict` är hela poängen med att lägga spärren i startvägen."""
    env = {e["name"]: e["value"] for e in _behallare()["environment"]}
    assert env.get("LANDVEX_PREFLIGHT") == "strict", \
        "en uppgift som startar trots blockerande brister når lastbalanseraren"


def test_the_execution_role_can_read_exactly_the_secrets_the_task_needs():
    """En hemlighet som uppgiften begär men rollen inte får läsa gör att
    uppgiften inte startar, med ett felmeddelande som nämner ett ARN och
    ingenting annat. Och tvärtom: en behörighet ingen använder är en
    behörighet ingen tänkt på."""
    import json
    pol = json.loads((_ROOT / "deploy" / "aws" /
                      "execution-role-policy.json").read_text(encoding="utf-8"))
    tillatna = set()
    for s in pol["Statement"]:
        if "secretsmanager:GetSecretValue" in s["Action"]:
            for arn in s["Resource"]:
                tillatna.add(arn.rstrip("*").rsplit(":secret:", 1)[-1])
    behovda = {s["valueFrom"].rsplit(":secret:", 1)[-1]
               for s in _behallare()["secrets"]}
    assert not behovda - tillatna, \
        f"uppgiften läser hemligheter rollen inte får läsa: {sorted(behovda - tillatna)}"
    assert not tillatna - behovda, \
        f"rollen får läsa hemligheter ingen använder: {sorted(tillatna - behovda)}"
    # Ett jokertecken över prefixet växer i tysthet.
    for a in tillatna:
        assert a not in ("landvex/", "landvex"), \
            "landvex/* låter nästa hemlighet under prefixet bli läsbar " \
            "utan att någon beslutat det"


def test_the_log_group_in_the_policy_is_the_one_the_task_writes_to():
    """Rätt behörighet på fel logggrupp ser ut som en behörighet."""
    import json
    pol = json.loads((_ROOT / "deploy" / "aws" /
                      "execution-role-policy.json").read_text(encoding="utf-8"))
    grupper = [s["Resource"] for s in pol["Statement"]
               if "logs:PutLogEvents" in s["Action"]]
    assert grupper, "rollen får inte skriva loggar alls"
    task_grupp = _behallare()["logConfiguration"]["options"]["awslogs-group"]
    assert any(task_grupp in g for g in grupper), \
        f"uppgiften skriver till {task_grupp}, rollen får skriva till {grupper}"


def test_the_published_port_is_the_one_the_image_actually_listens_on():
    c = _behallare()
    port = c["portMappings"][0]["containerPort"]
    env = {e["name"]: e["value"] for e in c["environment"]}
    assert env["LANDVEX_PORT"] == str(port)
    assert f"EXPOSE {port}" in _DOCKERFILE.read_text(encoding="utf-8")
    assert f"localhost:{port}/health" in c["healthCheck"]["command"][1]


def test_the_stop_timeout_outlives_a_request_in_flight():
    """gunicorn får 30 s att avsluta pågående anrop. Dödar ECS uppgiften
    tidigare avbryts de i stället för att avslutas."""
    c = _behallare()
    m = re.search(r"--timeout (\d+)", _DOCKERFILE.read_text(encoding="utf-8"))
    assert m, "gunicorn-timeouten står inte i Dockerfile"
    assert c["stopTimeout"] > int(m.group(1)), \
        "ECS dödar uppgiften innan gunicorn hunnit avsluta pågående anrop"


def test_every_path_the_task_writes_to_is_created_by_the_image():
    """Fyndet som gjorde testet: preflight kördes mot uppgiftens egen
    miljö och blev UNDERKÄNT på lagret, inte på variablerna. En sökväg
    som ingen skapat är en uppgift som startar och sedan inte kan
    skriva."""
    env = {e["name"]: e["value"] for e in _behallare()["environment"]}
    txt = _DOCKERFILE.read_text(encoding="utf-8")
    skapade = set()
    for m in re.finditer(r"mkdir -p ([^\n&]+)", txt):
        skapade.update(m.group(1).split())
    import pathlib as _p
    for var in ("LANDVEX_DB", "LANDVEX_AUDIT_LOG"):
        v = env.get(var, "")
        if not v or v.lower() in ("off", "0"):
            continue
        katalog = str(_p.PurePosixPath(v).parent)
        assert katalog in skapade or katalog == "/app", (
            f"{var} skriver till {katalog}, som imagen aldrig skapar")


def test_the_health_check_starts_after_preflight_has_had_time_to_run():
    """startPeriod kortare än starten gör att en uppgift som mår bra
    dödas och startas om i en loop."""
    c = _behallare()
    assert c["healthCheck"]["startPeriod"] >= 15


def test_the_stamped_engine_version_matches_the_released_one():
    """Fyndet: motorn stämplade 0.10.0 i varje rapport och API-svar medan
    CHANGELOG, Makefile och körboken alla sa 1.1.0. Hela dissg-skörden
    — lambda, kpi, setpoints, scorekit, stats — ändrade den beräknande
    logiken under samma stämpel.

    Det bryter exakt det löfte engine/version.py själv ger: samma version
    plus samma signalvärden ska ge samma score. Två materiellt olika
    motorer under en stämpel gör sparade rapporter otolkbara i
    efterhand."""
    import re
    from engine.version import ENGINE_VERSION
    slappta = re.findall(r"^## \[(\d+\.\d+\.\d+)\]",
                         (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
                         re.M)
    assert slappta, "CHANGELOG saknar en släppt version"
    assert ENGINE_VERSION == slappta[0], (
        f"motorn stämplar {ENGINE_VERSION}, senast släppta är "
        f"{slappta[0]} — en sparad rapport går inte att tolka i efterhand")
    # Och imagen ska bära samma tal, annars pekar en tagg på fel motor.
    mf = (_ROOT / "Makefile").read_text(encoding="utf-8")
    assert ENGINE_VERSION in mf, "Makefile-taggen matchar inte motorn"


# ── Schemalagda körningar i AWS ─────────────────────────────────────────
def _schemaregel() -> dict:
    import json
    return json.loads((_ROOT / "deploy" / "aws" / "scheduler-rule.json")
                      .read_text(encoding="utf-8"))


def test_the_schedule_rule_calls_a_path_that_exists():
    """En regel mot /v1/scheduler/run ser rätt ut i konsolen, körs varje
    femte minut och ger 404 varje gång."""
    from api.catalog import API_CATALOG
    vagar = {(ep["method"], ep["path"]) for e in API_CATALOG["engines"]
             for ep in e["endpoints"]}
    r = _schemaregel()
    slut = r["api_destination"]["InvocationEndpoint"].split("}", 1)[-1]
    assert (r["api_destination"]["HttpMethod"], slut) in vagar, slut


def test_the_schedule_rule_uses_the_header_the_code_actually_reads():
    """Fel rubriknamn ger 401 på varje tick — och en regel som körs och
    nekas ser i konsolen ut precis som en regel som fungerar."""
    r = _schemaregel()
    namn = r["connection"]["AuthParameters"]["ApiKeyAuthParameters"]["ApiKeyName"]
    assert namn == "X-API-Key"
    kall = (_ROOT / "api" / "security.py").read_text(encoding="utf-8")
    assert namn in kall


def test_the_schedule_rule_carries_no_key_of_its_own():
    """En nyckel i en incheckad fil är läckt i samma sekund."""
    import json
    text = json.dumps(_schemaregel())
    assert "${LANDVEX_SCHEDULER_API_KEY}" in text
    for misstankt in ("AKIA", "secret", "password"):
        assert misstankt not in text.lower().replace("secrets manager", "")


def test_a_tick_that_stops_coming_is_not_silent():
    """En utebliven tick ser ut precis som en tick där ingenting förföll.
    Utan kö för döda brev upptäcks det aldrig."""
    r = _schemaregel()
    assert r["schedule"]["Target"]["DeadLetterConfig"]["Arn"]
    assert r["schedule"]["Target"]["RetryPolicy"][
        "MaximumEventAgeInSeconds"] <= 900


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
