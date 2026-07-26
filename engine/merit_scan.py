"""Meritfrågan körd mot en marknad: vilka kommuner presterar mätbart bäst?

Hämtar signalbilden per region ur källkedjan och lämnar den till
`engine.merit`, som rangordnar på samma bevisregler som används när
plattformen ifrågasätter en plats.
"""
from __future__ import annotations

from .datasources.base import Resolver
from .markets import get_market
from .merit import DIMENSIONS, merit, rank
from .models import Location

# Alla signaler som meritdimensionerna behöver.
_NEEDED = sorted({sid for spec in DIMENSIONS.values()
                  for sid, _ in spec["signals"]})


def _signals(lat: float, lon: float, resolver: Resolver | None) -> dict:
    res = resolver or _fallback()
    got, _ = res.resolve(Location(lat, lon), "generisk", _NEEDED)
    return {sid: {"value": getattr(sv, "value", None),
                  "source": getattr(sv, "source", None)}
            for sid, sv in got.items()}


_FALLBACK = None


def _fallback() -> Resolver:
    global _FALLBACK
    if _FALLBACK is None:
        from .datasources.mock import MockSource
        _FALLBACK = Resolver([MockSource()])
    return _FALLBACK


def market_merit(market: str = "se", *, top_n: int = 10,
                 resolver: Resolver | None = None) -> dict:
    """Rangordna en marknads regioner på näringslivsförmåga."""
    mkt = get_market(market)
    regions = [{"code": code, "name": name,
                "signals": _signals(lat, lon, resolver)}
               for code, name, lat, lon in mkt.regions]
    out = rank(regions, top_n=top_n)
    out["market"] = market
    out["market_label_en"] = mkt.label_en
    return out


def region_merit(region_query: str, market: str = "se", *,
                 resolver: Resolver | None = None) -> dict:
    """En plats näringslivsförmåga, jämförd med marknadens övriga."""
    mkt = get_market(market)
    target = None
    for r in mkt.regions:
        if r[1].lower() == region_query.lower() or r[0] == region_query:
            target = r
            break
    if target is None:
        raise ValueError(f"Region not covered: {region_query}.")

    from .merit import dimension_scores
    peer_scores: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for code, name, lat, lon in mkt.regions:
        if code == target[0]:
            continue
        for did, d in dimension_scores(_signals(lat, lon, resolver)).items():
            if d["score"] is not None:
                peer_scores[did].append(d["score"])

    code, name, lat, lon = target
    return merit(code, name, _signals(lat, lon, resolver),
                 peer_scores=peer_scores)
