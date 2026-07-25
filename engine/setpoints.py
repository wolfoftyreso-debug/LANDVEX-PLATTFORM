"""Setpoint- & toleranslager – kalibrerade referensvärden (dissg russin E).

ECU-stil-kalibrering per indikator: ett börvärde (setpoint) och fyra
nästlade zoner (optimal ⊂ acceptable ⊂ warning; utanför = critical), var
och en med härledningsprovenens. Det ger Landvex ett ÄRLIGT, sourcat
referenslager: "var ligger detta värde mot ett kalibrerat optimum?" i
stället för en godtycklig 0–100-normalisering.

Tabellen är DATA (ny indikator = ny rad). Hårda tal ur dissg
setpoint-tolerance.ts (Maastricht 60 %, Gini 0.30, TFR 2.1, social
tillit 65 …) med källa. Rent stdlib, deterministiskt.

`direction`:
  higher_better  – högre är bättre (livslängd, tillit)
  lower_better   – lägre är bättre (arbetslöshet, skuld, Gini)
  neutral_optimal– ett målfönster, avvikelse åt båda håll är sämre (inflation, TFR)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

INF = math.inf


@dataclass(frozen=True)
class Setpoint:
    code: str
    label: str
    unit: str
    setpoint: float                 # kalibrerat börvärde (optimumcentrum)
    direction: str                  # higher_better|lower_better|neutral_optimal
    optimal: tuple[float, float]    # (lo, hi) inklusive
    acceptable: tuple[float, float]
    warning: tuple[float, float]
    source: str = ""


# Kalibreringstabell – hårda referensvärden med källa (dissg setpoint-tolerance).
SETPOINTS: tuple[Setpoint, ...] = (
    Setpoint("tfr", "Total fertility rate", "children/woman", 2.1,
             "neutral_optimal", (2.0, 2.4), (1.8, 2.6), (1.5, 3.0),
             "Replacement level 2.1 (demographic convention)."),
    Setpoint("dependency_ratio", "Dependency ratio", "%", 50.0,
             "lower_better", (0, 55), (0, 60), (0, 65),
             ">60% = structural stress (OECD)."),
    Setpoint("inflation_cpi", "CPI inflation", "%", 2.0,
             "neutral_optimal", (1.5, 2.5), (1.0, 3.0), (0.0, 4.0),
             "Central-bank target band 2% ±0.5."),
    Setpoint("unemployment", "Unemployment", "%", 4.5,
             "lower_better", (0, 4.5), (0, 6.0), (0, 8.0),
             "~NAIRU reference 4.5%."),
    Setpoint("debt_to_gdp", "Public debt / GDP", "%", 60.0,
             "lower_better", (0, 60), (0, 80), (0, 100),
             "Maastricht criterion 60%."),
    Setpoint("life_expectancy", "Life expectancy", "years", 82.0,
             "higher_better", (82, INF), (80, INF), (78, INF),
             "High-income reference ~82y."),
    Setpoint("infant_mortality", "Infant mortality", "per 1000", 3.0,
             "lower_better", (0, 3), (0, 5), (0, 8),
             "Best-performing systems ≤3/1000."),
    Setpoint("gini", "Gini coefficient", "index", 0.30,
             "lower_better", (0, 0.30), (0, 0.35), (0, 0.40),
             "Low-inequality reference 0.30."),
    Setpoint("social_trust", "Social trust", "%", 65.0,
             "higher_better", (65, INF), (55, INF), (45, INF),
             "High-trust society reference 65%."),
)

_BY_CODE: dict[str, Setpoint] = {s.code: s for s in SETPOINTS}

# Representativ zon-score (heuristik, märkt) för att mata t.ex. λ-axlar.
_ZONE_SCORE = {"optimal": 90.0, "acceptable": 70.0, "warning": 45.0,
               "critical": 20.0}


def _in(v: float, band: tuple[float, float]) -> bool:
    return band[0] <= v <= band[1]


def assess_zone(code: str, value: float) -> dict:
    """Placera ett värde i sin kalibrerade zon med avvikelse mot börvärdet.

    Returnerar {code, value, setpoint, zone, deviation_pct, direction, unit,
    source}. zone ∈ {optimal, acceptable, warning, critical}.
    """
    s = _BY_CODE.get(code)
    if s is None:
        raise ValueError(f"okänt setpoint: {code}")
    v = float(value)
    if _in(v, s.optimal):
        zone = "optimal"
    elif _in(v, s.acceptable):
        zone = "acceptable"
    elif _in(v, s.warning):
        zone = "warning"
    else:
        zone = "critical"
    dev = ((v - s.setpoint) / s.setpoint * 100.0) if s.setpoint else 0.0
    return {"code": s.code, "label": s.label, "unit": s.unit,
            "value": v, "setpoint": s.setpoint, "direction": s.direction,
            "zone": zone, "deviation_pct": round(dev, 4),
            "source": s.source}


def zone_score(code: str, value: float) -> float:
    """Representativ 0–100-score ur zonen (heuristik, märkt) – för λ-axlar m.m."""
    return _ZONE_SCORE[assess_zone(code, value)["zone"]]


def catalog() -> list[dict]:
    """Setpoint-tabellen som självbeskrivande data (för /v1/setpoints)."""
    def _b(t: tuple[float, float]) -> list:
        return [None if x == INF else x for x in t]
    return [{"code": s.code, "label": s.label, "unit": s.unit,
             "setpoint": s.setpoint, "direction": s.direction,
             "optimal": _b(s.optimal), "acceptable": _b(s.acceptable),
             "warning": _b(s.warning), "source": s.source}
            for s in SETPOINTS]
