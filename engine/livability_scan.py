"""Livsvillkorsfrågan körd över marknader: var kan just det här hushållet
bygga ett bra liv?

Hämtar per region: efterfrågan på yrket (bristprognosen), nettolön efter
skatt för marknaden, och livsvillkorssignalerna. Väger ihop dem med
hushållets vikter och rangordnar – men lämnar ALLTID tillbaka hindret
(rätt att arbeta, erkännande av legitimation) tillsammans med varje
marknad, eftersom det avgör före allt annat.
"""
from __future__ import annotations

from .datasources.base import Resolver
from .datasources.faults import OUR_BUGS
from .livability import (DIMENSIONS, HOUSEHOLDS, caveats, explain, framing,
                         mobility, score_place)
from .markets import MARKETS, get_market
from .models import Location
from .stats import minmax
from .wages import FX_PER_SEK, PPP_CAVEAT, wage
from .workforce import national_map

_SIGNALS = sorted({sid for spec in DIMENSIONS.values()
                   for sid, _ in spec["signals"]})

_FALLBACK = None


def _resolver(r: Resolver | None) -> Resolver:
    global _FALLBACK
    if r is not None:
        return r
    if _FALLBACK is None:
        from .datasources.mock import MockSource
        _FALLBACK = Resolver([MockSource()])
    return _FALLBACK


def _net_pay_common(occupation: str, market: str) -> tuple[float | None, dict]:
    """Nettolön omräknad till EN gemensam valuta (SEK).

    Utan omräkning jämförs 27 200 SEK med 4 000 USD som om de vore samma
    tal – marknader kan då inte rangordnas alls. Kursen är den dokumenterade
    schablonen i löneenginen, och omräkningen är INTE köpkraftsjusterad;
    det står i svarets caveats.
    """
    try:
        w = wage(occupation, market)
    except OUR_BUGS:
        # wage() är vår egen kod: ett AttributeError där betydde
        # "marknad utan löneunderlag", och marknaden föll tyst ur
        # rankingen — en trasig lönemotor såg ut som tunn data.
        raise
    except Exception:  # noqa: BLE001 – marknad utan löneunderlag
        return None, {}
    net = w.get("net_monthly")
    if net is None:
        return None, w
    rate = FX_PER_SEK.get(w.get("currency", "SEK"))
    if not rate:
        return None, w
    return float(net) / rate, w


def livability_ranking(occupation: str, household: str, *,
                       markets: list[str] | None = None,
                       top_n: int = 10, per_market: int = 12,
                       citizenship: str = "eu",
                       resolver: Resolver | None = None) -> dict:
    """Rangordna platser för ett hushåll, över en eller flera marknader."""
    if household not in HOUSEHOLDS:
        raise ValueError(f"unknown household: {household}. "
                         f"Choose {', '.join(HOUSEHOLDS)}")
    markets = markets or ["se"]
    res = _resolver(resolver)

    # Nettolön per marknad, normaliserad mot varandra (samma valuta via
    # löneenginens omräkning) – annars kan marknader inte jämföras.
    pays, wage_rows = {}, {}
    for m in markets:
        val, row = _net_pay_common(occupation, m)
        wage_rows[m] = row
        if val is not None:
            pays[m] = val
    lo, hi = (min(pays.values()), max(pays.values())) if pays else (0.0, 0.0)

    rows, mock, total = [], 0, 0
    barriers = {m: mobility(occupation, m, citizenship=citizenship)
                for m in markets}

    for m in markets:
        if m not in MARKETS:
            continue
        mkt = get_market(m)
        nm = national_map(occupation, market=m)
        shortage = {k["kommun_kod"]: k.get("brist") or 0
                    for k in nm.get("kommuner", [])}
        smax = max(shortage.values()) if shortage else 0
        # minmax ger redan 0–100 – multiplicera inte igen.
        pay_score = (minmax(pays[m], lo, hi) if m in pays and hi > lo
                     else (70.0 if m in pays else None))

        for code, name, lat, lon in mkt.regions[:per_market]:
            got, _ = res.resolve(Location(lat, lon), "generisk", _SIGNALS)
            signals = {}
            for sid, sv in got.items():
                src = getattr(sv, "source", None)
                signals[sid] = {"value": getattr(sv, "value", None),
                                "source": src}
                total += 1
                if src == "mock":
                    mock += 1
            jd = minmax(shortage.get(code, 0), 0, smax) if smax else None
            sc = score_place(household, signals, job_demand=jd,
                             net_pay=pay_score)
            if sc["score"] is None:
                continue
            rows.append({
                "market": m, "market_label_en": mkt.label_en,
                "region": name, "region_code": code,
                "score": sc["score"], "weight_covered": sc["weight_covered"],
                "dimensions": sc["dimensions"],
                **explain(sc, household),
                "mobility": barriers[m],
            })

    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    measured = 1.0 - (mock / total if total else 0.0)

    return {
        "occupation": occupation, "household": household,
        "household_label_en": HOUSEHOLDS[household]["label_en"],
        "weighted_for_en": HOUSEHOLDS[household]["means_en"],
        "markets": markets,
        # Hindret först: det avgör före varje poäng i listan.
        "before_you_compare_en": [
            f"{barriers[m]['market'].upper()}: barrier {barriers[m]['barrier']}"
            f" — {barriers[m]['practical_en']}" for m in markets],
        "mobility": barriers,
        "ranking": rows[:top_n], "assessed": len(rows),
        # Bäst OCH sämst. Att bara visa toppen är att välja åt läsaren;
        # datan säger båda och båda redovisas.
        "worst": rows[-min(top_n, 5):][::-1] if rows else [],
        "spread_en": (f"Best {rows[0]['region']} ({rows[0]['score']:g}) — "
                      f"worst {rows[-1]['region']} ({rows[-1]['score']:g}) "
                      f"of {len(rows)} places assessed. This is what the data "
                      f"says on your weighting; take it or leave it."
                      if rows else "Nothing could be assessed."),
        "wages": wage_rows,
        "measured_share": round(measured, 4),
        "caveats_en": [PPP_CAVEAT] + caveats(measured),
        "framing": framing(household, occupation),
    }
