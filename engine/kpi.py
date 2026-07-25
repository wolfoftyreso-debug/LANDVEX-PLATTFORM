"""KPI-motor – registry, invert-medveten status/trend, tröskel-alerts.

Skördat ur dissg (kpi_definitions-schema, kolada-ingest status-regel,
kpi-alerts tröskeltabell, calculate-relevance rank). Bygger på
`engine.integrity` (trend-härledning), `engine.stats` (velocity) och
`engine.scorekit` (relevans-rank). Rent stdlib, deterministiskt.

En KPI är DATA (`KpiDefinition`); status, trend och alerts är rena
funktioner av värden. `is_inverted` fångar "lägre är bättre"-indikatorer
(t.ex. arbetslöshet) så att statusen blir korrekt utan specialfall i
motorn.

Källor i dissg: migration 20260201214947 (kpi_definitions/kpi_values),
kolada-ingest 197-227 (status/trend), kpi-alerts 19-146 (trösklar),
calculate-relevance 84-319 (rank).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from . import scorekit
from .integrity import derive_trend

# 7 kategorier (kpi_definitions category enum).
CATEGORIES: tuple[str, ...] = (
    "demografi_halsa", "arbete_produktivitet", "ekonomisk_barkraft",
    "social_stabilitet", "karnsystem_funktion", "infrastruktur",
    "systemrisk_styrning",
)


@dataclass(frozen=True)
class KpiDefinition:
    """En KPI som data. `is_inverted`=True när minskning är positivt.

    Alert-trösklar (valfria): `warning`/`critical` absolutnivåer med
    `direction` ('above'|'below'), och `velocity_warning`/`velocity_critical`
    som SIGNERADE trend-%-trösklar (positiv = larma vid stigning, negativ =
    larma vid fall).
    """
    kpi_index: int                      # 1..100
    code: str
    name: str
    category: str
    unit: str = ""
    is_inverted: bool = False
    warning: float | None = None
    critical: float | None = None
    direction: str = "above"            # 'above' | 'below'
    velocity_warning: float | None = None
    velocity_critical: float | None = None

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"okänd kategori: {self.category}")
        if not (1 <= self.kpi_index <= 100):
            raise ValueError("kpi_index måste vara 1..100")


def derive_status(value: float, previous: float | None, is_inverted: bool,
                  stable_pct: float = 0.5) -> dict:
    """Invert-medveten status + trend (kolada-ingest 197-227).

    |Δ%| < stable_pct → stable/neutral. Annars: förbättring → positive;
    försämring → critical om |Δ|>5 %, annars warning.
    """
    direction, trend_pct = derive_trend(value, previous, stable_pct=stable_pct)
    if direction == "stable":
        return {"status": "neutral", "trend": "stable", "trend_percent": trend_pct}
    improving = (direction == "down") if is_inverted else (direction == "up")
    if improving:
        status = "positive"
    else:
        status = "critical" if abs(trend_pct) > 5.0 else "warning"
    return {"status": status, "trend": direction, "trend_percent": trend_pct}


def evaluate_alerts(defn: KpiDefinition, value: float,
                    previous: float | None = None) -> list[dict]:
    """Absolut- och velocity-tröskelvarningar (kpi-alerts 58-146).

    Absolut brytning kollas först (riktnings-medveten), sedan velocity mot
    trend-%. Returnerar en lista av {alert_type, severity, detail}.
    """
    alerts: list[dict] = []
    # --- Absolut brytning ---
    if defn.critical is not None or defn.warning is not None:
        if defn.direction == "above":
            if defn.critical is not None and value >= defn.critical:
                sev = "critical"
            elif defn.warning is not None and value >= defn.warning:
                sev = "warning"
            else:
                sev = None
        else:  # below
            if defn.critical is not None and value <= defn.critical:
                sev = "critical"
            elif defn.warning is not None and value <= defn.warning:
                sev = "warning"
            else:
                sev = None
        if sev:
            alerts.append({"alert_type": "threshold_breach", "severity": sev,
                           "detail": f"{defn.code}={value} {defn.direction} "
                                     f"{getattr(defn, sev)}"})
    # --- Velocity ---
    if previous not in (None, 0):
        _, trend_pct = derive_trend(value, previous, stable_pct=0.0)
        sev = _velocity_severity(trend_pct, defn.velocity_warning,
                                 defn.velocity_critical)
        if sev:
            alerts.append({"alert_type": "velocity_warning", "severity": sev,
                           "detail": f"{defn.code} Δ={trend_pct}%"})
    return alerts


def _velocity_severity(trend_pct: float, warn: float | None,
                       crit: float | None) -> str | None:
    def breached(thr: float | None) -> bool:
        if thr is None:
            return False
        return trend_pct >= thr if thr > 0 else trend_pct <= thr
    if breached(crit):
        return "critical"
    if breached(warn):
        return "warning"
    return None


def rank_relevance(rows: list[dict], highlight_threshold: float = 50.0) -> list[dict]:
    """Rangordna KPI-rader på 6-faktors relevans (calculate-relevance).

    Varje rad bär de sex komponenterna 0–100 (impact, acceleration, breadth,
    persistence, responsibility, data_confidence) + valfri `code`. Returnerar
    rader sorterade fallande på total med nedbrytning och primary_reason.
    """
    scored = []
    for r in rows:
        s = scorekit.score(list(scorekit.RELEVANCE), r, highlight_threshold)
        scored.append({**{k: r[k] for k in ("code", "name") if k in r},
                       "relevance": s})
    return sorted(scored, key=lambda x: (-x["relevance"]["total"],
                                         x.get("code", "")))


# --- Exempel-registry (data). Riktiga trösklar ur kpi-alerts 19-44. --------
REGISTRY: tuple[KpiDefinition, ...] = (
    KpiDefinition(1, "life_expectancy", "Life expectancy", "demografi_halsa",
                  "years", warning=82, critical=80, direction="below",
                  velocity_warning=-0.5, velocity_critical=-1.0),
    KpiDefinition(2, "employment_rate_net", "Net employment rate",
                  "arbete_produktivitet", "%", warning=68, critical=65,
                  direction="below", velocity_warning=-1.0, velocity_critical=-2.0),
    KpiDefinition(3, "excess_mortality", "Excess mortality", "demografi_halsa",
                  "%", is_inverted=True, warning=3, critical=5, direction="above",
                  velocity_warning=20, velocity_critical=50),
    KpiDefinition(4, "violent_crime_rate", "Violent crime rate",
                  "social_stabilitet", "per 100k", is_inverted=True,
                  warning=40, critical=50, direction="above"),
    KpiDefinition(5, "energy_stability", "Energy stability",
                  "karnsystem_funktion", "index", warning=60, critical=40,
                  direction="below"),
)

_BY_CODE: dict[str, KpiDefinition] = {d.code: d for d in REGISTRY}


def kpi_catalog() -> list[dict]:
    """Registret som självbeskrivande data (för /v1/kpi)."""
    return [dataclasses.asdict(d) for d in REGISTRY]


def evaluate(code: str, value: float, previous: float | None = None) -> dict:
    """Status + trend + alerts för en KPI-kod (för /v1/kpi/evaluate)."""
    d = _BY_CODE.get(code)
    if d is None:
        raise ValueError(f"okänd KPI: {code}")
    st = derive_status(value, previous, d.is_inverted)
    return {"code": code, "name": d.name, "category": d.category,
            "unit": d.unit, "is_inverted": d.is_inverted, "value": value,
            "previous": previous, **st,
            "alerts": evaluate_alerts(d, value, previous)}
