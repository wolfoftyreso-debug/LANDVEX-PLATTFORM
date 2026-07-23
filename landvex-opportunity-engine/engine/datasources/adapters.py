"""Adaptrar för produktionskällor.

Var och en implementerar DataSource.fetch() och läggs FÖRE MockSource
i Resolver-kedjan. Då tar verklig data automatiskt över per signal,
och data_coverage i rapporten stiger i takt med att källor kopplas in.

Status:

  ScbSource      – IMPLEMENTERAD (kommunnivå). SCB:s öppna PxWeb-API.
                   Signaler: pop_growth_pct, income_index,
                   age_20_45_share, share_65plus, residential_density.
                   pop_radius/families_share kräver DeSO/rutnät resp.
                   hushållsdata → kvar på mock tills geodatafasen.

  MovementSource – Rörelsedata (t.ex. Telia Crowd Insights eller
                   motsvarande, licensavtal krävs).
                   Signaler: foot_traffic, flow_*, commuter_flow,
                   target_match_pct.

  PermitsSource  – Bygglov & detaljplaner (kommunala öppna data,
                   Boverket, tredjepartsaggregatorer).
                   Signaler: building_permits, detail_plans,
                   development_m2, renovation_index.

  PlacesSource   – Konkurrens & utbud (Google Places / Bolagsverket /
                   recensionsdata).
                   Signaler: competition_pressure, provider_gap
                   + extras["competitors"].

Nycklar och avtal hanteras i AWS via Secrets Manager; se infra/aws-notes.md.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from ..models import Location, SignalValue
from .base import DataSource
from . import scb


class _NotWiredSource(DataSource):
    """Gemensam bas: returnerar tomt tills adaptern är kopplad."""

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        return {}, {}


class ScbSource(DataSource):
    """Verklig befolknings-/inkomstdata från SCB, kommunnivå.

    Kvalitetsflaggan speglar spatial upplösning: kommunstatistik på ett
    10-minutersområde är verklig men grov → quality < 1.0. Vid nätverks-
    eller tabellfel returneras tomt och källan pausas en stund
    (Resolver faller vidare till mock; data_coverage förblir ärlig).
    """

    name = "scb"
    SIGNALS = ("pop_growth_pct", "income_index", "age_20_45_share",
               "share_65plus", "residential_density")
    _QUALITY = {"pop_growth_pct": 0.7, "income_index": 0.7,
                "age_20_45_share": 0.7, "share_65plus": 0.7,
                "residential_density": 0.55}   # härledd via hushållssnitt

    def __init__(self, client: scb.ScbClient | None = None,
                 locator: scb.KommunLocator | None = None,
                 retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        self._client = client
        self._locator = locator or scb.KommunLocator()
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0

    @property
    def client(self) -> scb.ScbClient:
        if self._client is None:
            self._client = scb.ScbClient()
        return self._client

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        wanted = [s for s in signal_ids if s in self.SIGNALS]
        if not wanted or self._clock() < self._down_until:
            return {}, {}
        hit = self._locator.locate(location.lat, location.lon)
        if hit is None:
            return {}, {}
        kommun, kommun_namn = hit

        raw: dict[str, float] = {}
        extras: dict[str, Any] = {}
        failures = 0

        if any(s in wanted for s in
               ("pop_growth_pct", "age_20_45_share", "share_65plus")):
            try:
                sig, extra = scb.population_signals(self.client, kommun)
                raw.update(sig)
                extras.update(extra)
            except Exception:
                failures += 1
        if "income_index" in wanted:
            try:
                raw["income_index"] = scb.income_index_signal(self.client, kommun)
            except Exception:
                failures += 1
        if "residential_density" in wanted:
            try:
                raw["residential_density"] = scb.density_signal(self.client, kommun)
            except Exception:
                failures += 1

        if failures and not raw:      # allt föll → paus, mock tar över helt
            self._down_until = self._clock() + self._retry_after_s
            return {}, {}

        signals = {sid: SignalValue(sid, raw[sid], source=self.name,
                                    quality=self._QUALITY[sid])
                   for sid in wanted if sid in raw}
        if signals:
            info = {"kommun": kommun, "kommun_namn": kommun_namn,
                    "notis": "Kommunnivå – förfinas till DeSO/rutnät "
                             "i geodatafasen."}
            for k in ("ar", "folkmangd_kommun"):
                if k in extras:
                    info[k] = extras.pop(k)
            extras = {"scb": info}
        return signals, extras


def production_sources() -> list[DataSource]:
    """Källkedjan före MockSource i produktion (ordning = prioritet)."""
    return [ScbSource(), PermitsSource(), PlacesSource(), MovementSource()]


class MovementSource(_NotWiredSource):
    name = "movement"


class PermitsSource(_NotWiredSource):
    name = "permits"


class PlacesSource(_NotWiredSource):
    name = "places"
