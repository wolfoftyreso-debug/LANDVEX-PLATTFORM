"""Datakällslager.

En DataSource levererar signalvärden + "extras" (rådetaljer för
narrativ, t.ex. konkurrentlistan). Resolver frågar källor i
prioritetsordning och faller tillbaka på nästa källa per signal.

I AWS-fasen kopplas riktiga adaptrar in (SCB, rörelsedata, bygglov,
platsdata) – motorn behöver inte ändras, bara källistan.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable

from ..models import Location, SignalValue


class DataSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        """Returnerar ({signal_id: SignalValue}, extras)."""


class Resolver:
    """Frågar källor i ordning; första källa som har en signal vinner.

    TIDSBUDGET. Varje källa har sin egen timeout, men ett svar som frågar
    flera källor i rad betalar dem allihop. Med sex sekunder per källa
    räckte två tröga källor för att /v1/report skulle ta tretton sekunder
    — mot en budget på 700 ms. En människa väntade i tretton sekunder på
    ett svar som ändå till slut blev mock.

    `budget_ms` är taket för hur länge ETT anrop får ägna åt levande
    källor sammanlagt. När det är slut hoppas resterande källor över och
    MockSource tar vid, precis som när en källa är nere.

    Överhoppet redovisas i `extras["resolver"]`. Att tyst sluta fråga
    vore samma fel som tyst nedgradering: svaret blir tunnare än det ser
    ut, och ingen får veta varför.

    ÄRLIGT OM TAKET: budgeten kollas FÖRE varje källa, så en källa som
    redan är i luften får göra klart. Värsta fallet är alltså budgeten
    plus EN källas timeout (1200 + 2500 ms), inte budgeten. Att avbryta
    mitt i ett anrop kräver trådar, och den komplexiteten är inte värd
    det när strömbrytaren ändå gör andra anropet snabbt. Taket är ett
    tak på hur många tröga källor ett svar betalar, inte en garanti på
    millisekunden.
    """

    # Noll = inget tak (tester och batchjobb som inte har någon som väntar).
    DEFAULT_BUDGET_MS = 1200.0

    def __init__(self, sources: list[DataSource],
                 budget_ms: float | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.sources = sources
        self.budget_ms = (self.DEFAULT_BUDGET_MS if budget_ms is None
                          else float(budget_ms))
        self._clock = clock

    def resolve(self, location: Location, vertical_id: str,
                signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        values: dict[str, SignalValue] = {}
        extras: dict[str, Any] = {}
        missing = list(signal_ids)
        started = self._clock()
        skipped: list[str] = []
        for src in self.sources:
            if not missing:
                break
            spent_ms = (self._clock() - started) * 1000.0
            # MockSource är sist och kostar ingenting; den hoppas aldrig
            # över, annars vore svaret tomt i stället för ärligt märkt.
            if (self.budget_ms > 0 and spent_ms >= self.budget_ms
                    and getattr(src, "name", "") != "mock"):
                skipped.append(getattr(src, "name", src.__class__.__name__))
                continue
            got, ex = src.fetch(location, vertical_id, missing)
            for sid, sv in got.items():
                if sv.value is not None and sid not in values:
                    values[sid] = sv
            for k, v in ex.items():
                extras.setdefault(k, v)
            missing = [s for s in signal_ids if s not in values]
        if skipped:
            extras["resolver"] = {
                "budget_ms": self.budget_ms,
                "spent_ms": round((self._clock() - started) * 1000.0, 1),
                "skipped_sources": skipped,
                "why_en": (
                    f"The live-source time budget of {self.budget_ms:.0f} ms "
                    f"was spent before these sources were reached, so they "
                    f"were not queried and mock values stand in their place. "
                    f"They are labelled mock like any other, and "
                    f"data_coverage reflects it."),
            }
        return values, extras
