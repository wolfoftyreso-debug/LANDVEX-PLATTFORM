"""Cachande wrapper runt en verklig datakälla.

Läggs runt varje produktionskälla i Resolver-kedjan: träff i cachen
undviker API-anrop (och kostnader/latens), miss delegeras till den
inre källan och resultatet skrivs tillbaka med tidsstämpel. TTL sätts
per källa – SCB uppdateras årsvis, rörelsedata betydligt oftare.

Cachen är platsnycklad på avrundade koordinater + radie, samma
upplösning som MockSource:s seed (~100 m). Mock cachas aldrig – den
är redan deterministisk och gratis.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from ..models import Location, SignalValue
from ..storage.base import Store
from .base import DataSource

# TTL per källa (sekunder). Styr hur länge verklig data återanvänds.
DEFAULT_TTLS: dict[str, float] = {
    "scb": 7 * 24 * 3600.0,        # årsstatistik – veckovis omhämtning räcker
    "permits": 24 * 3600.0,
    "places": 24 * 3600.0,
    "movement": 6 * 3600.0,
}
FALLBACK_TTL = 24 * 3600.0


def loc_key(location: Location) -> str:
    return f"{location.lat:.3f}:{location.lon:.3f}:{location.radius_minutes}"


class CachedSource(DataSource):

    def __init__(self, inner: DataSource, store: Store,
                 ttl_s: float | None = None,
                 clock: Callable[[], float] = time.time):
        self.inner = inner
        self.name = inner.name          # cachade värden behåller källnamnet
        self.store = store
        self.ttl_s = ttl_s if ttl_s is not None else \
            DEFAULT_TTLS.get(inner.name, FALLBACK_TTL)
        self._clock = clock

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        now = self._clock()
        key = loc_key(location)

        cached = self.store.get_cached_signals(self.name, key)
        hits = {sid: SignalValue(sid, v, source=self.name, quality=q)
                for sid, (v, q, ts) in cached.items()
                if sid in signal_ids and now - ts < self.ttl_s}

        extras: dict[str, Any] = {}
        ex = self.store.get_cached_extras(self.name, key)
        if ex is not None and now - ex[1] < self.ttl_s:
            extras = ex[0]

        # Signaler som varken är färska i cachen eller redan hämtade.
        # Källor svarar bara på sina egna signaler, så överflödiga id:n
        # i listan är billiga no-ops för den inre källan.
        missing = [s for s in signal_ids if s not in hits]
        if missing:
            got, gex = self.inner.fetch(location, vertical_id, missing)
            if got:
                self.store.put_cached_signals(
                    self.name, key,
                    {sid: (sv.value, sv.quality) for sid, sv in got.items()
                     if sv.value is not None}, now)
                hits.update(got)
            if gex:
                extras = {**extras, **gex}
                self.store.put_cached_extras(self.name, key, extras, now)
        return hits, extras
