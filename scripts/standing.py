"""Var vi står, och vad som kommer härnäst — mätt, inte nedskrivet.

    python3 -m scripts.standing            # läsbar rapport
    python3 -m scripts.standing --md       # markdown att klistra in
    python3 -m scripts.standing --json     # för en pipeline

Den här filen finns för att ett lägesdokument åldras i tysthet. Siffror
skrivna för hand var sanna den dag någon skrev dem, och blir felaktiga
utan att någon märker det — och en läsare som upptäcker EN fel siffra
slutar tro på hela sidan.

Därför mäts allt i avsnitt 1 och 2 ur koden vid körning:

  * antal marknader, regioner, beslut, sensorklasser, källor
  * vilka beslut som är BYGGDA och vilka som bara är planerade
  * vilka sensorklasser som saknar adapter
  * vilka klasser som bara har EN leverantör och därför aldrig kan
    bekräftas av ett oberoende nät
  * vilka källor som är LIVEVERIFIERADE (härifrån: noll — nätet är
    stängt, och att skriva något annat vore att hitta på)
  * om den här miljön skulle klara startspärren

Planen i avsnitt 3 är däremot ett mänskligt beslut och står som data i
den här filen. Varje post bär ett `done_when` som läser samma mätning:
en punkt som blivit klar markeras ✓ och räknas bort automatiskt. Planen
kan alltså inte påstå att något återstår som redan är gjort.

Avsnitt 4 är det jag INTE kan veta: konkurrentbilden kommer ur analys,
inte ur en mätning, och den ska verifieras där nätet är öppet.

Rent stdlib. Körs från repots rot.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_W = 78


# ── 1. Mätningen ────────────────────────────────────────────────────────
def matning() -> dict:
    """Allt som går att räkna fram ur koden. Inga handskrivna tal."""
    from engine import offering, sensors, surface
    from engine.datasources import register_apis, sensor_apis
    from engine.deployment import preflight
    from engine.markets import MARKETS

    beslut = list(offering.DECISIONS)
    byggda = [d for d in beslut if d.get("status") == "built"]
    planerade = [d for d in beslut if d.get("status") != "built"]

    s = sensors.catalog()
    lagen = s.get("by_state", {})
    utan_adapter = sorted(k for k, v in sensors.SENSORS.items()
                          if getattr(v, "state", None) != "adapter"
                          and not isinstance(v, dict))
    if not utan_adapter:                      # SENSORS kan bära dict-rader
        utan_adapter = sorted(k for k, v in sensors.SENSORS.items()
                              if (v.get("state") if isinstance(v, dict)
                                  else getattr(v, "state", "")) != "adapter")

    leverantorer = {k: [c.__name__ for c in grupp]
                    for k, grupp in sensor_apis.PROVIDERS.items()}

    def _lage(k: str) -> str:
        v = sensors.SENSORS[k]
        return v.get("state") if isinstance(v, dict) else getattr(v, "state", "")

    # Bara klasser vi FAKTISKT kan läsa räknas här. En klass utan adapter
    # saknar inte ett andra nät — den saknar det första, och det är en
    # annan lucka som redovisas för sig.
    ensamma = sorted(k for k, v in leverantorer.items()
                     if len(v) < 2 and _lage(k) == "adapter")

    # Verifierade källor: läses ur klasserna och ur registerkatalogen,
    # aldrig ur en förhoppning. Sensorklienterna bär `verified_live` som
    # klassattribut, registerklasserna som fält i sin katalograd — båda
    # räknas, annars ser bilden bättre ut än den är.
    kallor: dict[str, bool] = {}
    for grupp in sensor_apis.PROVIDERS.values():
        for c in grupp:
            kallor[c.__name__] = bool(getattr(c, "verified_live", False))
    for rad in register_apis.providers_status().get("providers", []):
        kallor[f"register:{rad['id']}"] = bool(rad.get("verified_live"))
    verifierade = sorted(k for k, v in kallor.items() if v)
    overifierade = sorted(k for k, v in kallor.items() if not v)

    regioner = 0
    for m in MARKETS.values():
        r = (m.get("regions") if isinstance(m, dict)
             else getattr(m, "regions", None)) or []
        regioner += len(r)

    rutter = sorted(set(re.findall(
        r'@app\.(?:get|post|put|delete|patch)\(\s*["\']([^"\']+)',
        (_ROOT / "api" / "main.py").read_text(encoding="utf-8"))))

    pf = preflight(os.environ)
    from scripts.preflight import utgaende

    return {
        "markets": len(MARKETS),
        "regions": regioner,
        "promises": [p["id"] for p in surface.PROMISES],
        "decisions_total": len(beslut),
        "decisions_built": [d["id"] for d in byggda],
        "decisions_planned": [{"id": d["id"], "question_en": d["question_en"],
                               "plan": d.get("plan")} for d in planerade],
        "sensor_classes": len(sensors.SENSORS),
        "sensor_states": lagen,
        "sensor_classes_without_adapter": utan_adapter,
        "sensor_providers": leverantorer,
        "classes_with_one_provider": ensamma,
        "sources_verified": len(verifierade),
        "sources_verified_names": verifierade,
        "sources_unverified": len(overifierade),
        "register_countries": len(getattr(register_apis, "PROVIDER_FOR", {})),
        "endpoints": len(rutter),
        "engine_modules": len(list((_ROOT / "engine").glob("*.py"))),
        "test_suites": len(list((_ROOT / "tests").glob("test_*.py"))),
        "preflight_ready": pf["ready"],
        "preflight_counts": pf["counts"],
        "egress_hosts": len(utgaende(os.environ)),
    }


# ── 2. Luckorna, härledda ur mätningen ──────────────────────────────────
def luckor(m: dict) -> list[dict]:
    """Vad som saknas — räknat fram, inte ihågkommet."""
    ut = []
    if m["sources_verified"] == 0:
        ut.append({
            "id": "no_verified_source",
            "severity": "blocking",
            "what_en": f"{m['sources_unverified']} source clients, not one "
                       f"verified against a live endpoint.",
            "means_en": "Until a probe has received a byte from the real "
                        "host, this is architecture, not intelligence. It "
                        "is the first thing a buyer asks about."})
    if m["decisions_planned"]:
        ut.append({
            "id": "decisions_not_built",
            "severity": "gap",
            "what_en": ", ".join(d["id"] for d in m["decisions_planned"]),
            "means_en": "Sold surface that does not exist yet. Every one of "
                        "these is a routine enterprise objection."})
    if m["classes_with_one_provider"]:
        ut.append({
            "id": "no_second_network",
            "severity": "gap",
            "what_en": ", ".join(m["classes_with_one_provider"]),
            "means_en": "A single network can never corroborate itself. "
                        "These classes are capped at the 'weak' band by "
                        "design, whatever they measure."})
    if m["sensor_classes_without_adapter"]:
        ut.append({
            "id": "classes_without_adapter",
            "severity": "gap",
            "what_en": ", ".join(m["sensor_classes_without_adapter"]),
            "means_en": "Described in the catalogue, not readable. Honest "
                        "as long as the state says so — and it does."})
    if not m["preflight_ready"]:
        c = m["preflight_counts"]
        ut.append({
            "id": "environment_not_ready",
            "severity": "info",
            "what_en": f"{c['blocking']} blocking, {c['warnings']} warning(s) "
                       f"in THIS environment.",
            "means_en": "Expected on a build machine. Run "
                        "`make preflight` where it should be ready."})
    return ut


# ── 3. Planen (mänskligt beslut, med automatisk avräkning) ──────────────
def _har_beslut(m: dict, id_: str) -> bool:
    return id_ in m["decisions_built"]


PLAN: tuple[dict, ...] = (
    # ── Nivå 1: gör produkten säljbar ────────────────────────────────
    {"id": "verify_live_sources", "tier": 1,
     "what_en": "Run `make probe` where egress is open. It reports one "
                "verdict per source and prints the exact file:line to flip "
                "for those that answered — and for no others.",
     "why_en": "It is the difference between a working machine and proven "
               "intelligence, and it is the first question every buyer "
               "asks.",
     "blocked_by_en": "needs a network that allows outbound HTTPS — nothing "
                      "else",
     "market_en": "Placer, Advan and Dewey sell verified data as the entire "
                  "product. We cannot claim the ground until we stand on it.",
     "done_when": lambda m: m["sources_verified"] > 0},

    {"id": "export_findings", "tier": 1,
     "what_en": "Build the planned export decision: CSV/Parquet out, and an "
                "API path a customer's own tools can pull.",
     "why_en": "The single most common enterprise objection in this "
               "category. Small work, disproportionate effect.",
     "blocked_by_en": "nothing",
     "market_en": "Esri, Buxton and Palantir all assume the data leaves "
                  "into Power BI, Tableau or Snowflake.",
     "done_when": lambda m: _har_beslut(m, "export_findings")},

    {"id": "scheduled_runs", "tier": 1,
     "what_en": "Let the monitors wake themselves — EventBridge (or cron) "
                "against /v1/monitors/run.",
     "why_en": "A monitoring product that cannot wake up is a report. The "
               "engine already does everything except the trigger.",
     "blocked_by_en": "nothing",
     "market_en": "Zencity and StreetLight are bought for the schedule as "
                  "much as for the analysis.",
     "done_when": lambda m: _har_beslut(m, "scheduled_runs")},

    {"id": "coverage_surface", "tier": 1,
     "what_en": "A public surface that states what we can and cannot answer "
                "in a given place, built from the source and sensor state "
                "we already compute.",
     "why_en": "No competitor publishes theirs. That is exactly why it "
               "sells — and the data behind it already exists.",
     "blocked_by_en": "nothing",
     "market_en": "The whole alt-data segment hides single-sourcing. "
                  "Publishing coverage is a wedge, not a weakness.",
     "done_when": None},

    # ── Nivå 2: bygger vallgraven ────────────────────────────────────
    {"id": "quixzoom_vision", "tier": 2,
     "what_en": "Wire the Vision step that reads submitted quiXzoom media "
                "into observed development m² for the Contradiction Index.",
     "why_en": "The only genuinely proprietary source within reach — human "
               "ground truth. Everything else we read is open data anyone "
               "can replicate in a month.",
     "blocked_by_en": "needs the media schema from the quiXzoom side",
     "market_en": "Nobody in segments A–E has field observation. This is "
                  "where a moat can exist at all.",
     "done_when": None},

    {"id": "second_provider_per_class", "tier": 2,
     "what_en": "Give the single-provider sensor classes a second, "
                "independent network.",
     "why_en": "Each added independent modality raises the corroboration "
               "band measurably — a number we can sell, computed by the "
               "engine rather than asserted.",
     "blocked_by_en": "nothing (open APIs exist for most of them)",
     "market_en": "Corroboration is the one claim competitors structurally "
                  "cannot make: their business rests on always producing a "
                  "figure.",
     "done_when": lambda m: not m["classes_with_one_provider"]},

    {"id": "geospatial_depth", "tier": 2,
     "what_en": "PostGIS in earnest: isochrones, drive-time bands, "
                "catchment modelling.",
     "why_en": "The entry ticket to site selection. Without trade areas we "
               "are not in that conversation at all.",
     "blocked_by_en": "Aurora + PostGIS (already the planned store)",
     "market_en": "Esri Business Analyst, Kalibrate and Sitewise compete on "
                  "exactly this.",
     "done_when": None},

    {"id": "calibration_at_scale", "tier": 2,
     "what_en": "Record outcomes until the Brier score means something, and "
                "publish the accuracy record.",
     "why_en": "An honest track record takes calendar time for everyone, "
               "including Palantir. Started late it stays late.",
     "blocked_by_en": "needs real decisions with real outcomes — customers, "
                      "not code",
     "market_en": "Competitors show case studies. Nobody shows a calibration "
                  "curve.",
     "done_when": None},

    {"id": "gtfs_realtime", "tier": 2,
     "what_en": "Public transport in real time (GTFS-RT).",
     "why_en": "Closes the last unbuilt sensor class and adds a second "
               "independent network to several detections.",
     "blocked_by_en": "YOUR DECISION: protobuf breaks the dependency-free "
                      "core. Either accept one dependency, or write a "
                      "minimal decoder for the handful of fields we read.",
     "market_en": "Transit feeds are open; the work is the format, not the "
                  "access.",
     "done_when": None},

    # ── Nivå 3: strategiskt ──────────────────────────────────────────
    {"id": "compliance_pack", "tier": 3,
     "what_en": "SOC 2 path, DPA, processing register, a model card per "
                "engine.",
     "why_en": "EU public sector asks this before it asks what the product "
               "does.",
     "blocked_by_en": "organisational, not technical",
     "market_en": "It is how Tyler and OpenGov hold municipal accounts.",
     "done_when": None},

    {"id": "white_label", "tier": 3,
     "what_en": "Reports under the customer's own brand.",
     "why_en": "The consultancy channel (Sweco, WSP, Ramboll and their "
               "equivalents) resells or it does not carry us.",
     "blocked_by_en": "nothing",
     "market_en": "Consultancies sell the same answers as a service today.",
     "done_when": lambda m: _har_beslut(m, "white_label")},

    {"id": "own_dashboards", "tier": 3,
     "what_en": "Let customers build their own views on the engine.",
     "why_en": "Turns a report into a platform, and moves the renewal "
                "conversation.",
     "blocked_by_en": "nothing",
     "market_en": "Expected by anyone who has used Foundry or a BI tool.",
     "done_when": lambda m: _har_beslut(m, "own_dashboards")},

    {"id": "partner_modality", "tier": 3,
     "what_en": "A second proprietary stream through partners — building "
                "meters, district heating, water.",
     "why_en": "The adapter exists; what is missing is one owner willing to "
               "share a feed.",
     "blocked_by_en": "a partner agreement",
     "market_en": "Utility telemetry is closed to everyone, which is "
                  "precisely what makes it worth having.",
     "done_when": None},
)

POSITION_EN = (
    "Do not fight the footfall vendors on footfall — that is lost by "
    "definition, and our own corroboration doctrine forces us to say so. "
    "Position as the layer that decides whether the data you already "
    "bought can be trusted: corroboration, refusal and accountability on "
    "top of any input. It is complementary rather than competitive to the "
    "data vendors, it is what procurement and auditors actually ask for, "
    "and it is the one thing a competitor cannot copy without giving up "
    "their own business model — because theirs rests on always producing "
    "a number."
)

INTE_MATBART_EN = (
    "Everything in `market_en` and in the positioning above comes from "
    "analysis, not from a measurement, and was written without network "
    "access (outbound HTTPS is policy-blocked in the build environment). "
    "Competitor names and positioning are stable; pricing, exact features "
    "and ownership may have moved. Verify where the network is open "
    "before quoting any of it to a customer."
)


ARBETSSATT = """\
Kör alltid detta först, i den här ordningen:

