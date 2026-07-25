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
    return {
        "occupation": code, "label_en": o.label_en, "sector_en": o.sector_en,
        "market": market, "currency": cur,
        "monthly_wage": monthly, "annual_wage": monthly * 12,
        "source": "schablon", "official_source_when_connected":
            OFFICIAL_SOURCES.get(market, OFFICIAL_SOURCES["world"]),
        "caveat": PPP_CAVEAT,
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
