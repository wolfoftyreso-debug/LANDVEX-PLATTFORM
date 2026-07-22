"""Datakällslager.

En DataSource levererar signalvärden + "extras" (rådetaljer för
narrativ, t.ex. konkurrentlistan). Resolver frågar källor i
prioritetsordning och faller tillbaka på nästa källa per signal.

I AWS-fasen kopplas riktiga adaptrar in (SCB, rörelsedata, bygglov,
platsdata) – motorn behöver inte ändras, bara källistan.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Location, SignalValue


class DataSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        """Returnerar ({signal_id: SignalValue}, extras)."""


class Resolver:
    """Frågar källor i ordning; första källa som har en signal vinner."""

    def __init__(self, sources: list[DataSource]):
        self.sources = sources

    def resolve(self, location: Location, vertical_id: str,
                signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        values: dict[str, SignalValue] = {}
        extras: dict[str, Any] = {}
        missing = list(signal_ids)
        for src in self.sources:
            if not missing:
                break
            got, ex = src.fetch(location, vertical_id, missing)
            for sid, sv in got.items():
                if sv.value is not None and sid not in values:
                    values[sid] = sv
            for k, v in ex.items():
                extras.setdefault(k, v)
            missing = [s for s in signal_ids if s not in values]
        return values, extras
