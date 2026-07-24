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
from .scb import _haversine_km


def _mission_latlon(m):
    """Plocka (lat, lon) ur ett quiXzoom-mission/submission-objekt.
    Mission har location:{lat,lng}; submission har toppnivå lat/lon."""
    if not isinstance(m, dict):
        return None, None
    loc = m.get("location")
    if isinstance(loc, dict):
        lat = loc.get("lat")
        lon = loc.get("lng", loc.get("lon"))
    else:
        lat = m.get("lat")
        lon = m.get("lon", m.get("lng"))
    try:
        return (float(lat), float(lon)) if lat is not None \
            and lon is not None else (None, None)
    except (TypeError, ValueError):
        return None, None


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
    """Fältobservationer (quiXzoom) – VIA AAMOS Core.

    VERKLIG MODELL (bekräftad av AAMOS-dev): quiXzoom är mission-baserat,
    INTE en /v1/observations-endpoint. Missions har formen
    {id, title, description, location:{lat,lng}, reward, currency,
    status, required_media, deadline, created_at} – notera fältet `lng`.
    Fältdata når oss via AAMOS Core (:3100) på /api/qz/missions
    (AAMOS_QUIXZOOM_PATH), inte direkt mot :3209 (beslut #2).

    Vad vi ÄRLIGT kan härleda idag: tätheten av missions inom radien
    runt punkten → signalen `field_observation_density`. Vi filtrerar
    på plats med missionernas location så densiteten är verkligt lokal,
    oavsett om servern förfiltrerar. Det precisa "observerat byggt"
    (development_m2) för kontradiktionsindexet kräver Vision-analys av
    det inskickade mediet och lämnas på mock tills Vision-pipelinen är
    trådad – vi hittar aldrig på siffran.

    Källan är ej ansluten tills AAMOS_CORE_URL är satt; då faller
    Resolvern ärligt vidare till mock. Transporten (AamosClient) är
    injicerbar för tester; fel pausar källan i stället för att fälla
    anropet.
    """

    name = "quixzoom"
    SIGNALS = ("field_observation_density",)
    RADIUS_KM = 10.0

    def __init__(self, client=None,
                 retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        # Default: en AamosClient som läser AAMOS_CORE_URL.
        if client is None:
            from integrations.aamos import AamosClient
            client = AamosClient()
        self._client = client
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0

    @property
    def base_url(self) -> str:
        # Health/status-lagret läser base_url för att avgöra anslutning.
        return getattr(self._client, "base_url", "")

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        if "field_observation_density" not in signal_ids:
            return {}, {}
        if not getattr(self._client, "connected", False):
            return {}, {}
        if self._clock() < self._down_until:
            return {}, {}
        try:
            data = self._client.quixzoom_missions(
                location.lat, location.lon, radius_km=self.RADIUS_KM)
        except Exception:
            self._down_until = self._clock() + self._retry_after_s
            return {}, {}
        # Robust mot svarsform: en lista av missions, eller {missions:[...]}
        missions = data.get("missions", data) if isinstance(data, dict) else data
        if isinstance(missions, dict):
            missions = missions.get("items", [])
        if not isinstance(missions, list):
            return {}, {}
        # Filtrera lokalt på missionens plats (fält `lng` i mission-objektet,
        # `lon` i submission; toppnivå-lat/lon som reserv) så densiteten är
        # verkligt lokal även om servern inte förfiltrerar.
        near = 0
        for m in missions:
            mlat, mlon = _mission_latlon(m)
            if mlat is None:
                near += 1                    # ingen plats → räkna med, ärligt
            elif _haversine_km(location.lat, location.lon, mlat, mlon) \
                    <= self.RADIUS_KM:
                near += 1
        density = float(near)
        values = {"field_observation_density": SignalValue(
            "field_observation_density", density, source=self.name,
            quality=0.8)}
        extras = {"quixzoom": {"missions_near": near, "radius_km": self.RADIUS_KM,
                               "via": "aamos_core"}}
        return values, extras
