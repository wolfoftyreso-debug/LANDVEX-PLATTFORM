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
        return "Låg", "Låg risk: stabil efterfrågan, rimliga hyror och hanterbar konkurrens.", score
    if score < 0.6:
        return "Medel", "Måttlig risk: enskilda faktorer bör bevakas, se nedbrytningen.", score
    return "Hög", "Förhöjd risk: kombination av vakanser, hyresnivå, konkurrens eller svag tillväxt.", score


def _recommendation(score: float, risk_level: str) -> str:
    if score >= 78 and risk_level != "Hög":
        return "Mycket god etableringsmöjlighet."
    if score >= 64:
        return "God etableringsmöjlighet – med förbehåll enligt nedbrytningen."
    if score >= 50:
        return "Osäkert läge. Kräver tydlig differentiering eller lägre kostnadsbas."
    return "Svagt underlag för etablering på denna plats i nuläget."


def analyze(location: Location, vertical_id: str,
            resolver: Resolver | None = None) -> OpportunityReport:
    if vertical_id not in VERTICALS:
        raise ValueError(f"Okänd vertikal: {vertical_id}. "
                         f"Tillgängliga: {', '.join(sorted(VERTICALS))}")
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
            f"{f.label_sv}: index {int(fscore)}/100."
        factors.append(FactorScore(f.id, f.label_sv, fscore, f.weight, text))

    total_w = sum(f.weight for f in factors) or 1.0
    score = round(sum(f.score * f.weight for f in factors) / total_w, 0)

    risk_level, risk_text, _ = _risk(values)
    coverage = (sum(1 for v in values.values() if v.source != "mock") /
                max(1, len(values)))

    caveats = []
    if coverage < 1.0:
        caveats.append("Delar av underlaget bygger på simulerad data. "
                       "Kopplas mot verkliga källor (SCB, rörelsedata, bygglov, "
                       "platsdata) i produktionsmiljön.")
    caveats.append("Beslutsunderlag, inte ett ja/nej. Scoren visar förutsättningar – "
                   "utförande, koncept och prissättning avgör utfallet.")

    return OpportunityReport(
        vertical_id=vertical_id,
        vertical_label_sv=prof.label_sv,
        location=location,
        opportunity_score=score,
        factors=factors,
        risk_level=risk_level,
        risk_narrative_sv=risk_text,
        recommendation_sv=_recommendation(score, risk_level),
        insights_sv=pattern_insights(vertical_id, extras),
        data_coverage=round(coverage, 2),
        caveats_sv=caveats,
    )
