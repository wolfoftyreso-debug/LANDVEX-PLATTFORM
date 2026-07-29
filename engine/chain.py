"""Fyra avsikter kunden faktiskt har — inte sextiotre motorer hon inte bad om.

`surface.py` svarar "vilken FRÅGA löser detta" (fyra löften, sorterat
efter vem som frågar). Den här modulen svarar en annan, lika verklig
fråga: "vilken sorts AKTIVITET är det här", sorterat efter vad kunden
vill ÅSTADKOMMA härnäst — förstå, kontrollera, samla in, eller agera.
Två giltiga kartor över samma motorer, inte en ersättning för den andra.

    1. Beslutsintelligens   "Jag behöver förstå verkligheten och fatta
                             ett beslut." → alltid ett beslutsunderlag.
    2. Kontrollintelligens  "Jag behöver verifiera att något verkligen
                             stämmer." → alltid verifierad status.
    3. Datainsamling        "Jag behöver skapa ny kunskap." → alltid ny
                             rådata, aldrig analyserad än.
    4. Aktivering           "Jag vill använda kunskapen för att skapa
                             affärer eller åtgärder." → något lämnade
                             plattformen: en leverans, en export, ett
                             larm, ett schemalagt jobb.

Samma spärr som `surface.py`, testad likadant: varje motor hör till
EXAKT en kategori. Ingen hemlös, ingen dubbelräknad.

**De två kedjorna är INTE en tredje, fullständig taxonomi.** Ett
förslag var att visa EN pipeline (observation → objektdetektering →
klassificering → verifiering → …) bakom varenda analys, för att göra
tydligt att det är samma motor oavsett om man analyserar vägar,
fastigheter eller marknader. Det är sant i sak — men "objektdetektering"
är en påstådd förmåga plattformen INTE har: verdikten på ett
kontrollerat objekt kommer från en mänsklig zoomer, aldrig från
datorseende på en bild (Vision-pipelinen är medvetet outbyggd, se
ARCHITECTURE/CLAUDE.md). Att skriva "objektdetektering" här vore precis
den sortens påstådda förmåga plattformen annars vägrar att låtsas ha.

Verkligheten är att det finns TVÅ verkliga kedjor, inte en:

* **GROUND_TRUTH_CHAIN** — för motorer som kontrollerar ett FYSISKT
  objekt (kontroll/infrastruktur/sponsrade uppdrag/sensorer): en
  människa i fält, en verdikt, en historik, en aggregering.
* **SIGNAL_CHAIN** — för motorer som räknar på STATISTISKA signaler
  (möjlighet/risk/kompetens/index): en källkedja, normalisering,
  viktning, konfidens.

Båda konvergerar i SAMMA sak — ett svar som bär sin egen konfidens och
vägrar hellre än gissar när underlaget är för tunnt. Det är den
verkliga enhetliga tråden, inte en låtsad enhetlig pipeline.
Kedjornas motorlistor är REPRESENTATIVA exempel, inte en fullständig,
testad täckning som kategorierna ovan.

Rent stdlib.
"""
from __future__ import annotations

CATEGORIES: tuple[dict, ...] = (
    {
        "id": "decision_intelligence",
        "order": 1,
        "label_en": "Decision Intelligence",
        "intent_en": "I need to understand reality and make a decision.",
        "result_en": "A decision basis — score, drivers, risk, benchmark "
                     "or forecast, with its confidence and what it "
                     "refuses to say stated alongside it. Never a bare "
                     "number.",
        "engines": (
            "ask", "opportunity", "workforce", "risk", "compare",
            "opportunity_intel", "risk_intelligence", "gaps", "plan",
            "segments", "installed_base", "indices", "kpi", "lambda",
            "setpoints", "decision", "entrypoints", "wages", "flows",
            "land", "livability", "merit", "scenario", "correlate",
            "event_study", "benchmark", "sensitive", "accountability",
            "saturation", "admin",
        ),
    },
    {
        "id": "control_intelligence",
        "order": 2,
        "label_en": "Control Intelligence",
        "intent_en": "I need to verify that something is actually true.",
        "result_en": "Verified status — checked against a routine, a "
                     "schedule, or an independent second source. Never "
                     "asserted, and a check without evidence is refused.",
        "engines": (
            "claims", "feeds", "worthiness", "corrections", "inspections",
            "infrastructure", "sensors", "corroboration", "mrai",
            "analysis", "selfaudit", "provenance", "outcomes", "brief",
            "monitors", "strim", "coverage", "platform",
        ),
    },
    {
        "id": "data_collection",
        "order": 3,
        "label_en": "Data Collection",
        "intent_en": "I need to create new knowledge, not analyse what "
                     "already exists.",
        "result_en": "New raw material — a dispatched mission, an "
                     "imported feed, a registered account. Nothing "
                     "analysed yet; that happens one step later.",
        "engines": (
            "sponsorship", "staff", "company", "visitor", "data_sources",
        ),
    },
    {
        "id": "activation",
        "order": 4,
        "label_en": "Activation",
        "intent_en": "I want to turn the knowledge into business or "
                     "action.",
        "result_en": "Something left the platform — a signed delivery, "
                     "an export, a notification, a scheduled job. A "
                     "failed attempt is logged as failed, never as sent.",
        "engines": (
            "deliveries", "connections", "pushes", "export", "scheduler",
            "inbox", "customer", "offering", "surface", "chain",
            "aamos_integration",
        ),
    },
)


