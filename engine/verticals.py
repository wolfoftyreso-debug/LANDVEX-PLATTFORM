"""Vertikalprofiler.

Varje bransch definieras som data, inte kod: faktorer, vikter och
vilka signaler som ingår. Ny vertikal = ny profil här, inga kodändringar
i motorn. Det är detta som gör att en frisör och en elektriker får
helt olika analyser ur samma system.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorSpec:
    id: str
    label_en: str
    weight: float
    signals: tuple  # ((signal_id, vikt), ...)


@dataclass(frozen=True)
class VerticalProfile:
    id: str
    label_en: str
    factors: tuple


def _f(id, label, weight, *signals):
    return FactorSpec(id, label, weight, tuple(signals))


VERTICALS: dict[str, VerticalProfile] = {p.id: p for p in [

    VerticalProfile("frisor", "Hair salon", (
        _f("kundunderlag", "Customer base", 0.22, ("pop_radius", 1.0)),
        _f("synlighet",    "Visibility",    0.18, ("foot_traffic", 1.0)),
        _f("matchning",    "Target match",  0.16, ("target_match_pct", 1.0)),
        _f("konkurrens",   "Competition",   0.18, ("competition_pressure", 0.6), ("provider_gap", 0.4)),
        _f("kopkraft",     "Purchasing power", 0.14, ("income_index", 1.0)),
        _f("tillvaxt",     "Growth",        0.12, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("elektriker", "Electrician", (
        _f("fastighetsbestand", "Building stock", 0.24,
           ("detached_homes", 0.6), ("avg_building_age", 0.4)),
        _f("byggaktivitet", "Construction & renovation activity", 0.26,
           ("building_permits", 0.6), ("renovation_index", 0.4)),
        _f("elektrifiering", "Electrification", 0.16, ("ev_per_capita", 1.0)),
        _f("naringsliv", "Business & industry", 0.14, ("business_density", 1.0)),
        _f("marknadsutrymme", "Market headroom", 0.20,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
    )),

    VerticalProfile("gym", "Gym & fitness", (
        _f("malgrupp", "Age structure & target group", 0.22,
           ("age_20_45_share", 0.7), ("pop_radius", 0.3)),
        _f("kopkraft", "Purchasing power", 0.14, ("income_index", 1.0)),
        _f("bostadstathet", "Residential density", 0.16, ("residential_density", 1.0)),
        _f("tillganglighet", "Parking & public transport", 0.16,
           ("parking_score", 0.5), ("transit_score", 0.5)),
        _f("rorelse", "Morning/evening movement patterns", 0.16, ("commuter_flow", 1.0)),
        _f("konkurrens", "Competition", 0.16, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("restaurang", "Restaurant", (
        _f("lunch", "Lunch traffic", 0.20,
           ("flow_midday", 0.6), ("office_workers", 0.4)),
        _f("kvall", "Evening traffic", 0.20, ("flow_evening", 1.0)),
        _f("besoksnaring", "Tourism, hotels & events", 0.16,
           ("hotel_beds", 0.4), ("tourism_index", 0.35), ("event_days", 0.25)),
        _f("tillganglighet", "Parking & location", 0.12,
           ("parking_score", 0.5), ("transit_score", 0.5)),
        _f("kopkraft", "Purchasing power", 0.14, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.18, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("cafe", "Café", (
        _f("morgon", "Morning flow", 0.26, ("flow_morning", 1.0)),
        _f("dag", "Midday flow", 0.18, ("flow_midday", 1.0)),
        _f("eftermiddag", "Afternoon flow", 0.16, ("flow_afternoon", 1.0)),
        _f("gangtrafik", "Total foot traffic", 0.16, ("foot_traffic", 1.0)),
        _f("kopkraft", "Purchasing power", 0.10, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.14, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("bygg", "Construction company", (
        _f("detaljplaner", "Upcoming zoning plans", 0.24, ("detail_plans", 1.0)),
        _f("exploatering", "Development projects", 0.22, ("development_m2", 1.0)),
        _f("bygglov", "Building permit volume", 0.20, ("building_permits", 1.0)),
        _f("infrastruktur", "Infrastructure & municipal investment", 0.18,
           ("infra_invest", 1.0)),
        _f("marknadsutrymme", "Market headroom", 0.16, ("provider_gap", 1.0)),
    )),

    VerticalProfile("tandlakare", "Dental practice", (
        _f("barnfamiljer", "Families with children", 0.22, ("families_share", 1.0)),
        _f("aldre", "Senior population", 0.18, ("share_65plus", 1.0)),
        _f("forsakring", "Insurance coverage", 0.16, ("insurance_index", 1.0)),
        _f("konkurrens", "Competition & supply gap", 0.26,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("vardutbud", "Other care services", 0.18, ("care_supply", 1.0)),
    )),

    VerticalProfile("vvs", "Plumbing & HVAC company", (
        _f("fastighetsbestand", "Building stock", 0.24,
           ("detached_homes", 0.6), ("avg_building_age", 0.4)),
        _f("byggaktivitet", "Construction & renovation activity", 0.28,
           ("building_permits", 0.6), ("renovation_index", 0.4)),
        _f("exploatering", "Development projects", 0.14, ("development_m2", 1.0)),
        _f("marknadsutrymme", "Market headroom", 0.22,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
        _f("kopkraft", "Purchasing power", 0.12, ("income_index", 1.0)),
    )),

    VerticalProfile("bilverkstad", "Car repair shop", (
        _f("bilbestand", "Car stock & vehicle age", 0.26,
           ("cars_per_1000", 0.6), ("avg_car_age", 0.4)),
        _f("upptagning", "Catchment area", 0.18,
           ("pop_radius", 0.6), ("detached_homes", 0.4)),
        _f("pendling", "Commuting & traffic", 0.16, ("commuter_flow", 1.0)),
        _f("naringsliv", "Business customers", 0.12, ("business_density", 1.0)),
        _f("marknadsutrymme", "Market headroom", 0.18,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("kopkraft", "Purchasing power", 0.10, ("income_index", 1.0)),
    )),

    VerticalProfile("veterinar", "Veterinary clinic", (
        _f("djurunderlag", "Pet population", 0.30,
           ("pets_per_1000", 0.7), ("detached_homes", 0.3)),
        _f("barnfamiljer", "Families with children", 0.16, ("families_share", 1.0)),
        _f("kopkraft", "Purchasing power", 0.16, ("income_index", 1.0)),
        _f("konkurrens", "Competition & supply gap", 0.24,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("tillvaxt", "Growth", 0.14, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("lager", "Warehousing & logistics", (
        _f("logistiklage", "Logistics location", 0.28, ("logistics_access", 1.0)),
        _f("naringsliv", "Business density", 0.18, ("business_density", 1.0)),
        _f("exploatering", "Land & development", 0.20,
           ("development_m2", 0.6), ("detail_plans", 0.4)),
        _f("infrastruktur", "Infrastructure investment", 0.16,
           ("infra_invest", 1.0)),
        _f("kostnadslage", "Cost level (rent)", 0.18, ("rent_index", 1.0)),
    )),

    VerticalProfile("forskola", "Preschool", (
        _f("barnunderlag", "Child population", 0.32,
           ("families_share", 0.7), ("pop_radius", 0.3)),
        _f("tillvaxt", "Growth", 0.18, ("pop_growth_pct", 1.0)),
        _f("bostadstathet", "Residential density", 0.15, ("residential_density", 1.0)),
        _f("utbud", "Supply & place shortage", 0.20,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("tillganglighet", "Drop-off/pick-up access", 0.15,
           ("parking_score", 0.5), ("transit_score", 0.5)),
    )),

    VerticalProfile("apotek", "Pharmacy", (
        _f("upptagning", "Catchment area", 0.25, ("pop_radius", 1.0)),
        _f("aldre", "Senior population", 0.20, ("share_65plus", 1.0)),
        _f("flode", "Customer flow", 0.20, ("foot_traffic", 1.0)),
        _f("vardutbud", "Proximity to care", 0.15, ("care_supply", 1.0)),
        _f("konkurrens", "Competition", 0.20, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("optiker", "Optician", (
        _f("upptagning", "Catchment area", 0.25, ("pop_radius", 1.0)),
        _f("aldre", "Senior population", 0.20, ("share_65plus", 1.0)),
        _f("synlighet", "Visibility", 0.20, ("foot_traffic", 1.0)),
        _f("kopkraft", "Purchasing power", 0.15, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.20, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("bageri", "Bakery", (
        _f("morgon", "Morning flow", 0.30, ("flow_morning", 1.0)),
        _f("gangtrafik", "Foot traffic", 0.20, ("foot_traffic", 1.0)),
        _f("bostadstathet", "Residential density", 0.15, ("residential_density", 1.0)),
        _f("kopkraft", "Purchasing power", 0.15, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.20, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("livsmedel", "Grocery store", (
        _f("upptagning", "Catchment area", 0.30,
           ("pop_radius", 0.6), ("residential_density", 0.4)),
        _f("parkering", "Parking", 0.15, ("parking_score", 1.0)),
        _f("tillvaxt", "Growth", 0.15, ("pop_growth_pct", 1.0)),
        _f("kopkraft", "Purchasing power", 0.15, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.25, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("aldreomsorg", "Elderly care & home care", (
        _f("aldre", "Senior population", 0.35, ("share_65plus", 1.0)),
        _f("upptagning", "Catchment area", 0.15, ("pop_radius", 1.0)),
        _f("vardutbud", "Other care services", 0.15, ("care_supply", 1.0)),
        _f("utbud", "Supply gap", 0.20, ("provider_gap", 1.0)),
        _f("tillvaxt", "Growth", 0.15, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("stadfirma", "Cleaning company", (
        _f("foretagskunder", "Business customers", 0.30,
           ("business_density", 0.6), ("office_workers", 0.4)),
        _f("bostadstathet", "Household customers", 0.20, ("residential_density", 1.0)),
        _f("kopkraft", "Purchasing power", 0.15, ("income_index", 1.0)),
        _f("marknadsutrymme", "Market headroom", 0.20,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
        _f("tillvaxt", "Growth", 0.15, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("malare", "Painting company", (
        _f("fastighetsbestand", "Building stock", 0.25,
           ("detached_homes", 0.6), ("avg_building_age", 0.4)),
        _f("renovering", "Renovation activity", 0.25, ("renovation_index", 1.0)),
        _f("bygglov", "Construction activity", 0.15, ("building_permits", 1.0)),
        _f("kopkraft", "Purchasing power", 0.15, ("income_index", 1.0)),
        _f("marknadsutrymme", "Market headroom", 0.20,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
    )),

    VerticalProfile("laddinfra", "EV charging infrastructure", (
        _f("elbilar", "EV density", 0.30, ("ev_per_capita", 1.0)),
        _f("fordonsflotta", "Vehicle fleet", 0.15, ("cars_per_1000", 1.0)),
        _f("pendling", "Commuter flows", 0.20, ("commuter_flow", 1.0)),
        _f("naringsliv", "Businesses & fleets", 0.15, ("business_density", 1.0)),
        _f("tillvaxt", "Growth", 0.20, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("cykelverkstad", "Bicycle repair shop", (
        _f("flode", "Cycling & commuter flows", 0.30,
           ("foot_traffic", 0.5), ("commuter_flow", 0.5)),
        _f("malgrupp", "Young adults", 0.20, ("age_20_45_share", 1.0)),
        _f("bostadstathet", "Residential density", 0.15, ("residential_density", 1.0)),
        _f("kopkraft", "Purchasing power", 0.10, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.25, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("generisk", "Generic business", (
        _f("kundunderlag", "Customer base", 0.28, ("pop_radius", 1.0)),
        _f("synlighet", "Visibility", 0.20, ("foot_traffic", 1.0)),
        _f("kopkraft", "Purchasing power", 0.18, ("income_index", 1.0)),
        _f("konkurrens", "Competition", 0.18, ("competition_pressure", 1.0)),
        _f("tillvaxt", "Growth", 0.16, ("pop_growth_pct", 1.0)),
    )),
]}

# Signaler som styr riskbedömningen (gemensamt för alla vertikaler).
RISK_SIGNALS = ("vacancy_rate", "rent_index", "pop_growth_pct", "competition_pressure")
