"""Fyra löften. Hela katalogen under dem.

Katalogen (`/v1/catalog`) beskriver fyrtiotalet motorer och ett hundratal
endpoints — exakta tal rapporteras av `surface()`, aldrig av den här
texten, eftersom ett tal i en kommentar ruttnar tyst. Katalogen är sann
och den ska finnas kvar — maskiner behöver den, och en agent som
integrerar mot plattformen behöver varenda rad.

Men den beskriver VAD SOM BYGGDES, inte vad någon får. Ingen människa
köper fyrtiofem motorer. En katalog som lika gärna kunde vara ett
organisationsschema svarar inte på kundens enda fråga: *vad kan jag göra
med det här?*

Den här modulen är ytan. Fyra löften i den ordning en människa faktiskt
möter dem:

    1. Är det sant?        någon påstår något om en plats
    2. Finns det plats?    du överväger att satsa
    3. Vad har ändrats?    du har redan satsat
    4. Vem bär det?        beslutet togs och ska stå sig

Varje löfte namnger frågan med kundens ord, EN ingång som svarar först,
och de motorer som ligger under. Motorerna tas inte bort — de slutar
vara det man möter.

Två regler, båda testade:

  * **Varje motor tillhör exakt ett löfte.** Ingen får bli hemlös när
    ytan krymper, och ingen får räknas två gånger för att ytan ska se
    större ut. Det testet är skillnaden mellan en verklig sammanfattning
    och en reklamsida ovanpå en oförändrad röra.
  * **Ingången måste finnas.** Samma spärr som `offering` har: ett löfte
    som pekar på en endpoint som inte existerar är en lögn med
    fördröjning.

Rent stdlib.
"""
from __future__ import annotations

# `engines` är katalogens id:n. `entry` är den endpoint som svarar först
# på löftets fråga — inte den enda, den första.
PROMISES: tuple[dict, ...] = (
    {
        "id": "is_it_true",
        "order": 1,
        "question_en": "Is that actually true?",
        "question_sv": "Stämmer det där?",
        "for_en": "Anyone who has been handed a number and cannot place it "
                  "— a resident, a journalist, a board member.",
        "settles_en": "Whether a claim about a place holds up, and on what "
                      "the answer rests.",
        "refusal_en": "When the basis is too thin, this is the promise that "
                      "says so instead of producing a number.",
        "entry": "/v1/benchmark",
        # `selfaudit` hör hit av samma skäl som `provenance`: frågan
        # "stämmer det där?" gäller även plattformen själv, och den som
        # ska lita på ett svar måste kunna se granskningen av apparaten
        # som gav det.
        "engines": ("ask", "benchmark", "setpoints", "kpi", "lambda",
                    "indices", "claims", "provenance", "sensitive",
                    "worthiness", "strim", "wages", "corrections",
                    "data_sources", "platform", "coverage", "mrai",
                    "selfaudit"),
    },
    {
        "id": "is_there_room",
        "order": 2,
        "question_en": "Is there room for me here?",
        "question_sv": "Finns det plats för mig här?",
        "for_en": "Anyone about to commit money, years or a household to a "
                  "place — operators, brokers, municipalities, families.",
        "settles_en": "Where a specific business or life has the best "
                      "chance, measured against comparable places.",
        "refusal_en": "With no business register connected for a market, no "
                      "establishment count is invented.",
        "entry": "/v1/report",
        "engines": ("opportunity", "opportunity_intel", "saturation",
                    "gaps", "plan", "risk", "risk_intelligence", "compare",
                    "segments", "installed_base", "workforce", "flows", "land",
                    "livability", "merit", "entrypoints"),
    },
    {
        "id": "what_changed",
        "order": 3,
        "question_en": "What changed that I should know about?",
        "question_sv": "Vad har ändrats som jag borde veta?",
        "for_en": "Anyone who has already committed — and cannot watch "
                  "everything themselves.",
        "settles_en": "What to look at this week, ranked by decision value "
                      "rather than by when it happened.",
        "refusal_en": "A quiet day is reported as a quiet day, never padded "
                      "with noise to look valuable.",
        "entry": "/v1/brief",
        # `sensors` hör hit och inte till provenance: den handlar om vad
        # plattformen alls KAN märka, vilket är det här löftets gräns.
        "engines": ("brief", "monitors", "inbox", "feeds", "event_study",
                    "scenario", "correlate", "sensors", "corroboration",
                    "aamos_integration", "scheduler", "analysis"),
    },
    {
        "id": "who_carries_it",
        "order": 4,
        "question_en": "Who carries this decision — and did it work?",
        "question_sv": "Vem bär beslutet, och höll det?",
        "for_en": "Boards, auditors, public bodies and anyone who will be "
                  "asked afterwards.",
        "settles_en": "Which named person committed to what, and how the "
                      "outcome actually turned out against it.",
        "refusal_en": "A decision with no named owner is refused at the "
                      "point of commitment, not discovered later.",
        "entry": "/v1/decisions/commit",
        # Också det kommersiella förhållandet: vad du köpte, vem du är,
        # och vad plattformen därmed är skyldig dig.
        "engines": ("accountability", "decision", "outcomes", "offering",
                    "surface", "customer", "visitor", "admin",
                    "inspections", "export", "pushes", "sponsorship"),
    },
)


def promises() -> list[dict]:
    return [dict(p, engines=list(p["engines"]))
            for p in sorted(PROMISES, key=lambda p: p["order"])]


def promise_of(engine_id: str) -> dict | None:
    """Vilket löfte en motor ligger under. Ingen motor är hemlös."""
    for p in PROMISES:
        if engine_id in p["engines"]:
            return dict(p, engines=list(p["engines"]))
    return None


def surface(detail: bool = False) -> dict:
    """Ytan. `detail=True` tar med motorerna under varje löfte."""
    from api.catalog import API_CATALOG
    by_id = {g["id"]: g for g in API_CATALOG["engines"]}
    out = []
    for p in promises():
        row = {k: v for k, v in p.items() if k != "engines"}
        row["engine_count"] = len(p["engines"])
        row["endpoint_count"] = sum(
            len(by_id[e]["endpoints"]) for e in p["engines"] if e in by_id)
        if detail:
            row["engines"] = [
                {"id": e, "label_en": by_id[e]["label_en"],
                 "endpoints": [x["path"] for x in by_id[e]["endpoints"]]}
                for e in p["engines"] if e in by_id]
        out.append(row)
    return {
        "promises": out,
        "promise_count": len(out),
        "engine_count": len(API_CATALOG["engines"]),
        "endpoint_count": sum(len(g["endpoints"])
                              for g in API_CATALOG["engines"]),
        "principle_en": (
            "Four promises, not forty-five engines. The catalogue at "
            "/v1/catalog is complete and unchanged — machines need every "
            "row of it. This is what a person is offered, and it is the "
            "same platform underneath: every engine belongs to exactly "
            "one promise, and a test asserts none was left homeless or "
            "counted twice."),
        "what_makes_it_different_en": (
            "Each promise names what it refuses. Every comparable tool "
            "answers with a confident number; the position here is that a "
            "number without a stated basis is worth less than an honest "
            "refusal."),
        "full_catalogue": "/v1/catalog",
    }
