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

import os
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
               "share_65plus", "residential_density", "population_total")
    _QUALITY = {"pop_growth_pct": 0.7, "income_index": 0.7,
                "age_20_45_share": 0.7, "share_65plus": 0.7,
                "residential_density": 0.55,   # härledd via hushållssnitt
                "population_total": 0.9}       # exakt på kommunnivå

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
               ("pop_growth_pct", "age_20_45_share", "share_65plus",
                "population_total")):
            try:
                sig, extra = scb.population_signals(self.client, kommun)
                raw.update(sig)
                raw["population_total"] = float(extra["folkmangd_kommun"])
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
                    "notis": "Municipality level – refined to DeSO/grid "
                             "in the geodata phase."}
            for k in ("ar", "folkmangd_kommun"):
                if k in extras:
                    info[k] = extras.pop(k)
            extras = {"scb": info}
        return signals, extras


def production_sources() -> list[DataSource]:
    """Källkedjan före MockSource i produktion (ordning = prioritet)."""
    return [ScbSource(), PermitsSource(), PlacesSource(), MovementSource(),
            QuixzoomSource()]


class MovementSource(_NotWiredSource):
    name = "movement"


class PermitsSource(_NotWiredSource):
    name = "permits"


class PlacesSource(_NotWiredSource):
    name = "places"


class QuixzoomSource(DataSource):
    """Fältobservationer (quiXzoom) – Landvex-ekosystemets observations-
    lager och nyckelkälla för kontradiktionsindexet: officiell plandata
    vs faktiskt observerad aktivitet.

    Riktig HTTP-klient mot quiXzoom-API:ts /v1/observations
    (RealityIntelligence-tjänsten, :3209 i produktionsmiljön). Basadress
    sätts via LANDVEX_QUIXZOOM_URL; utan den är källan ej ansluten och
    Resolvern faller ärligt vidare till mock. Transporten är injicerbar
    för tester. Fel pausar källan (som SCB-adaptern) i stället för att
    fälla anropet.
    """

    name = "quixzoom"
    SIGNALS = ("development_m2", "renovation_index", "foot_traffic",
               "vacancy_rate")
    _QUALITY = {"development_m2": 0.8, "renovation_index": 0.7,
                "foot_traffic": 0.75, "vacancy_rate": 0.7}

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str], dict] | None = None,
                 retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_QUIXZOOM_URL", ""))
        self._transport = transport or self._http_get
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0

    def _http_get(self, url: str) -> dict:
        import json
        import urllib.request
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        wanted = [s for s in signal_ids if s in self.SIGNALS]
        if not wanted or not self.base_url:
            return {}, {}
        if self._clock() < self._down_until:
            return {}, {}
        url = (f"{self.base_url.rstrip('/')}/v1/observations"
               f"?lat={location.lat}&lon={location.lon}"
               f"&signals={','.join(wanted)}")
        try:
            data = self._transport(url)
        except Exception:
            self._down_until = self._clock() + self._retry_after_s
            return {}, {}
        obs = data.get("observations", data if isinstance(data, dict) else {})
        values = {}
        for sid in wanted:
            v = obs.get(sid)
            if isinstance(v, dict):
                v = v.get("value")
            if v is None:
                continue
            values[sid] = SignalValue(sid, float(v), source=self.name,
                                      quality=self._QUALITY.get(sid, 0.7))
        extras = {"quixzoom": {"observed_at": data.get("observed_at"),
                               "network": data.get("network", "quixzoom")}} \
            if values else {}
        return values, extras
