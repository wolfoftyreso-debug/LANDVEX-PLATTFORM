"""Samhällsscenarier – "vi påstår inte, vi spekulerar inte, vi visar data".

Plattformens identitet gjord till en grind. Det här lagret producerar
scenarier ENDAST när underlaget är trovärdigt:

  1. TILLRÄCKLIGT MÅNGA TROVÄRDIGA KÄLLOR (`MIN_SOURCES`), och
  2. en SYSTEMATISK HISTORISK TENDENS (en signifikant trend, inte brus), och
  3. tillräcklig historik (`MIN_HISTORY`).

Saknas något → status `insufficient_basis` med skälen (det är "vi
spekulerar inte" i kod). Finns det → ett scenario med baslinje + ett
konfidensband som VIDGAS med horisonten och krymper med datakvalitet,
explicita antaganden, källorna, och den obligatoriska caveaten att det är
ett scenario, inte en prognos. Aldrig ett bart "kommer att hända".

Detta står inte i strid med neutralitetsgrinden: den blockerar OGRUNDAD
spekulation i fritext; det här lagret visar GRUNDADE scenarier med hela
underlaget synligt. Rent stdlib, bygger på `engine.stats`.
"""
from __future__ import annotations

import math

from .integrity import framing_disclosure
from .stats import linreg_trend, mean

MIN_HISTORY = 5
MIN_SOURCES = 2
MIN_R2 = 0.5   # en tendens måste FÖRKLARA variansen, inte bara luta
_MILESTONES = (1, 3, 5, 10)

CAVEAT = ("Scenario grounded in credible sources and a systematic historical "
          "tendency — NOT a prediction. Assumptions are explicit and the band "
          "widens with the horizon; it shows what the data supports, not what "
          "will happen.")


def _fit(series: list[float]):
    n = len(series)
    xs = list(range(n))
    mx, my = mean(xs), mean(series)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, series, strict=False)) / sxx if sxx else 0.0
    intercept = my - slope * mx
    resid = [y - (slope * x + intercept) for x, y in zip(xs, series, strict=False)]
    rmse = math.sqrt(mean([e * e for e in resid])) if n else 0.0
    ss_tot = sum((y - my) ** 2 for y in series)
    ss_res = sum(e * e for e in resid)
    r2 = (1 - ss_res / ss_tot) if ss_tot else 0.0
    return slope, intercept, rmse, r2, n


def assess_basis(series: list[float], sources: list) -> dict:
    """Är underlaget trovärdigt nog att alls uttala ett scenario?"""
    n = len(series)
    reasons = []
    if n < MIN_HISTORY:
        reasons.append(f"only {n} historical points (need ≥ {MIN_HISTORY})")
    if len(sources) < MIN_SOURCES:
        reasons.append(f"only {len(sources)} credible sources (need ≥ {MIN_SOURCES})")
    trend = linreg_trend(series) if n >= 2 else {"significant": False,
                                                 "direction": "stable", "r2": 0.0}
    # Systematisk tendens = signifikant riktning SOM förklarar variansen (R²),
    # annars är det brus med en lutning.
    if not (trend["significant"] and trend["r2"] >= MIN_R2):
        reasons.append(f"no systematic historical tendency "
                       f"(R²={trend['r2']:.2f} < {MIN_R2} or not significant)")
    return {"credible": not reasons, "reasons": reasons, "trend": trend}


def _credibility(n: int, r2: float, n_sources: int, coverage: float) -> str:
    score = (min(1.0, n / 20) * 0.3 + max(0.0, r2) * 0.3
             + min(1.0, n_sources / 4) * 0.2 + coverage * 0.2)
    return "high" if score >= 0.7 else "medium" if score >= 0.45 else "low"


def project(series: list[float], sources: list, *, horizon: int = 3,
            coverage: float = 1.0, metric: str = "indicator") -> dict:
    """Ett trovärdighets-grindat scenario. Se modulens docstring.

    horizon = antal perioder framåt. Returnerar antingen
    {status:"insufficient_basis", reasons} eller ett fullt scenario med
    baslinje, band, milstolpar (vidgande band), antaganden, källor, caveat.
    """
    basis = assess_basis(series, sources)
    if not basis["credible"]:
        return {"status": "insufficient_basis", "metric": metric,
                "reasons": basis["reasons"], "n_sources": len(sources),
                "caveat": "We do not speculate: the basis is not credible enough "
                          "to state a scenario. " + "; ".join(basis["reasons"]),
                "framing": framing_disclosure({"basis": "insufficient"})}
    slope, intercept, rmse, r2, n = _fit(series)
    spread = rmse if rmse > 0 else abs(series[-1]) * 0.02

    def band(h: int) -> dict:
        base = intercept + slope * (n - 1 + h)
        half = spread * (1 + h / max(1, n)) / max(0.2, coverage) * 1.96
        return {"horizon": h, "baseline": round(base, 4),
                "low": round(base - half, 4), "high": round(base + half, 4),
                "band_width": round(2 * half, 4)}

    conf = _credibility(n, r2, len(sources), coverage)
    return {
        "status": "scenario", "metric": metric, "horizon": horizon,
        "scenario": band(horizon),
        "milestones": [band(h) for h in _MILESTONES],
        "confidence": conf,
        "basis": {"history_points": n, "n_sources": len(sources),
                  "sources": sources, "coverage": coverage,
                  "tendency": {"direction": basis["trend"]["direction"],
                               "r2": r2, "significant": True}},
        "assumptions": [
            "the observed systematic historical tendency continues",
            "no structural break in the underlying system",
            "the credible sources remain representative",
            "uncertainty (the band) widens with the horizon"],
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"history_points": n, "n_sources": len(sources), "coverage": coverage,
             "method": "linear tendency + widening interval",
             "note": "scenario, not prediction"}),
    }
