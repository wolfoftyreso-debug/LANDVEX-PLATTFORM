"""Livsvillkor för ett HUSHÅLL – "var kan jag bygga ett bra liv?"

Plattformen har kunnat svara företaget och kommunen. Den här frågan är en
annan: en enskild människa med ett yrke, ett hushåll och en vardag som ska
gå ihop. Ett medelvärde för en region svarar inte på den – en ensamstående
med barn väger förskola, skolvägar, trygghet och nettolön helt annorlunda
än ett par utan barn.

Två saker skiljer det här lagret från en vanlig rankning:

1. **Hushållet sätter vikterna.** `HOUSEHOLDS` är data: varje hushållstyp
   bär sin egen viktprofil över dimensionerna. Byt hushåll och listan
   ändras – det är hela poängen.

2. **Hindret kommer före rankningen.** För ett REGLERAT yrke (sjuksköterska,
   läkare, jurist) avgörs möjligheten först av rätten att arbeta och av om
   legitimationen erkänns. En lista som sätter en amerikansk stad överst
   utan att nämna visum, NCLEX och delstatslicens är inte ett svar – den är
   vilseledande. `MOBILITY` bär det som data per marknad, och svaret leder
   med det.

`MOBILITY` är en sammanfattning av regelverkets FORM, inte juridisk
rådgivning, och det står i varje svar. Det säger vilken sorts process som
gäller och var den prövas – aldrig att en enskild person kommer att bli
godkänd.

Rent stdlib.
"""
from __future__ import annotations

from .integrity import framing_disclosure
from .signals import CATALOG, normalize

# ── Hushållstyper: vikter som data ──────────────────────────────────────
HOUSEHOLDS: dict[str, dict] = {
    "single_parent": {
        "label_en": "Single parent with children",
        "means_en": "One income, no second adult to absorb a sick child or a "
                    "late shift. Childcare, school and safety carry as much "
                    "weight as pay.",
        "weights": {"job_demand": 0.14, "net_pay": 0.13, "childcare": 0.15,
                    "schools": 0.11, "safety": 0.12, "housing": 0.10,
                    "cost_of_living": 0.10, "healthcare": 0.06,
                    "communications": 0.04, "social": 0.03, "mobility": 0.02,
                    "support_services": 0.0}},
    "single": {
        "label_en": "Single adult, no children",
        "means_en": "Pay, prospects and the cost of living dominate; "
                    "childcare does not apply.",
        "weights": {"job_demand": 0.22, "net_pay": 0.20, "housing": 0.15,
                    "cost_of_living": 0.12, "safety": 0.10, "social": 0.08,
                    "communications": 0.06, "healthcare": 0.04,
                    "mobility": 0.03, "childcare": 0.0, "schools": 0.0,
                    "support_services": 0.0}},
    "couple_children": {
        "label_en": "Couple with children",
        "means_en": "Two incomes soften pay risk; schools and space matter "
                    "more.",
        "weights": {"job_demand": 0.12, "net_pay": 0.11, "childcare": 0.11,
                    "schools": 0.15, "safety": 0.12, "housing": 0.13,
                    "cost_of_living": 0.10, "healthcare": 0.06,
                    "communications": 0.05, "social": 0.03, "mobility": 0.02,
                    "support_services": 0.0}},
    "single_parent_special_needs": {
        "label_en": "Single parent, child needing additional support",
        "means_en": "Everything the single-parent case weighs, plus the "
                    "capacity that decides whether daily life works at all: "
                    "health, care and school support. A place with strong "
                    "average schools but no support capacity is the wrong "
                    "place.",
        "weights": {"support_services": 0.22, "healthcare": 0.13,
                    "childcare": 0.11, "schools": 0.10, "job_demand": 0.10,
                    "net_pay": 0.09, "safety": 0.08, "housing": 0.07,
                    "cost_of_living": 0.05, "communications": 0.03,
                    "social": 0.02, "mobility": 0.0}},
    "senior": {
        "label_en": "Older adult / retiring",
        "means_en": "Healthcare access and safety outrank the labour market.",
        "weights": {"healthcare": 0.22, "safety": 0.17, "housing": 0.15,
                    "cost_of_living": 0.12, "social": 0.12,
                    "support_services": 0.08, "mobility": 0.06,
                    "communications": 0.04, "net_pay": 0.02,
                    "job_demand": 0.02, "childcare": 0.0, "schools": 0.0}},
}

