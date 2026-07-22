"""Adapterstubbar för produktionskällor.

Var och en implementerar DataSource.fetch() och läggs FÖRE MockSource
i Resolver-kedjan. Då tar verklig data automatiskt över per signal,
och data_coverage i rapporten stiger i takt med att källor kopplas in.

Planerade källor:

  ScbSource      – SCB:s öppna API:er (befolkning på rutnät/DeSO,
                   inkomst, åldersstruktur, hushåll). Öppet, gratis.
                   Signaler: pop_radius, pop_growth_pct, income_index,
                   age_20_45_share, families_share, share_65plus,
                   residential_density.

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

from typing import Any

from ..models import Location, SignalValue
from .base import DataSource


class _NotWiredSource(DataSource):
    """Gemensam bas: returnerar tomt tills adaptern är kopplad."""

    def fetch(self, location: Location, vertical_id: str,
              signal_ids: list[str]) -> tuple[dict[str, SignalValue], dict[str, Any]]:
        return {}, {}


class ScbSource(_NotWiredSource):
    name = "scb"


class MovementSource(_NotWiredSource):
    name = "movement"


class PermitsSource(_NotWiredSource):
    name = "permits"


class PlacesSource(_NotWiredSource):
    name = "places"
