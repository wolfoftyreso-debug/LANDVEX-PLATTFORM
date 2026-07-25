"""Lambda-index – geometrisk λ över samhällsaxlar (dissg "Lambda 1.0").

Skördat russin C. Ett enda läsbart tal för ett systems balans:
λ ≈ 1.0 = balanserat, λ < 1.0 = ineffektivitet/slöseri, λ > 1.0 =
överhettning/risk. Varje axel normaliseras 0–100 → 0.7–1.3 (median
50 → 1.0), och axlarna kollapsas med GEOMETRISKT medelvärde:

    λ = (a1 · a2 · … · aN)^(1/N)

Det geometriska medelvärdet är hela poängen: det STRAFFAR extremvärden
och blockerar "kompenserande lögner" – en stark axel kan inte maska en
svag (till skillnad från aritmetiskt medel). Rent stdlib, deterministiskt.

Källa i dissg: src/lib/lambda/lambda-1.0.ts:297,304-329;
lambda-calculator.ts:60-67,350-407 (band).
"""
from __future__ import annotations

import math

# 8 axlar (LambdaAxis). Etiketter för oscilloskop-vyn.
AXES: tuple[tuple[str, str], ...] = (
    ("ECON", "Economy"), ("HEALTH", "Health"), ("LABOR", "Labor"),
    ("EDUC", "Education"), ("SOCIAL", "Social stability"),
    ("CLIMATE", "Climate"), ("GOV", "Governance"), ("DEMO", "Demography"),
)
_AXIS_KEYS = tuple(k for k, _ in AXES)

# Interpretationsband (fallande), (min_inklusive, kod, etikett, färg).
BANDS: tuple[tuple[float, str, str, str], ...] = (
    (1.30, "critical_overheat", "Critical overheating", "#FF3B30"),
    (1.15, "overheated", "Overheated", "#FF9500"),
    (1.10, "warning_high", "Running hot", "#FFCC00"),
    (0.90, "balanced", "Balanced", "#34C759"),
    (0.85, "warning_low", "Running cold", "#FFCC00"),
    (0.70, "inefficient", "Inefficient", "#FF9500"),
    (0.00, "critical_inefficient", "Critical inefficiency", "#FF3B30"),
)


def normalize_axis(raw: float) -> float:
    """0–100 → 0.7–1.3 (median 50 → 1.0). Klippt till [0.7, 1.3]."""
    v = 0.7 + (max(0.0, min(100.0, float(raw))) / 100.0) * 0.6
    return round(v, 6)


def interpret(lam: float) -> dict[str, str]:
    for lo, code, label, color in BANDS:
        if lam >= lo:
            return {"code": code, "label": label, "color": color}
    lo, code, label, color = BANDS[-1]
    return {"code": code, "label": label, "color": color}


def lambda_score(axes: dict[str, float]) -> dict:
    """Beräkna λ ur axelvärden 0–100. Saknad axel utelämnas ärligt.

    Returnerar {lambda, interpretation, coverage, axes[], primary_drivers[]}.
    `coverage` = andel av de 8 axlarna som fanns (ärlig täckning, princip 4).
    `primary_drivers` = axlarna längst från optimum (1.0), störst avvikelse
    först – förklarbarheten bakom talet.
    """
    present = [(k, float(axes[k])) for k in _AXIS_KEYS if k in axes]
    if not present:
        return {"lambda": None, "interpretation": interpret(1.0),
                "coverage": 0.0, "axes": [], "primary_drivers": []}
    norm = [(k, normalize_axis(v), v) for k, v in present]
    prod = 1.0
    for _, n, _raw in norm:
        prod *= n
    lam = round(prod ** (1.0 / len(norm)), 4)
    axis_rows = [{"axis": k, "raw": round(raw, 4), "normalized": n,
                  "deviation": round(n - 1.0, 4)} for k, n, raw in norm]
    drivers = sorted(axis_rows, key=lambda r: -abs(r["deviation"]))
    return {
        "lambda": lam,
        "interpretation": interpret(lam),
        "coverage": round(len(norm) / len(_AXIS_KEYS), 4),
        "axes": axis_rows,
        "primary_drivers": [d["axis"] for d in drivers[:3]],
    }


def lambda_index(axes: dict[str, float]) -> dict:
    """Publik ingång (alias för lambda_score) – stämpelbar i API-svaret."""
    return lambda_score(axes)
