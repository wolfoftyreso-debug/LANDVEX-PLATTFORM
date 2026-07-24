"""Specialisering – gör Opportunity Score personlig för DIG, inte generisk.

En elektriker som satsar på laddboxar bryr sig om andra signaler än en
som gör industri. Specialiseringen lägger en vikt-överlagring på
vertikalens faktorer (factor_boost): en multiplikator > 1 lyfter de
faktorer som betyder mest för nischen. Ren data – ny specialisering =
ny rad, inga motorändringar, inga påhittade signaler. Boostarna
omfördelar bara tyngden mellan faktorer som redan finns och mäts.

Vertikaler utan meningsfull specialisering returnerar tom lista
(generellt läge). Faktornamnen refererar de verkliga factor-id:na i
engine/verticals.py.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecDef:
    id: str
    label_en: str
    factor_boost: dict          # {factor_id: multiplikator}
    notis_en: str               # varför nischen väger dessa faktorer


def _s(id, label, boost, notis):
    return SpecDef(id, label, boost, notis)


SPECIALIZATIONS: dict[str, tuple[SpecDef, ...]] = {
    "elektriker": (
        _s("solceller", "Solar PV",
           {"fastighetsbestand": 1.5, "elektrifiering": 1.2},
           "Weights detached-home stock and electrification – solar sits "
           "on villa roofs."),
        _s("laddboxar", "EV chargers",
           {"elektrifiering": 1.8, "fastighetsbestand": 1.2},
           "Weights EV density and home stock – charger demand tracks "
           "the electric fleet."),
        _s("industri", "Industry",
           {"naringsliv": 1.8, "marknadsutrymme": 1.1},
           "Weights business & industry density."),
        _s("fastigheter", "Property management",
           {"fastighetsbestand": 1.6},
           "Weights the standing building stock (recurring service)."),
        _s("nyproduktion", "New construction",
           {"byggaktivitet": 1.7},
           "Weights building permits and construction activity."),
        _s("service", "Service & maintenance",
           {"fastighetsbestand": 1.4, "marknadsutrymme": 1.2},
           "Weights installed base and market headroom."),
        _s("jour", "On-call / emergency",
           {"marknadsutrymme": 1.5},
           "Weights market headroom – fewer competitors, faster calls."),
        _s("smarta_hem", "Smart home",
           {"elektrifiering": 1.3, "fastighetsbestand": 1.3},
           "Weights electrification and higher-value home stock."),
    ),
    "vvs": (
        _s("varmepump", "Heat pumps",
           {"fastighetsbestand": 1.5, "kopkraft": 1.3},
           "Weights villa stock and purchasing power."),
        _s("nyproduktion", "New construction",
           {"byggaktivitet": 1.6, "exploatering": 1.4},
           "Weights permits and land development."),
        _s("service", "Service & maintenance",
           {"fastighetsbestand": 1.4, "marknadsutrymme": 1.2},
           "Weights installed base and headroom."),
        _s("industri", "Industry & property",
           {"exploatering": 1.3, "marknadsutrymme": 1.2},
           "Weights development and market headroom."),
    ),
    "bygg": (
        _s("nyproduktion", "New housing",
           {"detaljplaner": 1.5, "exploatering": 1.5, "bygglov": 1.3},
           "Weights detailed plans, land development and permits."),
        _s("renovering", "Renovation (ROT)",
           {"marknadsutrymme": 1.3, "infrastruktur": 1.1},
           "Weights market headroom over new-build pipeline."),
        _s("offentligt", "Public / infrastructure",
           {"infrastruktur": 1.7},
           "Weights public infrastructure investment."),
    ),
    "malare": (
        _s("nyproduktion", "New construction",
           {"bygglov": 1.5, "renovering": 1.2},
           "Weights permits and construction pipeline."),
        _s("renovering", "Renovation (ROT)",
           {"renovering": 1.6, "fastighetsbestand": 1.3},
           "Weights renovation activity and ageing stock."),
        _s("fastigheter", "Property clients",
           {"fastighetsbestand": 1.5, "marknadsutrymme": 1.1},
           "Weights the standing building stock."),
    ),
    "bilverkstad": (
        _s("service", "General service",
           {"bilbestand": 1.5, "kopkraft": 1.1},
           "Weights the car fleet and purchasing power."),
        _s("dack", "Tyres & seasonal",
           {"bilbestand": 1.4, "pendling": 1.3},
           "Weights fleet size and commuting distance."),
        _s("elbil", "EV service",
           {"kopkraft": 1.4, "bilbestand": 1.2},
           "Weights purchasing power (newer EV fleet)."),
    ),
}


def specializations_for(vertical_id: str) -> list[dict]:
    """Val för en vertikal (tom = generellt läge)."""
    return [{"id": s.id, "label_en": s.label_en, "notis_en": s.notis_en}
            for s in SPECIALIZATIONS.get(vertical_id, ())]


def specialization_boost(vertical_id: str, spec_id: str | None) -> dict:
    """Faktor-boostar för en specialisering (tom dict = ingen)."""
    if not spec_id:
        return {}
    for s in SPECIALIZATIONS.get(vertical_id, ()):
        if s.id == spec_id:
            return dict(s.factor_boost)
    return {}


def specialization_def(vertical_id: str, spec_id: str | None):
    if not spec_id:
        return None
    for s in SPECIALIZATIONS.get(vertical_id, ()):
        if s.id == spec_id:
            return s
    return None


def specialization_catalog() -> dict:
    return {vid: specializations_for(vid) for vid in SPECIALIZATIONS}
