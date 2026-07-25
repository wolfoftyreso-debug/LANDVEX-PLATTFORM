"""Mättnadsfrågan körd mot en marknad – "hur mättad är X i Y?".

Binder ihop `engine.saturation` med marknads- och signallagret: hämtar
utbudet (register först, uppskattning som märkt fallback), befolkningen och
konkurrenssignalen för regionen OCH för dess jämförelsegrupp, och lämnar
tillbaka ett svar med percentil, band och vad som skulle krävas för att nå
gruppens median.

Jämförelsegruppen är andra regioner i samma marknad. Det är medvetet: en
förort ska jämföras med jämförbara kommuner, inte med riksgenomsnittet där
storstäderna drar iväg.

Rent stdlib (bygger på befintliga motorer).
"""
from __future__ import annotations

from .datasources.base import Resolver
from .markets import get_market
from .models import Location
from .registers import RegisterClient
from .saturation import saturation, supply_for
from .scoring import analyze


def _signals_for(lat: float, lon: float, vertical: str,
                 resolver: Resolver | None) -> dict:
    """Befolkning + konkurrenstryck för en punkt, ur signallagret."""
    loc = Location(lat, lon)
    rep = analyze(loc, vertical, resolver=resolver)
    sig = rep.signals or {}

    def val(name):
        row = sig.get(name)
        return row.get("value") if isinstance(row, dict) else row

    # analyze returnerar bara de signaler branschens faktorer använder.
    # Befolkningen behövs för normeringen oavsett bransch, så den hämtas
    # direkt ur källkedjan.
    population = val("population_total")
    if population is None:
        res = resolver or _default_resolver()
        got, _ = res.resolve(loc, vertical, ["population_total"])
        row = got.get("population_total")
        population = getattr(row, "value", None)

    return {"population": population,
            "competition_pressure": val("competition_pressure"),
            "demand_index": rep.opportunity_score,
            "source": (sig.get("competition_pressure") or {}).get("source")}


_FALLBACK_RESOLVER = None


def _default_resolver() -> Resolver:
    """Mock-kedjan när ingen resolver skickats in (test/CLI)."""
    global _FALLBACK_RESOLVER
    if _FALLBACK_RESOLVER is None:
        from .datasources.mock import MockSource
        _FALLBACK_RESOLVER = Resolver([MockSource()])
    return _FALLBACK_RESOLVER


def market_saturation(vertical: str, region_query: str, *,
                      market: str = "se", resolver: Resolver | None = None,
                      client: RegisterClient | None = None,
                      peer_limit: int = 25) -> dict:
    """Mättnad för en bransch i en region, jämförd med marknadens övriga."""
    mkt = get_market(market)
    target = None
    for r in mkt.regions:
        if r[1].lower() == region_query.lower() or r[0] == region_query:
            target = r
            break
    if target is None:
        raise ValueError(
            f"Region not covered: {region_query}. "
            f"{market.upper()} currently has {len(mkt.regions)} regions.")

    client = client or RegisterClient()
    code, name, lat, lon = target
    t = _signals_for(lat, lon, vertical, resolver)
    supply = supply_for(vertical, market, code,
                        population=t["population"] or 0,
                        competition_pressure=t["competition_pressure"],
                        client=client)

    peers = []
    for r in mkt.regions:
        if r[0] == code:
            continue
        if len(peers) >= peer_limit:
            break
        p = _signals_for(r[2], r[3], vertical, resolver)
        s = supply_for(vertical, market, r[0],
                       population=p["population"] or 0,
                       competition_pressure=p["competition_pressure"],
                       client=client)
        if s.get("count") is not None and p["population"]:
            peers.append({"name": r[1], "count": s["count"],
                          "population": p["population"]})

    return saturation(vertical, code, name,
                      population=t["population"] or 0, supply=supply,
                      peers=peers, country=market,
                      demand_index=t.get("demand_index"))
