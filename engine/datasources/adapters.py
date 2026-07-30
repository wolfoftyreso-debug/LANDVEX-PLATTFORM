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
from .faults import OUR_BUGS
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

    connected = False       # en stubbe är per definition inte ansluten

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
    # SCB:s PxWeb är svensk statistik och lokaliseringen sker mot
    # svenska kommuncentroider. En punkt i Texas får inget svar här.
    markets = ("se",)
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
            except OUR_BUGS:
                raise
            except Exception:
                failures += 1
        if "income_index" in wanted:
            try:
                raw["income_index"] = scb.income_index_signal(self.client, kommun)
            except OUR_BUGS:
                raise
            except Exception:
                failures += 1
        if "residential_density" in wanted:
            try:
                raw["residential_density"] = scb.density_signal(self.client, kommun)
            except OUR_BUGS:
                raise
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


class HarvestedSource(DataSource):
    """Skördad öppen data — läser LAGRET, aldrig nätet.

    Det här är den enda källan i kedjan som garanterat inte kan göra ett
    utgående anrop. Den skillnaden är hela poängen: Overpass svarar på
    sekunder, svarsbudgeten är 700 ms, och en publik gratistjänst ska
    inte få samma fråga av varje besökare. Skörden sker på schema
    (`engine/scheduler.JOB_KINDS["harvest"]`), och frågan läser resultatet.

    Källan svarar bara när raden är BÅDE färsk nog och nära nog. Är den
    för gammal eller för långt bort returneras ingenting, Resolvern
    faller vidare till mock, och `data_coverage` sjunker som den ska —
    i stället för att ett gammalt tal serveras tyst som ett aktuellt.
    """

    name = "harvested"

    def __init__(self):
        self._memo: list | None = None

    def _rader(self) -> list:
        # Läs lagret en gång per instans. Täckningsytan frågar både
        # `markets` och `connected`, och compare_markets gör det för 35
        # marknader — utan memo blev det sjuttio läsningar av hela
        # tabellen för att svara på en fråga.
        if self._memo is None:
            from engine import harvest
            self._memo = harvest.all_rows()
        return self._memo

    @property
    def markets(self) -> tuple:
        """Räckvidden är vad som FAKTISKT är skördat, inte vad som skulle
        kunna skördas. En källa som är påslagen men aldrig körd kan inte
        svara, och täckningsytan får inte påstå något annat."""
        return tuple(sorted({r.get("market", "") for r in self._rader()
                             if r.get("market")}))

    @property
    def connected(self) -> bool:
        return bool(self._rader())

    # Vad skörden kan fylla. Läses av engine/coverage.py; en tom lista
    # hade gjort källan osynlig i täckningen hur mycket den än svarade.
    @property
    def SIGNALS(self) -> tuple:      # noqa: N802 – kontraktet är versalt
        from engine import harvest
        return tuple(sorted({sid for s in harvest.SOURCES.values()
                             for sid in s["signals"]}))

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        from engine import harvest

        ut: dict[str, SignalValue] = {}
        extras: dict[str, Any] = {}
        for kalla in harvest.SOURCES:
            # Konkurrenssignalen är per bransch: nyckeln i lagret bär
            # vertikalen, annars hade frisörernas antal svarat för
            # bilverkstäderna.
            onskade = [f"{s}:{vertical_id}" if s == "competition_pressure"
                       else s for s in signal_ids]
            traffar = harvest.read(kalla, location.lat, location.lon, onskade)
            for nyckel, rad in traffar.items():
                sid = nyckel.split(":", 1)[0]
                if sid in ut or rad.get("value") is None:
                    continue
                ut[sid] = SignalValue(sid, float(rad["value"]),
                                      source=kalla,
                                      quality=float(rad["quality"]))
                extras.setdefault("harvested", {})[sid] = {
                    "source": kalla, "region_code": rad["region_code"],
                    "distance_km": rad["distance_km"],
                    "age_days": rad["age_days"],
                    "observed_count": rad.get("observed_count"),
                    "basis_en": (
                        f"Harvested from {kalla} "
                        f"{rad['age_days']:g} day(s) ago, "
                        f"{rad['distance_km']:g} km from the point. A "
                        f"reading from the next municipality is a weaker "
                        f"basis than one from the place itself."),
                }
        return ut, extras