# ── Dimensioner: vad de mäts med ────────────────────────────────────────
# job_demand och net_pay fylls av arbetsmarknads- respektive lönelagret.
DIMENSIONS: dict[str, dict] = {
    "job_demand": {"label_en": "Demand for your occupation",
                   "means_en": "Shortage means bargaining power: more choice "
                               "of employer, and less risk of being stuck.",
                   "signals": ()},
    "net_pay": {"label_en": "Pay after tax",
                "means_en": "What actually reaches the account, not the "
                            "advertised salary.",
                "signals": ()},
    "childcare": {"label_en": "Childcare",
                  "means_en": "Whether a place can actually take your child "
                              "while you work a shift.",
                  "signals": (("care_supply", 0.6), ("families_share", 0.4))},
    "schools": {"label_en": "Schools",
                "means_en": "Attainment and the digital base under it.",
                "signals": (("education_outcomes", 0.7),
                            ("digital_connectivity", 0.3))},
    "safety": {"label_en": "Safety",
               "means_en": "Reported crime level and road safety.",
               "signals": (("crime_index", 0.6), ("road_safety", 0.4))},
    "housing": {"label_en": "Housing you can afford",
                "means_en": "Whether a single income covers somewhere to "
                            "live.",
                "signals": (("housing_affordability", 0.7),
                            ("rent_index", 0.3))},
    "healthcare": {"label_en": "Healthcare access",
                   "means_en": "Getting seen when you or a child needs it.",
                   "signals": (("healthcare_access", 1.0),)},
    "social": {"label_en": "Social fabric",
               "means_en": "Trust and reported life satisfaction — what it "
                           "is like to arrive as a stranger.",
               "signals": (("social_trust", 0.5), ("life_satisfaction", 0.5))},
    "cost_of_living": {
        "label_en": "Everyday cost of living",
        "means_en": "Rent, food and the basics — what is left of the pay "
                    "once the month is paid for.",
        "signals": (("rent_index", 0.5), ("food_access", 0.3),
                    ("haircut_price", 0.2))},
    "communications": {
        "label_en": "Communications",
        "means_en": "Connectivity and transport links — reaching work, "
                    "school and the rest of the world.",
        "signals": (("digital_connectivity", 0.6), ("transit_score", 0.4))},
    "support_services": {
        "label_en": "Support services",
        "means_en": "Health, care and social capacity for a child or adult "
                    "who needs more than the standard offer.",
        "signals": (("healthcare_access", 0.4), ("care_supply", 0.3),
                    ("education_outcomes", 0.2), ("social_trust", 0.1))},
    "mobility": {"label_en": "Getting around",
                 "means_en": "Transit and active mobility — a car-free "
                             "school run is a different life.",
                 "signals": (("transit_score", 0.6), ("active_mobility", 0.4))},
}

# ── Rätt att arbeta + erkännande av legitimation, per marknad ───────────
# Skrivet ur en EU-medborgares perspektiv (frågan ställs från Sverige).
# Detta är regelverkets FORM, inte ett besked om en enskild ansökan.
EU_FREE_MOVEMENT = (
    "at", "be", "cz", "de", "dk", "es", "fi", "fr", "ie", "it", "nl", "pl",
    "pt", "se", "bg", "cy", "ee", "gr", "hr", "hu", "lt", "lu", "lv", "mt",
    "ro", "si", "sk",
)

REGULATED_PROFESSIONS = {
    "sjukskoterska": {"label_en": "Registered nurse",
                      "eu_automatic": True,
                      "us_exam": "NCLEX-RN", "us_body": "state board of nursing"},
    "lakare": {"label_en": "Doctor", "eu_automatic": True,
               "us_exam": "USMLE", "us_body": "state medical board"},
    "underskoterska": {"label_en": "Assistant nurse", "eu_automatic": False,
                       "us_exam": "state CNA certification",
                       "us_body": "state registry"},
    "larare": {"label_en": "Teacher", "eu_automatic": False,
               "us_exam": "state teaching licence", "us_body": "state board"},
}


def mobility(occupation: str, market: str, *,
             citizenship: str = "eu") -> dict:
    """Vad som krävs för att FÅ arbeta – före allt annat."""
    prof = REGULATED_PROFESSIONS.get(occupation)
    regulated = prof is not None
    in_eu = market in EU_FREE_MOVEMENT
    if citizenship == "eu" and in_eu:
        steps = ["Right to work: freedom of movement — no work permit."]
        if regulated and prof["eu_automatic"]:
            steps.append("Qualification: automatic recognition under the EU "
                         "professional qualifications directive.")
        elif regulated:
            steps.append("Qualification: recognition decided by the host "
                         "country's competent authority (general system).")
        steps.append("Language: employer and patient-safety requirements "
                     "apply even where recognition is automatic.")
        return {"market": market, "barrier": "low", "steps_en": steps,
                "practical_en": "Legally the most direct move: you may take "
                                "the job while paperwork proceeds in most "
                                "cases.",
                "regulated": regulated}
    if market in ("us", "ca"):
        steps = ["Right to work: employment-based visa or permanent "
                 "residence required — this is the binding constraint, not "
                 "the job market."]
        if regulated:
            steps += ["Credential evaluation of the foreign qualification.",
                      f"Examination: {prof['us_exam']}.",
                      f"Licensure: granted per state by the "
                      f"{prof['us_body']} — it does not transfer between "
                      f"states automatically.",
                      "English proficiency test typically required."]
        return {"market": market, "barrier": "high", "steps_en": steps,
                "practical_en": "Expect a process measured in many months to "
                                "years before you may legally work, whatever "
                                "the local shortage looks like.",
                "regulated": regulated}
    return {"market": market, "barrier": "unknown",
            "steps_en": ["Right to work and recognition rules for this market "
                         "are not carried in the platform."],
            "practical_en": "Not assessed — the platform does not guess at "
                            "immigration or licensing rules.",
            "regulated": regulated}


