"""Är den här miljön redo att ta emot riktig trafik?

    python3 -m scripts.preflight              # rapportera
    python3 -m scripts.preflight --strict     # fäll om något blockerar
    python3 -m scripts.preflight --json       # för en deploy-pipeline
    python3 -m scripts.preflight --gate       # containerns startspärr
    python3 -m scripts.preflight --template   # en komplett .env att fylla i

Kör den i AWS-uppgiften INNAN servern får trafik — som en ECS-container
med `essential: false`, ett CodeBuild-steg, eller första raden i
entrypointen. En checklista i ett dokument läses en gång; en som fäller
bygget läses varje gång.

Vad den kontrollerar, i den ordning som spelar roll:

  1. **Blockerande**   variabler utan vilka systemet startar OSÄKERT
     eller tappar data. Öppet API, eller SQLite bakom två repliker.
  2. **Kombinationer** som är farligare än summan av delarna. Att sakna
     både nycklar och JWT är inte två saknade inställningar — det är ett
     öppet API.
  3. **Lagret**        går det att skriva till på riktigt? En sökväg som
     ser rätt ut men ligger på en read-only mount upptäcks annars av
     första kunden som sparar något.
  4. **Försämringar**  källor som inte är inkopplade. De är inte fel —
     plattformen degraderar ärligt — men skillnaden mellan VALD och
     UPPTÄCKT försämring är hela poängen.

Hemliga värden skrivs aldrig ut. En hemlighet som läckt i en startlogg
är läckt, och en startlogg hamnar i CloudWatch.

`--template` skriver ut en komplett miljöfil, genererad ur samma register
som kontrollen läser. En handskriven .env.example glider ifrån koden inom
ett par veckor och blir då sämre än ingen alls, eftersom man tror på den.

`--gate` är den form containern kör vid start. Vad ett underkänt resultat
KOSTAR bestäms av LANDVEX_PREFLIGHT:

    strict   servern startar inte (rätt i produktion)
    warn     servern startar, skälen ligger överst i loggen (standard)
    off      ingen kontroll alls

    exit 0  redo
    exit 1  blockerande brist (endast med --strict eller --gate + strict)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

from engine.deployment import ENVIRONMENT, ORCHESTRATION, preflight

_W = 76


def _kan_skriva(sokvag: str) -> tuple[bool, str]:
    """Går det att SKRIVA dit, inte bara att sökvägen ser rätt ut?"""
    if not sokvag or sokvag.lower() in ("off", "0"):
        return True, "disabled on purpose"
    katalog = os.path.dirname(os.path.abspath(sokvag)) or "."
    if not os.path.isdir(katalog):
        return False, f"{katalog} does not exist"
    try:
        with tempfile.NamedTemporaryFile(dir=katalog, prefix=".preflight-"):
            pass
    except OSError as e:
        return False, f"{katalog} is not writable: {e.strerror}"
    return True, f"{katalog} is writable"


def _lagerkontroll(env: dict) -> list[dict]:
    kontroller = []
    db = env.get("LANDVEX_DB", "landvex.db")
    ok, varfor = _kan_skriva(db)
    kontroller.append({"check": "LANDVEX_DB", "ok": ok, "detail_en": varfor})
    logg = env.get("LANDVEX_AUDIT_LOG", "landvex-audit.log")
    ok2, varfor2 = _kan_skriva(logg)
    kontroller.append({"check": "LANDVEX_AUDIT_LOG", "ok": ok2,
                       "detail_en": varfor2})
    if env.get("LANDVEX_PG_DSN"):
        # DSN:et prövas INTE här: ett preflight som öppnar en
        # databasanslutning kan hänga i trettio sekunder på en felaktig
        # security group, och då blir hälsokontrollen själv problemet.
        # Formen kontrolleras; anslutningen görs av appen.
        dsn = env["LANDVEX_PG_DSN"]
        ok3 = dsn.startswith(("postgres://", "postgresql://"))
        kontroller.append({
            "check": "LANDVEX_PG_DSN", "ok": ok3,
            "detail_en": ("looks like a PostgreSQL DSN (not connected here "
                          "— a hanging connect would make preflight the "
                          "problem)" if ok3 else
                          "does not start with postgresql:// — check it")})
    return kontroller


def kontrollera(env: dict | None = None) -> dict:
    env = os.environ if env is None else env
    r = preflight(env)
    r["storage"] = _lagerkontroll(env)
    r["storage_ok"] = all(k["ok"] for k in r["storage"])
    r["ready"] = r["ready"] and r["storage_ok"]
    return r


def _rubrik(t: str) -> None:
    print()
    print(t)
    print("─" * min(len(t), _W))


def rapportera(r: dict) -> None:
    c = r["counts"]
    print("═" * _W)
    print("  LANDVEX preflight")
    print("═" * _W)
    print(f"  {c['set']} set · {c['blocking']} blocking · "
          f"{c['degraded']} degraded · {c['warnings']} warning(s)")

    if r["warnings"]:
        _rubrik("Dangerous combinations")
        for w in r["warnings"]:
            print(f"  !! {w['issue_en']}")
            for rad in _bryt(w["detail_en"], 72):
                print(f"     {rad}")

    if r["blocking"]:
        _rubrik("Blocking — set these before taking traffic")
        for b in r["blocking"]:
            print(f"  ✗ {b['name']}")
            for rad in _bryt(b["consequence_en"], 72):
                print(f"     {rad}")
            if b["example"]:
                print(f"     e.g. {b['example']}")

    _rubrik("Storage")
    for k in r["storage"]:
        print(f"  {'ok' if k['ok'] else '✗ '} {k['check']:22s} "
              f"{k['detail_en']}")

    if r["degraded"]:
        _rubrik(f"Running without these ({len(r['degraded'])})")
        for d in r["degraded"]:
            print(f"  ·  {d['name']}")
            for rad in _bryt(d["consequence_en"], 72):
                print(f"     {rad}")

    _rubrik("Set")
    for s in r["set"]:
        print(f"  ·  {s['name']:30s} {s['value'][:40]}")

    print()
    print("─" * _W)
    if r["ready"]:
        print("  Ready. Every degradation above is a CHOICE, not a surprise.")
    else:
        print("  Not ready. See the blocking items above.")
    for rad in _bryt(r["note_en"], 72):
        print(f"  {rad}")
    print()


def _bryt(text: str, bredd: int) -> list[str]:
    ut, rad = [], ""
    for ord_ in text.split():
        if len(rad) + len(ord_) + 1 > bredd:
            ut.append(rad)
            rad = ord_
        else:
            rad = f"{rad} {ord_}".strip()
    if rad:
        ut.append(rad)
    return ut


_TIERTEXT = {
    "required": ("REQUIRED — without these the system starts unsafely or "
                 "loses data"),
    "recommended": ("RECOMMENDED — it runs without them, but worse or less "
                    "honestly"),
    "optional": "OPTIONAL — a connection to something, not a precondition",
}


def mall() -> str:
    """En komplett miljöfil, genererad ur registret.

    Genererad, inte skriven: en handskriven .env.example glider ifrån
    koden och blir då sämre än ingen alls, eftersom man tror på den.
    """
    rader = [
        "# LANDVEX Opportunity Engine — environment.",
        "# Generated by `python3 -m scripts.preflight --template`.",
        "# Every line below comes from engine/deployment.ENVIRONMENT, which",
        "# a test holds against what the code actually reads.",
        "#",
        "# Secrets are left EMPTY on purpose. Keep them in a secret store",
        "# (AWS Secrets Manager) and inject them as `secrets` in the task",
        "# definition — a value in a file gets committed sooner or later.",
    ]
    def _avsnitt(rubrik: str, register: dict, namn: list[str]) -> None:
        rader.extend(["", "# " + "─" * 68, f"# {rubrik}", "# " + "─" * 68])
        for k in namn:
            v = register[k]
            rader.append("")
            for rad in _bryt(v["purpose_en"], 68):
                rader.append(f"# {rad}")
            for rad in _bryt("If unset: " + v["if_unset_en"], 68):
                rader.append(f"#   {rad}")
            if v["secret"]:
                rader.append("#   SECRET — inject from a secret store.")
                rader.append(f"{k}=")
            else:
                rader.append(f"{k}={v['example']}")

    for niva in ("required", "recommended", "optional"):
        namn = [k for k, v in sorted(ENVIRONMENT.items())
                if v["tier"] == niva]
        if namn:
            _avsnitt(_TIERTEXT[niva], ENVIRONMENT, namn)

    # Läses av det som STARTAR appen, aldrig av appen. Preflight kan inte
    # uttala sig om dem — processen ser dem inte — men de måste stå här,
    # annars tappas de tyst när mallen genereras.
    _avsnitt("NOT READ BY THE APPLICATION — docker-compose reads these",
             ORCHESTRATION, sorted(ORCHESTRATION))
    return "\n".join(rader) + "\n"


def _lage(env: dict) -> str:
    lage = str(env.get("LANDVEX_PREFLIGHT", "") or "warn").strip().lower()
    return lage if lage in ("strict", "warn", "off") else "warn"


def main(argv: list[str]) -> int:
    if "--template" in argv:
        print(mall(), end="")
        return 0

    lage = _lage(os.environ)
    if "--gate" in argv and lage == "off":
        print("preflight: skipped (LANDVEX_PREFLIGHT=off)")
        return 0

    r = kontrollera()
    if "--json" in argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        rapportera(r)

    if r["ready"]:
        return 0
    if "--strict" in argv:
        return 1
    if "--gate" in argv and lage == "strict":
        print("  LANDVEX_PREFLIGHT=strict — refusing to serve traffic.")
        return 1
    if "--gate" in argv:
        print("  LANDVEX_PREFLIGHT=warn — starting anyway. Set 'strict' in "
              "production so a misconfigured task never reaches the load "
              "balancer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
