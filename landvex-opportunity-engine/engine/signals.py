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
    label_sv: str
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
    raise ValueError(f"Okänd normalisering: {d.norm}")


def _s(id, label, unit, norm, p1=0.0, p2=1.0):
    return SignalDef(id, label, unit, norm, p1, p2)


CATALOG: dict[str, SignalDef] = {s.id: s for s in [
    # ── Befolkning & köpkraft ─────────────────────────────────────────
    _s("pop_radius",        "Personer inom radie",          "pers",   "saturating", 6000),
    _s("pop_growth_pct",    "Befolkningstillväxt",          "%",      "linear", -2.0, 8.0),
    _s("income_index",      "Medelinkomst (rikssnitt=100)", "index",  "linear", 70, 130),
    _s("age_20_45_share",   "Andel 20–45 år",               "%",      "linear", 15, 45),
    _s("families_share",    "Andel barnfamiljer",           "%",      "linear", 10, 40),
    _s("share_65plus",      "Andel 65+",                    "%",      "linear", 10, 35),
    _s("residential_density","Bostadstäthet",               "hh/km²", "saturating", 800),
    # ── Flöden & synlighet ────────────────────────────────────────────
    _s("foot_traffic",      "Förbipasserande per dag",      "pers",   "saturating", 2500),
    _s("target_match_pct",  "Målgruppsmatchning",           "%",      "linear", 20, 80),
    _s("flow_morning",      "Flöde morgon (06–10)",         "pers/h", "saturating", 400),
    _s("flow_midday",       "Flöde lunch (11–14)",          "pers/h", "saturating", 500),
    _s("flow_afternoon",    "Flöde eftermiddag (14–18)",    "pers/h", "saturating", 400),
    _s("flow_evening",      "Flöde kväll (18–23)",          "pers/h", "saturating", 350),
    _s("commuter_flow",     "Pendlarflöde morgon/kväll",    "pers",   "saturating", 3000),
    # ── Tillgänglighet ────────────────────────────────────────────────
    _s("parking_score",     "Parkeringstillgång",           "0–10",   "linear", 0, 10),
    _s("transit_score",     "Kollektivtrafik",              "0–10",   "linear", 0, 10),
    # ── Konkurrens (härledd i datalagret) ─────────────────────────────
    _s("competition_pressure", "Effektivt konkurrenstryck", "0–10",   "inverse", 0, 10),
    _s("provider_gap",      "Utbudsgap (efterfrågan/utbud)","kvot",   "linear", 0.8, 2.0),
    # ── Fastighet, bygg & näringsliv ──────────────────────────────────
    _s("detached_homes",    "Villor/småhus inom område",    "st",     "saturating", 2500),
    _s("building_permits",  "Bygglov senaste 12 mån",       "st",     "saturating", 120),
    _s("renovation_index",  "Renoveringsaktivitet",         "index",  "linear", 20, 100),
    _s("avg_building_age",  "Snittålder fastigheter",       "år",     "band", 25, 60),
    _s("ev_per_capita",     "Elbilar per 1000 inv",         "st",     "saturating", 60),
    _s("business_density",  "Företag per 1000 inv",         "st",     "saturating", 55),
    _s("office_workers",    "Kontorsarbetare inom radie",   "pers",   "saturating", 4000),
    _s("hotel_beds",        "Hotellbäddar inom radie",      "st",     "saturating", 600),
    _s("tourism_index",     "Turismindex",                  "0–100",  "linear", 0, 100),
    _s("event_days",        "Evenemangsdagar per år",       "dagar",  "saturating", 40),
    _s("detail_plans",      "Kommande detaljplaner",        "st",     "saturating", 8),
    _s("development_m2",    "Exploateringsyta",             "1000 m²","saturating", 150),
    _s("infra_invest",      "Infrastruktursatsningar",      "mnkr",   "saturating", 400),
    _s("insurance_index",   "Försäkringsnivå tandvård",     "index",  "linear", 60, 120),
    _s("care_supply",       "Övrigt vårdutbud",             "0–10",   "band", 3, 7),
    # ── Riskindikatorer ───────────────────────────────────────────────
    _s("vacancy_rate",      "Vakansgrad lokaler",           "%",      "inverse", 2, 15),
    _s("rent_index",        "Hyresnivå (snitt=100)",        "index",  "inverse", 90, 160),
]}
