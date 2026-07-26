"""Parametrarnas härkomst – var kommer siffran i koden ifrån?

Plattformen är sträng med DATANS ursprung: ett värde märks `mock`, ett
antal märks `measured: false`, en okänd ort besvaras aldrig med en annan
orts siffror. Men den har varit helt tyst om sitt EGET ursprung.

`MIN_R2 = 0.5` avgör om ett scenario alls får uttalas. `MIN_CELL = 10`
avgör om en känslig fråga får besvaras. `childcare: 0.15` avgör vilken
kommun som hamnar överst för en ensamstående förälder. Ingen av dem hade
en källa. Kommentarerna förklarade vad talet gör – aldrig varför det är
just det talet.

Det här registret stänger den luckan. Varje inställbar konstant deklarerar
sin härkomst i en av fyra klasser:

    sourced     spårbar till en namngiven extern auktoritet
    convention  etablerad praxis i fältet, med praxisen namngiven
    calibrated  härledd ur utfallsdata I DEN HÄR plattformen
    assumed     någon valde den. Omdöme, inget annat.

`assumed` är inte skamligt – men det ska stå. Ett system som redovisar
att en tröskel är gissad låter läsaren värdera slutsatsen därefter. Ett
som döljer det låter en gissning se ut som ett fynd.

Rent stdlib.
"""
from __future__ import annotations

CLASSES = ("sourced", "convention", "calibrated", "assumed")

# modul.NAMN → härkomst
PARAMETERS: dict[str, dict] = {
    # ── Grindar: avgör OM systemet får uttala sig ────────────────────
    "sensitive.MIN_CELL": {
        "value": 10, "class": "convention",
        "basis_en": "k-anonymity with k=10 is the common floor in official "
                    "statistics disclosure control (Eurostat/ONS practice) "
                    "for small-cell suppression.",
        "affects_en": "Whether a question about a protected category is "
                      "answered at all."},
    "scenario.MIN_SOURCES": {
        "value": 2, "class": "assumed",
        "basis_en": "Chosen so a single source can never carry a scenario. "
                    "Two is a judgement, not a finding — three would be "
                    "defensible and stricter.",
        "affects_en": "Whether a scenario is stated or refused."},
    "scenario.MIN_HISTORY": {
        "value": 5, "class": "assumed",
        "basis_en": "Fewer points cannot show a tendency apart from noise. "
                    "Five is judgement; no power calculation was done.",
        "affects_en": "Whether a scenario is stated or refused."},
    "scenario.MIN_R2": {
        "value": 0.5, "class": "assumed",
        "basis_en": "Requires the trend to explain at least half the "
                    "variance so a sloped noise cloud cannot pass as a "
                    "tendency. The 0.5 boundary itself is picked.",
        "affects_en": "Whether a scenario is stated or refused."},
    "sensitive.MIN_SOURCES": {
        "value": 2, "class": "assumed",
        "basis_en": "Same judgement as scenario.MIN_SOURCES, applied where "
                    "the cost of being wrong is higher.",
        "affects_en": "Whether a sensitive association is shown."},
    "saturation.MIN_PEERS": {
        "value": 5, "class": "assumed",
        "basis_en": "A percentile over fewer than five comparators mostly "
                    "describes the comparators. Five is a floor by "
                    "judgement.",
        "affects_en": "Whether a saturation verdict is given."},
    "merit.MIN_PEERS": {
        "value": 5, "class": "assumed",
        "basis_en": "Same judgement as saturation.MIN_PEERS: a percentile "
                    "over fewer than five comparators mostly describes the "
                    "comparators rather than the place.",
        "affects_en": "Whether a place is said to lead on a dimension."},
    "merit.MIN_COVERAGE": {
        "value": 0.5, "class": "assumed",
        "basis_en": "Refuses to judge a place when half its signals are "
                    "missing. The half is judgement.",
        "affects_en": "Whether a place is assessed at all."},
    "outcomes.MIN_SAMPLE": {
        "value": 30, "class": "convention",
        "basis_en": "n=30 is the usual rule-of-thumb floor before a rate is "
                    "treated as an estimate rather than an anecdote. A "
                    "convention, not a proof.",
        "affects_en": "Whether a calibrated survival probability is offered."},
    "corrections.MIN_SUBMITTERS": {
        "value": 5, "class": "assumed",
        "basis_en": "Five independent submitters before community data may "
                    "move a value. Picked to be hard to brigade, not "
                    "derived.",
        "affects_en": "Whether a community correction adapts a value."},
    "corrections.MAX_CV": {
        "value": 0.15, "class": "assumed",
        "basis_en": "Submissions must agree within a 15% coefficient of "
                    "variation. The 15 is judgement.",
        "affects_en": "Whether scattered guesses can adapt a value."},
    "flows.MIN_SOURCES": {
        "value": 2, "class": "assumed",
        "basis_en": "Same judgement as scenario.MIN_SOURCES: one source can "
                    "never carry a cost-benefit assessment on its own.",
        "affects_en": "Whether an expected-value assessment is produced."},

    # ── Referensvärden: faktiskt spårbara ────────────────────────────
    "setpoints.debt_to_gdp": {
        "value": 60, "class": "sourced",
        "basis_en": "Maastricht convergence criterion, EU Treaty protocol.",
        "affects_en": "Which zone a debt level is reported in."},
    "setpoints.gini": {
        "value": 0.30, "class": "sourced",
        "basis_en": "Common low-inequality reference in OECD income "
                    "distribution reporting.",
        "affects_en": "Which zone an inequality level is reported in."},
    "setpoints.tfr": {
        "value": 2.1, "class": "sourced",
        "basis_en": "Replacement-level fertility, standard demographic "
                    "reference.",
        "affects_en": "Which zone a fertility rate is reported in."},

    # ── Omräkning och schabloner ─────────────────────────────────────
    "wages.TAX_WEDGE": {
        "value": "22 markets, 0.08–0.40", "class": "assumed",
        "basis_en": "Effective tax-wedge schablon per market, in the region "
                    "of published OECD figures but NOT taken from a named "
                    "table per market. Replace with the official rate per "
                    "market before any of it is quoted.",
        "affects_en": "Net pay, and therefore every cross-market pay "
                      "comparison."},
    "wages.FX_PER_SEK": {
        "value": "8 currencies", "class": "assumed",
        "basis_en": "Documented standard rates, not a live feed and not "
                    "purchasing-power adjusted. Stated in PPP_CAVEAT.",
        "affects_en": "Whether two markets' pay can be compared at all."},
    "workforce.COMPLETION_RATE": {
        "value": 0.85, "class": "assumed",
        "basis_en": "Share of training places that become graduates. A "
                    "schablon; the real rate varies widely by programme.",
        "affects_en": "How much a simulated increase in training places "
                      "closes a shortage."},
    "installed_base._EVENTS_PER_TECH_YEAR": {
        "value": 400.0, "class": "assumed",
        "basis_en": "Service events per technician per year. Trade practice "
                    "figure, not measured here.",
        "affects_en": "Estimated technician demand."},
    "commission.QZ_TOKEN_USD_SCHABLON": {
        "value": 0.15, "class": "assumed",
        "basis_en": "Standard estimate for the token rate; quiXzoom sets the "
                    "actual rate. Labelled as an estimate in the catalogue.",
        "affects_en": "Displayed commission value per lead."},
    "risk._DATA_WEIGHT": {
        "value": 0.12, "class": "assumed",
        "basis_en": "How much data uncertainty counts toward total risk. "
                    "Picked so thin data raises risk without dominating it.",
        "affects_en": "Total risk score."},
    "indices.CONTRADICTION_THRESHOLD": {
        "value": 35, "class": "assumed",
        "basis_en": "Gap between planned and observed before a contradiction "
                    "is flagged. Judgement.",
        "affects_en": "Whether a contradiction is reported."},

    # ── Viktprofiler: rena omdömen ───────────────────────────────────
    "livability.HOUSEHOLDS": {
        "value": "5 profiles × 12 dimensions", "class": "assumed",
        "basis_en": "How much a household type weighs childcare against pay "
                    "against safety. Reasoned, but not derived from survey "
                    "data on stated preferences. Different weights give a "
                    "different ranking, and the ranking should be read as "
                    "one weighting among possible ones.",
        "affects_en": "The entire livability ordering."},
    "merit.DIMENSIONS": {
        "value": "6 dimensions", "class": "assumed",
        "basis_en": "Which signals constitute business capability, and their "
                    "internal weights. Judgement.",
        "affects_en": "The entire merit ranking."},
    "inbox.STAKE_WEIGHT": {
        "value": "5 stake kinds", "class": "assumed",
        "basis_en": "That a committed decision outranks a watch, which "
                    "outranks a place, is a deliberate policy: accountability "
                    "before curiosity. The numbers implementing it are "
                    "judgement.",
        "affects_en": "Which events reach a person first."},

    # ── Prestandabudgetar ────────────────────────────────────────────
    "perf.percentiles": {
        "value": "p95 / p99", "class": "convention",
        "basis_en": "p95 for routine interactions and p99 for what may never "
                    "fail is standard practice in performance budgeting.",
        "affects_en": "Whether a performance run passes."},
    "perf.DEFAULT_MAX_REGRESSION": {
        "value": 2.0, "class": "assumed",
        "basis_en": "Twice as slow counts as a regression. Picked to sit "
                    "above normal machine variance without hiding real "
                    "slowdowns.",
        "affects_en": "Whether a build fails on a slowdown."},
}


