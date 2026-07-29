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
from .datasources.defaults import default_resolver
from .models import Location
from .signals import CATALOG, normalize
from .verticals import VERTICALS



@dataclass(frozen=True)
class RiskDimension:
    id: str
    label_en: str
    weight: float
    signals: tuple              # ((signal_id, vikt), ...)
    mitigation_en: str          # åtgärdsförslag när risken är förhöjd


DIMENSIONS: tuple[RiskDimension, ...] = (
    RiskDimension(
        "marknadsrisk", "Market risk", 0.26,
        (("competition_pressure", 0.6), ("provider_gap", 0.4)),
        "Differentiate the concept, secure a niche segment or reconsider "
        "the location before signing agreements."),
    RiskDimension(
        "efterfragerisk", "Demand risk", 0.24,
        (("pop_radius", 0.40), ("pop_growth_pct", 0.35),
         ("target_match_pct", 0.25)),
        "Expand the catchment area (longer opening hours, mobile service, "
        "e-commerce) or choose a location closer to the target group's "
        "flows."),
    RiskDimension(
        "kostnadsrisk", "Cost risk", 0.22,
        (("rent_index", 0.6), ("vacancy_rate", 0.4)),
        "Negotiate a stepped rent/shorter lease term – high vacancy in "
        "the area is a bargaining position."),
    RiskDimension(
        "utvecklingsrisk", "Development risk", 0.16,
        (("building_permits", 0.4), ("detail_plans", 0.3),
         ("infra_invest", 0.3)),
        "Low development activity: do not count on growth-driven "
        "demand – base your calculations on today's market."),
)

_DATA_WEIGHT = 0.12   # dataosäkerhetens vikt i totalrisken


def _band(risk: float) -> str:
    if risk < 35:
        return "Low"
    if risk < 60:
        return "Medium"
    return "High" if risk < 75 else "Very high"


def required_signals() -> list[str]:
    return sorted({sid for d in DIMENSIONS for sid, _ in d.signals})


def assess(location: Location, vertical_id: str,
           resolver: Resolver | None = None) -> dict[str, Any]:
    """Riskprofil för plats + vertikal. JSON-redo dict."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    res = resolver or default_resolver()
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
            parts.append({"signal_id": sid, "label_en": CATALOG[sid].label_en,
                          "varde": sv.value, "enhet": CATALOG[sid].unit,
                          "kalla": sv.source,
                          "riskbidrag": round(100 * (1 - n), 0)})
        risk = round(100 * (1 - num / den), 0) if den else 50.0
        parts.sort(key=lambda p: -p["riskbidrag"])
        worst = parts[0] if parts else None
        narrative = (f"{d.label_en} {int(risk)}/100 – largest factor: "
                     f"{worst['label_en'].lower()} ({worst['varde']} "
                     f"{worst['enhet']}, source {worst['kalla']})."
                     if worst else f"{d.label_en}: no data available.")
        dims.append({"id": d.id, "label_en": d.label_en, "risk": risk,
                     "band": _band(risk), "narrativ_en": narrative,
                     "signaler": parts,
                     "atgard_en": d.mitigation_en if risk >= 60 else None})
        total_num += d.weight * risk
        total_den += d.weight

    # Dataosäkerhet: låg täckning/kvalitet är en risk i sig.
    coverage = (sum(1 for v in values.values() if v.source != "mock") /
                max(1, len(values)))
    avg_q = (sum(v.quality for v in values.values()) /
             max(1, len(values)))
    data_risk = round(100 * (1 - (0.5 * coverage + 0.5 * avg_q)), 0)
    dims.append({"id": "dataosakerhet", "label_en": "Data uncertainty",
                 "risk": data_risk, "band": _band(data_risk),
                 "narrativ_en": f"{int(100 * coverage)}% of signals come "
                                f"from real sources. Uncertainty decreases "
                                f"as adapters are connected.",
                 "signaler": [],
                 "atgard_en": ("Supplement with site visits and local "
                               "primary data before deciding."
                               if data_risk >= 60 else None)})
    total_num += _DATA_WEIGHT * data_risk
    total_den += _DATA_WEIGHT

    total = round(total_num / total_den, 0)
    worst_dim = max(dims, key=lambda d: d["risk"])
    return {
        "vertical_id": vertical_id,
        "vertical_label_en": VERTICALS[vertical_id].label_en,
        "location": {"lat": location.lat, "lon": location.lon,
                     "address": location.address,
                     "radius_minutes": location.radius_minutes},
        "total_risk": total,
        "band": _band(total),
        "narrativ_en": (f"Overall risk {int(total)}/100 "
                        f"({_band(total).lower()}). The heaviest dimension "
                        f"is {worst_dim['label_en'].lower()} "
                        f"({int(worst_dim['risk'])}/100)."),
        "dimensioner": dims,
        "data_coverage": round(coverage, 2),
        "caveats_en": ["The risk profile is decision support, not a "
                       "guarantee. Dimension weights are documented and "
                       "identical for all locations – comparability before "
                       "fine-tuning."],
    }
