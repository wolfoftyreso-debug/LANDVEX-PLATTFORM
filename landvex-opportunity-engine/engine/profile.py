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
        {"id": "0-500k",   "label_sv": "0–500 000 kr"},
        {"id": "500k-2m",  "label_sv": "500 000 – 2 miljoner"},
        {"id": "2-5m",     "label_sv": "2–5 miljoner"},
        {"id": "5-10m",    "label_sv": "5–10 miljoner"},
        {"id": "10m+",     "label_sv": "10 miljoner +"},
    ],
    "team_size": [
        {"id": "1",     "label_sv": "Bara jag"},
        {"id": "2-5",   "label_sv": "2–5 anställda"},
        {"id": "5-20",  "label_sv": "5–20 anställda"},
        {"id": "20-50", "label_sv": "20–50 anställda"},
        {"id": "50+",   "label_sv": "Fler än 50"},
    ],
    "business_model": [
        {"id": "nyetablering",   "label_sv": "Nyetablering"},
        {"id": "kop_befintligt", "label_sv": "Köpa befintligt"},
        {"id": "franchise",      "label_sv": "Franchise"},
        {"id": "expansion",      "label_sv": "Expandera"},
        {"id": "filial",         "label_sv": "Filial"},
        {"id": "mobilt",         "label_sv": "Mobilt koncept"},
        {"id": "premium",        "label_sv": "Premium"},
        {"id": "lagpris",        "label_sv": "Lågpris"},
    ],
    "risk_tolerance": [
        {"id": "lag",       "label_sv": "Låg"},
        {"id": "normal",    "label_sv": "Normal"},
        {"id": "hog",       "label_sv": "Hög"},
        {"id": "aggressiv", "label_sv": "Aggressiv"},
    ],
    "commute_km": [
        {"id": 10,   "label_sv": "10 km"},
        {"id": 30,   "label_sv": "30 km"},
        {"id": 100,  "label_sv": "100 km"},
        {"id": None, "label_sv": "Ingen gräns"},
    ],
    "environments": [
        {"id": "stad",        "label_sv": "Stad"},
        {"id": "forort",      "label_sv": "Förort"},
        {"id": "landsbygd",   "label_sv": "Landsbygd"},
        {"id": "turistort",   "label_sv": "Turistort"},
        {"id": "industrizon", "label_sv": "Industrizon"},
    ],
    "horizon_years": [
        {"id": 1,  "label_sv": "1 år"},
        {"id": 3,  "label_sv": "3 år"},
        {"id": 5,  "label_sv": "5 år"},
        {"id": 10, "label_sv": "10 år"},
    ],
    "goal": [
        {"id": "maximal_vinst",  "label_sv": "Maximal vinst"},
        {"id": "stabilitet",     "label_sv": "Stabilitet"},
        {"id": "livsstil",       "label_sv": "Livsstil"},
        {"id": "bygga_kedja",    "label_sv": "Bygga kedja"},
        {"id": "exit",           "label_sv": "Exit"},
        {"id": "passiv_inkomst", "label_sv": "Passiv inkomst"},
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
        raise ValueError("Profilen måste vara ett objekt.")
    vid = d.get("vertical_id")
    if vid not in VERTICALS:
        raise ValueError(f"Okänd vertikal: {vid}. "
                         f"Tillgängliga: {', '.join(sorted(VERTICALS))}")

    def choice(key: str, default):
        val = d.get(key, default)
        if val not in _ids(key):
            raise ValueError(f"Ogiltigt värde för {key}: {val!r}. "
                             f"Tillåtna: {_ids(key)}")
        return val

    envs = d.get("environments", []) or []
    bad = [e for e in envs if e not in _ids("environments")]
    if bad:
        raise ValueError(f"Ogiltig miljötyp: {bad}. Tillåtna: {_ids('environments')}")

    commute = d.get("commute_km", None)
    if commute is not None and (not isinstance(commute, (int, float)) or commute <= 0):
        raise ValueError("commute_km måste vara ett positivt tal eller null.")
    if commute is not None and (d.get("home_lat") is None or d.get("home_lon") is None):
        raise ValueError("Pendlingsgräns kräver home_lat och home_lon.")

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
    return {"vertical_id": [{"id": v.id, "label_sv": v.label_sv}
                            for v in VERTICALS.values()],
            **PROFILE_OPTIONS}
