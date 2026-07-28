"""Beställning av fältuppdrag — eller ett tydligt nej.

`engine/datasources/quixzoom_direct.py` LÄSER uppdrag. Ingenting i
plattformen har kunnat beställa ett, och det är den saknade länken som
gör paketeringen `per_mission` i `engine/commercial.py` märkt NOT
DELIVERABLE — och som gör att löftet om leverans inom 24–72 timmar inte
har någon motsvarighet i koden.

**quiXzoom:s beställnings-API-kontrakt är inte bekräftat härifrån.**
Nätet är policyspärrat i byggmiljön, och ingen har skickat oss ett
exempelsvar. Klienten byggs därför som de andra i det här projektet:

  * transporten är injicerbar, så den går att testa mot en fixtur,
  * `verified_live = False` tills en probe fått ett svar från riktig
    värd,
  * och den **VÄGRAR** när `LANDVEX_QUIXZOOM_URL` saknas i stället för
    att returnera ett påhittat uppdrags-id.

Det sista är hela poängen. Ett låtsat uppdrags-id ser ut som en beställd
kontroll ända fram till dagen någon frågar varför ingen varit på plats —
och då står det i registret att kontrollen är beställd.

Formen nedan (`asset`, `checks`, `due_at`, `radius_m`) är vad Landvex
behöver kunna säga. Stämmer den inte med quiXzoom:s faktiska API är det
en översättning i `_kropp()`, inte en omskrivning av modulen.

Rent stdlib.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from engine.datasources.faults import OUR_BUGS, unreachable


class DispatchRefused(RuntimeError):
    """Beställningen gick inte att göra, och varför."""


def _http(url: str, payload: bytes, headers: dict, timeout: float) -> bytes:
    r = urllib.request.Request(url, data=payload, headers=headers,
                               method="POST")
    op = urllib.request.build_opener()
    with op.open(r, timeout=timeout) as svar:
        return svar.read()


class MissionDispatcher:
    """Beställer en kontroll av ett objekt hos quiXzoom."""

    id = "quixzoom_dispatch"
    verified_live = False        # ingen probe har fått svar härifrån

    def __init__(self, base_url: str | None = None,
                 transport: Callable[..., bytes] | None = None,
                 timeout: float = 10.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_QUIXZOOM_URL", ""))
        self.path = os.environ.get("LANDVEX_QUIXZOOM_MISSION_PATH",
                                   "/api/missions")
        self.key = os.environ.get("LANDVEX_QUIXZOOM_KEY", "")
        self._transport = transport or _http
        self.timeout = timeout
        self.last_error: BaseException | None = None

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def _kropp(self, asset: dict, rut: dict, due_at: str,
               radius_m: int) -> dict:
        """Vad Landvex behöver säga. Översätts här om quiXzoom vill ha
        det annorlunda — resten av modulen berörs inte."""
        return {
            "title": f"{rut.get('label_en') or 'Inspection'}: "
                     f"{asset.get('label_en') or asset['id']}",
            "location": {"lat": asset.get("lat"), "lng": asset.get("lon")},
            "address": asset.get("address", ""),
            "radius_m": radius_m,
            "due_at": due_at,
            "required_media": ["photo"],
            "checklist": list(rut.get("checks", ())),
            "reference": {"asset_id": asset["id"],
                          "routine_id": rut["id"]},
        }

    def dispatch(self, asset: dict, rut: dict, due_at: str, *,
                 radius_m: int = 50) -> dict:
        """Beställ ETT uppdrag. Höjer DispatchRefused i stället för att
        hitta på ett id."""
        if not self.connected:
            raise DispatchRefused(
                "LANDVEX_QUIXZOOM_URL is not set, so no mission was "
                "ordered and no mission id exists. Nothing was invented: "
                "a fabricated id looks like an ordered check right up to "
                "the day someone asks why nobody came.")
        if asset.get("lat") is None or asset.get("lon") is None:
            raise DispatchRefused(
                f"asset {asset.get('id')!r} has no coordinates — a field "
                f"contributor cannot be sent to an object without a place")

        url = self.base_url.rstrip("/") + self.path
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["X-API-Key"] = self.key
        payload = json.dumps(self._kropp(asset, rut, due_at, radius_m),
                             ensure_ascii=False).encode()
        try:
            rå = self._transport(url, payload, headers, self.timeout)
        except OUR_BUGS:
            raise                     # vårt fel, inte omvärldens
        except Exception as e:        # noqa: BLE001
            self.last_error = e
            if unreachable(e):
                raise DispatchRefused(
                    f"never got there: {type(e).__name__}: {e}. The "
                    f"network stopped the call — this says nothing about "
                    f"quiXzoom or about the asset.") from e
            raise DispatchRefused(
                f"quiXzoom refused the order: {type(e).__name__}: {e}"
            ) from e

        self.last_error = None
        try:
            svar: Any = json.loads(rå)
        except json.JSONDecodeError as e:
            raise DispatchRefused(
                "quiXzoom answered with something that is not JSON — the "
                "order may or may not have been placed, and this side "
                "will not guess which") from e
        mid = svar.get("id") or svar.get("mission_id")
        if not mid:
            raise DispatchRefused(
                f"quiXzoom answered without a mission id ({sorted(svar)}) "
                f"— without one the check cannot be tied to its evidence")
        return {"mission_id": str(mid), "ordered_at": svar.get("created_at",
                                                              ""),
                "asset_id": asset["id"], "routine_id": rut["id"],
                "due_at": due_at, "source": "quixzoom",
                "raw_status": svar.get("status", "")}


def status() -> dict:
    d = MissionDispatcher()
    return {
        "id": d.id, "connected": d.connected,
        "verified_live": d.verified_live,
        "base_url_set": bool(d.base_url),
        "note_en": (
            "Ordering is built but never confirmed against a live "
            "quiXzoom endpoint from this environment — outbound network "
            "is policy-blocked here. Run it where the network is open "
            "before trusting the payload shape; the body is assembled in "
            "MissionDispatcher._kropp and is the only thing that changes "
            "if quiXzoom expects a different envelope."),
    }


def dispatch_due(tenant: str, today: object = "",
                 dispatcher: MissionDispatcher | None = None) -> dict:
    """Beställ uppdrag för allt som förfaller hos EN kund.

    Vägran per objekt räknas som vägran, inte som fel: att en beställning
    inte gick att göra är ett svar, och det ska stå vilket objekt det
    gällde och varför.
    """
    from engine import inspections as I

    d = dispatcher or MissionDispatcher()
    rutiner = {r["id"]: r for r in I.all_routines(tenant)}
    bestallda, vagrade = [], []
    for rad in I.due_now(tenant, today)["due"]:
        rut = rutiner.get(rad.get("routine_id"))
        if rut is None:
            vagrade.append({"asset_id": rad["asset"]["id"],
                            "why_en": "no routine covers this object"})
            continue
        try:
            bestallda.append(d.dispatch(rad["asset"], rut, rad["next_due"]))
        except DispatchRefused as e:
            vagrade.append({"asset_id": rad["asset"]["id"],
                            "why_en": str(e)})
    return {
        "ordered": bestallda, "refused": vagrade,
        "ordered_count": len(bestallda), "refused_count": len(vagrade),
        "connected": d.connected,
        "note_en": ("Refusals are answers, not errors. Each one names the "
                    "object and the reason — a run that ordered nothing "
                    "because the endpoint is unset looks exactly like a "
                    "run with nothing due, unless it says so."),
    }
