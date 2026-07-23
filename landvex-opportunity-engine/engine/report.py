"""Decision Report – ett samlat beslutsunderlag från alla motorer.

En fråga ("ska vi etablera X i Y?") kräver i praktiken svar från flera
motorer. /v1/report komponerar dem deterministiskt till EN rapport:
opportunity-analys, riskprofil, etableringsplan, målgrupper,
servicebehov och stadens alla index – med gemensam engine_version och
unionen av alla caveats. Ingen ny analys görs här: samma motorer, samma
ärlighetsprinciper, bara komposition (API-first: en agent eller klient
kan hämta hela underlaget i ett anrop).
"""
from __future__ import annotations

from typing import Any

from .datasources.base import Resolver
from .indices import city_assessment
from .installed_base import service_analysis
from .markets import DEFAULT_MARKET, get_market, get_region
from .models import Location
from .plan import establishment_plan
from .risk import assess
from .scoring import analyze
from .segments import segment_analysis
from .verticals import VERTICALS
from .version import ENGINE_VERSION


def decision_report(kommun_kod: str, vertical_id: str,
                    market: str = DEFAULT_MARKET,
                    resolver: Resolver | None = None) -> dict[str, Any]:
    """Komplett beslutsunderlag för en vertikal i en region."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    mkt = get_market(market)
    kod, namn, lat, lon = get_region(market, kommun_kod)
    loc = Location(lat, lon, address=namn)

    analysis = analyze(loc, vertical_id, resolver=resolver).to_dict() \
        if resolver is not None else analyze(loc, vertical_id).to_dict()
    risk = assess(loc, vertical_id, resolver=resolver) \
        if resolver is not None else assess(loc, vertical_id)
    plan = establishment_plan(kod, vertical_id, market=market)
    segments = segment_analysis(kod, market=market, resolver=resolver) \
        if resolver is not None else segment_analysis(kod, market=market)
    service = service_analysis(kod, market=market, resolver=resolver) \
        if resolver is not None else service_analysis(kod, market=market)
    indices = city_assessment(kod, market=market, resolver=resolver) \
        if resolver is not None else city_assessment(kod, market=market)

    caveats: list[str] = []
    for block in (analysis.get("caveats_en"), risk.get("caveats_en"),
                  plan.get("caveats_en"), segments.get("caveats_en"),
                  service.get("caveats_en"), indices.get("caveats_en")):
        for c in block or []:
            if c not in caveats:
                caveats.append(c)

    score = analysis.get("opportunity_score", 0)
    return {
        "kommun": namn, "kommun_kod": kod,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "vertical": vertical_id,
        "vertical_label_en": VERTICALS[vertical_id].label_en,
        "sammanfattning_en": (
            f"Decision report for {VERTICALS[vertical_id].label_en.lower()} "
            f"in {namn}: opportunity score {round(score)}/100, "
            f"total risk {round(risk.get('total_risk', 0))}/100, "
            f"total investment {plan['investering_tkr']['totalt'][0]}–"
            f"{plan['investering_tkr']['totalt'][1]} k{plan['currency']} "
            f"(standard estimate)."),
        "analysis": analysis,
        "risk": risk,
        "plan": plan,
        "segments": segments,
        "service": service,
        "indices": indices,
        "caveats_en": caveats,
        "engine_version": ENGINE_VERSION,
    }