def _dim_score(dim: str, signals: dict) -> tuple[float | None, list, float]:
    spec = DIMENSIONS[dim]
    parts, weights, drivers = [], [], []
    for sid, w in spec["signals"]:
        row = signals.get(sid) or {}
        raw = row.get("value") if isinstance(row, dict) else row
        d = CATALOG.get(sid)
        if d is None or raw is None:
            continue
        n = normalize(d, raw)
        if n is None:
            continue
        parts.append(n * w)
        weights.append(w)
        drivers.append({"signal_id": sid, "value": raw,
                        "normalized": round(n, 4),
                        "source": (row.get("source")
                                   if isinstance(row, dict) else None)})
    wsum = sum(weights)
    total = sum(w for _, w in spec["signals"]) or 1.0
    return ((round(sum(parts) / wsum * 100, 2) if wsum else None),
            drivers, round(wsum / total, 4))


def score_place(household: str, signals: dict, *,
                job_demand: float | None = None,
                net_pay: float | None = None) -> dict:
    """Poängsätt en plats för ett hushåll. job_demand/net_pay 0–100."""
    if household not in HOUSEHOLDS:
        raise ValueError(f"unknown household: {household}. "
                         f"Choose {', '.join(HOUSEHOLDS)}")
    weights = HOUSEHOLDS[household]["weights"]
    dims, used_w, parts = {}, 0.0, 0.0
    for dim in DIMENSIONS:
        w = weights.get(dim, 0.0)
        if dim == "job_demand":
            sc, drivers, cov = job_demand, [], (1.0 if job_demand is not None
                                               else 0.0)
        elif dim == "net_pay":
            sc, drivers, cov = net_pay, [], (1.0 if net_pay is not None else 0.0)
        else:
            sc, drivers, cov = _dim_score(dim, signals)
        dims[dim] = {"dimension": dim, "label_en": DIMENSIONS[dim]["label_en"],
                     "means_en": DIMENSIONS[dim]["means_en"],
                     "score": sc, "weight": w, "coverage": cov,
                     "drivers": drivers}
        if sc is not None and w > 0:
            parts += sc * w
            used_w += w
    return {"score": round(parts / used_w, 2) if used_w else None,
            "weight_covered": round(used_w, 4),
            "dimensions": list(dims.values())}


def explain(place: dict, household: str) -> dict:
    """Vad som bär och vad som drar ned – för just det här hushållet."""
    dims = [d for d in place["dimensions"]
            if d["score"] is not None and d["weight"] > 0]
    dims.sort(key=lambda d: -(d["score"] * d["weight"]))
    strong = [d for d in dims if d["score"] >= 60][:3]
    weak = sorted([d for d in dims if d["score"] < 45],
                  key=lambda d: d["score"] * -d["weight"])[:3]
    return {
        "carries_en": ("Strongest for you: "
                       + ", ".join(f"{d['label_en'].lower()} ({d['score']:g})"
                                   for d in strong)
                       if strong else "Nothing scores strongly for you here."),
        "costs_en": ("Weakest for you: "
                     + ", ".join(f"{d['label_en'].lower()} ({d['score']:g})"
                                 for d in weak)
                     if weak else "No dimension scores poorly for you here."),
        "weighted_for_en": HOUSEHOLDS[household]["means_en"],
    }


LIMITS_EN = [
    "Right to work and professional recognition are summarised as process, "
    "not as a decision on your case — they are not legal advice.",
    "Language requirements are set by employers and patient-safety rules and "
    "are not scored here.",
    "Shift patterns, ward staffing and union agreements decide day-to-day "
    "working conditions; the platform has no feed for them and does not "
    "estimate them.",
    "A place that scores well on averages can still be wrong for one "
    "person — this ranks conditions, it does not know your life.",
    "Support for a child with additional needs is decided case by case by a "
    "school and a health authority. The platform scores CAPACITY in an area, "
    "never whether a specific child will be granted a specific support — no "
    "data source can tell you that.",
]


def caveats(measured_share: float) -> list[str]:
    out = list(LIMITS_EN)
    if measured_share < 0.999:
        out.insert(0, f"Only {measured_share:.0%} of the underlying values "
                      f"come from a connected real source; the rest are "
                      f"simulated and labelled source=\"mock\". Treat the "
                      f"ordering as a method demonstration until the "
                      f"sources are connected.")
    return out


def framing(household: str, occupation: str) -> dict:
    return framing_disclosure({
        "weighted_for": household, "occupation": occupation,
        "ranks": "conditions, not outcomes",
        "not_legal_advice": True, "not_causal": True})
