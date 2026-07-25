"""Statistik-kit – ren stdlib, ingen numpy. Skördat ur dissg analyze-kpi.

Riktig signal-detektion i stället för heuristiska delta: konsekutiv
trend-styrka, CUSUM change-point, Pearson/Spearman-korrelation, lag-
korskorrelation och z-score-anomali – plus normaliserings- och
percentil-hjälpare. Allt deterministiskt och beroendefritt (Landvex-
princip 2 + 5).

Källor i dissg (fil:rad): analyze-kpi 56-181, 305-318; normalization.ts;
correlation-engine.ts (Spearman via rangordning).
"""
from __future__ import annotations

import math


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def pstdev(xs: list[float]) -> float:
    """Populations-standardavvikelse (0.0 för tom/enpunktslista)."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / n)


def trend_strength(values: list[float]) -> dict:
    """Längsta konsekutiva riktning + styrka (analyze-kpi 56-91).

    strength = min(100, (max_konsekutiv / n) * 100 + 20). Riktning ur den
    sista sammanhängande sekvensen.
    """
    n = len(values)
    if n < 2:
        return {"direction": "stable", "strength": 0.0, "max_run": 0}
    best, best_dir = 0, "stable"
    cur, cur_dir = 1, "stable"
    for a, b in zip(values, values[1:]):
        d = "up" if b > a else ("down" if b < a else "stable")
        if d == cur_dir and d != "stable":
            cur += 1
        else:
            cur, cur_dir = 1, d
        if d != "stable" and cur > best:
            best, best_dir = cur, d
    strength = min(100.0, (best / n) * 100.0 + 20.0)
    return {"direction": best_dir, "strength": round(strength, 4),
            "max_run": best}


def cusum_changepoint(values: list[float], threshold: float = 2.5) -> dict:
    """CUSUM change-point-detektion (analyze-kpi 94-133).

    Standardisera (v−mean)/std, ackumulera, spåra max |CUSUM|. detected om
    max > threshold (~2.5 ≈ 95%). significance skalas 50–100.
    """
    n = len(values)
    sd = pstdev(values)
    if n < 3 or sd == 0:
        return {"detected": False, "max_cusum": 0.0, "significance": 0.0,
                "index": -1}
    m = mean(values)
    cusum = 0.0
    max_cusum = 0.0
    idx = -1
    for i, v in enumerate(values):
        cusum += (v - m) / sd
        if abs(cusum) > max_cusum:
            max_cusum, idx = abs(cusum), i
    detected = max_cusum > threshold
    significance = min(100.0, (max_cusum / threshold) * 50.0 + 50.0) \
        if detected else round(min(50.0, (max_cusum / threshold) * 50.0), 4)
    return {"detected": detected, "max_cusum": round(max_cusum, 4),
            "significance": round(significance, 4), "index": idx}


def pearson(x: list[float], y: list[float]) -> float:
    """Pearsons r (analyze-kpi 136-152). 0.0 vid degenererad indata."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x, y = x[:n], y[:n]
    mx, my = mean(x), mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x)
                    * sum((b - my) ** 2 for b in y))
    return round(num / den, 6) if den else 0.0


def _ranks(xs: list[float]) -> list[float]:
    """Medelrang (ties → snittrang)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    """Spearmans rho via rangordning (correlation-engine.ts 64-78)."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    return pearson(_ranks(x[:n]), _ranks(y[:n]))


def lag_correlation(x: list[float], y: list[float], max_lag: int = 6) -> dict:
    """Korskorrelation över lag 0..max_lag, bästa |r| (analyze-kpi 155-181).

    Positiv lag: y släpar efter x (x[t] mot y[t+lag]).
    """
    best = {"best_lag": 0, "correlation": 0.0}
    n = min(len(x), len(y))
    for lag in range(0, max_lag + 1):
        if n - lag < 2:
            break
        r = pearson(x[:n - lag], y[lag:n])
        if abs(r) > abs(best["correlation"]):
            best = {"best_lag": lag, "correlation": r}
    return best


def zscore_anomaly(values: list[float], value: float | None = None,
                   z_threshold: float = 2.0) -> dict:
    """Z-score-anomali (analyze-kpi 305-318). Testar sista punkten om value=None.

    z = |v − mean| / std; anomali om z > threshold.
    confidence = min(0.5 + (z−2)*0.15, 0.95); signal_strength = min(z/4, 1).
    """
    if len(values) < 2:
        return {"is_anomaly": False, "z": 0.0, "confidence": 0.0,
                "signal_strength": 0.0}
    sd = pstdev(values)
    v = values[-1] if value is None else float(value)
    if sd == 0:
        return {"is_anomaly": False, "z": 0.0, "confidence": 0.0,
                "signal_strength": 0.0}
    z = abs(v - mean(values)) / sd
    is_anom = z > z_threshold
    return {
        "is_anomaly": is_anom, "z": round(z, 4),
        "confidence": round(min(0.5 + (z - 2.0) * 0.15, 0.95), 4)
        if is_anom else 0.0,
        "signal_strength": round(min(z / 4.0, 1.0), 4),
    }


def linreg_trend(values: list[float], significance_pct: float = 2.0) -> dict:
    """Linjär regression: lutning, R², riktning, signifikans (normalization.ts).

    x = 0..n−1. `significant` om |lutning per steg| ≥ significance_pct % av
    medelvärdet. Riktning ur lutningens tecken.
    """
    n = len(values)
    if n < 2:
        return {"slope": 0.0, "r2": 0.0, "direction": "stable",
                "significant": False}
    xs = list(range(n))
    mx, my = mean(xs), mean(values)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return {"slope": 0.0, "r2": 0.0, "direction": "stable",
                "significant": False}
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, values)) / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in values)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, values))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot else 0.0
    thresh = abs(my) * significance_pct / 100.0
    direction = "stable"
    if abs(slope) >= thresh and thresh > 0:
        direction = "up" if slope > 0 else "down"
    return {"slope": round(slope, 6), "r2": round(r2, 4),
            "direction": direction, "significant": direction != "stable"}


def percentile_rank(value: float, population: list[float]) -> float:
    """Percentilrang 0–100: ((antal_under + 0.5*antal_lika)/n)*100."""
    n = len(population)
    if n == 0:
        return 0.0
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return round(((below + 0.5 * equal) / n) * 100.0, 4)


def minmax(value: float, lo: float, hi: float) -> float:
    """Min-max-normalisering till 0–100 (klippt)."""
    if hi == lo:
        return 0.0
    return round(max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0)), 4)
