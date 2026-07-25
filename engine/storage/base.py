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
    def save_report(self, report: dict[str, Any], created_at: float) -> str:
        """Sparar en rapport (dict från OpportunityReport.to_dict()).
        Returnerar genererat rapport-id."""

    @abstractmethod
    def get_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """Full rapport + metadata, eller None."""

    @abstractmethod
    def list_reports(self, limit: int = 20) -> list[dict[str, Any]]:
        """Sammanfattningar, nyast först."""

    # ── Sparade affärsprofiler ───────────────────────────────────────

    @abstractmethod
    def save_profile(self, profile: dict[str, Any], created_at: float) -> str:
        """Sparar en affärsprofil (dict från BusinessProfile.to_dict()).
        Returnerar genererat profil-id."""

    @abstractmethod
    def get_profile(self, profile_id: str) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    def list_profiles(self, limit: int = 50) -> list[dict[str, Any]]:
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

    def close(self) -> None:  # valfritt att överskugga
        pass
