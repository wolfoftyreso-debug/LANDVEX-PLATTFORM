"""Universal Object Model — minimal: EN sammanhållen vy per objekt,
byggd av data som redan finns i `inspections.py`/`infrastructure.py`.

Det här är en integrationsfråga, inte en ny algoritm — precis som
strategidokumentets "Digital Twin"-avsnitt konstaterar. Varje fält
nedan kommer från en befintlig motor:

    Object     asset-raden i inspections.py:s register.
    Location   lat/lon/adress på samma rad.
    Condition  `inspections.compliance()`:s statusrad (om en rutin
               täcker klassen) OCH/ELLER `infrastructure.status()`
               (om klassen finns i OBJECT_TYPES) — ett objekt kan sakna
               den ena, den andra, eller ha båda.
    History    varje check på objektet, senaste först.
    Evidence   redan en del av varje check (evidence_ref/mission_id).
    Verified   varje granskning (`inspections.review()`) av de checkarna.

Fem fält från modellen i strategidokumentet saknas MEDVETET och
uttryckligen, inte tyst: Geometry (allt är punktdata), Owner (bara ett
tenant-fält, ingen rik ägarmodell), Lifecycle (bara installed_at),
Relationships (Reality Graph är inte byggd) och Policies (Policy
Engine är inte byggd). `cannot_en` säger det, i stället för att låtsas
vyn är fullständig.

Rent stdlib.
"""
from __future__ import annotations

from . import infrastructure as INFRA
from . import inspections as I


class ObjectNotFound(ValueError):
    """Inget objekt med det id:t i registret."""


def object_view(object_id: str, assets: list[dict], routines: list[dict],
                checks: list[dict], observations: list[dict],
                reviews: list[dict], *,
                today: object = "", now: float = 0.0) -> dict:
    """Universal Object Model, minimal version — ett objekt, allt vi
    faktiskt vet om det, från EN sammanhållen vy i stället för fem."""
    asset = next((a for a in assets if a.get("id") == object_id), None)
    if asset is None:
        raise ObjectNotFound(f"no object {object_id!r} in the register")
    kind = asset.get("kind", "")

    egna_checks = sorted(
        (c for c in checks if c.get("asset_id") == object_id),
        key=lambda c: c.get("performed_at", ""), reverse=True)
    egna_granskningar = [r for r in reviews if r.get("asset_id") == object_id]

    # Samma matchning som `_rutin_for()` internt (kind, ett specifikt
    # id, eller en id-lista) — inte en förenklad kopia av den, för att
    # inte råka missa ett objekt en rutin faktiskt täcker.
    rad = I.compliance([asset], routines, checks, today)["rows"]
    compliance = (rad[0] if rad and rad[0].get("status") != "no_routine"
                 else None)

    condition = None
    if kind in INFRA.OBJECT_TYPES:
        condition = INFRA.status(object_id, kind, observations, now=now)

    return {
        "object": asset,
        "compliance": compliance,
        "condition": condition,
        "history": egna_checks,
        "history_count": len(egna_checks),
        "reviews": egna_granskningar,
        "reviewed_count": len(egna_granskningar),
        "what_en": ("Everything currently known about one object, from "
                    "one composed view instead of five separate calls — "
                    "compliance status (if a routine covers this class), "
                    "condition (if infrastructure.py defines this class), "
                    "full check history, and every second-person review "
                    "on record."),
        "cannot_en": ("Five fields a complete object model would carry "
                      "are not here, on purpose, not silently: Geometry "
                      "(everything is a point, never a shape), a rich "
                      "Owner (only a tenant string), full Lifecycle "
                      "(only an install date, no decommission state), "
                      "Relationships (no graph between objects exists "
                      "yet), and Policies (no per-tenant rule overrides "
                      "exist yet)."),
    }
