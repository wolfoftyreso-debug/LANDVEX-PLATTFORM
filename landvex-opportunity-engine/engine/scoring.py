"""Scoringmotorn.

Flöde: hämta signaler → normalisera (0..1) → vikta per faktor →
aggregera till Opportunity Score (0–100) → riskbedömning →
rekommendation + narrativ + mönsterinsikter.

v1 är en transparent, regelbaserad viktmodell. Det är avsiktligt:
prediktion av överlevnadssannolikhet kräver utfallsdata som byggs upp
över tid. Vikterna kalibreras sedan mot utfall (v2) och ersätts på
sikt av ERP-modellen (Expected Revenue Potential) i SageMaker (v3).
"""
from __future__ import annotations

from .explain import factor_narrative, pattern_insights
from .models import FactorScore, Location, OpportunityReport
from .version import ENGINE_VERSION
from .signals import CATALOG, normalize
from .verticals import RISK_SIGNALS, VERTICALS
from .datasources.base import Resolver
from .datasources.mock import MockSource

_DEFAULT_RESOLVER = Resolver([MockSource()])


def required_signals(vertical_id: str) -> list[str]:
    prof = VERTICALS[vertical_id]
    ids = {sid for f in prof.factors for sid, _ in f.signals}
    ids.update(RISK_SIGNALS)
    return sorted(ids)


def _risk(values) -> tuple[str, str, float]:
    """Riskscore 0..1 (högre = mer risk) → nivå + narrativ."""
    parts = []
    for sid in RISK_SIGNALS:
        sv = values.get(sid)
        if sv is None or sv.value is None:
            continue
        n = normalize(CATALOG[sid], sv.value)
        # För riskindikatorer med inverse-norm är lågt n = hög risk.
        bad = 1.0 - n if CATALOG[sid].norm == "inverse" else \
              (1.0 - n if sid == "pop_growth_pct" else n)
        if sid == "competition_pressure":  # inverse: högt tryck → lågt n → hög risk
            bad = 1.0 - n
        parts.append(bad)
    score = sum(parts) / len(parts) if parts else 0.5
    if score < 0.35:
        return "Low", ("Low risk: stable demand, reasonable rents and "
                       "manageable competition."), score
    if score < 0.6:
        return "Medium", ("Moderate risk: individual factors should be "
                          "monitored – see the breakdown."), score
    return "High", ("Elevated risk: a combination of vacancies, rent levels, "
                    "competition or weak growth."), score


def _recommendation(score: float, risk_level: str) -> str:
    if score >= 78 and risk_level != "High":
        return "Very good establishment opportunity."
    if score >= 64:
        return ("Good establishment opportunity – with reservations per "
                "the breakdown.")
    if score >= 50:
        return ("Uncertain outlook. Requires clear differentiation or a "
                "lower cost base.")
    return "Weak case for establishing at this location at present."


def analyze(location: Location, vertical_id: str,
            resolver: Resolver | None = None) -> OpportunityReport:
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    prof = VERTICALS[vertical_id]
    res = resolver or _DEFAULT_RESOLVER

    values, extras = res.resolve(location, vertical_id, required_signals(vertical_id))

    factors: list[FactorScore] = []
    for f in prof.factors:
        num, den = 0.0, 0.0
        for sid, w in f.signals:
            sv = values.get(sid)
            n = normalize(CATALOG[sid], sv.value) if sv else None
            if n is not None:
                num += w * n
                den += w
        fscore = round(100.0 * num / den, 0) if den else 0.0
        text = factor_narrative(f.id, location, values, extras) or \
            f"{f.label_en}: index {int(fscore)}/100."
        factors.append(FactorScore(f.id, f.label_en, fscore, f.weight, text))

    total_w = sum(f.weight for f in factors) or 1.0
    score = round(sum(f.score * f.weight for f in factors) / total_w, 0)

    risk_level, risk_text, risk_score = _risk(values)
    coverage = (sum(1 for v in values.values() if v.source != "mock") /
                max(1, len(values)))
    signal_breakdown = {
        sid: {"value": sv.value, "source": sv.source, "quality": sv.quality,
              "normalized": round(normalize(CATALOG[sid], sv.value), 3)}
        for sid, sv in sorted(values.items()) if sv.value is not None}

    caveats = []
    if coverage < 1.0:
        caveats.append("Parts of the underlying data are simulated. "
                       "Real sources (SCB, movement data, building permits, "
                       "place data) are connected in the production "
                       "environment.")
    caveats.append("Decision support, not a yes/no. The score shows "
                   "conditions – execution, concept and pricing determine "
                   "the outcome.")

    return OpportunityReport(
        vertical_id=vertical_id,
        vertical_label_en=prof.label_en,
        location=location,
        opportunity_score=score,
        factors=factors,
        risk_level=risk_level,
        risk_score=round(risk_score, 3),
        risk_narrative_en=risk_text,
        recommendation_en=_recommendation(score, risk_level),
        insights_en=pattern_insights(vertical_id, extras),
        data_coverage=round(coverage, 2),
        caveats_en=caveats,
        signals=signal_breakdown,
        engine_version=ENGINE_VERSION,
    )
