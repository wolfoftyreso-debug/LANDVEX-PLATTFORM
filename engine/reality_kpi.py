"""Reality Coverage, Freshness och Confidence — samma tre mätningar som
redan finns i `inspections.compliance()` och `infrastructure.status()` /
`freshness_record()`, bara rullade upp per objektklass i stället för per
enskilt objekt eller fält.

Ingen ny mätning uppfinns här. Det här är en aggregeringsmodul:

    COVERAGE     `compliance()`:s `share_current`, grupperat på `kind`.
                 Gäller varje objektklass som har en rutin — oavsett om
                 klassen är känd av `infrastructure.py` eller inte.
    FRESHNESS    `freshness_record()`:s `current_fields`/`of_fields`,
                 summerat per `kind`. Gäller bara klasser som finns i
                 `infrastructure.OBJECT_TYPES` — resten har inga fält att
                 räkna åldern på.
    CONFIDENCE   Samma `freshness_record()`, andelen fält vars
                 korroboreringsband INTE är "none". Aldrig en procentsats
                 som låtsas vara en poäng — se `infrastructure.py`:s egen
                 doktrin om band kontra score.

En fjärde KPI, Reality Risk, saknas medvetet: ingen motor i katalogen
poängsätter fysisk säkerhetsrisk idag, så det finns inget att rulla upp
utan att hitta på ett tal. `reality_kpi()`:s `risk_en`-fält vägrar med
skäl i stället för att gissa.

Rena funktioner, precis som `inspections.compliance()`/`infrastructure.due()`
— den här modulen läser ALDRIG ett lager själv, API-lagret hämtar listorna
och skickar in dem, exakt samma ansvarsfördelning som resten av kodbasen.

Rent stdlib.
"""
from __future__ import annotations

import time as _time

from . import inspections as I
from . import infrastructure as INFRA


def _coverage_by_kind(assets: list[dict], routines: list[dict],
                      checks: list[dict], today: object) -> dict[str, dict]:
    per_kind: dict[str, list[dict]] = {}
    for a in assets:
        per_kind.setdefault(a.get("kind", ""), []).append(a)
    out = {}
    for kind, kind_assets in per_kind.items():
        comp = I.compliance(kind_assets, routines, checks, today)
        out[kind] = {"objects": comp["count"],
                     "share_current": comp["share_current"]}
    return out


def _freshness_confidence_by_kind(assets: list[dict],
                                  observations: list[dict],
                                  now: float) -> dict[str, dict]:
    known = [a for a in assets if a.get("kind") in INFRA.OBJECT_TYPES]
    per_kind: dict[str, list[dict]] = {}
    for a in known:
        per_kind.setdefault(a["kind"], []).append(a)
    out = {}
    for kind, kind_assets in per_kind.items():
        current_fields = of_fields = 0
        confident_fields = 0
        for a in kind_assets:
            rec = INFRA.freshness_record(a["id"], kind, observations, now=now)
            current_fields += rec["current_fields"]
            of_fields += rec["of_fields"]
            if rec["confidence_bands"] != ["none"]:
                confident_fields += rec["current_fields"]
        out[kind] = {
            "objects": len(kind_assets),
            "share_current": (round(current_fields / of_fields, 4)
                              if of_fields else None),
            "share_corroborated": (round(confident_fields / of_fields, 4)
                                   if of_fields else None),
        }
    return out


def reality_kpi(assets: list[dict], routines: list[dict], checks: list[dict],
                observations: list[dict], *,
                today: object = "", now: float = 0.0) -> dict:
    """De tre KPI:er som går att räkna idag, rullade upp per objektklass.

    En rad per objektklass som förekommer i `assets` — aldrig en rad för
    en klass ingen har registrerat, och aldrig ett Freshness/Confidence-
    tal för en klass `infrastructure.py` inte känner till.
    """
    nu = now or _time.time()
    coverage = _coverage_by_kind(assets, routines, checks, today)
    fc = _freshness_confidence_by_kind(assets, observations, nu)
    kinder = sorted(set(coverage) | set(fc))
    rader = []
    for kind in kinder:
        rader.append({
            "kind": kind,
            "coverage": coverage.get(kind),
            "freshness": ({"share_current": fc[kind]["share_current"]}
                         if kind in fc else None),
            "confidence": ({"share_corroborated": fc[kind]["share_corroborated"]}
                          if kind in fc else None),
        })
    return {
        "kinds": rader,
        "risk_en": ("Reality Risk is not computed: no engine in the "
                    "catalogue scores physical safety risk today. Rather "
                    "than estimate one, this KPI is refused until that "
                    "gap closes."),
        "what_en": ("Coverage: share of registered objects whose latest "
                    "check is still current, per class. Freshness: share "
                    "of observed fields still inside their freshness "
                    "window, per class. Confidence: share of fields "
                    "corroborated by more than one independent source, "
                    "per class."),
        "cannot_en": ("A class with no routine has no Coverage row. A "
                      "class infrastructure.py does not define has no "
                      "Freshness or Confidence row — nothing here is "
                      "estimated to fill either gap."),
    }
