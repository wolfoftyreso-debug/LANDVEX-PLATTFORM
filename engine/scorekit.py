"""Generisk viktad komponent-scorer – det mest återanvända russinet ur dissg.

Samma form dyker upp tre gånger i referensprototypen och unifieras här:

  * 6-faktors relevans-rank (calculate-relevance/index.ts:84-319)
  * 4-faktors åtgärdsprioritet (prioritize-actions/index.ts:52-70)
  * 5-faktors wrapped-worthiness (worthinessEngine.ts:106-401)

Alla har formen: varje komponent ger ett normaliserat värde 0–100, en
vikt, och kan vara *inverterad* (100 − v, t.ex. risk där lågt är bra); de
vägs samman, klipps till 0–100, och ett tröskelvärde avgör highlight.
Utfallet bär full nedbrytning + den mest bidragande komponenten som
"primary_reason" – förklarbarhet före prediktion (Landvex-princip 3).

Ren stdlib, deterministisk. Vikttabellerna är DATA (ny profil = ny
konstant), ingen affärsregel gömd i motorlogiken.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    """En scoring-komponent. `weight` behöver inte summera till 1 – normaliseras.

    invert=True vänder värdet (100 − v) innan viktning (för dimensioner där
    lågt är bra, t.ex. risk/kostnad). `reason` är den mänskliga etiketten
    som blir primary_reason om komponenten dominerar.
    """
    key: str
    weight: float
    invert: bool = False
    reason: str = ""


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def score(components: list[Component], values: dict[str, float],
          highlight_threshold: float = 50.0) -> dict:
    """Väg samman komponenter till ett 0–100-tal med full nedbrytning.

    values: {key: 0–100}. Saknad nyckel behandlas som 0. Returnerar
    {total, highlight, breakdown[], primary_reason, secondary_reasons[]}.
    Determinism: samma indata → samma utfall (stabil sortering på bidrag,
    sedan key för lika värden).
    """
    total_w = sum(c.weight for c in components)
    if total_w <= 0:
        return {"total": 0.0, "highlight": False, "breakdown": [],
                "primary_reason": "", "secondary_reasons": []}
    breakdown = []
    acc = 0.0
    for c in components:
        raw = _clamp(float(values.get(c.key, 0.0)))
        eff = (100.0 - raw) if c.invert else raw
        contribution = eff * (c.weight / total_w)
        acc += contribution
        breakdown.append({"key": c.key, "value": round(raw, 4),
                          "effective": round(eff, 4),
                          "weight": c.weight,
                          "contribution": round(contribution, 4),
                          "reason": c.reason or c.key})
    ranked = sorted(breakdown, key=lambda b: (-b["contribution"], b["key"]))
    total = round(_clamp(acc), 4)
    return {
        "total": total,
        "highlight": total >= highlight_threshold,
        "breakdown": breakdown,
        "primary_reason": ranked[0]["reason"] if ranked else "",
        "secondary_reasons": [b["reason"] for b in ranked[1:3]],
    }


def band(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    """Mappa ett värde till ett band. `bands` = ((min_inklusive, etikett), …)
    i FALLANDE ordning. Första matchande gräns vinner."""
    for lo, label in bands:
        if value >= lo:
            return label
    return bands[-1][1] if bands else ""


# --- Konkreta vikt-profiler ur dissg (data, inte kod) --------------------
# 6-faktors relevans: vad påverkar flest, mest, nu, där ansvar finns.
RELEVANCE: tuple[Component, ...] = (
    Component("impact", 0.30, reason="High societal impact"),
    Component("acceleration", 0.20, reason="Rapid change"),
    Component("breadth", 0.15, reason="Wide geographic spread"),
    Component("persistence", 0.15, reason="Sustained trend"),
    Component("responsibility", 0.10, reason="Clear responsibility"),
    Component("data_confidence", 0.10, reason="Strong data confidence"),
)

# 4-faktors åtgärdsprioritet: risk är inverterad (låg risk är bra).
ACTION: tuple[Component, ...] = (
    Component("effect", 0.40, reason="Large expected effect"),
    Component("cost", 0.25, invert=True, reason="Low cost"),
    Component("risk", 0.20, invert=True, reason="Low risk"),
    Component("reversibility", 0.15, reason="Reversible"),
)
# Prioritetsband (fallande): ≥80 kritisk, ≥65 hög, ≥45 medel, ≥25 låg, annars bevaka.
ACTION_BANDS: tuple[tuple[float, str], ...] = (
    (80.0, "critical"), (65.0, "high"), (45.0, "medium"),
    (25.0, "low"), (0.0, "monitor"),
)

# 5-faktors wrapped-worthiness (caps 40/25/15/10/10 → normaliserade vikter).
WORTHINESS: tuple[Component, ...] = (
    Component("relevance", 0.40, reason="High relevance"),
    Component("magnitude", 0.25, reason="Large change"),
    Component("velocity", 0.15, reason="Accelerating"),
    Component("quality", 0.10, reason="High data quality"),
    Component("impact", 0.10, reason="Cross-domain impact"),
)
