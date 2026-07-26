"""SVK / ENTSO-E-adapter – elsystemets realtidsläge (dissg russin G).

De faktiska SVK/ENTSO-E-endpointsen + de härledda måtten (stabilitet,
balans) i samma kontrakt som övriga adaptrar: stdlib, injicerbar transport,
EJ ansluten förrän LANDVEX_SVK_URL sätts, ärlig degradering.

Härledda mått (dissg svk-ingest 289,321):
  stability_score = max(0, 100 − |freq − 50.0|·100)   # 0.01 Hz ≈ 1% tapp
  balance_mw      = production − consumption + import − export

ENTSO-E Sverige EIC 10YSE-1--------K; psrType B14 kärnkraft / B12 vatten /
B19 vind. Kräver ENTSOE_API_KEY vid live-anrop. Verifiera med
scripts/svk_probe.py.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable
from .faults import OUR_BUGS

_UA = "landvex-opportunity-engine/svk"
SWEDEN_EIC = "10YSE-1--------K"
PSR = {"B14": "nuclear", "B12": "hydro", "B19": "wind"}


def stability_score(freq_hz: float) -> float:
    """0–100. 50.00 Hz = 100; varje 0.01 Hz avvikelse ≈ 1% tapp."""
    return round(max(0.0, 100.0 - abs(float(freq_hz) - 50.0) * 100.0), 4)


def balance_mw(production: float, consumption: float,
               imp: float = 0.0, exp: float = 0.0) -> float:
    return round(production - consumption + imp - exp, 4)


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class SvkClient:
    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 6.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_SVK_URL", "")).rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def production_mix(self) -> dict[str, Any] | None:
        """Hämta produktionsmix + härledda mått. Returnerar
        {mix:{nuclear,hydro,wind,…}, production_mw, frequency_hz,
        stability_score, balance_mw} eller None (ärlig degradering)."""
        if not self.connected:
            return None
        try:
            raw = json.loads(self._transport(
                f"{self.base_url}/productionmix", self.timeout))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001
            return None
        return self.normalize(raw)

    @staticmethod
    def normalize(raw: dict) -> dict:
        mix = {}
        # Antingen {mix:{...}} eller {productionmix:[{psrType,quantity}]}
        if isinstance(raw.get("mix"), dict):
            mix = {k: float(v) for k, v in raw["mix"].items()}
        else:
            for row in raw.get("productionmix", []):
                name = PSR.get(row.get("psrType"), row.get("psrType", "other"))
                mix[name] = mix.get(name, 0.0) + float(row.get("quantity", 0))
        prod = float(raw.get("production_mw", sum(mix.values())))
        out: dict[str, Any] = {"mix": mix, "production_mw": round(prod, 2)}
        if "frequency_hz" in raw:
            f = float(raw["frequency_hz"])
            out["frequency_hz"] = f
            out["stability_score"] = stability_score(f)
        if "consumption_mw" in raw:
            out["balance_mw"] = balance_mw(
                prod, float(raw["consumption_mw"]),
                float(raw.get("import_mw", 0)), float(raw.get("export_mw", 0)))
        return out

    def status(self) -> dict:
        return {"name": "svk", "connected": self.connected,
                "base_url": self.base_url or None, "eic": SWEDEN_EIC,
                "provides": ["production_mix", "stability_score", "balance_mw"]}