```bash
python3 -m scripts.standing     # den här bilden, mätt på nytt
make test                       # alla sviter, utan pytest och utan nät
make preflight                  # klarar den här miljön riktig trafik?
make probe                      # vilka källor svarar? (kräver öppet nät)
```

Ta den ÖVERSTA öppna punkten på nivå 1. Är den blockerad av nätet
(`verify_live_sources`), gå vidare till nästa — blockeringen är
miljöns, inte kodens.

Regler som gäller i det här bygget och som inte får förhandlas bort:

* **Ärlighet före täckning.** En källa som inte svarat är `mock` och
  märks `mock`. `data_coverage` får aldrig skrivas upp. Motorn hellre
  avstår än gissar, och `cannot_en`/`never_en` står i svaret.
* **Bevisa före du fixar.** Varje påstående om ett fel ska ha en
  körning bakom sig. Varje fix ska ha ett test som faller utan den.
* **Aldrig förfalska en AAMOS-token.** Rätt åtgärd är ett riktigt
  tjänstekonto från AAMOS admin.
* **Checka aldrig in `.env` eller hemligheter.**
  `engine/datasources/verified.json` är miljöspecifik och gitignorerad —
  committa den aldrig som allmän sanning.
* **Två API-lager, ett kontrakt.** Ändrar du `api/main.py` ska
  `api/dev_server.py` följa med; `tests/test_contract.py` låser dem lika.