def summary() -> dict:
    """Hur mycket av plattformens omdöme som vilar på gissningar."""
    by_class = {c: [] for c in CLASSES}
    for name, p in PARAMETERS.items():
        by_class[p["class"]].append(name)
    total = len(PARAMETERS)
    assumed = len(by_class["assumed"])
    return {
        "total": total,
        "by_class": {c: len(v) for c, v in by_class.items()},
        "assumed_share": round(assumed / total, 4) if total else 0.0,
        "gates": [n for n, p in PARAMETERS.items()
                  if "answered at all" in p["affects_en"]
                  or "refused" in p["affects_en"]
                  or "Whether" in p["affects_en"]],
        "headline_en": (
            f"{assumed} of {total} tunable parameters are judgement calls "
            f"with no external source. That is not a defect in itself — it "
            f"is a fact a reader is entitled to weigh, and it is stated "
            f"rather than hidden."),
        "note_en": "The platform labels its data's provenance. This labels "
                   "its own. A threshold that decides whether the system may "
                   "speak deserves at least as much scrutiny as the numbers "
                   "it lets through.",
    }


def parameters(cls: str = "") -> list[dict]:
    if cls and cls not in CLASSES:
        raise ValueError(f"unknown class: {cls}. Choose {', '.join(CLASSES)}")
    return [{"parameter": n, **p} for n, p in sorted(PARAMETERS.items())
            if not cls or p["class"] == cls]


def provenance_of(name: str) -> dict | None:
    p = PARAMETERS.get(name)
    return {"parameter": name, **p} if p else None
