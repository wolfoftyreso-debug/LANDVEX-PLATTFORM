"""Index Engine – Intelligence Map-lagren.

Speglar Landvex-plattformens kartprodukt: sex index per stad/region
(Infrastructure Risk, Commercial Vitality, Safety, Climate Risk,
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
from .markets import DEFAULT_MARKET, get_market, get_region
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
    IndexDef("commercial_activity", "Commercial Vitality",
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
    IndexDef("city_health", "City Health",
             "Composite city health: safety, transit access, public "
             "investment, growth and commercial base.",
             "styrka", "free",
             (("crime_index", 0.25), ("transit_score", 0.25),
              ("infra_invest", 0.2), ("pop_growth_pct", 0.15),
              ("business_density", 0.15))),
    IndexDef("sanitation", "Sanitation & Cleanliness",
             "How clean a city keeps itself: waste collection, street "
             "cleanliness, pest pressure and drainage — the difference between "
             "a clinical Amsterdam street and wading through gutter-water at "
             "night. Higher is cleaner.",
             "styrka", "free",
             (("street_cleanliness", 0.35), ("waste_collection", 0.25),
              ("pest_pressure", 0.25), ("drainage_index", 0.15))),
    IndexDef("haircut_index", "Haircut Index",
             "A light cost-of-living / purchasing-power proxy (in the spirit "
             "of the Big Mac index): the local price of a standard haircut, "
             "which tracks wages, rents and the commercial base.",
             "styrka", "free",
             (("haircut_price", 0.7), ("business_density", 0.3))),
    IndexDef("gender_balance", "Gender Balance",
             "The women-to-men ratio: near parity scores high; a strong skew "
             "(a mining town, a tech hub, a university city) scores lower. "
             "Descriptive only — balance is not a value judgement.",
             "styrka", "free",
             (("gender_ratio", 1.0),)),
    IndexDef("road_safety", "Road Safety",
             "How safe the roads are (fatalities, infrastructure, enforcement "
             "proxy). Higher is safer.",
             "styrka", "free", (("road_safety", 1.0),)),
    IndexDef("healthcare_access", "Healthcare Access",
             "Access to care: appointment availability, supply and coverage. "
             "Higher is better access.",
             "styrka", "free",
             (("healthcare_access", 0.7), ("care_supply", 0.3))),
    IndexDef("housing_affordability", "Housing Affordability",
             "How affordable housing is relative to local incomes. Higher is "
             "more affordable.",
             "styrka", "free", (("housing_affordability", 1.0),)),
    IndexDef("air_quality", "Air Quality",
             "Ambient air quality (particulates, NO₂ proxy). Higher is cleaner.",
             "styrka", "free", (("air_quality", 1.0),)),
    IndexDef("digital_readiness", "Digital Readiness",
             "Connectivity and the digital commercial base: broadband, digital "
             "services and business density. Higher is more ready.",
             "styrka", "free",
             (("digital_connectivity", 0.7), ("business_density", 0.3))),
    IndexDef("wellbeing", "Wellbeing",
             "Composite quality of life: life satisfaction, safety and transit "
             "access. Higher is better.",
             "styrka", "free",
             (("life_satisfaction", 0.6), ("crime_index", 0.2),
              ("transit_score", 0.2))),
    IndexDef("labor_market", "Labour Market",
             "Labour participation and the local business base. Higher is a "
             "stronger, more inclusive job market.",
             "styrka", "free",
             (("labor_participation", 0.7), ("business_density", 0.3))),
    IndexDef("justice", "Justice & Rule of Law",
             "Court efficiency, case clearance and enforcement (proxy). Higher "
             "means faster, more reliable justice.",
             "styrka", "free", (("justice_efficiency", 1.0),)),
    IndexDef("education", "Education",
             "School outcomes and the digital learning base. Higher is better "
             "attainment and access.",
             "styrka", "free",
             (("education_outcomes", 0.7), ("digital_connectivity", 0.3))),
    IndexDef("social_trust", "Social Trust",
             "Interpersonal and institutional trust — the social capital a "
             "place runs on. Higher is more trust.",
             "styrka", "free", (("social_trust", 1.0),)),
    IndexDef("energy_resilience", "Energy Resilience",
             "Grid stability, supply diversity and reserve margin (proxy). "
             "Higher is more resilient.",
             "styrka", "free", (("energy_resilience", 1.0),)),
    IndexDef("mobility", "Active Mobility",
             "Walking, cycling and transit access — how well a place moves "
             "without a car. Higher is better.",
             "styrka", "free",
             (("active_mobility", 0.6), ("transit_score", 0.4))),
    IndexDef("food_security", "Food Security",
             "Access to affordable, adequate food (supply, price, deserts "
             "proxy). Higher is more secure.",
             "styrka", "free", (("food_access", 1.0),)),
    IndexDef("rights_inclusion", "Rights & Inclusion",
             "Legal protection of civil rights, marriage equality maturity, "
             "anti-discrimination scope, reported minority safety and the "
             "gender pay gap. Descriptive of the legal/lived state — never "
             "a verdict. Higher is stronger protection and inclusion.",
             "styrka", "free",
             (("civil_rights_protection", 0.30),
              ("antidiscrimination_scope", 0.25),
              ("minority_safety", 0.20),
              ("marriage_equality_years", 0.10),
              ("gender_pay_gap", 0.15))),
]}

# Tematiska familjer – grupperar indexen för en läsbar samhällsöversikt.
# (Ren metadata; index_catalog/assess är oförändrade.)
INDEX_FAMILIES: dict[str, tuple[str, ...]] = {
    "Economy": ("commercial_activity", "digital_readiness", "infrastructure_risk",
                "housing_affordability", "haircut_index", "labor_market"),
    "Health": ("city_health", "healthcare_access", "sanitation", "air_quality",
               "food_security"),
    "Safety": ("safety_index", "road_safety", "justice"),
    "Environment": ("climate_risk", "air_quality"),
    "Society": ("wellbeing", "social_trust", "gender_balance", "education",
                "mobility", "rights_inclusion"),
    "Growth & governance": ("urban_growth", "energy_resilience",
                            "contradiction_index"),
}


def index_families() -> list[dict]:
    """Indexen grupperade i tematiska familjer (för översiktsvyer)."""
    known = set(INDEX_TYPES) | {"contradiction_index"}
    return [{"family": fam,
             "indices": [{"id": i, "label_en": INDEX_TYPES[i].label_en}
                         for i in ids if i in INDEX_TYPES]
             + ([{"id": "contradiction_index",
                  "label_en": "Contradiction Index"}]
                if "contradiction_index" in ids else [])}
            for fam, ids in INDEX_FAMILIES.items()
            if all(i in known for i in ids)]

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
    "picture. quiXzoom field observations (mission density) connect via "
    "AAMOS Core; the precise observed-development signal awaits the "
    "Vision pipeline that analyses the submitted media – it is never "
    "fabricated in the meantime.",
]


def city_assessment(kommun_kod: str, market: str = DEFAULT_MARKET,
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


def index_map(index_id: str, market: str = DEFAULT_MARKET,
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
