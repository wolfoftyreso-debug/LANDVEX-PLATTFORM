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
    label_sv: str
    weight: float
    signals: tuple  # ((signal_id, vikt), ...)


@dataclass(frozen=True)
class VerticalProfile:
    id: str
    label_sv: str
    factors: tuple


def _f(id, label, weight, *signals):
    return FactorSpec(id, label, weight, tuple(signals))


VERTICALS: dict[str, VerticalProfile] = {p.id: p for p in [

    VerticalProfile("frisor", "Frisörsalong", (
        _f("kundunderlag", "Kundunderlag", 0.22, ("pop_radius", 1.0)),
        _f("synlighet",    "Synlighet",    0.18, ("foot_traffic", 1.0)),
        _f("matchning",    "Matchning",    0.16, ("target_match_pct", 1.0)),
        _f("konkurrens",   "Konkurrens",   0.18, ("competition_pressure", 0.6), ("provider_gap", 0.4)),
        _f("kopkraft",     "Köpkraft",     0.14, ("income_index", 1.0)),
        _f("tillvaxt",     "Tillväxt",     0.12, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("elektriker", "Elektriker", (
        _f("fastighetsbestand", "Fastighetsbestånd", 0.24,
           ("detached_homes", 0.6), ("avg_building_age", 0.4)),
        _f("byggaktivitet", "Bygg- & renoveringsaktivitet", 0.26,
           ("building_permits", 0.6), ("renovation_index", 0.4)),
        _f("elektrifiering", "Elektrifiering", 0.16, ("ev_per_capita", 1.0)),
        _f("naringsliv", "Företag & industri", 0.14, ("business_density", 1.0)),
        _f("marknadsutrymme", "Marknadsutrymme", 0.20,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
    )),

    VerticalProfile("gym", "Gym & träning", (
        _f("malgrupp", "Åldersstruktur & målgrupp", 0.22,
           ("age_20_45_share", 0.7), ("pop_radius", 0.3)),
        _f("kopkraft", "Köpkraft", 0.14, ("income_index", 1.0)),
        _f("bostadstathet", "Bostadstäthet", 0.16, ("residential_density", 1.0)),
        _f("tillganglighet", "Parkering & kollektivtrafik", 0.16,
           ("parking_score", 0.5), ("transit_score", 0.5)),
        _f("rorelse", "Rörelsemönster morgon/kväll", 0.16, ("commuter_flow", 1.0)),
        _f("konkurrens", "Konkurrens", 0.16, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("restaurang", "Restaurang", (
        _f("lunch", "Lunchflöden", 0.20,
           ("flow_midday", 0.6), ("office_workers", 0.4)),
        _f("kvall", "Kvällsflöden", 0.20, ("flow_evening", 1.0)),
        _f("besoksnaring", "Turism, hotell & evenemang", 0.16,
           ("hotel_beds", 0.4), ("tourism_index", 0.35), ("event_days", 0.25)),
        _f("tillganglighet", "Parkering & läge", 0.12,
           ("parking_score", 0.5), ("transit_score", 0.5)),
        _f("kopkraft", "Köpkraft", 0.14, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.18, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("cafe", "Café", (
        _f("morgon", "Morgonflöde", 0.26, ("flow_morning", 1.0)),
        _f("dag", "Dagflöde", 0.18, ("flow_midday", 1.0)),
        _f("eftermiddag", "Eftermiddagsflöde", 0.16, ("flow_afternoon", 1.0)),
        _f("gangtrafik", "Gångtrafik totalt", 0.16, ("foot_traffic", 1.0)),
        _f("kopkraft", "Köpkraft", 0.10, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.14, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("bygg", "Byggföretag", (
        _f("detaljplaner", "Kommande detaljplaner", 0.24, ("detail_plans", 1.0)),
        _f("exploatering", "Exploateringar", 0.22, ("development_m2", 1.0)),
        _f("bygglov", "Bygglovsvolym", 0.20, ("building_permits", 1.0)),
        _f("infrastruktur", "Infrastruktur- & kommuninvesteringar", 0.18,
           ("infra_invest", 1.0)),
        _f("marknadsutrymme", "Marknadsutrymme", 0.16, ("provider_gap", 1.0)),
    )),

    VerticalProfile("tandlakare", "Tandläkarpraktik", (
        _f("barnfamiljer", "Barnfamiljer", 0.22, ("families_share", 1.0)),
        _f("aldre", "Äldre befolkning", 0.18, ("share_65plus", 1.0)),
        _f("forsakring", "Försäkringsnivå", 0.16, ("insurance_index", 1.0)),
        _f("konkurrens", "Konkurrens & utbudsgap", 0.26,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("vardutbud", "Övrigt vårdutbud", 0.18, ("care_supply", 1.0)),
    )),

    VerticalProfile("vvs", "VVS-företag", (
        _f("fastighetsbestand", "Fastighetsbestånd", 0.24,
           ("detached_homes", 0.6), ("avg_building_age", 0.4)),
        _f("byggaktivitet", "Bygg- & renoveringsaktivitet", 0.28,
           ("building_permits", 0.6), ("renovation_index", 0.4)),
        _f("exploatering", "Exploateringar", 0.14, ("development_m2", 1.0)),
        _f("marknadsutrymme", "Marknadsutrymme", 0.22,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
        _f("kopkraft", "Köpkraft", 0.12, ("income_index", 1.0)),
    )),

    VerticalProfile("bilverkstad", "Bilverkstad", (
        _f("bilbestand", "Bilbestånd & fordonsålder", 0.26,
           ("cars_per_1000", 0.6), ("avg_car_age", 0.4)),
        _f("upptagning", "Upptagningsområde", 0.18,
           ("pop_radius", 0.6), ("detached_homes", 0.4)),
        _f("pendling", "Pendling & trafik", 0.16, ("commuter_flow", 1.0)),
        _f("naringsliv", "Företagskunder", 0.12, ("business_density", 1.0)),
        _f("marknadsutrymme", "Marknadsutrymme", 0.18,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("kopkraft", "Köpkraft", 0.10, ("income_index", 1.0)),
    )),

    VerticalProfile("veterinar", "Veterinärklinik", (
        _f("djurunderlag", "Djurunderlag", 0.30,
           ("pets_per_1000", 0.7), ("detached_homes", 0.3)),
        _f("barnfamiljer", "Barnfamiljer", 0.16, ("families_share", 1.0)),
        _f("kopkraft", "Köpkraft", 0.16, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens & utbudsgap", 0.24,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("tillvaxt", "Tillväxt", 0.14, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("lager", "Lager & logistik", (
        _f("logistiklage", "Logistikläge", 0.28, ("logistics_access", 1.0)),
        _f("naringsliv", "Näringslivstäthet", 0.18, ("business_density", 1.0)),
        _f("exploatering", "Mark & exploatering", 0.20,
           ("development_m2", 0.6), ("detail_plans", 0.4)),
        _f("infrastruktur", "Infrastrukturinvesteringar", 0.16,
           ("infra_invest", 1.0)),
        _f("kostnadslage", "Kostnadsläge (hyra)", 0.18, ("rent_index", 1.0)),
    )),

    VerticalProfile("forskola", "Förskola", (
        _f("barnunderlag", "Barnunderlag", 0.32,
           ("families_share", 0.7), ("pop_radius", 0.3)),
        _f("tillvaxt", "Tillväxt", 0.18, ("pop_growth_pct", 1.0)),
        _f("bostadstathet", "Bostadstäthet", 0.15, ("residential_density", 1.0)),
        _f("utbud", "Utbud & platsbrist", 0.20,
           ("provider_gap", 0.6), ("competition_pressure", 0.4)),
        _f("tillganglighet", "Hämta/lämna-läge", 0.15,
           ("parking_score", 0.5), ("transit_score", 0.5)),
    )),

    VerticalProfile("apotek", "Apotek", (
        _f("upptagning", "Upptagningsområde", 0.25, ("pop_radius", 1.0)),
        _f("aldre", "Äldre befolkning", 0.20, ("share_65plus", 1.0)),
        _f("flode", "Kundflöde", 0.20, ("foot_traffic", 1.0)),
        _f("vardutbud", "Närhet till vård", 0.15, ("care_supply", 1.0)),
        _f("konkurrens", "Konkurrens", 0.20, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("optiker", "Optiker", (
        _f("upptagning", "Upptagningsområde", 0.25, ("pop_radius", 1.0)),
        _f("aldre", "Äldre befolkning", 0.20, ("share_65plus", 1.0)),
        _f("synlighet", "Synlighet", 0.20, ("foot_traffic", 1.0)),
        _f("kopkraft", "Köpkraft", 0.15, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.20, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("bageri", "Bageri", (
        _f("morgon", "Morgonflöde", 0.30, ("flow_morning", 1.0)),
        _f("gangtrafik", "Gångtrafik", 0.20, ("foot_traffic", 1.0)),
        _f("bostadstathet", "Bostadstäthet", 0.15, ("residential_density", 1.0)),
        _f("kopkraft", "Köpkraft", 0.15, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.20, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("livsmedel", "Livsmedelsbutik", (
        _f("upptagning", "Upptagningsområde", 0.30,
           ("pop_radius", 0.6), ("residential_density", 0.4)),
        _f("parkering", "Parkering", 0.15, ("parking_score", 1.0)),
        _f("tillvaxt", "Tillväxt", 0.15, ("pop_growth_pct", 1.0)),
        _f("kopkraft", "Köpkraft", 0.15, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.25, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("aldreomsorg", "Äldreomsorg & hemtjänst", (
        _f("aldre", "Äldre befolkning", 0.35, ("share_65plus", 1.0)),
        _f("upptagning", "Upptagningsområde", 0.15, ("pop_radius", 1.0)),
        _f("vardutbud", "Övrigt vårdutbud", 0.15, ("care_supply", 1.0)),
        _f("utbud", "Utbudsgap", 0.20, ("provider_gap", 1.0)),
        _f("tillvaxt", "Tillväxt", 0.15, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("stadfirma", "Städfirma", (
        _f("foretagskunder", "Företagskunder", 0.30,
           ("business_density", 0.6), ("office_workers", 0.4)),
        _f("bostadstathet", "Hushållskunder", 0.20, ("residential_density", 1.0)),
        _f("kopkraft", "Köpkraft", 0.15, ("income_index", 1.0)),
        _f("marknadsutrymme", "Marknadsutrymme", 0.20,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
        _f("tillvaxt", "Tillväxt", 0.15, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("malare", "Måleri", (
        _f("fastighetsbestand", "Fastighetsbestånd", 0.25,
           ("detached_homes", 0.6), ("avg_building_age", 0.4)),
        _f("renovering", "Renoveringsaktivitet", 0.25, ("renovation_index", 1.0)),
        _f("bygglov", "Byggaktivitet", 0.15, ("building_permits", 1.0)),
        _f("kopkraft", "Köpkraft", 0.15, ("income_index", 1.0)),
        _f("marknadsutrymme", "Marknadsutrymme", 0.20,
           ("provider_gap", 0.7), ("competition_pressure", 0.3)),
    )),

    VerticalProfile("laddinfra", "Laddinfrastruktur", (
        _f("elbilar", "Elbilstäthet", 0.30, ("ev_per_capita", 1.0)),
        _f("fordonsflotta", "Fordonsflotta", 0.15, ("cars_per_1000", 1.0)),
        _f("pendling", "Pendlingsflöden", 0.20, ("commuter_flow", 1.0)),
        _f("naringsliv", "Näringsliv & flottor", 0.15, ("business_density", 1.0)),
        _f("tillvaxt", "Tillväxt", 0.20, ("pop_growth_pct", 1.0)),
    )),

    VerticalProfile("cykelverkstad", "Cykelverkstad", (
        _f("flode", "Cykel- & pendlingsflöden", 0.30,
           ("foot_traffic", 0.5), ("commuter_flow", 0.5)),
        _f("malgrupp", "Unga vuxna", 0.20, ("age_20_45_share", 1.0)),
        _f("bostadstathet", "Bostadstäthet", 0.15, ("residential_density", 1.0)),
        _f("kopkraft", "Köpkraft", 0.10, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.25, ("competition_pressure", 1.0)),
    )),

    VerticalProfile("generisk", "Generisk verksamhet", (
        _f("kundunderlag", "Kundunderlag", 0.28, ("pop_radius", 1.0)),
        _f("synlighet", "Synlighet", 0.20, ("foot_traffic", 1.0)),
        _f("kopkraft", "Köpkraft", 0.18, ("income_index", 1.0)),
        _f("konkurrens", "Konkurrens", 0.18, ("competition_pressure", 1.0)),
        _f("tillvaxt", "Tillväxt", 0.16, ("pop_growth_pct", 1.0)),
    )),
]}

# Signaler som styr riskbedömningen (gemensamt för alla vertikaler).
RISK_SIGNALS = ("vacancy_rate", "rent_index", "pop_growth_pct", "competition_pressure")
