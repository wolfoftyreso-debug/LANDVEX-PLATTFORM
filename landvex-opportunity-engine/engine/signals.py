"""Signalkatalog och normalisering.

Varje signal definierar hur ett råvärde översätts till 0..1:
  saturating : avtagande nytta, p1 = skalfaktor (bra vid ~2-3x p1)
  linear     : klipps mellan p1 (min) och p2 (max)
  inverse    : högre värde är sämre, klipps mellan p1 och p2
  band       : optimalt intervall p1..p2, faller av utanför
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SignalDef:
    id: str
    label_en: str
    unit: str
    norm: str
    p1: float = 0.0
    p2: float = 1.0


def normalize(d: SignalDef, x: float | None) -> float | None:
    if x is None:
        return None
    if d.norm == "saturating":
        return 1.0 - math.exp(-max(x, 0.0) / d.p1)
    if d.norm == "linear":
        return min(1.0, max(0.0, (x - d.p1) / (d.p2 - d.p1)))
    if d.norm == "inverse":
        return 1.0 - min(1.0, max(0.0, (x - d.p1) / (d.p2 - d.p1)))
    if d.norm == "band":
        if d.p1 <= x <= d.p2:
            return 1.0
        span = (d.p2 - d.p1) or 1.0
        dist = (d.p1 - x) if x < d.p1 else (x - d.p2)
        return max(0.0, 1.0 - dist / span)
    raise ValueError(f"Unknown normalization: {d.norm}")


def _s(id, label, unit, norm, p1=0.0, p2=1.0):
    return SignalDef(id, label, unit, norm, p1, p2)


CATALOG: dict[str, SignalDef] = {s.id: s for s in [
    # ── Befolkning & köpkraft ─────────────────────────────────────────
    _s("pop_radius",        "People within radius",         "people", "saturating", 6000),
    _s("population_total",  "Population (municipality)",    "people", "saturating", 80000),
    _s("pop_growth_pct",    "Population growth",            "%",      "linear", -2.0, 8.0),
    _s("income_index",      "Mean income (national avg=100)","index", "linear", 70, 130),
    _s("age_20_45_share",   "Share aged 20–45",             "%",      "linear", 15, 45),
    _s("families_share",    "Share of families with children","%",    "linear", 10, 40),
    _s("share_65plus",      "Share aged 65+",               "%",      "linear", 10, 35),
    _s("residential_density","Residential density",         "hh/km²", "saturating", 800),
    # ── Flöden & synlighet ────────────────────────────────────────────
    _s("foot_traffic",      "Passers-by per day",           "people", "saturating", 2500),
    _s("target_match_pct",  "Target group match",           "%",      "linear", 20, 80),
    _s("flow_morning",      "Morning flow (06–10)",         "people/h","saturating", 400),
    _s("flow_midday",       "Lunch flow (11–14)",           "people/h","saturating", 500),
    _s("flow_afternoon",    "Afternoon flow (14–18)",       "people/h","saturating", 400),
    _s("flow_evening",      "Evening flow (18–23)",         "people/h","saturating", 350),
    _s("commuter_flow",     "Commuter flow morning/evening","people", "saturating", 3000),
    # ── Tillgänglighet ────────────────────────────────────────────────
    _s("parking_score",     "Parking availability",         "0–10",   "linear", 0, 10),
    _s("transit_score",     "Public transport",             "0–10",   "linear", 0, 10),
    # ── Konkurrens (härledd i datalagret) ─────────────────────────────
    _s("competition_pressure", "Effective competitive pressure", "0–10", "inverse", 0, 10),
    _s("provider_gap",      "Supply gap (demand/supply)",   "ratio",  "linear", 0.8, 2.0),
    # ── Fastighet, bygg & näringsliv ──────────────────────────────────
    _s("detached_homes",    "Detached homes in area",       "units",  "saturating", 2500),
    _s("building_permits",  "Building permits last 12 mo",  "permits","saturating", 120),
    _s("renovation_index",  "Renovation activity",          "index",  "linear", 20, 100),
    _s("avg_building_age",  "Average building age",         "years",  "band", 25, 60),
    _s("ev_per_capita",     "EVs per 1,000 residents",      "units",  "saturating", 60),
    _s("business_density",  "Businesses per 1,000 residents","units", "saturating", 55),
    _s("office_workers",    "Office workers within radius", "people", "saturating", 4000),
    _s("hotel_beds",        "Hotel beds within radius",     "beds",   "saturating", 600),
    _s("tourism_index",     "Tourism index",                "0–100",  "linear", 0, 100),
    _s("event_days",        "Event days per year",          "days",   "saturating", 40),
    _s("detail_plans",      "Upcoming zoning plans",        "plans",  "saturating", 8),
    _s("development_m2",    "Development area",             "1000 m²","saturating", 150),
    _s("field_observation_density", "quiXzoom field observations",
       "obs/area", "saturating", 40),
    _s("infra_invest",      "Infrastructure investment",    "M local","saturating", 400),
    _s("insurance_index",   "Dental insurance coverage",    "index",  "linear", 60, 120),
    _s("care_supply",       "Other care services",          "0–10",   "band", 3, 7),
    # ── Fordon, djur & logistik ───────────────────────────────────────
    _s("cars_per_1000",     "Cars per 1,000 residents",     "units",  "saturating", 450),
    _s("avg_car_age",       "Average car age",              "years",  "band", 9, 14),
    _s("pets_per_1000",     "Pets per 1,000 residents",     "units",  "saturating", 280),
    _s("logistics_access",  "Logistics access (highway/terminal)","0–10","linear", 0, 10),
    # ── Riskindikatorer ───────────────────────────────────────────────
    _s("vacancy_rate",      "Commercial vacancy rate",      "%",      "inverse", 2, 15),
    _s("rent_index",        "Rent level (avg=100)",         "index",  "inverse", 90, 160),
    _s("crime_index",       "Crime index (avg=100)",        "index",  "inverse", 70, 140),
    _s("climate_risk_index","Climate risk index",           "0–100",  "inverse", 10, 80),
]}