def categories() -> list[dict]:
    """Alla fyra, med räknade motorer/endpoints — aldrig påstådda."""
    from api.catalog import API_CATALOG
    by_id = {g["id"]: g for g in API_CATALOG["engines"]}
    out = []
    for c in sorted(CATEGORIES, key=lambda c: c["order"]):
        row = {k: v for k, v in c.items() if k != "engines"}
        row["engine_count"] = len(c["engines"])
        row["endpoint_count"] = sum(
            len(by_id[e]["endpoints"]) for e in c["engines"] if e in by_id)
        out.append(row)
    return out


def category_of(engine_id: str) -> dict | None:
    """Vilken avsiktskategori en motor hör till. Ingen motor är hemlös."""
    for c in CATEGORIES:
        if engine_id in c["engines"]:
            return {k: v for k, v in c.items() if k != "engines"}
    return None


GROUND_TRUTH_CHAIN: tuple[dict, ...] = (
    {"id": "observation", "label_en": "Observation",
     "does_en": "A zoomer visits the physical point and records what it "
                "looks like right now — dispatched via quiXzoom; the "
                "image itself is never stored on this platform, only the "
                "verdict and the mission reference."},
    {"id": "verdict", "label_en": "Verdict",
     "does_en": "The zoomer classifies what they found against the "
                "routine's defined checks — present/absent, pass/fail/"
                "unclear. A verdict with no evidence behind it is "
                "refused, never recorded as compliant by default."},
    {"id": "verification", "label_en": "Verification",
     "does_en": "The verdict is checked against what 'compliant' "
                "actually means for this object — the routine and its "
                "SLA, not a guess at what 'should' be fine."},
    {"id": "history", "label_en": "History",
     "does_en": "Every verdict is logged with its timestamp alongside "
                "every prior check on the same object. Nothing is "
                "estimated for the time between visits."},
    {"id": "aggregation", "label_en": "Aggregation",
     "does_en": "Individual verdicts roll up into a compliance record, a "
                "freshness status, or an installed-base age curve across "
                "a whole register."},
    {"id": "context", "label_en": "Context",
     "does_en": "The aggregate is placed against peers, an SLA promise, "
                "and prior periods — a single check means little; the "
                "pattern does."},
    {"id": "change_detection", "label_en": "Change detection",
     "does_en": "A deviation from the expected pattern — a miss, a "
                "decline, a threshold breach — is flagged as worth a "
                "look. A quiet period is reported as quiet, not padded."},
    {"id": "decision_recommendation", "label_en": "Decision recommendation",
     "does_en": "A due-list, a filed exception, or an alert names what a "
                "human should look at next — an option naming what it "
                "would resolve, never an instruction."},
)

SIGNAL_CHAIN: tuple[dict, ...] = (
    {"id": "signal_resolution", "label_en": "Signal resolution",
     "does_en": "A real connected source (SCB, Kolada, a business "
                "register …) answers first; a deterministic mock fills "
                "what nothing real reaches yet — always labelled which "
                "one it was."},
    {"id": "normalization", "label_en": "Normalization",
     "does_en": "Raw values become comparable 0–100 scores using a "
                "declared method per signal — saturating, linear, "
                "inverse or banded — never a hidden formula."},
    {"id": "weighting", "label_en": "Weighting",
     "does_en": "Normalized signals combine per the trade's declared "
                "weights. A niche (EV chargers vs. new-build electrics) "
                "reweights the same signals; it never invents new ones."},
    {"id": "confidence", "label_en": "Confidence",
     "does_en": "Coverage × source quality becomes a stated confidence "
                "band, not a hidden assumption baked into one number."},
    {"id": "peer_comparison", "label_en": "Peer comparison",
     "does_en": "The score is placed against comparable places, trades "
                "or periods — a percentile or benchmark, never a bare "
                "value with nothing to measure it against."},
    {"id": "decision_card", "label_en": "Decision card",
     "does_en": "Score, top drivers with their own source, risk, and any "
                "labelled scenario — with an explicit refusal wherever "
                "the basis is too thin to say more."},
)


def chains() -> dict:
    """De två verkliga kedjorna — illustrativa exempel, inte en tredje,
    fullständig taxonomi som konkurrerar med categories()."""
    return {
        "ground_truth": {
            "for_en": "Engines that check a physical object or "
                      "recurring real-world condition.",
            "stages": list(GROUND_TRUTH_CHAIN),
            "example_engines": ("inspections", "infrastructure",
                                "sponsorship", "sensors", "corroboration",
                                "brief", "monitors"),
        },
        "signal": {
            "for_en": "Engines that score a place, trade or occupation "
                      "from statistical and reference signals.",
            "stages": list(SIGNAL_CHAIN),
            "example_engines": ("opportunity", "risk", "workforce",
                                "indices", "gaps", "compare", "merit"),
        },
        "converge_on_en": "Both end in the same shape of answer: a "
                          "stated confidence, a named source, and a "
                          "refusal instead of a guess when the basis "
                          "is too thin — not a shared step-by-step "
                          "pipeline, which would overclaim what either "
                          "family actually does.",
    }


def chain_overview() -> dict:
    return {
        "tagline_en": "From observation to decision.",
        "categories": categories(),
        "chains": chains(),
        "principle_en": (
            "Four intents, not sixty-three engines to learn. Every "
            "engine belongs to exactly one intent category — a test "
            "asserts none is left homeless or counted twice, the same "
            "rule as the four promises at /v1/surface. What is NOT "
            "claimed: one identical pipeline behind every analysis. "
            "Field-verification engines run on a human zoomer's verdict, "
            "never on automated object detection from an image — the "
            "vision layer that would make that true is deliberately not "
            "built yet, and this overview says so instead of implying "
            "otherwise."),
        "full_catalogue": "/v1/catalog",
    }