def production_sources() -> list[DataSource]:
    """Källkedjan före MockSource i produktion (ordning = prioritet).

    HarvestedSource ligger SIST bland de riktiga: en direktansluten källa
    som svarar nu är alltid bättre än ett skördat värde från i går.
    """
    return [ScbSource(), LivabilitySource(), PermitsSource(), PlacesSource(),
            MovementSource(), QuixzoomSource(), HarvestedSource()]


class MovementSource(_NotWiredSource):
    name = "movement"


class PermitsSource(DataSource):
    """Bygglov & detaljplaner – "officiellt planerat"-signalerna.

    Verklig data för `building_permits`, `detail_plans`, `development_m2`
    från en kommunal/nationell öppen-datakälla via PermitsClient. Ej
    ansluten tills LANDVEX_PERMITS_URL är satt → Resolvern faller ärligt
    vidare till mock. Fel pausar källan i stället för att fälla anropet.
    Hittar aldrig på ett fält som feeden inte levererar.
    """

    name = "permits"
    SIGNALS = ("building_permits", "detail_plans", "development_m2")
    _QUALITY = {"building_permits": 0.75, "detail_plans": 0.75,
                "development_m2": 0.6}

    def __init__(self, client=None, retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        if client is None:
            from .permits import PermitsClient
            client = PermitsClient()
        self._client = client
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0

    @property
    def base_url(self) -> str:
        return getattr(self._client, "base_url", "")

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        wanted = [s for s in signal_ids if s in self.SIGNALS]
        if not wanted or not getattr(self._client, "connected", False):
            return {}, {}
        if self._clock() < self._down_until:
            return {}, {}
        try:
            raw = self._client.fetch_permits(location.lat, location.lon)
        except OUR_BUGS:
            # Ett attribut/namn/import som inte finns kan inte komma från en
            # server. Det är vårt fel och ska braka, inte tyst bli "mock".
            raise
        except Exception:
            self._down_until = self._clock() + self._retry_after_s
            return {}, {}
        values = {s: SignalValue(s, float(raw[s]), source=self.name,
                                 quality=self._QUALITY[s])
                  for s in wanted if s in raw}
        extras = {"permits": {"via": self.base_url}} if values else {}
        return values, extras


class PlacesSource(DataSource):
    """Konkurrens & utbud – `competition_pressure`, `provider_gap`.

    Verklig data från en places/register/recensionskälla via PlacesClient
    (+ konkurrentlista i extras). Ej ansluten tills LANDVEX_PLACES_URL är
    satt → Resolvern faller ärligt vidare till mock. Fel pausar källan.
    provider_gap hittas aldrig på – den kräver en efterfrågeuppskattning
    och kommer bara från feeden.
    """

    name = "places"
    SIGNALS = ("competition_pressure", "provider_gap")
    _QUALITY = {"competition_pressure": 0.7, "provider_gap": 0.65}

    def __init__(self, client=None, retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        if client is None:
            from .places import PlacesClient
            client = PlacesClient()
        self._client = client
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0

    @property
    def base_url(self) -> str:
        return getattr(self._client, "base_url", "")

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        wanted = [s for s in signal_ids if s in self.SIGNALS]
        if not wanted or not getattr(self._client, "connected", False):
            return {}, {}
        if self._clock() < self._down_until:
            return {}, {}
        try:
            raw, competitors = self._client.fetch_places(
                location.lat, location.lon, vertical_id)
        except OUR_BUGS:
            # Ett attribut/namn/import som inte finns kan inte komma från en
            # server. Det är vårt fel och ska braka, inte tyst bli "mock".
            raise
        except Exception:
            self._down_until = self._clock() + self._retry_after_s
            return {}, {}
        values = {s: SignalValue(s, float(raw[s]), source=self.name,
                                 quality=self._QUALITY[s])
                  for s in wanted if s in raw}
        extras = {"competitors": competitors} if values and competitors else {}
        return values, extras


class QuixzoomSource(DataSource):
    """Fältobservationer (quiXzoom) – VIA AAMOS Core.

    VERKLIG MODELL (bekräftad av AAMOS-dev): quiXzoom är mission-baserat,
    INTE en /v1/observations-endpoint. Missions har formen
    {id, title, description, location:{lat,lng}, reward, currency,
    status, required_media, deadline, created_at} – notera fältet `lng`.
    Fältdata når oss via AAMOS Core (:3100) på /api/quixzoom/missions
    (AAMOS_QUIXZOOM_PATH, bekräftad live på server-2 2026-07-30), inte
    direkt mot :3209 (beslut #2).

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
        # Default: via AAMOS Core (AAMOS_CORE_URL). Om LANDVEX_QUIXZOOM_URL är
        # satt föredras quiXzooms EGNA API (:3209) direkt – valfri alternativ
        # väg när Core-token saknas. Ingen bypass: :3209:s egen auth gäller.
        if client is None:
            if os.environ.get("LANDVEX_QUIXZOOM_URL"):
                from .quixzoom_direct import DirectQuixzoomClient
                client = DirectQuixzoomClient()
            else:
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
        except OUR_BUGS:
            # Ett attribut/namn/import som inte finns kan inte komma från en
            # server. Det är vårt fel och ska braka, inte tyst bli "mock".
            raise
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

class LivabilitySource(DataSource):
    """Livsvillkorssignaler ur myndighetsstatistik (Kolada SE, Eurostat EU).

    Fyller förskola, skola, trygghet, sjukvård, boendekostnad och socialt
    kapital med verkliga kommunala nyckeltal i stället för mock. Ej ansluten
    tills LANDVEX_KOLADA_URL (resp. LANDVEX_EUROSTAT_LIVE=1) är satt →
    Resolvern faller ärligt vidare till mock. Fel pausar källan.

    Kvaliteten speglar hur säker kopplingen är: ett KPI som bekräftats i
    skörden väger tyngre än en kandidat som proben ännu inte verifierat.
    """

    name = "livability"
    # Kolada är svenska kommuners nyckeltal.
    markets = ("se",)
    SIGNALS = ("care_supply", "education_outcomes", "crime_index",
               "healthcare_access", "life_satisfaction", "social_trust",
               "housing_affordability")
    _Q_VERIFIED = 0.8
    _Q_CANDIDATE = 0.55

    def __init__(self, client=None, locator=None, retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        if client is None:
            from .livability_sources import KoladaLivability
            client = KoladaLivability()
        self._client = client
        self._locator = locator
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0

    @property
    def base_url(self) -> str:
        return getattr(self._client, "base_url", "")

    def _kommun(self, location: Location) -> str | None:
        loc = self._locator
        if loc is None:
            from .scb import KommunLocator
            loc = self._locator = KommunLocator()
        hit = loc.locate(location.lat, location.lon)   # (kod, namn) | None
        return hit[0] if hit else None

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        wanted = [s for s in signal_ids if s in self.SIGNALS]
        if not wanted or not getattr(self._client, "connected", False):
            return {}, {}
        if self._clock() < self._down_until:
            return {}, {}
        try:
            kommun = self._kommun(location)
            if kommun is None:
                return {}, {}
            from .livability_sources import KOLADA_SIGNALS
            values, meta = {}, {}
            for sid in wanted:
                got = self._client.value(sid, kommun)
                if got is None:
                    continue      # ingen siffra ⇒ mock tar över, märkt mock
                q = (self._Q_VERIFIED if KOLADA_SIGNALS[sid]["verified"]
                     else self._Q_CANDIDATE)
                values[sid] = SignalValue(sid, float(got["value"]),
                                          source=self.name, quality=q)
                meta[sid] = {"kpi": got.get("kpi"), "year": got.get("year"),
                             "raw_value": got.get("raw_value"),
                             "transform": got.get("transform"),
                             "label_en": got.get("label_en")}
        except OUR_BUGS:
            # Ett attribut/namn/import som inte finns kan inte komma från en
            # server. Det är vårt fel och ska braka, inte tyst bli "mock".
            raise
        except Exception:
            self._down_until = self._clock() + self._retry_after_s
            return {}, {}
        extras = {"livability_kpis": meta} if meta else {}
        return values, extras
