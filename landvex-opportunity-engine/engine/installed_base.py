"""Installed Base Engine – varje installerad produkt är ett framtida
servicebehov.

Grundprincip: kan vi uppskatta var produkter finns, hur gamla de är
och hur länge de lever, kan vi uppskatta var efterfrågan på service,
reservdelar och kompetens uppstår – innan den syns i annonser.

Generell modell, INTE regler per bransch: varje produkttyp beskrivs
med egenskaper (PRODUCT_TYPES) – installerad bas-proxy, livslängd,
serviceintervall, certifieringskrav, felmönster, säsong, kopplat
serviceyrke (Workforce-motorn) och betjänande vertikal (svep/gap/
plan). Ny produktkategori = ny datarad, samma motor. Det gäller
värmepumpar såväl som hissar, robotar eller personbilar.

Kedjan per region:
  bas (uppskattad ur signaler) → medelålder (antagande: jämn
  åldersfördelning, dokumenterat) → utbyten till målåret
  (bas × horisont/livslängd) → servicetillfällen/år
  (bas / intervall) → teknikerbehov (tillfällen / kapacitet)
  → kompetensläge (Workforce-brist för serviceyrket)
  → mismatch: stor bas + teknikerbrist = affärsmöjlighet.

Allt är uppskattningar ur signalproxies och märks så; verkliga
installationsregister (t.ex. F-gas-registret, elnätsanslutningar,
besiktningsregister) är adapterkandidater i samma Resolver-mönster.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.mock import MockSource
from .markets import get_market, get_region
from .models import Location
from .signals import CATALOG, normalize
from .verticals import VERTICALS
from .workforce import OCCUPATIONS, forecast

_DEFAULT_RESOLVER = Resolver([MockSource()])

BASE_YEAR = 2026
_EVENTS_PER_TECH_YEAR = 400.0   # servicetillfällen per tekniker/år (schablon)


@dataclass(frozen=True)
class ProductType:
    id: str
    label_en: str
    kategori_en: str
    livslangd_ar: float
    serviceintervall_ar: float
    # Basuppskattning: mode "per_unit" (signal × faktor),
    # "per_1000pop" (signal/1000 inv × befolkning × faktor),
    # "density_scaled" (befolkning/1000 × faktor × normaliserad signal).
    bas_signal: str
    bas_mode: str
    bas_faktor: float
    tillvaxt_signaler: tuple          # ((signal_id, vikt), ...) nyinstallation
    occupation_id: str | None         # serviceyrke i Workforce-katalogen
    vertical_id: str                  # betjänande vertikal
    certifiering_en: str
    felmonster_en: str
    reservdelar_en: str
    sasong_en: str


def _p(*args):
    return ProductType(*args)


PRODUCT_TYPES: dict[str, ProductType] = {p.id: p for p in [
    _p("varmepump_luft", "Air-source heat pumps", "Energy & heating",
       15, 2, "detached_homes", "per_unit", 0.45,
       (("detached_homes", 0.4), ("renovation_index", 0.3), ("pop_growth_pct", 0.3)),
       "kyltekniker", "vvs",
       "F-gas certificate (category I–II)",
       "Compressor failures and refrigerant leaks, rising sharply "
       "after year 10.",
       "Compressors, fan motors, circuit boards",
       "Breakdowns in winter, planned service in autumn"),
    _p("varmepump_berg", "Ground-source heat pumps", "Energy & heating",
       20, 3, "detached_homes", "per_unit", 0.18,
       (("detached_homes", 0.5), ("pop_growth_pct", 0.5)),
       "vvs_montor", "vvs",
       "Certified well driller for new installations",
       "Circulation pumps and control systems after year 12.",
       "Circulation pumps, expansion vessels, control boards",
       "Steady demand, peak at the cold start of the season"),
    _p("solcellsanlaggning", "Solar PV systems", "Energy & electrical",
       25, 4, "detached_homes", "per_unit", 0.15,
       (("ev_per_capita", 0.3), ("detached_homes", 0.3), ("development_m2", 0.2),
        ("pop_growth_pct", 0.2)),
       "elektriker", "elektriker",
       "Licensed electrical installer (AL authorization)",
       "Inverters last ~12 years – a replacement wave mid-way through "
       "the system's life.",
       "Inverters, optimizers, battery storage",
       "Installation peak in spring/summer"),
    _p("laddbox", "EV charging boxes", "Energy & electrical",
       10, 3, "ev_per_capita", "per_1000pop", 0.6,
       (("ev_per_capita", 0.6), ("pop_growth_pct", 0.4)),
       "elektriker", "elektriker",
       "Licensed electrical installer",
       "Software faults and load-balancing issues; connectors wear out.",
       "Connectors, circuit boards, software updates",
       "Steady demand, peak at new-car deliveries"),
    _p("hiss", "Elevators", "Building technology",
       30, 0.5, "residential_density", "density_scaled", 1.1,
       (("residential_density", 0.5), ("development_m2", 0.5)),
       "drifttekniker", "generisk",
       "Accredited elevator inspection body; certified elevator technician",
       "Door mechanisms and control systems; statutory recurring "
       "inspections.",
       "Door mechanisms, ropes, control electronics",
       "Statutory inspection cycle – steady year-round"),
    _p("personbil", "Passenger cars", "Vehicles",
       18, 1, "cars_per_1000", "per_1000pop", 1.0,
       (("cars_per_1000", 0.5), ("pop_growth_pct", 0.5)),
       None, "bilverkstad",
       "None in general; brand authorization for warranty service",
       "Wear parts continuously; electronics faults dominate after year 8.",
       "Brakes, tires, batteries, sensors",
       "Tire changes spring/autumn, inspection peaks"),
    _p("industrirobot", "Industrial robots", "Industrial automation",
       12, 1, "business_density", "density_scaled", 0.9,
       (("business_density", 0.5), ("infra_invest", 0.5)),
       "drifttekniker", "lager",
       "Vendor certification (ABB/KUKA/Fanuc etc.)",
       "Gearboxes and cabling; unplanned stops are the most costly.",
       "Servo motors, gearboxes, control cabinets",
       "Service windows during production stops (summer/Christmas)"),
    _p("ventilation", "Ventilation units (HRV)", "Building technology",
       20, 1, "residential_density", "density_scaled", 2.0,
       (("residential_density", 0.4), ("building_permits", 0.3),
        ("development_m2", 0.3)),
       "fastighetstekniker", "vvs",
       "OVK certification for inspection",
       "Fan bearings and neglected filters; energy performance declines "
       "with age.",
       "Fans, filters, heat exchangers, controls",
       "OVK cycles; filter changes spring/autumn"),
    _p("jordbruksmaskin", "Agricultural machinery", "Agriculture",
       15, 1, "detached_homes", "per_unit", 0.06,
       (("detached_homes", 0.6), ("pop_growth_pct", 0.4)),
       "maskinforare", "generisk",
       "None in general; vendor training per make",
       "Hydraulics and electronics; in-season breakdowns are "
       "production-critical.",
       "Hydraulics, filters, electronics",
       "Extreme seasonal peaks in spring and harvest"),
    _p("byggmaskin", "Construction machinery", "Construction & civil works",
       10, 0.5, "building_permits", "per_unit", 1.2,
       (("building_permits", 0.5), ("development_m2", 0.5)),
       "maskinforare", "bygg",
       "Operator training certificate; recurring inspections",
       "Drivetrains and hydraulics; downtime cost dominates.",
       "Tracks, hydraulics, engines",
       "Construction season spring–autumn"),
    _p("medicinteknik", "Medical equipment", "Healthcare",
       12, 1, "share_65plus", "density_scaled", 0.8,
       (("share_65plus", 0.6), ("pop_growth_pct", 0.4)),
       "drifttekniker", "generisk",
       "Vendor certification; MDR regulations",
       "Calibration drift; service agreements are patient-safety critical.",
       "Sensors, calibration, software",
       "Steady, contract-driven"),
    _p("it_infrastruktur", "IT infrastructure (server rooms)", "IT",
       8, 0.5, "business_density", "density_scaled", 1.5,
       (("business_density", 0.6), ("office_workers", 0.4)),
       "it_tekniker", "generisk",
       "None in general; vendor certifications",
       "Disks and power supplies; cooling dependency makes heat waves "
       "critical.",
       "Disks, power supplies, UPS batteries",
       "Steady; service windows at night"),
]}


def product_catalog() -> list[dict[str, Any]]:
    return [{"id": p.id, "label_en": p.label_en, "kategori_en": p.kategori_en,
             "livslangd_ar": p.livslangd_ar,
             "serviceintervall_ar": p.serviceintervall_ar,
             "certifiering_en": p.certifiering_en,
             "serviceyrke_en": (OCCUPATIONS[p.occupation_id].label_en
                                if p.occupation_id else None),
             "betjanas_av_en": VERTICALS[p.vertical_id].label_en}
            for p in PRODUCT_TYPES.values()]


def _needed_signals() -> list[str]:
    need = {"population_total"}
    for p in PRODUCT_TYPES.values():
        need.add(p.bas_signal)
        need.update(s for s, _ in p.tillvaxt_signaler)
    return sorted(need)


def _resolve_market(market: str, resolver: Resolver | None) -> dict[str, dict]:
    res = resolver or _DEFAULT_RESOLVER
    needed = _needed_signals()
    out = {}
    for code, name, lat, lon in get_market(market).regions:
        values, _ = res.resolve(Location(lat, lon, address=name),
                                "installed_base", needed)
        out[code] = {sid: sv.value for sid, sv in values.items()
                     if sv.value is not None}
    return out


def _base_units(p: ProductType, sig: dict) -> float:
    v = sig.get(p.bas_signal, 0.0)
    pop = sig.get("population_total", 0.0)
    if p.bas_mode == "per_unit":
        return v * p.bas_faktor
    if p.bas_mode == "per_1000pop":
        return v * pop / 1000.0 * p.bas_faktor
    n = normalize(CATALOG[p.bas_signal], v) or 0.0
    return pop / 1000.0 * p.bas_faktor * n           # density_scaled


def _growth(p: ProductType, sig: dict) -> float:
    g = 0.0
    for sid, w in p.tillvaxt_signaler:
        if sid not in sig:
            continue
        if sid == "pop_growth_pct":
            g += w * max(-3.0, min(3.0, sig[sid])) / 100.0
        else:
            g += w * ((normalize(CATALOG[sid], sig[sid]) or 0.5) - 0.5) * 0.06
    return max(-0.02, min(0.08, g))


def _region_row(p: ProductType, sig: dict, horizon: int) -> dict[str, Any]:
    bas = _base_units(p, sig)
    g = _growth(p, sig)
    utbyten = bas * min(1.0, horizon / p.livslangd_ar)
    service_ar = bas / p.serviceintervall_ar
    tekniker = math.ceil(service_ar / _EVENTS_PER_TECH_YEAR) if bas else 0
    return {"installerad_bas": int(round(bas)),
            "medelalder_ar": round(p.livslangd_ar / 2, 1),
            "utbyten_till_malar": int(round(utbyten)),
            "servicetillfallen_per_ar": int(round(service_ar)),
            "teknikerbehov": tekniker,
            "nyinstallationstakt_pct_ar": round(100 * g, 1)}


def _tech_status(p: ProductType, kod: str, market: str, target_year: int,
                 resolver) -> dict[str, Any]:
    if p.occupation_id is None:
        return {"status": "ej_modellerat",
                "text_en": "The service occupation is not modeled in the "
                           "Workforce catalog yet."}
    f = forecast(kod, target_year, [p.occupation_id], resolver=resolver,
                 market=market)["prognoser"][0]
    brist = f["brist"] > 0
    return {"occupation_id": p.occupation_id, "label_en": f["label_en"],
            "brist": f["brist"], "status": "brist" if brist else "balans",
            "text_en": (f"Shortage of {f['brist']} {f['label_en'].lower()}"
                        f"(s) by {target_year} – service capacity is the "
                        f"bottleneck."
                        if brist else
                        f"Balanced market for {f['label_en'].lower()}s.")}


_ANTAGANDEN = [
    "The installed base is an estimate from signal proxies (detached-home "
    "stock, EV density, residential/business density) – not registers.",
    "The age distribution is assumed uniform over the lifespan; "
    "replacements by the target year = base × horizon/lifespan.",
    f"Technician demand = service events/year ÷ {int(_EVENTS_PER_TECH_YEAR)} "
    f"(standard-estimate capacity per technician).",
    "Real installation registers (F-gas, grid connections, inspections) "
    "are adapter candidates that improve precision.",
]


def service_analysis(kommun_kod: str, market: str = "se",
                     target_year: int = 2031,
                     resolver: Resolver | None = None) -> dict[str, Any]:
    """Servicebehovsprofil för en region: alla produkttyper."""
    mkt = get_market(market)
    kod, namn, *_ = get_region(market, kommun_kod)
    data = _resolve_market(market, resolver)
    sig = data[kod]
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= 20:
        raise ValueError(f"Target year must be between {BASE_YEAR + 1} "
                         f"and {BASE_YEAR + 20}.")

    rows = []
    for p in PRODUCT_TYPES.values():
        r = _region_row(p, sig, horizon)
        rows.append({
            "product_id": p.id, "label_en": p.label_en,
            "kategori_en": p.kategori_en, **r,
            "livslangd_ar": p.livslangd_ar,
            "serviceintervall_ar": p.serviceintervall_ar,
            "certifiering_en": p.certifiering_en,
            "felmonster_en": p.felmonster_en,
            "reservdelar_en": p.reservdelar_en,
            "sasong_en": p.sasong_en,
            "teknikerlage": _tech_status(p, kod, market, target_year, resolver),
            "betjanas_av": {"vertical_id": p.vertical_id,
                            "label_en": VERTICALS[p.vertical_id].label_en},
        })
    rows.sort(key=lambda x: -x["utbyten_till_malar"])
    topp = rows[0]
    return {"kommun": namn, "kommun_kod": kod,
            "market": mkt.id, "market_label_en": mkt.label_en,
            "basar": BASE_YEAR, "malar": target_year,
            "produkter": rows,
            "sammanfattning_en": (
                f"Largest upcoming service wave in {namn}: "
                f"{topp['label_en'].lower()} – about "
                f"{topp['utbyten_till_malar']} replacements by {target_year} "
                f"and {topp['servicetillfallen_per_ar']} service events "
                f"per year."),
            "antaganden_en": list(_ANTAGANDEN)}


def service_demand_map(product_id: str, market: str = "se",
                       target_year: int = 2031,
                       resolver: Resolver | None = None,
                       top_n: int = 5) -> dict[str, Any]:
    """Var uppstår servicebehovet för en produkttyp – karta + mismatch."""
    p = PRODUCT_TYPES.get(product_id)
    if p is None:
        raise ValueError(f"Unknown product type: {product_id}. "
                         f"Available: {', '.join(sorted(PRODUCT_TYPES))}")
    mkt = get_market(market)
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= 20:
        raise ValueError(f"Target year must be between {BASE_YEAR + 1} "
                         f"and {BASE_YEAR + 20}.")
    data = _resolve_market(market, resolver)

    rows = []
    for code, name, lat, lon in mkt.regions:
        r = _region_row(p, data[code], horizon)
        tek = _tech_status(p, code, market, target_year, resolver)
        rows.append({"kommun": name, "kommun_kod": code,
                     "lat": lat, "lon": lon, **r,
                     "teknikerlage": tek,
                     "mismatch": tek.get("status") == "brist" and
                                 r["installerad_bas"] > 0})
    rows.sort(key=lambda x: -x["utbyten_till_malar"])
    snitt = (sum(x["utbyten_till_malar"] for x in rows) / len(rows)) or 1.0
    mismatches = [r["kommun"] for r in rows if r["mismatch"]][:3]

    return {"product_id": p.id, "label_en": p.label_en,
            "market": mkt.id, "market_label_en": mkt.label_en,
            "bbox": list(mkt.bbox),
            "basar": BASE_YEAR, "malar": target_year,
            "regioner": rows,
            "heatmap": [{"kommun": r["kommun"], "kommun_kod": r["kommun_kod"],
                         "lat": r["lat"], "lon": r["lon"],
                         "score": r["utbyten_till_malar"],
                         "band": ("gron" if r["utbyten_till_malar"] >= 1.25 * snitt
                                  else "gul" if r["utbyten_till_malar"] >= 0.75 * snitt
                                  else "rod")} for r in rows],
            "sammanfattning_en": (
                f"Largest service demand for {p.label_en.lower()} by "
                f"{target_year}: "
                + ", ".join(r["kommun"] for r in rows[:3]) + "."
                + (f" Large base BUT technician shortage (mismatch) in: "
                   f"{', '.join(mismatches)}." if mismatches else "")),
            "betjanas_av": {"vertical_id": p.vertical_id,
                            "label_en": VERTICALS[p.vertical_id].label_en},
            "antaganden_en": list(_ANTAGANDEN)}
