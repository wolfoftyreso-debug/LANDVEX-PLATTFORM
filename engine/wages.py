"""Löneregister – standardlön per standardyrke, över marknader.

Bygger på det befintliga yrkesregistret (`workforce.OCCUPATIONS`, med
svenska löneankare ur lönestatistiknivå) och lägger ett jämförelselager:
slå upp en yrkeslön i valfri marknad och jämför över marknader.

ÄRLIGHET (princip 4): den svenska lönen är ett schablonankare på
lönestatistiknivå; övriga marknader härleds via DOKUMENTERADE FX-kurser –
det är INTE riktiga lokala löner och INTE köpkraftsjusterat (PPP). Varje
svar märks därför `source="schablon"` med en PPP-caveat. Riktiga lokala
löner kommer via adaptrar mot de offentliga registren (SCB
Lönestrukturstatistik, US BLS OES, Eurostat earnings, ILOSTAT) i samma
Resolver-mönster – de överskrider schablonen per marknad när de kopplas.

Rent stdlib.
"""
from __future__ import annotations

from .integrity import framing_disclosure
from .markets import DEFAULT_MARKET, FX_PER_SEK, MARKETS
from .stats import mean, percentile_rank
from .workforce import OCCUPATIONS

# Offentliga register som fyller på riktiga lokala löner (adapter-kandidater).
OFFICIAL_SOURCES = {
    "se": "SCB Lönestrukturstatistik (SSYK)",
    "us": "US BLS Occupational Employment and Wage Statistics (SOC)",
    "eu": "Eurostat earnings (ISCO)",
    "world": "ILOSTAT (ISCO-08)",
}
PPP_CAVEAT = ("Swedish wage anchor converted via documented FX — NOT real "
              "local wages and NOT purchasing-power adjusted. A schablon until "
              "the local official register is connected.")


# Effektiv skattekil (inkomstskatt + anställdas sociala avgifter som andel av
# brutto) – schablon per marknad. INTE 100%+ (personlig take-home-skatt ligger
# långt under det); riktiga progressiva tabeller ersätter detta via adapter.
TAX_WEDGE: dict[str, float] = {
    "se": 0.32, "no": 0.34, "dk": 0.36, "fi": 0.30, "de": 0.39, "fr": 0.30,
    "nl": 0.34, "be": 0.40, "at": 0.33, "it": 0.31, "es": 0.24, "pt": 0.26,
    "pl": 0.25, "cz": 0.23, "ie": 0.26, "us": 0.24, "ca": 0.25, "mx": 0.11,
    "co": 0.10, "ma": 0.12, "ng": 0.08, "sn": 0.10,
}
DEFAULT_TAX = 0.20


def tax_rate(market: str) -> float:
    return TAX_WEDGE.get(market, DEFAULT_TAX)


def _currency(market: str) -> str:
    m = MARKETS.get(market)
    if m is None:
        raise ValueError(f"unknown market: {market}")
    return m.currency


def wage_catalog() -> list[dict]:
    """Alla standardyrken med svenskt löneankare (SEK/mån)."""
    return [{"code": o.id, "label_en": o.label_en, "sector_en": o.sector_en,
             "se_monthly_sek": int(o.salary_tkr_month * 1000)}
            for o in OCCUPATIONS.values()]


def wage(code: str, market: str = DEFAULT_MARKET) -> dict:
    """Standardlön för ett yrke i en marknad (schablon via FX)."""
    o = OCCUPATIONS.get(code)
    if o is None:
        raise ValueError(f"unknown occupation: {code}")
    cur = _currency(market)
    monthly_sek = o.salary_tkr_month * 1000.0
    fx = FX_PER_SEK.get(cur, 1.0)
    monthly = round(monthly_sek * fx)
    rate = tax_rate(market)
    net = round(monthly * (1 - rate))
    return {
        "occupation": code, "label_en": o.label_en, "sector_en": o.sector_en,
        "market": market, "currency": cur,
        "monthly_wage": monthly, "annual_wage": monthly * 12,
        "tax_rate": rate, "net_monthly": net, "net_annual": net * 12,
        "take_home_pct": round((1 - rate) * 100, 1),
        "source": "schablon", "official_source_when_connected":
            OFFICIAL_SOURCES.get(market, OFFICIAL_SOURCES["world"]),
        "caveat": PPP_CAVEAT + " Tax is an effective-wedge schablon per market "
                  "(income tax + employee social contributions), not a "
                  "progressive per-income calculation.",
        "framing": framing_disclosure(
            {"anchor": "SE wage statistics", "conversion": f"FX SEK→{cur}",
             "ppp_adjusted": False, "note": "schablon, not real local wages"}),
    }


def compare(code: str, markets: list[str]) -> dict:
    """Jämför ett yrkes standardlön över marknader. Normaliserar till USD för
    rangordning (schablon via FX), med tydlig PPP-caveat."""
    o = OCCUPATIONS.get(code)
    if o is None:
        raise ValueError(f"unknown occupation: {code}")
    rows = []
    for mk in markets:
        w = wage(code, mk)
        usd = round(o.salary_tkr_month * 1000.0 * FX_PER_SEK.get("USD", 0.095))
        rows.append({"market": mk, "currency": w["currency"],
                     "monthly_wage": w["monthly_wage"], "monthly_usd": usd})
    rows.sort(key=lambda r: -r["monthly_usd"])
    return {
        "occupation": code, "label_en": o.label_en, "markets": rows,
        "note": "Ranked by FX-converted USD (schablon). PPP would change the "
                "order — a high nominal wage can buy less locally.",
        "caveat": PPP_CAVEAT,
        "framing": framing_disclosure(
            {"normalised_to": "USD via FX", "ppp_adjusted": False,
             "note": "nominal comparison, not cost-of-living adjusted"}),
    }


