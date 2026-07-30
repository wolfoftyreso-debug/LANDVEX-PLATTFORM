"""Bostadsmarknad: pris per kvadratmeter mot vad beståndets standard
motiverar — och vad kommunen planerar för framtiden.

Samma gräns som `engine/land.py`, men den motsatta sidan av den:
land.py vägrar VISA ett pris eftersom ett tal format som ett pris
används som ett i en förhandling. Den här modulen visar ETT pris —
men bara det pris som kommer ur ett RIKTIGT transaktionsregister, ALDRIG
ett härlett belopp byggt av andra signaler. Skillnaden är inte
kosmetisk: land.py:s vägran gäller PÅHITTADE prislika tal; ett äkta,
källbelagt medianpris från en myndighet är motsatsen till det.

Tre delar:

    PRICE      pris/kvm ur ett officiellt transaktionsregister.
               Ansluts INTE ⇒ vägras med skäl, hittar aldrig på ett tal
               — exakt samma regel som `engine/registers.py`:s
               etableringsantal.
    STANDARD   ett relativt kvalitetsläge (0–100, samma bandmönster som
               land.py) byggt av EXISTERANDE signaler i katalogen
               (byggnadsålder, renoveringstakt, boendekostnad) —
               aldrig en valuta, precis som land.py.
    PLANS      kommunens översikts- och detaljplaner: vad som är
               planerat, inte vad som redan finns. Samma
               ej-ansluten-tills-URL-satt-regel som priset.

`price_vs_standard` kombinerar PRICE och STANDARD i EN enkel,
redovisad kvot (pris delat med standardpoäng) — aldrig ett påstått
"rättvist pris" eller en prognos. En kvot är matematik; en prognos är
ett påstående om framtiden ingen kalibrerat modell här kan bära.

Rent stdlib.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

from .datasources.base import Resolver
from .datasources.defaults import default_resolver
from .datasources.faults import OUR_BUGS
from .markets import DEFAULT_MARKET, get_market, get_region
from .models import Location
from .signals import CATALOG, normalize

# Samma tröskel och samma skäl som land.py: ett kvalitetsläge byggt på
# simulerade signaler är en gissning, och den här gissningen skulle
# ställas mot ett verkligt pris.
MIN_COVERAGE = 0.35

STANDARD_FAMILIES: tuple[dict, ...] = (
    {"id": "stock_condition", "weight": 0.6,
     "label_en": "Housing stock condition",
     "signals": (("avg_building_age", 0.5), ("renovation_index", 0.5)),
     "what_en": "How old the buildings are and how much renovation "
                "activity is keeping them current.",
     "cannot_en": "Age is not condition — a well-maintained old building "
                  "can outscore a neglected new one on the ground; this "
                  "only sees the register's numbers."},
    {"id": "cost_context", "weight": 0.4,
     "label_en": "Cost context",
     "signals": (("housing_affordability", 1.0),),
     "what_en": "How housing cost here compares to the rest of the "
                "market — context for the price, not a judgement of it.",
     "cannot_en": "Affordability is relative to the market's own spread, "
                  "not to what any specific household can pay."},
)


class HousingRefused(ValueError):
    """Beräkningen gick inte att göra, och varför."""


BANDS: tuple[tuple[float, str, str], ...] = (
    (80.0, "very_strong", "Very strong relative standard"),
    (65.0, "strong", "Strong relative standard"),
    (45.0, "average", "Around the market average"),
    (30.0, "weak", "Weak relative standard"),
    (0.0, "very_weak", "Very weak relative standard"),
)


def _band(v: float) -> tuple[str, str]:
    for grans, bid, label in BANDS:
        if v >= grans:
            return bid, label
    return BANDS[-1][1], BANDS[-1][2]


def _needed() -> list[str]:
    return sorted({sid for f in STANDARD_FAMILIES for sid, _ in f["signals"]})


def _family(fam: dict, values: dict) -> dict:
    num = den = 0.0
    drivare, saknade = [], []
    for sid, w in fam["signals"]:
        sv = values.get(sid)
        if sv is None or sv.value is None:
            saknade.append(sid)
            continue
        n = normalize(CATALOG[sid], sv.value) or 0.0
        num += w * n
        den += w
        drivare.append({"signal_id": sid, "label_en": CATALOG[sid].label_en,
                        "value": sv.value, "unit": CATALOG[sid].unit,
                        "kalla": sv.source, "normalised": round(n, 3)})
    akta = [d for d in drivare if d["kalla"] != "mock"]
    return {
        "id": fam["id"], "label_en": fam["label_en"], "weight": fam["weight"],
        "score": round(100 * num / den, 1) if den else None,
        "of_weight": round(den, 2), "drivers": drivare, "missing": saknade,
        "data_coverage": (round(len(akta) / len(drivare), 2)
                          if drivare else 0.0),
        "what_en": fam["what_en"], "cannot_en": fam["cannot_en"],
    }


def standard(region_code: str, market: str = DEFAULT_MARKET, *,
             resolver: Resolver | None = None) -> dict:
    """Relativt bostadsstandardläge (0–100) — eller en vägran.

    Aldrig en valuta, aldrig ett kvadratmeterpris — samma regel som
    land.py, av samma skäl.
    """
    mkt = get_market(market)
    kod, namn, lat, lon = get_region(market, region_code)
    res = resolver or default_resolver()
    values, _ = res.resolve(Location(lat, lon, address=namn),
                            "housing_standard", _needed())

    familjer = [_family(f, values) for f in STANDARD_FAMILIES]
    akta = sum(1 for v in values.values()
              if v.value is not None and v.source != "mock")
    totalt = sum(1 for v in values.values() if v.value is not None)
    tackning = round(akta / totalt, 2) if totalt else 0.0

    gemensamt = {
        "region": namn, "region_code": kod, "market": mkt.id,
        "market_label_en": mkt.label_en, "families": familjer,
        "data_coverage": tackning,
        "cannot_en": (
            "This is a relative STANDARD position, not a valuation and "
            "not a price. It carries no currency. It says only how this "
            "region's housing stock compares to others in the same "
            "market, on the drivers listed."),
    }
    if tackning < MIN_COVERAGE:
        return {
            **gemensamt, "status": "insufficient", "standard": None,
            "band": None, "band_en": None,
            "gate": {"required": MIN_COVERAGE, "measured": tackning},
            "refusal_en": (
                f"No standard position is computed for {namn}: "
                f"{round(tackning * 100)}% of the drivers rest on real "
                f"sources, below the {round(MIN_COVERAGE * 100)}% floor."),
            "how_to_fix_en": "Connect sources for this market (see /v1/coverage).",
        }
    raknade = [f for f in familjer if f["score"] is not None]
    vikt = sum(f["weight"] for f in raknade)
    lage = round(sum(f["score"] * f["weight"] for f in raknade) / vikt, 1)
    bid, blabel = _band(lage)
    return {
        **gemensamt, "status": "computed", "standard": lage,
        "band": bid, "band_en": blabel,
        "families_refused": [f["id"] for f in familjer if f["score"] is None],
        "summary_en": (f"{namn}: {blabel.lower()} ({lage}/100) housing "
                       f"standard relative to {mkt.label_en}'s other "
                       f"regions, on {round(tackning * 100)}% real data."),
    }


# ── Priset: bara riktigt, aldrig härlett ────────────────────────────────
def _live_enabled() -> bool:
    return os.environ.get("LANDVEX_LIVE", "1") != "0"


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "landvex/housing_market"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class HousingPriceClient:
    """Klient mot ett officiellt transaktionsregister (eller en spegel).

    Kontrakt: LANDVEX_HOUSING_PRICE_URL svarar på
        {base}/price-per-sqm?market=&region=
    med {"price_per_sqm": <number>, "currency": "<ISO4217>",
         "year": <int>, "source": "<register>", "sample_size": <int>}.
    Ej ansluten eller fel ⇒ None. Ett pris hittas ALDRIG på — se
    modulens doktrin överst.
    """

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 8.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_HOUSING_PRICE_URL", "")
                         ).rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def price_per_sqm(self, market: str, region_code: str) -> dict | None:
        if not self.connected or not _live_enabled():
            return None
        url = f"{self.base_url}/price-per-sqm?market={market}&region={region_code}"
        try:
            raw = json.loads(self._transport(url, self.timeout))
        except OUR_BUGS:
            raise
        except Exception:  # noqa: BLE001 — ärlig degradering, se registers.py
            return None
        if not isinstance(raw, dict) or raw.get("price_per_sqm") is None:
            return None
        try:
            pris = float(raw["price_per_sqm"])
        except (TypeError, ValueError):
            return None
        return {"price_per_sqm": pris,
                "currency": raw.get("currency", ""),
                "year": raw.get("year"),
                "source": raw.get("source", "official register"),
                "sample_size": raw.get("sample_size")}


def price(market: str, region_code: str, *,
          client: HousingPriceClient | None = None) -> dict:
    """Pris per kvadratmeter — `measured=True` bara ur ett riktigt
    register, precis som `engine/saturation.py`:s etableringsantal."""
    mkt = get_market(market)
    kod, namn, _, _ = get_region(market, region_code)
    c = client or HousingPriceClient()
    got = c.price_per_sqm(market, region_code)
    if got is None:
        return {
            "region": namn, "region_code": kod, "market": mkt.id,
            "price_per_sqm": None, "measured": False, "source": None,
            "why_en": (
                "LANDVEX_HOUSING_PRICE_URL is not connected, so no price "
                "is shown — a price this platform made up would be used "
                "in a negotiation. Connect an official transaction "
                "register to see this."),
        }
    return {"region": namn, "region_code": kod, "market": mkt.id,
            "price_per_sqm": got["price_per_sqm"], "measured": True,
            "currency": got["currency"], "year": got["year"],
            "source": got["source"], "sample_size": got["sample_size"],
            "why_en": f"From {got['source']}" +
                     (f", {got['year']}" if got["year"] else "") + "."}


def price_vs_standard(market: str, region_code: str, *,
                      client: HousingPriceClient | None = None,
                      resolver: Resolver | None = None) -> dict:
    """Priset delat med standardpoängen — en KVOT, aldrig ett påstått
    rättvist pris eller en prognos. Vägrar om endera sidan saknas."""
    p = price(market, region_code, client=client)
    s = standard(region_code, market, resolver=resolver)
    gemensamt = {"region": p["region"], "region_code": p["region_code"],
                "market": p["market"], "price": p, "standard": s}
    if not p["measured"]:
        return {**gemensamt, "status": "refused",
                "refusal_en": ("No price is connected for this region — "
                              "see price.why_en. A ratio needs both "
                              "sides."), "ratio": None}
    if s["status"] != "computed":
        return {**gemensamt, "status": "refused",
                "refusal_en": ("The housing-standard side has too little "
                              "real data — see standard.refusal_en. A "
                              "ratio needs both sides."), "ratio": None}
    ratio = round(p["price_per_sqm"] / s["standard"], 2)
    return {
        **gemensamt, "status": "computed", "ratio": ratio,
        "unit_en": f"{p.get('currency', '')}/m² per standard-point",
        "cannot_en": (
            "This is a simple division — price per m² divided by the "
            "standard score — not a predicted 'fair price', not a "
            "valuation, and not a forecast. No model here is calibrated "
            "to say what a price SHOULD be; this only says what it IS, "
            "per point of measured standard."),
    }


# ── Planerna: vad kommunen avser, inte vad som redan finns ─────────────
class MasterPlanClient:
    """Klient mot kommunens plan-API (översikts- och detaljplaner).

    Kontrakt: LANDVEX_MASTER_PLAN_URL svarar på
        {base}/plans?market=&region=
    med {"plans": [{"title", "kind", "adopted_year", "horizon_year",
                    "status", "summary_en"}]}.
    Ej ansluten ⇒ tom lista med skäl, aldrig påhittade planer.
    """

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 8.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_MASTER_PLAN_URL", "")
                         ).rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def plans_for(self, market: str, region_code: str) -> list[dict] | None:
        if not self.connected or not _live_enabled():
            return None
        url = f"{self.base_url}/plans?market={market}&region={region_code}"
        try:
            raw = json.loads(self._transport(url, self.timeout))
        except OUR_BUGS:
            raise
        except Exception:  # noqa: BLE001 — ärlig degradering
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("plans"), list):
            return None
        return raw["plans"]


def master_plans(market: str, region_code: str, *,
                 client: MasterPlanClient | None = None) -> dict:
    mkt = get_market(market)
    kod, namn, _, _ = get_region(market, region_code)
    c = client or MasterPlanClient()
    got = c.plans_for(market, region_code)
    if got is None:
        return {
            "region": namn, "region_code": kod, "market": mkt.id,
            "plans": [], "connected": False,
            "why_en": (
                "LANDVEX_MASTER_PLAN_URL is not connected, so no planning "
                "documents are shown — an empty list here means 'not "
                "connected', never 'nothing planned'. Connect the "
                "municipality's planning register to see this."),
        }
    return {"region": namn, "region_code": kod, "market": mkt.id,
            "plans": got, "connected": True,
            "why_en": f"{len(got)} planning document(s) from the "
                     f"connected register."}


def catalog() -> dict:
    return {
        "what_en": ("Housing price per m² from an official transaction "
                    "register, measured against a relative housing-"
                    "standard position, plus the municipality's own "
                    "planning documents for what comes next."),
        "standard_families": [
            {k: v for k, v in f.items() if k != "signals"}
            | {"signals": [s for s, _ in f["signals"]]}
            for f in STANDARD_FAMILIES],
        "coverage_floor": MIN_COVERAGE,
        "bands": [{"at_least": g, "band": b, "label_en": lbl}
                  for g, b, lbl in BANDS],
        "activate_price_with": "LANDVEX_HOUSING_PRICE_URL",
        "activate_plans_with": "LANDVEX_MASTER_PLAN_URL",
        "cannot_en": (
            "The price is never estimated — it is shown only when a real "
            "transaction register answers, exactly like the establishment "
            "counts in /v1/registers. The standard score carries no "
            "currency, exactly like /v1/land. The ratio between them is "
            "arithmetic, never a valuation or a forecast."),
    }
