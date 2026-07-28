"""Lagringsgränssnitt: platser/rapporter + signalcache med TTL.

Samma mönster som API-lagret: en beroendefri referensimplementation
(SqliteStore, stdlib) som fungerar lokalt, i Lambda (/tmp) och i test,
och en produktionsimplementation (PostgresStore, Aurora + PostGIS) med
identiskt gränssnitt. Motorn känner bara till detta gränssnitt.

Tidsstämplar är epoch-sekunder (float) i hela gränssnittet.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class Store(ABC):

    # ── Rapporter ────────────────────────────────────────────────────

    @abstractmethod
    def save_report(self, report: dict[str, Any], created_at: float, *,
                    tenant: str) -> str:
        """Sparar en rapport (dict från OpportunityReport.to_dict()).
        Returnerar genererat rapport-id."""

    @abstractmethod
    def get_report(self, report_id: str, *,
                   tenant: str) -> Optional[dict[str, Any]]:
        """Full rapport + metadata, eller None."""

    @abstractmethod
    def list_reports(self, limit: int = 20, *,
                     tenant: str) -> list[dict[str, Any]]:
        """Sammanfattningar, nyast först."""

    # ── Sparade affärsprofiler ───────────────────────────────────────

    @abstractmethod
    def save_profile(self, profile: dict[str, Any], created_at: float, *,
                     tenant: str) -> str:
        """Sparar en affärsprofil (dict från BusinessProfile.to_dict()).
        Returnerar genererat profil-id."""

    @abstractmethod
    def get_profile(self, profile_id: str, *,
                    tenant: str) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    def list_profiles(self, limit: int = 50, *,
                      tenant: str) -> list[dict[str, Any]]:
        """Sammanfattningar (id, namn, vertikal), nyast först."""

    # ── Signalcache (per källa, plats-nyckel) ────────────────────────

    @abstractmethod
    def get_cached_signals(self, source: str, loc_key: str
                           ) -> dict[str, tuple[float, float, float]]:
        """{signal_id: (value, quality, stored_at)} – TTL avgörs av anroparen."""

    @abstractmethod
    def put_cached_signals(self, source: str, loc_key: str,
                           signals: dict[str, tuple[float, float]],
                           stored_at: float) -> None:
        """signals = {signal_id: (value, quality)}; skriver över befintliga."""

    @abstractmethod
    def get_cached_extras(self, source: str, loc_key: str
                          ) -> Optional[tuple[dict[str, Any], float]]:
        """(extras, stored_at) eller None."""

    @abstractmethod
    def put_cached_extras(self, source: str, loc_key: str,
                          extras: dict[str, Any], stored_at: float) -> None: ...

    def bump_usage(self, tenant: str, month: str, quota: int):
        """Persistent kvoträkning. Returnerar True (tillåtet) / False
        (kvot nådd), eller None om lagret inte stöder det – då faller
        anroparen tillbaka på in-memory-räkning. Valfritt att överskugga."""
        return None

    # ── Utfall (kalibrering) ─────────────────────────────────────────
    def save_outcome(self, record: dict[str, Any]):
        """Persistera en utfallspost (append-only, idempotent på record['id']).
        Returnerar id, eller None om lagret inte stöder det – då faller
        anroparen tillbaka på process-minne. Valfritt att överskugga."""
        return None

    def all_outcomes(self) -> Optional[list[dict[str, Any]]]:
        """Alla utfallsposter, eller None om lagret inte stöder det."""
        return None

    # ── Ansvarsloop (beslut → utfall) ────────────────────────────────
    def save_decision(self, record: dict[str, Any]):
        """Persistera ett beslut (append-only, idempotent på id). None =
        stöds ej → anroparen faller tillbaka på process-minne."""
        return None

    def all_decisions(self) -> Optional[list[dict[str, Any]]]:
        return None

    def save_resolution(self, record: dict[str, Any]):
        """Persistera en utfalls-resolution (append-only, idempotent på id)."""
        return None

    def all_resolutions(self) -> Optional[list[dict[str, Any]]]:
        return None

    # ── Wiki-rättelser ───────────────────────────────────────────────
    def save_correction(self, record: dict[str, Any]):
        """Persistera en rättelse (append-only, idempotent på id). None =
        stöds ej → process-minne."""
        return None

    def all_corrections(self) -> Optional[list[dict[str, Any]]]:
        return None

    # ── Bevakningar (kontroll-infrastruktur / cron) ──────────────────
    def save_monitor(self, record: dict[str, Any]):
        """Persistera/uppdatera en bevakning (idempotent på id). None =
        stöds ej → process-minne."""
        return None

    def all_monitors(self) -> Optional[list[dict[str, Any]]]:
        return None

    def save_finding(self, record: dict[str, Any]):
        """Persistera en avvikelse (append-only, idempotent på checksum)."""
        return None

    def all_findings(self) -> Optional[list[dict[str, Any]]]:
        return None

    # ── Återkommande kontroller av kundens egna objekt ───────────────
    # Ingen av metoderna tar tenant: motorn filtrerar (engine/inspections
    # ._las), lagret lagrar. Samma delning som för bevakningar. Tenant
    # ligger som kolumn i SQLite för att raden ska gå att hänföra till en
    # kund utan att packa upp JSON.
    def save_asset(self, record: dict[str, Any]):
        """Persistera/uppdatera ett objekt (idempotent på tenant+id).
        None = stöds ej → process-minne."""
        return None

    def all_assets(self) -> Optional[list[dict[str, Any]]]:
        return None

    def save_routine(self, record: dict[str, Any]):
        """Persistera/uppdatera en kontrollrutin (idempotent på tenant+id)."""
        return None

    def all_routines(self) -> Optional[list[dict[str, Any]]]:
        return None

    def save_check(self, record: dict[str, Any]):
        """Persistera ett utfall (append-only). Bär ALDRIG media — bara
        domen och en referens till uppdraget hos quiXzoom."""
        return None

    def all_checks(self) -> Optional[list[dict[str, Any]]]:
        return None

    # ── Schemalagda körningar ────────────────────────────────────────
    def save_job(self, record: dict[str, Any]):
        """Persistera/uppdatera ett schemalagt jobb (idempotent på
        tenant+id). None = stöds ej → process-minne."""
        return None

    def all_jobs(self) -> Optional[list[dict[str, Any]]]:
        return None

    # ── Skördad öppen data (delas av alla kunder) ────────────────────
    def save_harvested(self, rows: list[dict[str, Any]]):
        """Skriv skördade rader (idempotent på source+region+signal).
        Ingen tenant: öppen referensdata är densamma för alla."""
        return None

    def all_harvested(self) -> Optional[list[dict[str, Any]]]:
        return None

    def save_news(self, rows: list[dict[str, Any]]):
        """Nyhetsposter (idempotent på checksumma). Ingen tenant:
        publicerad text är densamma för alla."""
        return None

    def all_news(self) -> Optional[list[dict[str, Any]]]:
        return None

    def claim_job(self, job_id: str, tenant: str, now: float,
                  gap_seconds: float):
        """Ta jobbet ATOMISKT om det inte körts inom `gap_seconds`.
        True = det här anropet äger körningen. None = stöds ej, och då
        gäller anroparens claim bara den egna processen."""
        return None

    def close(self) -> None:   # noqa: B027 – avsiktlig no-op, ej abstrakt
        """Stäng lagret. Medvetet INTE abstrakt: ett lager utan
        resurser att frigöra ska slippa implementera en tom metod,
        och anroparen ska slippa veta vilket sorts lager den har."""
