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
    label_sv: str
    kategori_sv: str
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
    certifiering_sv: str
    felmonster_sv: str
    reservdelar_sv: str
    sasong_sv: str


def _p(*args):
    return ProductType(*args)


PRODUCT_TYPES: dict[str, ProductType] = {p.id: p for p in [
    _p("varmepump_luft", "Luftvärmepumpar", "Energi & uppvärmning",
       15, 2, "detached_homes", "per_unit", 0.45,
       (("detached_homes", 0.4), ("renovation_index", 0.3), ("pop_growth_pct", 0.3)),
       "kyltekniker", "vvs",
       "F-gascertifikat (kategori I–II)",
       "Kompressorhaverier och köldmedieläckage, ökar kraftigt efter år 10.",
       "Kompressorer, fläktmotorer, kretskort",
       "Haverier vintertid, planerad service höst"),
    _p("varmepump_berg", "Bergvärmepumpar", "Energi & uppvärmning",
       20, 3, "detached_homes", "per_unit", 0.18,
       (("detached_homes", 0.5), ("pop_growth_pct", 0.5)),
       "vvs_montor", "vvs",
       "Certifierad brunnsborrare vid nyinstallation",
       "Cirkulationspumpar och styrsystem efter år 12.",
       "Cirkulationspumpar, expansionskärl, styrkort",
       "Jämn efterfrågan, topp vid kallstart av säsongen"),
    _p("solcellsanlaggning", "Solcellsanläggningar", "Energi & el",
       25, 4, "detached_homes", "per_unit", 0.15,
       (("ev_per_capita", 0.3), ("detached_homes", 0.3), ("development_m2", 0.2),
        ("pop_growth_pct", 0.2)),
       "elektriker", "elektriker",
       "Behörig elinstallatör (auktorisation AL)",
       "Växelriktare håller ~12 år – utbytesvåg mitt i anläggningens liv.",
       "Växelriktare, optimerare, batterilager",
       "Installationstopp vår/sommar"),
    _p("laddbox", "Laddboxar", "Energi & el",
       10, 3, "ev_per_capita", "per_1000pop", 0.6,
       (("ev_per_capita", 0.6), ("pop_growth_pct", 0.4)),
       "elektriker", "elektriker",
       "Behörig elinstallatör",
       "Mjukvarufel och lastbalanseringsproblem; kontaktdon slits.",
       "Kontaktdon, kretskort, mjukvaruuppdateringar",
       "Jämn efterfrågan, topp vid nybilsleveranser"),
    _p("hiss", "Hissar", "Fastighetsteknik",
       30, 0.5, "residential_density", "density_scaled", 1.1,
       (("residential_density", 0.5), ("development_m2", 0.5)),
       "drifttekniker", "generisk",
       "Ackrediterat hissbesiktningsorgan; certifierad hisstekniker",
       "Dörrmaskinerier och styrsystem; lagkrav på återkommande besiktning.",
       "Dörrmaskinerier, linor, styrelektronik",
       "Lagstyrd besiktningscykel – jämn året runt"),
    _p("personbil", "Personbilar", "Fordon",
       18, 1, "cars_per_1000", "per_1000pop", 1.0,
       (("cars_per_1000", 0.5), ("pop_growth_pct", 0.5)),
       None, "bilverkstad",
       "Ingen generell; märkesauktorisation för garantiservice",
       "Slitagedelar löpande; elektronikfel dominerar efter år 8.",
       "Bromsar, däck, batterier, sensorer",
       "Däckskiften vår/höst, besiktningstoppar"),
    _p("industrirobot", "Industrirobotar", "Industriell automation",
       12, 1, "business_density", "density_scaled", 0.9,
       (("business_density", 0.5), ("infra_invest", 0.5)),
       "drifttekniker", "lager",
       "Leverantörscertifiering (ABB/KUKA/Fanuc m.fl.)",
       "Växellådor och kablage; oplanerade stopp är dyrast.",
       "Servomotorer, växellådor, styrskåp",
       "Servicefönster vid produktionsstopp (sommar/jul)"),
    _p("ventilation", "Ventilationsaggregat (FTX)", "Fastighetsteknik",
       20, 1, "residential_density", "density_scaled", 2.0,
       (("residential_density", 0.4), ("building_permits", 0.3),
        ("development_m2", 0.3)),
       "fastighetstekniker", "vvs",
       "OVK-behörighet för besiktning",
       "Fläktlager och filterförsummelse; energiprestanda faller med åldern.",
       "Fläktar, filter, värmeväxlare, styr",
       "OVK-cykler; filterbyten vår/höst"),
]}


