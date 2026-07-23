"""Risk Engine – flerdimensionell riskprofil för en plats + vertikal.

Tredje motorn i Landvex-familjen (Opportunity → Workforce → Risk),
byggd på samma datakällslager. Där Opportunity-rapporten ger en samlad
risknivå bryter Risk Engine ner VARFÖR: fyra signaldrivna dimensioner
+ dataosäkerhet, var och en med score, narrativ och åtgärdsförslag.

Transparent som allt annat: dimensionsrisk = 100 × (1 − viktat
normaliserat signalvärde). Signalkatalogens normalisering pekar redan
"högre = bättre", så risken är komplementet – inga dolda modeller.

Dimensionerna är data: ny dimension = ny rad, inga motorändringar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.mock import MockSource
from .models import Location
from .signals import CATALOG, normalize
from .verticals import VERTICALS

_DEFAULT_RESOLVER = Resolver([MockSource()])


@dataclass(frozen=True)
class RiskDimension:
    id: str
    label_sv: str
    weight: float
    signals: tuple              # ((signal_id, vikt), ...)
    mitigation_sv: str          # åtgärdsförslag när risken är förhöjd


DIMENSIONS: tuple[RiskDimension, ...] = (
    RiskDimension(
        "marknadsrisk", "Marknadsrisk", 0.26,
        (("competition_pressure", 0.6), ("provider_gap", 0.4)),
        "Differentiera konceptet, säkra nischsegment eller ompröva läget "
        "innan avtal tecknas."),
    RiskDimension(
        "efterfragerisk", "Efterfrågerisk", 0.24,
        (("pop_radius", 0.40), ("pop_growth_pct", 0.35),
         ("target_match_pct", 0.25)),
        "Utöka upptagningsområdet (längre öppettider, mobil tjänst, "
        "e-handel) eller välj plats närmare målgruppens flöden."),
    RiskDimension(
        "kostnadsrisk", "Kostnadsrisk", 0.22,
        (("rent_index", 0.6), ("vacancy_rate", 0.4)),
        "Förhandla hyrestrappa/kortare bindningstid – hög vakans i "
        "området är ett förhandlingsläge."),
    RiskDimension(
        "utvecklingsrisk", "Utvecklingsrisk", 0.16,
        (("building_permits", 0.4), ("detail_plans", 0.3),
         ("infra_invest", 0.3)),
        "Låg utvecklingsaktivitet: räkna inte med tillväxtdriven "
        "efterfrågan – kalkylera på dagens marknad."),
)

_DATA_WEIGHT = 0.12   # dataosäkerhetens vikt i totalrisken


def _band(risk: float) -> str:
    if risk < 35:
        return "Låg"
    if risk < 60:
        return "Medel"
    return "Hög" if risk < 75 else "Mycket hög"


def required_signals() -> list[str]:
    return sorted({sid for d in DIMENSIONS for sid, _ in d.signals})


def assess(location: Location, vertical_id: str,
           resolver: Resolver | None = None) -> dict[str, Any]:
    """Riskprofil för plats + vertikal. JSON-redo dict."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Okänd vertikal: {vertical_id}. "
                         f"Tillgängliga: {', '.join(sorted(VERTICALS))}")
    res = resolver or _DEFAULT_RESOLVER
    values, _ = res.resolve(location, vertical_id, required_signals())

    dims = []
    total_num, total_den = 0.0, 0.0
    for d in DIMENSIONS:
        parts, num, den = [], 0.0, 0.0
        for sid, w in d.signals:
            sv = values.get(sid)
            if sv is None or sv.value is None:
                continue
            n = normalize(CATALOG[sid], sv.value)
            num += w * n
            den += w
            parts.append({"signal_id": sid, "label_sv": CATALOG[sid].label_sv,
                          "varde": sv.value, "enhet": CATALOG[sid].unit,
                          "kalla": sv.source,
                          "riskbidrag": round(100 * (1 - n), 0)})
        risk = round(100 * (1 - num / den), 0) if den else 50.0
        parts.sort(key=lambda p: -p["riskbidrag"])
        worst = parts[0] if parts else None
        narrative = (f"{d.label_sv} {int(risk)}/100 – största faktor: "
                     f"{worst['label_sv'].lower()} ({worst['varde']} "
                     f"{worst['enhet']}, källa {worst['kalla']})."
                     if worst else f"{d.label_sv}: underlag saknas.")
        dims.append({"id": d.id, "label_sv": d.label_sv, "risk": risk,
                     "band": _band(risk), "narrativ_sv": narrative,
                     "signaler": parts,
                     "atgard_sv": d.mitigation_sv if risk >= 60 else None})
        total_num += d.weight * risk
        total_den += d.weight

    # Dataosäkerhet: låg täckning/kvalitet är en risk i sig.
    coverage = (sum(1 for v in values.values() if v.source != "mock") /
                max(1, len(values)))
    avg_q = (sum(v.quality for v in values.values()) /
             max(1, len(values)))
    data_risk = round(100 * (1 - (0.5 * coverage + 0.5 * avg_q)), 0)
    dims.append({"id": "dataosakerhet", "label_sv": "Dataosäkerhet",
                 "risk": data_risk, "band": _band(data_risk),
                 "narrativ_sv": f"{int(100 * coverage)} % av signalerna kommer "
                                f"från verkliga källor. Osäkerheten minskar "
                                f"i takt med att adaptrar kopplas in.",
                 "signaler": [],
                 "atgard_sv": ("Komplettera med platsbesök och lokala "
                               "primärdata innan beslut." if data_risk >= 60
                               else None)})
    total_num += _DATA_WEIGHT * data_risk
    total_den += _DATA_WEIGHT

    total = round(total_num / total_den, 0)
    worst_dim = max(dims, key=lambda d: d["risk"])
    return {
        "vertical_id": vertical_id,
        "vertical_label_sv": VERTICALS[vertical_id].label_sv,
        "location": {"lat": location.lat, "lon": location.lon,
                     "address": location.address,
                     "radius_minutes": location.radius_minutes},
        "total_risk": total,
        "band": _band(total),
        "narrativ_sv": (f"Samlad risk {int(total)}/100 ({_band(total).lower()}). "
                        f"Tyngsta dimensionen är "
                        f"{worst_dim['label_sv'].lower()} "
                        f"({int(worst_dim['risk'])}/100)."),
        "dimensioner": dims,
        "data_coverage": round(coverage, 2),
        "caveats_sv": ["Riskprofilen är ett beslutsunderlag, inte en garanti. "
                       "Dimensionsvikterna är dokumenterade och lika för alla "
                       "platser – jämförbarhet före finjustering."],
    }
