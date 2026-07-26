"""Kolada-adapter – kommunala/nationella nyckeltal (dissg russin G).

De faktiska, fungerande Kolada-KPI-id:na (dyra att återupptäcka) i samma
kontrakt som SCB-/permits-/places-adaptrarna:

  * stdlib only (urllib, json); hör till engine/, kör i Lambda.
  * injicerbar transport → deterministiska fixturtester, inget nät.
  * EJ ansluten förrän LANDVEX_KOLADA_URL sätts → anropare faller ärligt
    tillbaka; ett Kolada-fel bryter aldrig ett svar.
  * plockar totalvärdet (gender=="T"); hittar aldrig på ett värde.

Kontrakt: LANDVEX_KOLADA_URL pekar på Kolada v2-basen
(https://api.kolada.se/v2). Hämtning:
  {base}/data/kpi/{kolada_id}/municipality/{muni}/year/{y1,y2,…}
muni "0000" = nationellt. Verifiera live med scripts/kolada_probe.py.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable
from .faults import OUR_BUGS

_UA = "landvex-opportunity-engine/kolada"

# Landvex-KPI-kod → Kolada-id (bekräftade i skörden).
KPI_IDS: dict[str, str] = {
    "life_expectancy": "N00914",
    "excess_mortality": "N00401",
    "long_term_exclusion": "N31813",
    "violent_crime_rate": "N07403",
    "healthcare_queue_functional": "N20401",
    "school_outcomes_grade9": "N15428",
}


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class KoladaClient:
    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 6.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_KOLADA_URL", "")).rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def fetch_kpi(self, code: str, municipality: str = "0000",
                  years: tuple[int, ...] = ()) -> dict[str, Any] | None:
        """Hämta ett KPI för en kommun (eller nationellt). Returnerar
        {code, kolada_id, value, year, municipality} eller None."""
        kid = KPI_IDS.get(code)
        if not (self.connected and kid):
            return None
        y = (",".join(str(x) for x in years)) if years else ""
        url = (f"{self.base_url}/data/kpi/{kid}/municipality/{municipality}"
               + (f"/year/{y}" if y else ""))
        try:
            raw = json.loads(self._transport(url, self.timeout))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001 - ärlig degradering
            return None
        val = self._pick_total(raw)
        if val is None:
            return None
        return {"code": code, "kolada_id": kid, "value": val["value"],
                "year": val["year"], "municipality": municipality}

    @staticmethod
    def _pick_total(raw: dict) -> dict | None:
        for row in raw.get("values", []) if isinstance(raw, dict) else []:
            period = row.get("period")
            for v in row.get("values", []):
                if v.get("gender") == "T" and v.get("value") is not None:
                    return {"value": float(v["value"]), "year": period}
        return None

    def status(self) -> dict:
        return {"name": "kolada", "connected": self.connected,
                "base_url": self.base_url or None,
                "kpi_catalog": sorted(KPI_IDS)}
