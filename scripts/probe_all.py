"""Kör varje probe, och skilj ett spärrat nät från en trasig adapter.

    python3 -m scripts.probe_all              # alla prober
    python3 -m scripts.probe_all --json       # för en pipeline
    python3 -m scripts.probe_all --only sensor,register
    python3 -m scripts.probe_all --timeout 90

Det här är kommandot att köra FÖRST i en miljö med öppet nät. Det svarar
på den enda fråga som skiljer arkitektur från intelligens: **vilka källor
svarade faktiskt?**

Varför den finns:

  1. Det var tio kommandon. Tio kommandon körs inte, eller körs delvis,
     och då är svaret på frågan ovan "vet inte" — vilket ser ut som "nej"
     i alla dokument som citerar det.

  2. Åtta av tio prober har bara exitkoderna 0 och 1. Där betyder 1 både
     "kom aldrig fram" och "svarade fel", och den skillnaden är hela
     poängen. En gång skrevs en spärrad brandvägg ner som en trasig
     adapter, och någon letade efter felet i koden i stället för i
     nätverkspolicyn. Den här filen klassar därför på FELTEXTEN, inte
     bara på koden, och säger hellre `unclear` än gissar `broken`.

  3. Ett `verified_live = True` får bara sättas för en källa som svarat.
     Rapporten skriver ut exakt vilka rader som ska ändras — file:line —
     och inga andra. En bock satt på känsla är värre än ingen bock.

Verdikt:

    answered        svarade, och svaret såg ut som dokumentationen
    wrong_shape     kom fram, men formen stämde inte — ADAPTERFEL
    empty           svarade utan träffar (giltigt: kan vara rätt svar)
    blocked         kom aldrig fram: policy, DNS, proxy — INTE adapterfel
    not_configured  ingen URL/nyckel satt; ingenting anropades
    our_bug         proben kraschade på VÅR kod — högsta prioritet
    unclear         gick inte att avgöra. Sägs rakt ut i stället för gissas

Exit 0 om ingenting är trasigt på vår sida. Exit 1 om någon probe föll på
vår egen kod. Ett spärrat nät är INTE ett fel här — det är ett svar.

Rent stdlib.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_W = 78

# Feltexter som betyder "kom aldrig fram". Ingen av dem säger något om
# adapterns kvalitet, och att låta dem räknas som adapterfel är precis
# den förväxling den här filen finns för att förhindra.
_SPARRAT = (
    # Frasen proberna själva skriver när de klassat felet som onåbart.
    "never got there",
    "403", "connect tunnel failed", "proxy", "connect_rejected",
    "connectionrefusederror", "connectionreseterror",
    "policy denial", "name or service not known",
    "temporary failure in name resolution", "network is unreachable",
    "no route to host", "connection refused", "certificate verify failed",
    "timed out", "timeout", "unreachable",
)

# Undantag som betyder att VI har skrivit fel, inte att motparten svarat
# konstigt. Samma lista som engine/datasources/faults.OUR_BUGS.
_VARA_BUGGAR = ("AttributeError", "NameError", "ImportError",
                "SyntaxError", "IndentationError", "TypeError")

_EJ_KONFIGURERAD = ("not configured", "inte konfigurerad", "unset",
                    "not set", "no url", "saknar url", "ingen url")

# Proben avslutade med 0 men provade ingenting. Det är INTE ett svar från
# en källa, och att räkna det som ett vore att bocka av en verifiering
# som aldrig skett. `livability_probe` gör exakt detta: exit 0 med
# "nothing to probe" i utdatan.
_INGENTING_PROVAT = ("nothing to probe", "dry run", "inget att prova")

# Meningar där proben SJÄLV säger att den inte kan avgöra vad som hände.
# De måste läsas före mönstren nedan: `register_probe` skriver
# "unreachable, path wrong, or the response shape differs", och att
# plocka ordet "unreachable" ur den meningen och kalla det ett verdikt
# är att låta en brasklapp se ut som ett mätvärde. Det var det här
# felet den här filen skrevs för att förhindra — och det uppstod i den
# på första körningen.
_UTTALAD_OSAKERHET = (
    "or the response shape differs",
    "nothing was invented",
    "could not tell",
    "går inte att avgöra",
)


def _prober() -> list[dict]:
    """Vad som ska köras. Sensorklasserna hämtas ur registret, så en ny
    klass provas automatiskt i stället för att glömmas bort här."""
    from engine.datasources.sensor_apis import PROVIDERS

    ut: list[dict] = []
    for klass in sorted(PROVIDERS):
        ut.append({
            "id": f"sensor:{klass}",
            "group": "sensor",
            "argv": ["scripts.sensor_probe", klass],
            "proves_en": f"sensor class {klass}",
            "classes": [c.__name__ for c in PROVIDERS[klass]],
            "rich_codes": True})

    # Ett land per registerimplementation — inte alla 16, eftersom de
    # delar klient och en fjärde PxWeb-träff inte bevisar något nytt.
    # Yrkesorden är svenska internt (`industry_code`). Att skicka
    # "electrician" gav "no industry code mapped", vilket min första
    # version läste som ett ADAPTERFEL — det var ett anropsfel.
    # Regionerna är probens egna dokumenterade exempel.
    for land, region, yrke, vad in (
            ("se", "0138", "elektriker", "PxWeb (SCB)"),
            ("us", "06037", "elektriker", "Census CBP"),
            ("de", "DE300", "elektriker", "Eurostat")):
        ut.append({
            "id": f"register:{land}",
            "group": "register",
            "argv": ["scripts.register_probe", land, region, yrke],
            "proves_en": f"business register via {vad}",
            "classes": [f"register:{vad}"],
            "rich_codes": True})

    for namn, argv, vad in (
            ("scb", ["scripts.scb_probe"], "SCB population/income/density"),
            ("kolada", ["scripts.kolada_probe"], "Kolada municipal KPIs"),
            ("svk", ["scripts.svk_probe"], "Svenska kraftnät grid telemetry"),
            ("livability", ["scripts.livability_probe", "0138"],
             "livability signals"),
            ("permits", ["scripts.permits_probe"], "building permits"),
            ("places", ["scripts.places_probe"], "places / competition"),
            ("programs", ["scripts.programs_probe"], "support programmes"),
            ("quixzoom", ["scripts.quixzoom_probe"], "quiXzoom observations"),
            ("aamos", ["scripts.aamos_smoke"], "AAMOS platform")):
        ut.append({"id": namn, "group": "source", "argv": argv,
                   "proves_en": vad, "classes": [], "rich_codes": False})
    return ut


def bedom(kod: int, utdata: str, rich_codes: bool) -> tuple[str, str]:
    """Verdikt + skäl. Feltexten går före exitkoden, eftersom åtta av tio
    prober inte har en kod för 'kom aldrig fram'."""
    låg = utdata.lower()

    if "traceback" in låg:
        for bugg in _VARA_BUGGAR:
            if bugg.lower() in låg:
                return "our_bug", f"proben kraschade på {bugg}"
        return "our_bug", "proben kraschade med en traceback"

    if "no industry code mapped" in låg:
        return "bad_args", ("yrket är inte mappat för landet — vårt "
                            "anropsfel, inte adapterns")

    if any(m in låg for m in _EJ_KONFIGURERAD):
        return "not_configured", "ingen URL eller nyckel satt"

    if any(m in låg for m in _INGENTING_PROVAT):
        return "nothing_probed", ("proben avslutade med 0 utan att prova "
                                  "något — inte ett svar från en källa")

    # Före mönsterletandet: säger proben själv att den inte vet?
    träff = next((m for m in _UTTALAD_OSAKERHET if m in låg), None)
    if träff:
        return "unclear", ("proben kan inte skilja spärrat nät från fel "
                           "sökväg eller ändrad form — den säger det själv")

    träff = next((m for m in _SPARRAT if m in låg), None)
    if träff:
        return "blocked", f"nätet stoppade anropet ({träff})"

    if kod == 0:
        return "answered", "svarade, och formen stämde"
    if kod == 3:
        return "blocked", "proben rapporterade: kom aldrig fram"
    if kod == 2:
        return "empty", "svarade utan träffar"
    if kod == 64:
        return "unclear", "felaktiga argument till proben — vårt fel"
    if kod == 1 and rich_codes:
        return "wrong_shape", "kom fram, men svaret matchade inte formen"
    if kod == 1:
        # Just den här tvetydigheten är skälet till filen. Utan en
        # feltext som pekar åt något håll är 1 inte tolkningsbart, och
        # att kalla det 'trasig adapter' vore att hitta på.
        return "unclear", ("exit 1 utan feltext: proben skiljer inte "
                           "spärrat från trasigt")
    return "unclear", f"okänd exitkod {kod}"


def _verified_rader() -> dict[str, str]:
    """Var står `verified_live` för varje klass? file:line, så att en
    bock kan sättas på rätt rad utan att någon letar."""
    ut: dict[str, str] = {}
    p = _ROOT / "engine" / "datasources" / "sensor_apis.py"
    nuvarande = None
    for i, rad in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
        m = re.match(r"class\s+(\w+)", rad)
        if m:
            nuvarande = m.group(1)
        elif "verified_live" in rad and "=" in rad and nuvarande:
            ut[nuvarande] = f"engine/datasources/sensor_apis.py:{i}"
    q = _ROOT / "engine" / "datasources" / "register_apis.py"
    for i, rad in enumerate(q.read_text(encoding="utf-8").split("\n"), 1):
        if '"verified_live"' in rad:
            ut.setdefault("register", f"engine/datasources/register_apis.py:{i}")
    return ut


def kor(timeout: float, bara: set[str] | None) -> list[dict]:
    resultat = []
    for p in _prober():
        if bara and p["group"] not in bara and p["id"] not in bara:
            continue
        print(f"  … {p['id']}", end="", flush=True)
        try:
            r = subprocess.run([sys.executable, "-m", *p["argv"]],
                               cwd=_ROOT, capture_output=True, text=True,
                               timeout=timeout)
            kod, utdata = r.returncode, (r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            kod, utdata = 3, "timed out"
        verdikt, skal = bedom(kod, utdata, p["rich_codes"])
        print(f"\r  {verdikt:15s} {p['id']}")
        resultat.append({**{k: v for k, v in p.items() if k != "argv"},
                         "cmd": "python3 -m " + " ".join(p["argv"]),
                         "exit": kod, "verdict": verdikt, "why": skal,
                         "tail": utdata.strip().split("\n")[-1][:160]})
    return resultat


def rapport(resultat: list[dict]) -> dict:
    per = {}
    for r in resultat:
        per[r["verdict"]] = per.get(r["verdict"], 0) + 1
    rader = _verified_rader()
    att_bocka = []
    for r in resultat:
        if r["verdict"] != "answered":
            continue
        for k in r["classes"] or []:
            att_bocka.append({"class": k,
                              "at": rader.get(k, rader.get("register", "?")),
                              "proved_by": r["cmd"]})
    return {
        "results": resultat, "counts": per,
        "set_verified_live": att_bocka,
        "our_bugs": [r["id"] for r in resultat if r["verdict"] == "our_bug"],
        "blocked": [r["id"] for r in resultat if r["verdict"] == "blocked"],
        "note_en": (
            "A blocked network is an answer, not a failure: it says nothing "
            "about the adapter. Only 'wrong_shape' and 'our_bug' are defects "
            "on our side. Set verified_live = True for the classes listed "
            "under set_verified_live and for no others — a tick set on a "
            "feeling is worse than no tick."),
    }


def skriv(r: dict) -> None:
    print()
    print("═" * _W)
    print("  Probe sweep — which sources actually answered")
    print("═" * _W)
    c = r["counts"]
    print("  " + " · ".join(f"{v} {k}" for k, v in sorted(c.items())))

    if r["our_bugs"]:
        print()
        print("  VÅRA BUGGAR — högsta prioritet, ingenting annat räknas "
              "förrän dessa är lösta:")
        for x in r["our_bugs"]:
            rad = next(y for y in r["results"] if y["id"] == x)
            print(f"    ✗ {x}: {rad['why']}")
            print(f"      {rad['tail']}")

    print()
    print("  " + "─" * (_W - 4))
    for x in r["results"]:
        mark = {"answered": "ok", "wrong_shape": "✗ ", "our_bug": "!!",
                "blocked": "··", "not_configured": "  ",
                "empty": "  ", "unclear": "? "}.get(x["verdict"], "  ")
        print(f"  {mark} {x['id']:22s} {x['verdict']:15s} {x['why']}")

    if r["set_verified_live"]:
        print()
        print("  Sätt verified_live = True HÄR, och ingen annanstans:")
        for x in r["set_verified_live"]:
            print(f"    {x['class']:22s} {x['at']}")
            print(f"      bevisad av: {x['proved_by']}")
    else:
        print()
        print("  Ingenting att bocka av. Ingen källa svarade — så ingen "
              "källa är verifierad.")

    if r["blocked"]:
        print()
        print(f"  {len(r['blocked'])} probe(r) kom aldrig fram. Det säger "
              f"ingenting om adaptrarna.")
        print("  Kontrollera nätverkspolicyn, inte koden: "
              "python3 -m scripts.preflight --egress")
    print()


def main(argv: list[str]) -> int:
    timeout = 60.0
    if "--timeout" in argv:
        timeout = float(argv[argv.index("--timeout") + 1])
    bara = None
    if "--only" in argv:
        bara = set(argv[argv.index("--only") + 1].split(","))

    resultat = kor(timeout, bara)
    r = rapport(resultat)
    if "--json" in argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        skriv(r)
    return 1 if r["our_bugs"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
