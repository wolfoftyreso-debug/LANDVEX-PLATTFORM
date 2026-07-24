"""Places / competition adapter — competition_pressure & provider_gap.

Feeds the competitive-supply signals from a places / registry / reviews
source (Google Places, Bolagsverket, review data, or an aggregator). These
drive competition risk, the competition gap on the decision card, and the
observed competition picture. Same contract as the SCB / permits / programs
adapters:

  * stdlib only; belongs to engine/, runs in Lambda.
  * injectable transport → deterministic fixture tests, no network.
  * NOT connected until LANDVEX_PLACES_URL is set → the Resolver falls
    through to mock honestly; a source error pauses the source.

Contract (what LANDVEX_PLACES_URL must return for ?lat=&lon=&vertical=): JSON,
either
  (a) an object with any of {competition_pressure (0–10), provider_gap
      (demand/supply ratio)} and an optional "competitors" list, or
  (b) a bare list of competitor records near the point — then
      competition_pressure is derived from the count (min(10, n)) and the
      list is passed through as extras["competitors"]. provider_gap is never
      fabricated — it needs a demand estimate and only comes from the feed.
Confirm the mapping live with scripts/places_probe.py before trusting it.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable

_UA = "landvex-opportunity-engine/places"
SIGNALS = ("competition_pressure", "provider_gap")


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class PlacesClient:
    """Client for a live places / competition source. Not connected until
    LANDVEX_PLACES_URL is set — reported honestly, never faked."""

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 6.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_PLACES_URL", ""))
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def fetch_places(self, lat: float, lon: float,
                     vertical_id: str) -> tuple[dict[str, float], list]:
        """Return (signals, competitors). Signals holds any of
        competition_pressure / provider_gap the feed provides; competitors is
        the raw list (for extras). Empty if not connected; raises on transport
        error (PlacesSource catches and pauses)."""
        if not self.connected:
            return {}, []
        url = (f"{self.base_url}{'&' if '?' in self.base_url else '?'}"
               f"lat={lat}&lon={lon}&vertical={vertical_id}")
        data = json.loads(self._transport(url, self.timeout))
        out: dict[str, float] = {}
        competitors: list = []
        if isinstance(data, dict):
            for s in SIGNALS:
                if isinstance(data.get(s), (int, float)):
                    out[s] = float(data[s])
            comp = data.get("competitors")
            if isinstance(comp, list):
                competitors = comp
                if "competition_pressure" not in out:
                    out["competition_pressure"] = float(min(10, len(comp)))
        elif isinstance(data, list):
            competitors = data
            out["competition_pressure"] = float(min(10, len(data)))
        return out, competitors

    def status(self) -> dict[str, Any]:
        if not self.connected:
            return {"source": "places", "status": "ej_ansluten",
                    "notis_en": "Set LANDVEX_PLACES_URL to connect a places / "
                                "competition source (Google Places, "
                                "Bolagsverket, review data, or an aggregator)."}
        return {"source": "places", "status": "ok",
                "notis_en": "Connected to a places / competition source."}
