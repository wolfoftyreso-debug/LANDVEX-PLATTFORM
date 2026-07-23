"""Affärsprofil – användarens förutsättningar och mål.

Profilen styr Sverigesvepet i engine/scan.py: vilka platser som
filtreras bort (pendling, miljötyp) och hur kandidater rankas
(risktolerans, målsättning). Alla valmöjligheter är data
(PROFILE_OPTIONS) så att frontend kan rendera formuläret direkt från
API:t och nya alternativ inte kräver motorändringar.

Identifierare utan å/ä/ö enligt projektprincip; etiketter på svenska.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .verticals import VERTICALS

PROFILE_OPTIONS: dict[str, list[dict[str, Any]]] = {
    "budget_band": [
        {"id": "0-500k",   "label_en": "0–500,000 SEK"},
        {"id": "500k-2m",  "label_en": "500,000 – 2 million"},
        {"id": "2-5m",     "label_en": "2–5 million"},
        {"id": "5-10m",    "label_en": "5–10 million"},
        {"id": "10m+",     "label_en": "10 million +"},
    ],
    "team_size": [
        {"id": "1",     "label_en": "Just me"},
        {"id": "2-5",   "label_en": "2–5 employees"},
        {"id": "5-20",  "label_en": "5–20 employees"},
        {"id": "20-50", "label_en": "20–50 employees"},
        {"id": "50+",   "label_en": "More than 50"},
    ],
    "business_model": [
        {"id": "nyetablering",   "label_en": "New establishment"},
        {"id": "kop_befintligt", "label_en": "Buy existing"},
        {"id": "franchise",      "label_en": "Franchise"},
        {"id": "expansion",      "label_en": "Expand"},
        {"id": "filial",         "label_en": "Branch office"},
        {"id": "mobilt",         "label_en": "Mobile concept"},
        {"id": "premium",        "label_en": "Premium"},
        {"id": "lagpris",        "label_en": "Low-cost"},
    ],
    "risk_tolerance": [
        {"id": "lag",       "label_en": "Low"},
        {"id": "normal",    "label_en": "Normal"},
        {"id": "hog",       "label_en": "High"},
        {"id": "aggressiv", "label_en": "Aggressive"},
    ],
    "commute_km": [
        {"id": 10,   "label_en": "10 km"},
        {"id": 30,   "label_en": "30 km"},
        {"id": 100,  "label_en": "100 km"},
        {"id": None, "label_en": "No limit"},
    ],
    "environments": [
        {"id": "stad",        "label_en": "City"},
        {"id": "forort",      "label_en": "Suburb"},
        {"id": "landsbygd",   "label_en": "Rural"},
        {"id": "turistort",   "label_en": "Tourist destination"},
        {"id": "industrizon", "label_en": "Industrial zone"},
    ],
    "horizon_years": [
        {"id": 1,  "label_en": "1 year"},
        {"id": 3,  "label_en": "3 years"},
        {"id": 5,  "label_en": "5 years"},
        {"id": 10, "label_en": "10 years"},
    ],
    "goal": [
        {"id": "maximal_vinst",  "label_en": "Maximum profit"},
        {"id": "stabilitet",     "label_en": "Stability"},
        {"id": "livsstil",       "label_en": "Lifestyle"},
        {"id": "bygga_kedja",    "label_en": "Build a chain"},
        {"id": "exit",           "label_en": "Exit"},
        {"id": "passiv_inkomst", "label_en": "Passive income"},
    ],
}


def _ids(key: str) -> list:
    return [o["id"] for o in PROFILE_OPTIONS[key]]


@dataclass(frozen=True)
class BusinessProfile:
    vertical_id: str
    budget_band: str = "500k-2m"
    team_size: str = "1"
    business_model: str = "nyetablering"
    risk_tolerance: str = "normal"
    commute_km: float | None = None          # None = ingen gräns
    home_lat: float | None = None
    home_lon: float | None = None
    environments: tuple[str, ...] = ()       # tom = alla miljötyper
    horizon_years: int = 3
    goal: str = "stabilitet"
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["environments"] = list(self.environments)
        return d


def profile_from_dict(d: dict[str, Any]) -> BusinessProfile:
    """Validerar och bygger en profil; ValueError med svensk text vid fel."""
    if not isinstance(d, dict):
        raise ValueError("The profile must be an object.")
    vid = d.get("vertical_id")
    if vid not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vid}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")

    def choice(key: str, default):
        val = d.get(key, default)
        if val not in _ids(key):
            raise ValueError(f"Invalid value for {key}: {val!r}. "
                             f"Allowed: {_ids(key)}")
        return val

    envs = d.get("environments", []) or []
    bad = [e for e in envs if e not in _ids("environments")]
    if bad:
        raise ValueError(f"Invalid environment type: {bad}. "
                         f"Allowed: {_ids('environments')}")

    commute = d.get("commute_km", None)
    if commute is not None and (not isinstance(commute, (int, float)) or commute <= 0):
        raise ValueError("commute_km must be a positive number or null.")
    if commute is not None and (d.get("home_lat") is None or d.get("home_lon") is None):
        raise ValueError("A commute limit requires home_lat and home_lon.")

    return BusinessProfile(
        vertical_id=vid,
        budget_band=choice("budget_band", "500k-2m"),
        team_size=choice("team_size", "1"),
        business_model=choice("business_model", "nyetablering"),
        risk_tolerance=choice("risk_tolerance", "normal"),
        commute_km=float(commute) if commute is not None else None,
        home_lat=d.get("home_lat"),
        home_lon=d.get("home_lon"),
        environments=tuple(envs),
        horizon_years=choice("horizon_years", 3),
        goal=choice("goal", "stabilitet"),
        name=str(d.get("name", "")),
    )


def profile_options() -> dict[str, Any]:
    """Formulärdata till frontend, inklusive aktuella vertikaler."""
    return {"vertical_id": [{"id": v.id, "label_en": v.label_en}
                            for v in VERTICALS.values()],
            **PROFILE_OPTIONS}
