"""Plattformshälsa – vad som är uppe, anslutet och pausat.

Delas av båda API-lagren. Källstatus läser Resolver-kedjans faktiska
tillstånd (felpausade adaptrar, ej anslutna stubbar) – systemets
"incident"-signal, exponerad i /health och /metrics.
"""
from __future__ import annotations

from typing import Any

from engine.datasources.adapters import _NotWiredSource
from engine.version import ENGINE_VERSION


def source_status(resolver) -> list[dict[str, Any]]:
    out = []
    for s in getattr(resolver, "sources", []):
        inner = getattr(s, "inner", s)          # CachedSource → inre källan
        name = getattr(inner, "name", "okand")
        if name == "mock":
            out.append({"source": "mock", "status": "ok",
                        "notis_sv": "Deterministisk fallback."})
            continue
        if isinstance(inner, _NotWiredSource):
            out.append({"source": name, "status": "ej_ansluten",
                        "notis_sv": "Adapterstub – väntar på datakälla."})
            continue
        down_until = getattr(inner, "_down_until", 0.0)
        clock = getattr(inner, "_clock", None)
        pausad = bool(down_until and clock and clock() < down_until)
        out.append({"source": name,
                    "status": "pausad" if pausad else "ok",
                    "notis_sv": ("Felpaus efter källfel – mock tar över, "
                                 "återförsök sker automatiskt." if pausad
                                 else "Ansluten.")})
    return out


def build_health(resolver, store) -> dict[str, Any]:
    kallor = source_status(resolver)
    degraderad = any(k["status"] == "pausad" for k in kallor)
    return {"status": "degraderad" if degraderad else "ok",
            "engine_version": ENGINE_VERSION,
            "persistens": (type(store).__name__.replace("Store", "").lower()
                           if store is not None else "av"),
            "kallor": kallor}