* **Sensorkatalogen ska stämma med terrängen.** En klass utan publikt
  API är `contract`, inte `adapter`.

När arbetet är klart: `make test`, `ruff check .`, uppdatera
`CHANGELOG.md`, commit och push till `claude/new-session-d9t6ni`.
"""


def plan(m: dict) -> list[dict]:
    ut = []
    for p in PLAN:
        klar = None
        if p["done_when"] is not None:
            try:
                klar = bool(p["done_when"](m))
            except Exception:      # en trasig kontroll får inte fälla lägesbilden
                klar = None
        ut.append({k: v for k, v in p.items() if k != "done_when"}
                  | {"done": klar})
    return ut


def rapport() -> dict:
    m = matning()
    p = plan(m)
    return {
        "measured": m,
        "gaps": luckor(m),
        "plan": p,
        "plan_open": [x["id"] for x in p if x["done"] is not True],
        "position_en": POSITION_EN,
        "not_measurable_en": INTE_MATBART_EN,
    }


# ── Utskrift ────────────────────────────────────────────────────────────
def _bryt(text: str, bredd: int) -> list[str]:
    ut, rad = [], ""
    for ord_ in str(text).split():
        if len(rad) + len(ord_) + 1 > bredd:
            ut.append(rad)
            rad = ord_
        else:
            rad = f"{rad} {ord_}".strip()
    if rad:
        ut.append(rad)
    return ut


def _rubrik(t: str) -> None:
    print()
    print(t)
    print("─" * min(len(t), _W))


def skriv(r: dict) -> None:
    m = r["measured"]
    print("═" * _W)
    print("  LANDVEX — where we stand, and what comes next")
    print("═" * _W)
    print("  Measured from the code at run time. Nothing here is "
          "transcribed.")

    _rubrik("Built")
    print(f"  {m['markets']} markets · {m['regions']} regions · "
          f"{m['endpoints']} endpoints · {m['engine_modules']} engine modules")
    print(f"  {len(m['decisions_built'])}/{m['decisions_total']} decisions "
          f"built · {len(m['promises'])} promises · "
          f"{m['test_suites']} test suites")
    print(f"  {m['sensor_classes']} sensor classes " +
          " · ".join(f"{v} {k}" for k, v in m["sensor_states"].items()))
    print(f"  {m['register_countries']} countries mapped to a business "
          f"register")
    print(f"  sources verified live: {m['sources_verified']} of "
          f"{m['sources_verified'] + m['sources_unverified']}")
    print(f"  this environment: preflight "
          f"{'READY' if m['preflight_ready'] else 'not ready'} · "
          f"{m['egress_hosts']} egress host(s) configured")

    _rubrik("Gaps (derived, not remembered)")
    for g in r["gaps"]:
        print(f"  [{g['severity']}] {g['what_en']}")
        for rad in _bryt(g["means_en"], 70):
            print(f"      {rad}")

    for niva in (1, 2, 3):
        poster = [p for p in r["plan"] if p["tier"] == niva]
        namn = {1: "Tier 1 — makes the product sellable",
                2: "Tier 2 — builds the moat",
                3: "Tier 3 — strategic"}[niva]
        _rubrik(namn)
        for p in poster:
            mark = "✓" if p["done"] is True else ("·" if p["done"] is None
                                                  else "○")
            print(f"  {mark} {p['id']}"
                  + ("   (done)" if p["done"] is True else ""))
            if p["done"] is True:
                continue
            for rad in _bryt(p["what_en"], 70):
                print(f"      {rad}")
            for rad in _bryt("Why: " + p["why_en"], 70):
                print(f"      {rad}")
            if p["blocked_by_en"] != "nothing":
                for rad in _bryt("Blocked by: " + p["blocked_by_en"], 70):
                    print(f"      {rad}")

    _rubrik("Positioning")
    for rad in _bryt(r["position_en"], 74):
        print(f"  {rad}")

    _rubrik("What this file cannot measure")
    for rad in _bryt(r["not_measurable_en"], 74):
        print(f"  {rad}")

    print()
    print("─" * _W)
    oppna = len(r["plan_open"])
    print(f"  {len(r['plan']) - oppna} of {len(r['plan'])} plan items closed "
          f"· {oppna} open · {len(r['gaps'])} gap(s)")
    print("  A closed item disappears from this list by itself. If it is "
          "still here, it is still open.")
    print()


def markdown(r: dict) -> str:
    m = r["measured"]
    u = ["# LANDVEX — nuläge och fortsatt plan", "",
         "_Genererad av `python3 -m scripts.standing --md`. Siffrorna är "
         "mätta ur koden vid körning._", "",
         "## Byggt", "",
         f"- {m['markets']} marknader, {m['regions']} regioner, "
         f"{m['endpoints']} endpoints, {m['engine_modules']} motormoduler",
         f"- {len(m['decisions_built'])} av {m['decisions_total']} beslut "
         f"byggda, {len(m['promises'])} löften, {m['test_suites']} testsviter",
         f"- {m['sensor_classes']} sensorklasser: " +
         ", ".join(f"{v} {k}" for k, v in m["sensor_states"].items()),
         f"- {m['register_countries']} länder mappade till företagsregister",
         f"- **Liveverifierade källor: {m['sources_verified']} av "
         f"{m['sources_verified'] + m['sources_unverified']}**", "",
         "## Luckor", ""]
    for g in r["gaps"]:
        u.append(f"- **{g['severity']}** — {g['what_en']} {g['means_en']}")
    for niva, namn in ((1, "Nivå 1 — gör produkten säljbar"),
                       (2, "Nivå 2 — bygger vallgraven"),
                       (3, "Nivå 3 — strategiskt")):
        u += ["", f"## {namn}", ""]
        for p in [x for x in r["plan"] if x["tier"] == niva]:
            if p["done"] is True:
                u.append(f"- ~~{p['id']}~~ (klart)")
                continue
            u.append(f"- **{p['id']}** — {p['what_en']}")
            u.append(f"  - Varför: {p['why_en']}")
            if p["blocked_by_en"] != "nothing":
                u.append(f"  - Blockeras av: {p['blocked_by_en']}")
            u.append(f"  - Marknad: {p['market_en']}")
    u += ["", "## Positionering", "", r["position_en"],
          "", "## Vad filen inte kan mäta", "", r["not_measurable_en"],
          "", "## Så arbetar du vidare", "", ARBETSSATT, ""]
    return "\n".join(u)


def main(argv: list[str]) -> int:
    r = rapport()
    if "--json" in argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif "--md" in argv:
        print(markdown(r), end="")
    else:
        skriv(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