# --- Kompensations-kontext: nominell lön ≠ verklig position ----------------
# In natura-förmåner och dolda kostnader som gör en rå lönejämförelse
# vilseledande. Data (illustrativ/schablon); utökas per yrke×region. `+` höjer
# den verkliga ersättningen, `-` sänker den.
COMP_CONTEXT: tuple[dict, ...] = (
    {"occupation": "factory", "region": "cn", "factor": "housing_included",
     "direction": "+", "note": "Employer dormitory housing is common — real "
     "compensation exceeds the cash wage."},
    {"occupation": "factory", "region": "us", "factor": "housing_not_included",
     "direction": "0", "note": "No employer housing (e.g. Detroit) — the cash "
     "wage must cover rent."},
    {"occupation": "mechanic", "region": "us", "factor": "tools_self_provided",
     "direction": "-", "note": "Mechanics typically buy their own tools "
     "(thousands of USD) — a real cost against the wage."},
    {"occupation": "mechanic", "region": "se", "factor": "tools_employer_provided",
     "direction": "+", "note": "Employer provides tools — no personal outlay."},
    {"occupation": "wait", "region": "do", "factor": "pays_to_work",
     "direction": "-", "note": "May pay for a shift slot at a beach bar."},
    {"occupation": "wait", "region": "do", "factor": "tips_commission",
     "direction": "+", "note": "Commission on everything sold — income well "
     "beyond the base wage."},
    {"occupation": "wait", "region": "us", "factor": "tips",
     "direction": "+", "note": "Tips are a large share of take-home."},
)


# Arbetsintensitet: hur mycket som faktiskt krävs per betald timme. Låg lön
# med mest väntan kan vara en bättre affär per ansträngning än hög lön med
# krav på produktion varje minut. `intensity` ∈ low|moderate|high.
LABOR_CONTEXT: tuple[dict, ...] = (
    {"occupation": "wait", "region": "th", "intensity": "low",
     "note": "Often idle between occasional customers — effort per paid hour "
     "is low."},
    {"occupation": "restaurant", "region": "th", "intensity": "low",
     "note": "Downtime is common; presence, not constant output, is expected."},
    {"occupation": "wait", "region": "us", "intensity": "high",
     "note": "Organized chain — expected to produce every minute of presence."},
    {"occupation": "restaurant", "region": "us", "intensity": "high",
     "note": "Chain productivity targets — continuous output during the shift."},
    {"occupation": "factory", "region": "cn", "intensity": "high",
     "note": "Line pace sets output; little idle time."},
)


def compensation_context(occupation: str, region: str) -> dict:
    """Icke-kontanta förmåner/kostnader OCH arbetsintensitet som gör en rå
    lönejämförelse vilseledande (boende, egna verktyg, dricks/provision,
    betala-för-passet; och hur mycket som krävs per betald timme).

    Matchar löst på yrkessträng + region. Returnerar faktorer, netto-riktning,
    arbetsintensitet och en tydlig caveat.
    """
    q = (occupation or "").lower()
    def _match(table):
        return [c for c in table
                if (c["occupation"] in q or q in c["occupation"])
                and c["region"] == region.lower()]
    rows = _match(COMP_CONTEXT)
    intensity_rows = _match(LABOR_CONTEXT)
    plus = sum(1 for c in rows if c["direction"] == "+")
    minus = sum(1 for c in rows if c["direction"] == "-")
    net = "higher" if plus > minus else "lower" if minus > plus else "mixed/neutral"
    intensity = intensity_rows[0]["intensity"] if intensity_rows else "unknown"
    return {
        "occupation": occupation, "region": region, "factors": rows,
        "net_real_vs_nominal": net if rows else "no context on record",
        "labor_intensity": intensity,
        "intensity_notes": [c["note"] for c in intensity_rows],
        "caveat": ("Nominal wage is not real compensation, and not the same "
                   "effort. In-kind housing, self-provided tools, tips/"
                   "commission and pay-to-work move the real cash position; "
                   "work intensity (idle waiting vs producing every minute) "
                   "moves the wage-per-effort. Compare both before wages."),
    }


def rank_by_wage(market: str = DEFAULT_MARKET, top: int = 0) -> dict:
    """Rangordna yrkena efter standardlön i en marknad."""
    rows = sorted((wage(o.id, market) for o in OCCUPATIONS.values()),
                  key=lambda w: -w["monthly_wage"])
    salaries = [o.salary_tkr_month for o in OCCUPATIONS.values()]
    for r in rows:
        anchor = OCCUPATIONS[r["occupation"]].salary_tkr_month
        r["percentile"] = round(percentile_rank(anchor, salaries), 1)
    return {"market": market, "currency": _currency(market),
            "median_monthly": round(mean([r["monthly_wage"] for r in rows])),
            "occupations": rows[:top] if top else rows,
            "caveat": PPP_CAVEAT}
