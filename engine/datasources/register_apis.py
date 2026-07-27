"""Riktiga registerklienter – ett protokoll per myndighet, inte en shim.

Att "koppla registret" betyder inte en generisk `{base}/establishments`.
Varje statistikmyndighet har sitt eget API, sitt eget frågeformat och sitt
eget svarsformat. Det här lagret talar dem på riktigt:

  PxWeb        SCB (SE), SSB (NO), Statistikbanken (DK), StatFin (FI).
               Nordiska myndigheter delar samma PxWeb-motor, så EN
               implementation täcker fyra länder: POST med en query-lista,
               svar i JSON-stat2.
  Census CBP   USA. GET mot api.census.gov med NAICS-kod och FIPS-geografi;
               svaret är en matris där rad 0 är kolumnrubriker.
  Eurostat     EU-brett fallback via NACE + NUTS-region, JSON-stat.
  Generic      Den enkla {base}/establishments-formen (egen spegel/proxy).

ÄRLIGHET OM VERIFIERING: tabell-/dataset-id:n nedan är de dokumenterade
sökvägarna, men de är INTE live-verifierade i utvecklingsmiljön – utgående
nätverk är spärrat här. Varje provider bär därför `verified=False` tills
`scripts/register_probe.py` körts mot det riktiga API:t i en miljö med
nätverk. Parsningen är däremot testad mot fixturer i varje API:s FAKTISKA
svarsformat, så det som återstår är att bekräfta sökvägen – inte koden.

Rent stdlib, injicerbar transport.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Callable
from .faults import OUR_BUGS

_UA = "landvex-opportunity-engine/registers"


def _http(url: str, payload: bytes | None, timeout: float) -> bytes:
    headers = {"Accept": "application/json", "User-Agent": _UA}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


class RegisterProvider:
    """Gemensamt gränssnitt: (land, region, näringsgrenskod) → antal.

    Bär samma strömbrytare som datakälls-adaptrarna (`_down_until` i
    adapters.py). Utan den blir EN otillgänglig myndighet till ETT
    misslyckat anrop PER REGION i samma request: en mättnadsjämförelse
    över 60 kommuner gjorde 60 blockerande HTTPS-anrop à ~0,3 s och tog
    19 sekunder att svara "vet inte" — 94 % av hela demons körtid, och
    exakt den väntan plattformens egen prestandadoktrin förbjuder.

    Ett misslyckande räcker som besked. Resten av regionerna degraderar
    omedelbart och lika ärligt.
    """

    id = "generic"
    verified = False

    def __init__(self, transport: Callable[[str, bytes | None, float], bytes] | None = None,
                 timeout: float = 10.0, retry_after_s: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):
        self._transport = transport or _http
        self.timeout = timeout
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._down_until = 0.0
        # Felet från det SENASTE misslyckade anropet. Utan det går det
        # inte att skilja "kom aldrig fram" från "svarade konstigt", och
        # då blir en spärrad brandvägg nedskriven som en trasig adapter.
        # `Breaker` i faults.py bär samma fält av samma skäl.
        self.last_error: BaseException | None = None

    # ── Strömbrytare ─────────────────────────────────────────────────
    @property
    def down(self) -> bool:
        """Sant medan källan är pausad efter ett misslyckande."""
        return self._clock() < self._down_until

    def _trip(self) -> None:
        self._down_until = self._clock() + self._retry_after_s

    def _reset(self) -> None:
        self._down_until = 0.0

    def fetch(self, url: str, payload: bytes | None = None) -> bytes | None:
        """Hämta genom strömbrytaren. None = källan är nere eller pausad."""
        if self.down:
            return None
        try:
            raw = self._transport(url, payload, self.timeout)
        except OUR_BUGS:
            raise            # vårt fel, inte omvärldens – se faults.py
        except Exception as e:   # noqa: BLE001 – ärlig degradering
            self.last_error = e
            self._trip()
            return None
        self.last_error = None
        self._reset()
        return raw

    def count(self, country: str, region: str, code: str) -> dict | None:
        raise NotImplementedError

    def describe(self) -> dict:
        return {"provider": self.id, "verified": self.verified}


# ── PxWeb: SE / NO / DK / FI ────────────────────────────────────────────
# Arbetsställen efter näringsgren och kommun. Sökvägarna är de dokumenterade
# tabellerna; de bekräftas av proben innan de får kallas verifierade.
PXWEB_TABLES: dict[str, dict] = {
    "se": {"base": os.environ.get("LANDVEX_SCB_BASE",
                                  "https://api.scb.se/OV0104/v1/doris/en/ssd"),
           "table": os.environ.get("LANDVEX_SCB_ESTAB_TABLE",
                                   "NV/NV0101/FDBR07"),
           "region_var": "Region", "industry_var": "SNI2007",
           "authority": "Statistics Sweden (SCB)"},
    "no": {"base": os.environ.get("LANDVEX_SSB_BASE",
                                  "https://data.ssb.no/api/v0/en/table"),
           "table": os.environ.get("LANDVEX_SSB_ESTAB_TABLE", "07091"),
           "region_var": "Region", "industry_var": "NACE2007",
           "authority": "Statistics Norway (SSB)"},
    "dk": {"base": os.environ.get("LANDVEX_DST_BASE",
                                  "https://api.statbank.dk/v1"),
           "table": os.environ.get("LANDVEX_DST_ESTAB_TABLE", "GEO2"),
           "region_var": "OMRÅDE", "industry_var": "BRANCHE07",
           "authority": "Statistics Denmark"},
    "fi": {"base": os.environ.get("LANDVEX_STATFIN_BASE",
                                  "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin"),
           "table": os.environ.get("LANDVEX_STATFIN_ESTAB_TABLE",
                                   "yrti/statfin_yrti_pxt_11yq.px"),
           "region_var": "Alue", "industry_var": "Toimiala",
           "authority": "Statistics Finland"},
}


class PxWebRegister(RegisterProvider):
    """POST en query-lista, läs JSON-stat2. Delas av de nordiska byråerna."""

    id = "pxweb"

    def count(self, country: str, region: str, code: str) -> dict | None:
        spec = PXWEB_TABLES.get(country)
        if spec is None:
            return None
        url = f"{spec['base'].rstrip('/')}/{spec['table']}"
        query = {
            "query": [
                {"code": spec["region_var"],
                 "selection": {"filter": "item", "values": [region]}},
                {"code": spec["industry_var"],
                 "selection": {"filter": "item", "values": [_nace_px(code)]}},
            ],
            "response": {"format": "json-stat2"},
        }
        body = self.fetch(url, json.dumps(query).encode())
        if body is None:
            return None          # nere eller pausad – aldrig ett påhittat tal
        try:
            raw = json.loads(body.decode("utf-8"))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001 – svaret gick inte att tolka
            return None
        return _parse_jsonstat(raw, spec["authority"], self.id)


def _nace_px(code: str) -> str:
    """PxWeb-tabellerna kodar NACE utan punkt ("43.21" → "4321")."""
    return code.replace(".", "")


def _parse_jsonstat(raw: dict, authority: str, provider: str) -> dict | None:
    """JSON-stat2: value är en lista eller ett glest dict. Ta första talet."""
    if not isinstance(raw, dict):
        return None
    val = raw.get("value")
    n = None
    if isinstance(val, list):
        nums = [v for v in val if isinstance(v, (int, float))]
        n = nums[0] if nums else None
    elif isinstance(val, dict):
        nums = [v for v in val.values() if isinstance(v, (int, float))]
        n = nums[0] if nums else None
    if n is None:
        return None
    year = None
    dim = raw.get("dimension") or {}
    for key in ("Tid", "Time", "time", "Vuosi", "TID"):
        cat = ((dim.get(key) or {}).get("category") or {}).get("index") or {}
        if cat:
            year = sorted(cat, key=lambda k: cat[k])[-1]
            break
    return {"count": int(n), "year": year, "source": authority,
            "provider": provider, "measured": True}


# ── US Census County Business Patterns ──────────────────────────────────
class CensusCbpRegister(RegisterProvider):
    """api.census.gov/data/{year}/cbp — ESTAB per NAICS och county.

    Svaret är en matris: rad 0 är kolumnrubriker, resten data.
    region = 5-siffrig FIPS (2 state + 3 county).
    """

    id = "census_cbp"

    def __init__(self, *a, year: str | None = None, api_key: str | None = None,
                 **kw):
        super().__init__(*a, **kw)
        self.base = os.environ.get("LANDVEX_CENSUS_BASE",
                                   "https://api.census.gov/data")
        self.year = year or os.environ.get("LANDVEX_CENSUS_YEAR", "2022")
        self.api_key = api_key if api_key is not None else os.environ.get(
            "LANDVEX_CENSUS_KEY", "")

    def count(self, country: str, region: str, code: str) -> dict | None:
        if country != "us" or len(region) < 5:
            return None
        state, county = region[:2], region[2:5]
        params = {"get": "ESTAB", "for": f"county:{county}",
                  "in": f"state:{state}", "NAICS2017": code}
        if self.api_key:
            params["key"] = self.api_key
        url = (f"{self.base}/{self.year}/cbp?"
               + urllib.parse.urlencode(params))
        body = self.fetch(url)
        if body is None:
            return None
        try:
            raw = json.loads(body.decode("utf-8"))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001
            return None
        if not (isinstance(raw, list) and len(raw) > 1):
            return None
        header, row = raw[0], raw[1]
        try:
            n = int(row[header.index("ESTAB")])
        except (ValueError, IndexError, TypeError):
            return None
        return {"count": n, "year": self.year,
                "source": "US Census Bureau, County Business Patterns",
                "provider": self.id, "measured": True}


# ── Eurostat (EU-brett fallback) ────────────────────────────────────────
class EurostatRegister(RegisterProvider):
    """Eurostat dissemination API – NACE × NUTS-region, JSON-stat."""

    id = "eurostat"

    def __init__(self, *a, dataset: str | None = None, **kw):
        super().__init__(*a, **kw)
        self.base = os.environ.get(
            "LANDVEX_EUROSTAT_BASE",
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data")
        self.dataset = dataset or os.environ.get("LANDVEX_EUROSTAT_DATASET",
                                                 "sbs_r_nuts2021")

    def count(self, country: str, region: str, code: str) -> dict | None:
        params = {"format": "JSON", "lang": "EN",
                  "geo": region, "nace_r2": _nace_eurostat(code),
                  "indic_sb": "V11910"}      # antal lokala enheter
        url = f"{self.base}/{self.dataset}?" + urllib.parse.urlencode(params)
        body = self.fetch(url)
        if body is None:
            return None
        try:
            raw = json.loads(body.decode("utf-8"))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001
            return None
        return _parse_jsonstat(raw, "Eurostat", self.id)


def _nace_eurostat(code: str) -> str:
    """Eurostat kodar NACE som "F43" / "S96" på avdelningsnivå; behåll
    undergruppen när den finns ("43.21" → "C4321" är fel, "4321" rätt)."""
    return code.replace(".", "")


# ── Generisk spegel ─────────────────────────────────────────────────────
class GenericRegister(RegisterProvider):
    """{base}/establishments?country=&region=&code=&scheme= – egen proxy."""

    id = "generic"

    def __init__(self, *a, base_url: str | None = None, **kw):
        super().__init__(*a, **kw)
        self.base = (base_url if base_url is not None
                     else os.environ.get("LANDVEX_REGISTER_URL", "")).rstrip("/")

    def count(self, country: str, region: str, code: str) -> dict | None:
        if not self.base:
            return None
        url = (f"{self.base}/establishments?country={country}&region={region}"
               f"&code={urllib.parse.quote(code)}")
        body = self.fetch(url)
        if body is None:
            return None
        try:
            raw = json.loads(body.decode("utf-8"))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(raw, dict) or raw.get("count") is None:
            return None
        try:
            return {"count": int(raw["count"]), "year": raw.get("year"),
                    "source": raw.get("source") or "configured mirror",
                    "provider": self.id, "measured": True}
        except (TypeError, ValueError):
            return None


# ── Vilken provider gäller för vilket land ──────────────────────────────
PROVIDER_FOR: dict[str, str] = {
    "se": "pxweb", "no": "pxweb", "dk": "pxweb", "fi": "pxweb",
    "us": "census_cbp",
    # Övriga EU-länder når vi brett via Eurostat tills nationella
    # adaptrar (SIRENE, GENESIS, DIRCE, ISTAT …) byggs var för sig.
    "de": "eurostat", "fr": "eurostat", "es": "eurostat", "it": "eurostat",
    "nl": "eurostat", "pl": "eurostat", "be": "eurostat", "at": "eurostat",
    "pt": "eurostat", "ie": "eurostat", "cz": "eurostat",
}

_CLASSES = {"pxweb": PxWebRegister, "census_cbp": CensusCbpRegister,
            "eurostat": EurostatRegister, "generic": GenericRegister}


# Delade instanser per land. En strömbrytare som återskapas vid varje
# anrop är ingen strömbrytare: den glömmer att myndigheten var nere innan
# nästa region hinner fråga, och en jämförelse över 60 kommuner gör då 60
# misslyckade anrop i rad. Instanserna är statelösa utöver brytaren, och
# `fetch` tar samma lås-fria väg som datakälls-adaptrarna.
_SHARED: dict[str, RegisterProvider] = {}


def provider_for(country: str, **kw) -> RegisterProvider:
    """Rätt klient för landet; generisk spegel om landet saknar adapter.

    Utan `kw` returneras den DELADE instansen, så att en nere myndighet
    bara kostar ett misslyckat anrop per paus — inte ett per region.
    Anropare som skickar in egen transport eller klocka (tester, prober)
    får en egen instans och stör därmed ingen annan.
    """
    name = PROVIDER_FOR.get(country, "generic")
    cls = _CLASSES.get(name, GenericRegister)
    if kw:
        return cls(**kw)
    if name not in _SHARED:
        _SHARED[name] = cls()
    return _SHARED[name]


def reset_breakers() -> None:
    """Nollställ pausade leverantörer (tester och långkörande processer)."""
    for p in _SHARED.values():
        p._reset()


def providers_status() -> dict:
    """Vad som är byggt, vad som är verifierat, och hur det slås på."""
    return {
        "providers": [
            {"id": "pxweb", "countries": ["se", "no", "dk", "fi"],
             "protocol": "PxWeb JSON query -> JSON-stat2 (POST)",
             "authorities": [PXWEB_TABLES[c]["authority"] for c in
                             ("se", "no", "dk", "fi")],
             "verified_live": False},
            {"id": "census_cbp", "countries": ["us"],
             "protocol": "api.census.gov/data/{year}/cbp (GET, matrix)",
             "authorities": ["US Census Bureau"], "verified_live": False},
            {"id": "eurostat", "countries": sorted(
                c for c, p in PROVIDER_FOR.items() if p == "eurostat"),
             "protocol": "Eurostat dissemination API (GET, JSON-stat)",
             "authorities": ["Eurostat"], "verified_live": False},
            {"id": "generic", "countries": ["any"],
             "protocol": "{base}/establishments (own mirror/proxy)",
             "authorities": ["operator-provided"], "verified_live": False},
        ],
        "note_en": "Response parsing is tested against fixtures in each API's "
                   "real format. The table and dataset identifiers are the "
                   "documented ones but are NOT live-verified from this "
                   "environment (outbound network is blocked here) — run "
                   "scripts/register_probe.py where the network is open and "
                   "verified_live becomes meaningful.",
        "probe": "python3 -m scripts.register_probe <country> <region> <trade>",
    }
