"""Målgruppsmotorn – segmentanalys på samma signallager.

Besvarar två frågor:
  1. "Hur ser målgrupperna ut i Umeå?"  → segmentprofil för en region
  2. "Var finns flest djurägare?"       → segmentkarta över marknaden

Segment är data (SEGMENTS): ett segment definieras av en signal, ett
beräkningsläge och vilka vertikaler som betjänar det. Nytt segment =
ny rad. Antal är UPPSKATTNINGAR härledda ur signalvärden × befolkning
och märks så; indexet jämför regionen mot marknadssnittet (beräknat
över marknadens regioner med samma källkedja – deterministiskt).

Kopplingen till affären: varje segment pekar på vertikaler, så en hög
djurägartäthet leder direkt vidare till veterinärsvep, gap-analys och
etableringsplan i samma plattform.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.mock import MockSource
from .markets import DEFAULT_MARKET, get_market, get_region
from .models import Location
from .verticals import VERTICALS

_DEFAULT_RESOLVER = Resolver([MockSource()])


@dataclass(frozen=True)
class SegmentDef:
    id: str
    label_en: str
    beskrivning_en: str
    signal: str
    mode: str            # "per_1000" | "share_pct" | "count" | "index"
    enhet_en: str
    verticals: tuple     # vertikaler som betjänar segmentet


SEGMENTS: dict[str, SegmentDef] = {s.id: s for s in [
    SegmentDef("djuragare", "Pet owners",
               "Households with pets – estimated from pet density.",
               "pets_per_1000", "per_1000", "pets",
               ("veterinar",)),
    SegmentDef("barnfamiljer", "Families with children",
               "Share of households with children.",
               "families_share", "share_pct", "people",
               ("tandlakare", "frisor", "gym")),
    SegmentDef("seniorer", "Seniors (65+)",
               "Share of the population aged 65 or older.",
               "share_65plus", "share_pct", "people",
               ("tandlakare", "frisor")),
    SegmentDef("unga_vuxna", "Young adults (20–45)",
               "Share of the population aged 20–45.",
               "age_20_45_share", "share_pct", "people",
               ("gym", "cafe", "restaurang")),
    SegmentDef("bilagare", "Car owners",
               "Cars per resident – a proxy for car-owning households.",
               "cars_per_1000", "per_1000", "cars",
               ("bilverkstad",)),
    SegmentDef("pendlare", "Commuters",
               "People in the morning and evening commuter flow.",
               "commuter_flow", "count", "people",
               ("cafe", "gym")),
    SegmentDef("villaagare", "Detached-home owners",
               "Detached and single-family homes in the catchment area.",
               "detached_homes", "count", "households",
               ("elektriker", "vvs", "bygg")),
    SegmentDef("hoginkomsttagare", "High-income earners",
               "Income level relative to the national average (index).",
               "income_index", "index", "index",
               ("frisor", "restaurang", "tandlakare")),
    SegmentDef("foretagare", "Business owners",
               "Businesses per 1,000 residents.",
               "business_density", "per_1000", "businesses",
               ("lager", "elektriker", "vvs")),
    SegmentDef("besokare", "Visitors & tourists",
               "Tourism and visitor intensity (index).",
               "tourism_index", "index", "index",
               ("restaurang", "cafe")),
]}


def segment_catalog() -> list[dict[str, Any]]:
    return [{"id": s.id, "label_en": s.label_en,
             "beskrivning_en": s.beskrivning_en,
             "betjanas_av": [VERTICALS[v].label_en for v in s.verticals]}
            for s in SEGMENTS.values()]


def _needed_signals() -> list[str]:
    return sorted({s.signal for s in SEGMENTS.values()} | {"population_total"})


def _resolve_market(market: str, resolver: Resolver | None
                    ) -> dict[str, dict[str, float]]:
    """{region_kod: {signal: värde}} för hela marknaden (för snitt)."""
    res = resolver or _DEFAULT_RESOLVER
    needed = _needed_signals()
    out: dict[str, dict[str, float]] = {}
    for code, name, lat, lon in get_market(market).regions:
        values, _ = res.resolve(Location(lat, lon, address=name),
                                "segments", needed)
        out[code] = {sid: sv.value for sid, sv in values.items()
                     if sv.value is not None}
    return out


def _estimate(seg: SegmentDef, value: float, pop: float) -> int | None:
    if seg.mode == "per_1000":
        return int(round(value * pop / 1000))
    if seg.mode == "share_pct":
        return int(round(value / 100 * pop))
    if seg.mode == "count":
        return int(round(value))
    return None                                     # index-segment


def _index_band(index: float) -> str:
    if index >= 120:
        return "mycket_over_snittet"
    if index >= 105:
        return "over_snittet"
    if index >= 95:
        return "kring_snittet"
    return "under_snittet" if index >= 80 else "langt_under_snittet"

_BAND_SV = {"mycket_over_snittet": "well above average",
            "over_snittet": "above average", "kring_snittet": "around average",
            "under_snittet": "below average",
            "langt_under_snittet": "far below average"}


def segment_analysis(kommun_kod: str, market: str = DEFAULT_MARKET,
                     resolver: Resolver | None = None) -> dict[str, Any]:
    """Målgruppsprofil för en region: alla segment med antal och index."""
    mkt = get_market(market)
    kod, namn, *_ = get_region(market, kommun_kod)
    data = _resolve_market(market, resolver)
    region = data[kod]
    pop = region.get("population_total", 0.0)

    rows = []
    for seg in SEGMENTS.values():
        value = region.get(seg.signal)
        if value is None:
            continue
        vals = [d[seg.signal] for d in data.values() if seg.signal in d]
        avg = sum(vals) / len(vals)
        index = round(value / avg * 100) if avg else 100
        rows.append({
            "segment_id": seg.id, "label_en": seg.label_en,
            "antal_uppskattat": _estimate(seg, value, pop),
            "enhet_en": seg.enhet_en,
            "varde": value,
            "index_mot_marknadssnitt": index,
            "band": _index_band(index),
            "narrativ_en": f"{seg.label_en}: {_BAND_SV[_index_band(index)]} "
                           f"(index {index}).",
            "betjanas_av": [{"vertical_id": v,
                             "label_en": VERTICALS[v].label_en}
                            for v in seg.verticals],
        })
    rows.sort(key=lambda r: -r["index_mot_marknadssnitt"])
    topp = rows[0]
    return {
        "kommun": namn, "kommun_kod": kod,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "befolkning": int(pop),
        "segment": rows,
        "sammanfattning_en": (
            f"Most distinctive target group in {namn}: "
            f"{topp['label_en'].lower()} (index "
            f"{topp['index_mot_marknadssnitt']} vs the market average)."),
        "caveats_en": [
            "Counts are estimates derived from signal values × population "
            "– not registers. The index compares against the average of "
            "the market's analyzed regions.",
        ],
    }


def segment_map(segment_id: str, market: str = DEFAULT_MARKET,
                resolver: Resolver | None = None,
                top_n: int = 5) -> dict[str, Any]:
    """Segmentkarta: var på marknaden finns segmentet – antal + index."""
    seg = SEGMENTS.get(segment_id)
    if seg is None:
        raise ValueError(f"Unknown segment: {segment_id}. "
                         f"Available: {', '.join(sorted(SEGMENTS))}")
    mkt = get_market(market)
    data = _resolve_market(market, resolver)
    vals = [d[seg.signal] for d in data.values() if seg.signal in d]
    avg = sum(vals) / len(vals) if vals else 1.0

    rows = []
    for code, name, lat, lon in mkt.regions:
        d = data[code]
        value = d.get(seg.signal)
        if value is None:
            continue
        index = round(value / avg * 100) if avg else 100
        band = _index_band(index)
        rows.append({"kommun": name, "kommun_kod": code,
                     "lat": lat, "lon": lon,
                     "antal_uppskattat": _estimate(
                         seg, value, d.get("population_total", 0.0)),
                     "varde": value, "index": index, "band": band})
    nyckel = ("antal_uppskattat" if seg.mode != "index" else "index")
    rows.sort(key=lambda r: -(r[nyckel] or 0))

    return {
        "segment_id": seg.id, "label_en": seg.label_en,
        "beskrivning_en": seg.beskrivning_en,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "bbox": list(mkt.bbox),
        "regioner": rows,
        "heatmap": [{"kommun": r["kommun"], "kommun_kod": r["kommun_kod"],
                     "lat": r["lat"], "lon": r["lon"], "score": r["index"],
                     "band": ("gron" if r["index"] >= 110 else
                              "gul" if r["index"] >= 90 else "rod")}
                    for r in rows],
        "sammanfattning_en": (
            f"Most {seg.label_en.lower()} in {mkt.label_en}: "
            + ", ".join(r["kommun"] for r in rows[:min(3, len(rows))])
            + ". Primarily served by "
            + ", ".join(VERTICALS[v].label_en.lower() for v in seg.verticals)
            + "."),
        "betjanas_av": [{"vertical_id": v, "label_en": VERTICALS[v].label_en}
                        for v in seg.verticals],
        "caveats_en": [
            "Counts are estimates from signal values × population; "
            "the index compares against the market average.",
        ],
    }
