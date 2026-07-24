"""Kärnmodeller för LANDVEX Opportunity Engine.

Medvetet beroendefria (endast stdlib) så att motorn kan köras i
Lambda, ECS, batch-jobb eller lokalt utan installation.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float
    address: str = ""
    radius_minutes: int = 10  # gång-/körtidsradie för upptagningsområde


@dataclass
class SignalValue:
    signal_id: str
    value: Optional[float]
    source: str = "mock"        # "mock" | "scb" | "movement" | "permits" | "places" | ...
    quality: float = 0.5        # 0..1, datakvalitet/aktualitet


@dataclass
class FactorScore:
    id: str
    label_en: str
    score: float                # 0..100
    weight: float
    narrative_en: str = ""


@dataclass
class OpportunityReport:
    vertical_id: str
    vertical_label_en: str
    location: Location
    opportunity_score: float            # 0..100
    factors: list[FactorScore] = field(default_factory=list)
    risk_level: str = "Medium"          # "Low" | "Medium" | "High"
    risk_score: float = 0.5             # 0..1 (högre = mer risk)
    risk_narrative_en: str = ""
    recommendation_en: str = ""
    insights_en: list[str] = field(default_factory=list)
    data_coverage: float = 0.0          # andel signaler med verklig (icke-mock) källa
    caveats_en: list[str] = field(default_factory=list)
    # Full signalnedbrytning (förklarbarhet): {signal_id: {value, source,
    # quality, normalized}}. Grund för drivkraftslistor och confidence.
    signals: dict[str, Any] = field(default_factory=dict)
    # Spårbarhet: motorversionen som beräknade rapporten.
    engine_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