def product_catalog() -> list[dict[str, Any]]:
    return [{"id": p.id, "label_sv": p.label_sv, "kategori_sv": p.kategori_sv,
             "livslangd_ar": p.livslangd_ar,
             "serviceintervall_ar": p.serviceintervall_ar,
             "certifiering_sv": p.certifiering_sv,
             "serviceyrke_sv": (OCCUPATIONS[p.occupation_id].label_sv
                                if p.occupation_id else None),
             "betjanas_av_sv": VERTICALS[p.vertical_id].label_sv}
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
                "text_sv": "Serviceyrket är inte modellerat i "
                           "Workforce-katalogen ännu."}
    f = forecast(kod, target_year, [p.occupation_id], resolver=resolver,
                 market=market)["prognoser"][0]
    brist = f["brist"] > 0
    return {"occupation_id": p.occupation_id, "label_sv": f["label_sv"],
            "brist": f["brist"], "status": "brist" if brist else "balans",
            "text_sv": (f"Brist på {f['brist']} {f['label_sv'].lower()} till "
                        f"{target_year} – servicekapaciteten är flaskhalsen."
                        if brist else
                        f"Balanserat läge för {f['label_sv'].lower()}.")}


_ANTAGANDEN = [
    "Installerad bas är en uppskattning ur signalproxies (villabestånd, "
    "elbilstäthet, bostads-/företagstäthet) – inte register.",
    "Åldersfördelningen antas jämn över livslängden; utbyten till målåret "
    "= bas × horisont/livslängd.",
    f"Teknikerbehov = servicetillfällen/år ÷ {int(_EVENTS_PER_TECH_YEAR)} "
    f"(schablonkapacitet per tekniker).",
    "Verkliga installationsregister (F-gas, elnätsanslutningar, "
    "besiktningar) är adapterkandidater som höjer precisionen.",
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
        raise ValueError(f"Målår måste ligga {BASE_YEAR + 1}–{BASE_YEAR + 20}.")

    rows = []
    for p in PRODUCT_TYPES.values():
        r = _region_row(p, sig, horizon)
        rows.append({
            "product_id": p.id, "label_sv": p.label_sv,
            "kategori_sv": p.kategori_sv, **r,
            "livslangd_ar": p.livslangd_ar,
            "serviceintervall_ar": p.serviceintervall_ar,
            "certifiering_sv": p.certifiering_sv,
            "felmonster_sv": p.felmonster_sv,
            "reservdelar_sv": p.reservdelar_sv,
            "sasong_sv": p.sasong_sv,
            "teknikerlage": _tech_status(p, kod, market, target_year, resolver),
            "betjanas_av": {"vertical_id": p.vertical_id,
                            "label_sv": VERTICALS[p.vertical_id].label_sv},
        })
    rows.sort(key=lambda x: -x["utbyten_till_malar"])
    topp = rows[0]
    return {"kommun": namn, "kommun_kod": kod,
            "market": mkt.id, "market_label_sv": mkt.label_sv,
            "basar": BASE_YEAR, "malar": target_year,
            "produkter": rows,
            "sammanfattning_sv": (
                f"Största kommande servicevåg i {namn}: "
                f"{topp['label_sv'].lower()} – cirka "
                f"{topp['utbyten_till_malar']} utbyten till {target_year} "
                f"och {topp['servicetillfallen_per_ar']} servicetillfällen "
                f"per år."),
            "antaganden_sv": list(_ANTAGANDEN)}


def service_demand_map(product_id: str, market: str = "se",
                       target_year: int = 2031,
                       resolver: Resolver | None = None,
                       top_n: int = 5) -> dict[str, Any]:
    """Var uppstår servicebehovet för en produkttyp – karta + mismatch."""
    p = PRODUCT_TYPES.get(product_id)
    if p is None:
        raise ValueError(f"Okänd produkttyp: {product_id}. "
                         f"Tillgängliga: {', '.join(sorted(PRODUCT_TYPES))}")
    mkt = get_market(market)
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= 20:
        raise ValueError(f"Målår måste ligga {BASE_YEAR + 1}–{BASE_YEAR + 20}.")
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

    return {"product_id": p.id, "label_sv": p.label_sv,
            "market": mkt.id, "market_label_sv": mkt.label_sv,
            "bbox": list(mkt.bbox),
            "basar": BASE_YEAR, "malar": target_year,
            "regioner": rows,
            "heatmap": [{"kommun": r["kommun"], "kommun_kod": r["kommun_kod"],
                         "lat": r["lat"], "lon": r["lon"],
                         "score": r["utbyten_till_malar"],
                         "band": ("gron" if r["utbyten_till_malar"] >= 1.25 * snitt
                                  else "gul" if r["utbyten_till_malar"] >= 0.75 * snitt
                                  else "rod")} for r in rows],
            "sammanfattning_sv": (
                f"Störst servicebehov för {p.label_sv.lower()} till "
                f"{target_year}: "
                + ", ".join(r["kommun"] for r in rows[:3]) + "."
                + (f" Stor bas MEN teknikerbrist (mismatch) i: "
                   f"{', '.join(mismatches)}." if mismatches else "")),
            "betjanas_av": {"vertical_id": p.vertical_id,
                            "label_sv": VERTICALS[p.vertical_id].label_sv},
            "antaganden_sv": list(_ANTAGANDEN)}
