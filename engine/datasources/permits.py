"""Building-permits / detail-plans adapter.

Feeds the "official planned" development signals — `building_permits`,
`detail_plans`, `permitted_m2` — from a municipal / national open-data
source (e.g. municipal open data, Boverket, Kolada, or a small aggregator
the dev team stands up). These drive market momentum, the 2-year demand
outlook, project risk, the "public pipeline" hidden opportunity, and the
planned side of the Contradiction Index (planned vs observed — the observed
side is quiXzoom field observations).

Same contract as the SCB / quiXzoom / programs adapters:
  * stdlib only (urllib, json); belongs to engine/, runs in Lambda.
  * injectable transport → deterministic fixture tests, no network.
  * NOT connected until LANDVEX_PERMITS_URL is set → the Resolver falls
    through to mock honestly; a source error pauses the source, never
    breaks a response.

Contract (what LANDVEX_PERMITS_URL must return for ?lat=&lon=): JSON, either
  (a) an object with any of {building_permits, detail_plans, permitted_m2}
      as numbers for the point/area, or
  (b) a list of permit records near the point — then building_permits is the
      count and permitted_m2 the summed area if records carry "area_m2".
Never fabricates a field the feed doesn't provide. Confirm the mapping live
with scripts/permits_probe.py before trusting it.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable

_UA = "landvex-opportunity-engine/permits"
SIGNALS = ("building_permits", "detail_plans", "permitted_m2")


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class PermitsClient:
    """Client for a live permits / detail-plans source. Not connected until
    LANDVEX_PERMITS_URL is set — reported honestly, never faked."""

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 2.5):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_PERMITS_URL", ""))
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def fetch_permits(self, lat: float, lon: float) -> dict[str, float]:
        """Return any of the three signals the feed provides for the point.
        Empty dict if not connected; raises on transport error (the caller —
        PermitsSource — catches and pauses)."""
        if not self.connected:
            return {}
        url = (f"{self.base_url}{'&' if '?' in self.base_url else '?'}"
               f"lat={lat}&lon={lon}")
        data = json.loads(self._transport(url, self.timeout))
        out: dict[str, float] = {}
        if isinstance(data, dict):
            for s in SIGNALS:
                if isinstance(data.get(s), (int, float)):
                    out[s] = float(data[s])
        elif isinstance(data, list):
            out["building_permits"] = float(len(data))
            areas = [r.get("area_m2") for r in data if isinstance(r, dict)]
            areas = [a for a in areas if isinstance(a, (int, float))]
            if areas:
                # PERMITTED, inte observerat byggt. Fältet hette
                # development_m2, vilket är kontradiktionsindexets
                # OBSERVERADE sida — så med bygglovskällan inkopplad
                # jämförde indexet bygglov mot bygglov och kunde
                # strukturellt inte hitta en motsägelse. quiXzoom-
                # adaptern vägrar uttryckligen fylla development_m2
                # ("vi hittar aldrig på siffran"); den här fyllde det
                # tyst från pappersarbetet.
                out["permitted_m2"] = float(sum(areas)) / 1000.0   # → 1000 m²
        return out

    def status(self) -> dict[str, Any]:
        if not self.connected:
            return {"source": "permits", "status": "ej_ansluten",
                    "notis_en": "Set LANDVEX_PERMITS_URL to connect a permits / "
                                "detail-plans source (municipal open data, "
                                "Boverket, Kolada, or an aggregator)."}
        return {"source": "permits", "status": "ok",
                "notis_en": "Connected to a permits / detail-plans source."}
