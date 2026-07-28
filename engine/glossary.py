"""Vad varje tal på ytan betyder — och vad det INTE säger.

Motorn bar 173 förklaringsfält på klarspråk (`means_en`, `cannot_en`,
`basis_en`, `why_en`) och konsolen visade noll av dem. Värre: ett
beslutskort visar sex tal utan enhet, utan skala och utan besked om
vilket håll som är bra. "Confidence 20" — är det bra? Av vad? Ingenstans
stod det.

Ett tal utan tolkning är inte data, det är en Rorschach-plätt. Läsaren
fyller i betydelsen själv, och fyller i fel.

Varje post här bär fyra saker, och den tredje är den som saknas i alla
andra verktyg:

    means_en    vad talet mäter, på ett språk en människa använder
    reads_en    hur man LÄSER det: skala, riktning, vad som är typiskt
    cannot_en   vad talet aldrig avgör — den vanligaste feltolkningen,
                utskriven innan någon hinner göra den
    from_en     var det kommer ifrån

`cannot_en` är inte en brasklapp. "Confidence" mäter datatäckning och
signalkvalitet, INTE hur sannolikt det är att företaget lyckas — och den
förväxlingen är exakt den som får någon att satsa sina pengar på fel
grund. Ett verktyg som låter läsaren gissa vilken av tolkningarna som
gäller har inte informerat, det har bara sett informerat ut.

Registret är DATA. En ny mätare på ytan är en ny rad här, inte en ny
kodgren — och ett test faller om ytan visar ett mått som saknar rad.

Rent stdlib.
"""
from __future__ import annotations


def _m(label_en: str, means_en: str, reads_en: str, cannot_en: str,
       from_en: str, scale: str = "") -> dict:
    return {"label_en": label_en, "means_en": means_en, "reads_en": reads_en,
            "cannot_en": cannot_en, "from_en": from_en, "scale": scale}


METRICS: dict[str, dict] = {
    "confidence": _m(
        "Confidence",
        "How much data stands behind this answer — coverage of the signals "
        "we wanted, multiplied by how good those signals are.",
        "0–100. Higher means the answer rests on more, and better, "
        "measurements. Below about 40 the picture is thin and the engine "
        "says so rather than hiding it.",
        "It says NOTHING about whether the business will succeed. A high "
        "confidence on a weak location means we are confident the location "
        "is weak. Reading it as a probability of success is the single most "
        "common mistake with a number like this.",
        "0.5 × data coverage + 0.5 × average signal quality "
        "(engine/scan.py:_confidence)", "0–100"),

    "risk_index": _m(
        "Risk index",
        "How much of what could go wrong at this location is already "
        "visible in the data — competition, dependence on a single "
        "employer, sensitivity to a downturn.",
        "0–100, where LOWER is better. The band beside it (low/medium/"
        "high) is the reading; the number is the detail behind the band.",
        "It is not a forecast of failure and it carries no probability. A "
        "low index means few visible risks — not that none exist. Risks "
        "nobody measures do not appear here.",
        "risk_score × 100 (engine/scan.py)", "0–100, lower is better"),

    "momentum": _m(
        "Momentum",
        "Which way the area is moving right now: building permits, "
        "renovation and development activity taken together.",
        "0–100. At or above 60 the area is improving, at or below 40 it is "
        "weakening, in between it is stable.",
        "**50 is what you get when nothing was measured**, not a "
        "measurement that the area is average. Check confidence beside it "
        "before reading 50 as 'stable'.",
        "mean of normalised momentum signals (engine/scan.py:_momentum)",
        "0–100"),

    "supply_gap": _m(
        "Supply gap",
        "How much demand there is for every existing provider — the room "
        "left in the market.",
        "A ratio. Above 1 means demand exceeds the supply on record; the "
        "higher the number, the more headroom.",
        "It cannot see providers that no register lists — unregistered, "
        "newly started or operating from a neighbouring area. Where no "
        "business register is connected the engine reports no count at all "
        "rather than estimating one.",
        "demand versus establishments on record "
        "(engine/scan.py:_competition_gap)", "ratio"),

    "time_window": _m(
        "Time window",
        "Roughly how long this opportunity is likely to stay open before "
        "others act on the same signals.",
        "Months, clipped to between 6 and 36. A large supply gap widens it; "
        "high momentum narrows it, because more people are noticing the "
        "same thing.",
        "It is a heuristic, not a deadline and not a forecast. Nothing in "
        "the data knows what a competitor intends to do next quarter.",
        "heuristic from supply gap and momentum "
        "(engine/scan.py:_time_window)", "6–36 months"),

    "rank_score": _m(
        "Rank (your profile)",
        "The opportunity score adjusted for YOU: your risk tolerance, your "
        "goal and the way you work.",
        "Higher is better. It is why the same town can rank first for one "
        "operator and tenth for another.",
        "It is not comparable between two different profiles, and it is not "
        "a score anyone else would see. Quoting it to someone with a "
        "different profile compares two different measurements.",
        "opportunity score − risk penalty + goal and work-style "
        "adjustment (engine/scan.py)", "0–100, personal"),

    "opportunity_score": _m(
        "Opportunity score",
        "How well this place fits this trade, before anything personal to "
        "you is taken into account.",
        "0–100. It is the comparable figure — the same for everyone asking "
        "about the same place and trade.",
        "It does not know your capital, your staff or your timing. It "
        "ranks places, it does not decide for you.",
        "weighted signal model (engine/scoring.py)", "0–100"),

    "data_coverage": _m(
        "Data coverage",
        "How much of what the engine wanted to measure it actually got.",
        "0–1. At 0 nothing live answered and every figure shown is "
        "simulated and labelled as such.",
        "Coverage is not accuracy. Full coverage of poor sources is still "
        "poor — which is why quality is weighed separately in confidence.",
        "share of requested signals that resolved (engine/datasources)",
        "0–1"),
}

# Vanligaste feltolkningen av hela kortet, inte av ett enskilt tal.
READING_THE_CARD_EN = (
    "Two numbers on this card answer different questions and are easy to "
    "swap: the score says how good the place looks, confidence says how "
    "much we actually know. A high score with low confidence is a lead "
    "worth checking, not a decision worth making — and the engine will "
    "keep saying so rather than quietly rounding the difference away."
)


def explain(metric_id: str) -> dict | None:
    return METRICS.get(metric_id)


def catalog() -> dict:
    return {
        "metrics": METRICS,
        "count": len(METRICS),
        "reading_the_card_en": READING_THE_CARD_EN,
        "principle_en": (
            "A number without an interpretation is not data, it is an "
            "inkblot: the reader supplies the meaning, and supplies it "
            "wrong. Every figure the surface shows carries what it means, "
            "how to read it, and — the part other tools leave out — what "
            "it never decides."),
    }
