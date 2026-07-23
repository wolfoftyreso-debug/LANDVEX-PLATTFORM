"""Index Engine – Intelligence Map-lagren.

Speglar Landvex-plattformens kartprodukt: fem index per stad/region
(Infrastructure Risk, Commercial Activity, Safety, Climate Risk,
Urban Growth) plus Kontradiktionsindexet – allt "sourced & traceable":
varje indexvärde bär sin signalnedbrytning med källa per rad.

Index är data (INDEX_TYPES): signaler + vikter + riktning
("risk" = högt är dåligt, "styrka" = högt är bra) + nivå (free/live).
Nytt index = ny rad.

KONTRADIKTIONSINDEXET är plattformens signatur: divergensen mellan
officiellt planerat (bygglov, detaljplaner) och faktiskt observerat
(exploatering, renovering). Hög divergens = officiella bilden och
verkligheten pekar åt olika håll – flaggas "kontradiktion upptäckt".
Precisionen stiger kraftigt när quiXzoom-observationslagret ansluts
(adapterstub finns i källkedjan); tills dess beräknas divergensen på
samma signalbild och märks därefter.

Banden följer kartlegenden: låg/måttlig/förhöjd/hög operativ risk
(grön/gul/orange/röd).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.mock import MockSource
from .markets import get_market, get_region
from .models import Location
from .signals import CATALOG, normalize

_DEFAULT_RESOLVER = Resolver([MockSource()])


@dataclass(frozen=True)
class IndexDef:
    id: str
    label_en: str
    beskrivning_en: str
    riktning: str          # "risk" | "styrka"
    niva: str              # "free" | "live"
    signals: tuple         # ((signal_id, vikt), ...)


INDEX_TYPES: dict[str, IndexDef] = {i.id: i for i in [
    IndexDef("infrastructure_risk", "Infrastructure Risk",
             "Risk of neglected infrastructure: low public investment, "
             "weak public transport, low development pace.",
             "risk", "free",
             (("infra_invest", 0.4), ("transit_score", 0.3),
              ("development_m2", 0.3))),
    IndexDef("commercial_activity", "Commercial Activity",
             "The pulse of the business community: business density, "
             "flows and office workplaces.",
             "styrka", "free",
             (("business_density", 0.4), ("foot_traffic", 0.3),
              ("office_workers", 0.3))),
    IndexDef("safety_index", "Safety Index",
             "Safety level based on the crime index (higher = safer).",
             "styrka", "free",
             (("crime_index", 1.0),)),
    IndexDef("climate_risk", "Climate Risk",
             "Physical climate risk exposure (flooding, heat, landslides).",
             "risk", "free",
             (("climate_risk_index", 1.0),)),
    IndexDef("urban_growth", "Urban Growth",
             "Growth momentum: population, building permits and "
             "development.",
             "styrka", "live",
             (("pop_growth_pct", 0.4), ("building_permits", 0.3),
              ("development_m2", 0.3))),
]}

# Kontradiktionsindexet: officiellt planerat vs observerat utfört.
_PLANNED = (("building_permits", 0.5), ("detail_plans", 0.5))
_OBSERVED = (("development_m2", 0.7), ("renovation_index", 0.3))
CONTRADICTION_THRESHOLD = 35


def _weighted_n(values: dict, pairs: tuple) -> tuple[float, list[dict]]:
    num = den = 0.0
    rows = []
    for sid, w in pairs:
        sv = values.get(sid)
        if sv is None or sv.value is None:
            continue
        n = normalize(CATALOG[sid], sv.value)
        num += w * n
        den += w
        rows.append({"signal_id": sid, "label_en": CATALOG[sid].label_en,
                     "varde": sv.value, "enhet": CATALOG[sid].unit,
                     "kalla": sv.source, "normaliserat": round(n, 2)})
    return (num / den if den else 0.5), rows


def _band(value: float, riktning: str) -> str:
    """Kartlegendens band: värdet är alltid 0–100."""
    risk = value if riktning == "risk" else 100 - value
    if risk < 30:
        return "lag"
    if risk < 50:
        return "mattlig"
    return "forhojd" if risk < 70 else "hog"

BAND_SV = {"lag": "Low operational risk", "mattlig": "Moderate",
           "forhojd": "Elevated", "hog": "High risk"}


def index_catalog() -> list[dict[str, Any]]:
    out = [{"id": i.id, "label_en": i.label_en,
            "beskrivning_en": i.beskrivning_en,
            "riktning": i.riktning, "niva": i.niva}
           for i in INDEX_TYPES.values()]
    out.append({"id": "contradiction_index", "label_en": "Contradiction Index",
                "beskrivning_en": "Divergence between officially planned "
                                  "and actually observed – the platform's "
                                  "signature analysis.",
                "riktning": "risk", "niva": "free"})
    return out


def _region_indices(values: dict) -> list[dict[str, Any]]:
    rows = []
    for idx in INDEX_TYPES.values():
        n, drivare = _weighted_n(values, idx.signals)
        value = round(100 * (1 - n) if idx.riktning == "risk" else 100 * n)
        band = _band(value, idx.riktning)
        rows.append({"index_id": idx.id, "label_en": idx.label_en,
                     "niva": idx.niva, "riktning": idx.riktning,
                     "varde": value, "band": band,
                     "band_en": BAND_SV[band],
                     "drivare": drivare,
                     "narrativ_en": f"{idx.label_en}: {value}/100 "
                                    f"({BAND_SV[band].lower()})."})
    # Kontradiktionsindexet.
    planerat, prow = _weighted_n(values, _PLANNED)
    observerat, orow = _weighted_n(values, _OBSERVED)
    div = round(min(100, abs(planerat - observerat) * 140))
    detected = div >= CONTRADICTION_THRESHOLD
    band = _band(div, "risk")
    rows.append({
        "index_id": "contradiction_index", "label_en": "Contradiction Index",
        "niva": "free", "riktning": "risk", "varde": div, "band": band,
        "band_en": BAND_SV[band],
        "kontradiktion_upptackt": detected,
        "drivare": [{**r, "roll": "officiellt_planerat"} for r in prow] +
                   [{**r, "roll": "observerat"} for r in orow],
        "narrativ_en": (
            f"Contradiction detected ({div}/100): officially planned and "
            f"observed activity point in different directions – dig "
            f"deeper before deciding."
            if detected else
            f"Official plans and observed activity are consistent "
            f"({div}/100)."),
    })
    return rows


def _needed_signals() -> list[str]:
    need = {s for i in INDEX_TYPES.values() for s, _ in i.signals}
    need.update(s for s, _ in _PLANNED)
    need.update(s for s, _ in _OBSERVED)
    return sorted(need)


_CAVEATS = [
    "All index values are traceable: each value carries its signal "
    "breakdown with a source per row.",
    "The Contradiction Index is currently computed on the same signal "
    "picture – precision improves when the quiXzoom observation layer "
    "is connected (stub in the source chain).",
]


def city_assessment(kommun_kod: str, market: str = "se",
                    resolver: Resolver | None = None) -> dict[str, Any]:
    """Alla index för en stad – 'click any city'-vyn."""
    mkt = get_market(market)
    kod, namn, lat, lon = get_region(market, kommun_kod)
    res = resolver or _DEFAULT_RESOLVER
    values, _ = res.resolve(Location(lat, lon, address=namn),
                            "indices", _needed_signals())
    rows = _region_indices(values)
    kontr = next(r for r in rows if r["index_id"] == "contradiction_index")
    return {"kommun": namn, "kommun_kod": kod,
            "market": mkt.id, "market_label_en": mkt.label_en,
            "index": rows,
            "sammanfattning_en": (
                f"{namn}: " + " · ".join(
                    f"{r['label_en']} {r['varde']}" for r in rows[:5]) +
                (". Contradiction detected."
                 if kontr["kontradiktion_upptackt"] else ".")),
            "caveats_en": list(_CAVEATS)}


def index_map(index_id: str, market: str = "se",
              resolver: Resolver | None = None,
              top_n: int = 5) -> dict[str, Any]:
    """Intelligence Map-lager: ett index över marknadens regioner."""
    giltiga = set(INDEX_TYPES) | {"contradiction_index"}
    if index_id not in giltiga:
        raise ValueError(f"Unknown index: {index_id}. "
                         f"Available: {', '.join(sorted(giltiga))}")
    mkt = get_market(market)
    res = resolver or _DEFAULT_RESOLVER
    needed = _needed_signals()
    regioner = []
    for code, name, lat, lon in mkt.regions:
        values, _ = res.resolve(Location(lat, lon, address=name),
                                "indices", needed)
        row = next(r for r in _region_indices(values)
                   if r["index_id"] == index_id)
        regioner.append({"kommun": name, "kommun_kod": code,
                         "lat": lat, "lon": lon,
                         "varde": row["varde"], "band": row["band"],
                         "band_en": row["band_en"],
                         "kontradiktion_upptackt":
                             row.get("kontradiktion_upptackt", False)})
    riktning = ("risk" if index_id == "contradiction_index"
                else INDEX_TYPES[index_id].riktning)
    regioner.sort(key=lambda r: -r["varde"] if riktning == "risk"
                  else -r["varde"])
    label = ("Contradiction Index" if index_id == "contradiction_index"
             else INDEX_TYPES[index_id].label_en)
    farg = {"lag": "gron", "mattlig": "gul", "forhojd": "orange", "hog": "rod"}
    return {"index_id": index_id, "label_en": label,
            "riktning": riktning,
            "market": mkt.id, "market_label_en": mkt.label_en,
            "bbox": list(mkt.bbox),
            "regioner": regioner,
            "heatmap": [{"kommun": r["kommun"], "kommun_kod": r["kommun_kod"],
                         "lat": r["lat"], "lon": r["lon"],
                         "score": r["varde"], "band": farg[r["band"]]}
                        for r in regioner],
            "sammanfattning_en": (
                f"{label} in {mkt.label_en} – "
                + ("highest risk" if riktning == "risk" else "strongest")
                + ": "
                + ", ".join(r["kommun"] for r in regioner[:3]) + "."),
            "caveats_en": list(_CAVEATS)}
