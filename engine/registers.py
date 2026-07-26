"""Företagsregister – de officiella källorna till hur många som faktiskt
bedriver en viss verksamhet på en viss plats.

Frågan "hur mättad är marknaden för elektriker i Tyresö?" kan bara besvaras
på riktigt av ett REGISTER: antalet verksamma arbetsställen i branschen,
i kommunen, från myndighetens egen förteckning. Allt annat är gissning.

Det här lagret är kartan över de registren för EU och USA – vem som för
dem, vilken näringsgrensindelning de använder (NACE i EU, NAICS i USA),
vilken geografisk finkornighet de går ner i, och hur de aktiveras. Ingen
registerdata bärs inline; klienten är config-aktiverad (`LANDVEX_REGISTER_URL`)
med injicerbar transport, precis som SCB-/Kolada-adaptrarna, och degraderar
ärligt när den inte är ansluten.

Näringsgrensindelningen är själva nyckeln: NACE rev. 2 gäller i hela EU
(SNI i Sverige och WZ i Tyskland är nationella utgåvor av samma kodverk),
medan USA använder NAICS. `industry_code(vertical, country)` översätter en
Landvex-bransch till rätt kod i rätt system, så samma fråga kan ställas mot
ett svenskt och ett amerikanskt register utan att koden vet skillnaden.

Rent stdlib.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

# ── Officiella register per land ────────────────────────────────────────
# granularity = finaste geografiska nivå registret publicerar på.
REGISTERS: dict[str, dict] = {
    # EU – NACE rev. 2 (nationella utgåvor)
    "se": {"name": "SCB Företagsregister (Bolagsverket as source of record)",
           "authority": "Statistics Sweden / Bolagsverket",
           "classification": "SNI 2007 (NACE rev. 2)",
           "granularity": "municipality (kommun)", "unit": "workplace",
           "open_data": True},
    "de": {"name": "Unternehmensregister / Handelsregister",
           "authority": "Destatis / Amtsgerichte",
           "classification": "WZ 2008 (NACE rev. 2)",
           "granularity": "Kreis (district)", "unit": "establishment",
           "open_data": True},
    "fr": {"name": "SIRENE",
           "authority": "INSEE",
           "classification": "NAF rev. 2 (NACE rev. 2)",
           "granularity": "commune", "unit": "établissement",
           "open_data": True},
    "es": {"name": "DIRCE (Directorio Central de Empresas)",
           "authority": "INE", "classification": "CNAE-2009 (NACE rev. 2)",
           "granularity": "municipio", "unit": "local", "open_data": True},
    "it": {"name": "Registro Imprese / ASIA",
           "authority": "InfoCamere / ISTAT",
           "classification": "ATECO 2007 (NACE rev. 2)",
           "granularity": "comune", "unit": "unità locale", "open_data": True},
    "nl": {"name": "Handelsregister (KVK)", "authority": "Kamer van Koophandel",
           "classification": "SBI 2008 (NACE rev. 2)",
           "granularity": "gemeente", "unit": "vestiging", "open_data": False},
    "dk": {"name": "CVR (Det Centrale Virksomhedsregister)",
           "authority": "Erhvervsstyrelsen",
           "classification": "DB07 (NACE rev. 2)",
           "granularity": "kommune", "unit": "produktionsenhed",
           "open_data": True},
    "no": {"name": "Enhetsregisteret", "authority": "Brønnøysundregistrene",
           "classification": "SN2007 (NACE rev. 2)",
           "granularity": "kommune", "unit": "underenhet", "open_data": True},
    "fi": {"name": "YTJ / Business Information System",
           "authority": "PRH & Vero", "classification": "TOL 2008 (NACE rev. 2)",
           "granularity": "kunta", "unit": "toimipaikka", "open_data": True},
    "pl": {"name": "REGON", "authority": "GUS",
           "classification": "PKD 2007 (NACE rev. 2)",
           "granularity": "gmina", "unit": "jednostka lokalna",
           "open_data": True},
    "be": {"name": "Kruispuntbank van Ondernemingen (KBO/BCE)",
           "authority": "FOD Economie",
           "classification": "NACE-BEL 2008",
           "granularity": "gemeente/commune", "unit": "vestigingseenheid",
           "open_data": True},
    "at": {"name": "Firmenbuch / Unternehmensregister",
           "authority": "Statistik Austria",
           "classification": "ÖNACE 2008 (NACE rev. 2)",
           "granularity": "Gemeinde", "unit": "Arbeitsstätte",
           "open_data": False},
    "pt": {"name": "Ficheiro de Unidades Estatísticas", "authority": "INE",
           "classification": "CAE rev. 3 (NACE rev. 2)",
           "granularity": "município", "unit": "estabelecimento",
           "open_data": True},
    "ie": {"name": "CRO Register", "authority": "Companies Registration Office",
           "classification": "NACE rev. 2",
           "granularity": "county", "unit": "establishment", "open_data": True},
    "cz": {"name": "Registr ekonomických subjektů (RES)",
           "authority": "ČSÚ", "classification": "CZ-NACE",
           "granularity": "obec", "unit": "provozovna", "open_data": True},
    # USA – NAICS
    "us": {"name": "County Business Patterns (CBP) + QCEW",
           "authority": "US Census Bureau / Bureau of Labor Statistics",
           "classification": "NAICS 2022",
           "granularity": "county (and ZIP via ZBP)", "unit": "establishment",
           "open_data": True},
    "ca": {"name": "Canadian Business Counts",
           "authority": "Statistics Canada",
           "classification": "NAICS Canada 2022",
           "granularity": "census subdivision", "unit": "establishment",
           "open_data": True},
}

# ── Bransch → näringsgrenskod ───────────────────────────────────────────
# NACE rev. 2 gäller alla EU-utgåvor (SNI/WZ/NAF/CNAE/ATECO är samma träd);
# NAICS för US/CA. Koderna är på den nivå registren faktiskt publicerar.
INDUSTRY_CODES: dict[str, dict[str, str]] = {
    "elektriker":        {"nace": "43.21", "naics": "238210"},
    "vvs":               {"nace": "43.22", "naics": "238220"},
    "malare":            {"nace": "43.34", "naics": "238320"},
    "bygg":              {"nace": "41.20", "naics": "236200"},
    "taklaggare":        {"nace": "43.91", "naics": "238160"},
    "glasmasteri":       {"nace": "43.34", "naics": "238150"},
    "solceller":         {"nace": "43.21", "naics": "238220"},
    "frisor":            {"nace": "96.02", "naics": "812112"},
    "hudvard":           {"nace": "96.02", "naics": "812112"},
    "restaurang":        {"nace": "56.10", "naics": "722511"},
    "cafe":              {"nace": "56.30", "naics": "722515"},
    "bageri":            {"nace": "10.71", "naics": "311811"},
    "livsmedel":         {"nace": "47.11", "naics": "445110"},
    "gym":               {"nace": "93.13", "naics": "713940"},
    "padel":             {"nace": "93.11", "naics": "713940"},
    "hotell":            {"nace": "55.10", "naics": "721110"},
    "bilverkstad":       {"nace": "45.20", "naics": "811111"},
    "dackverkstad":      {"nace": "45.20", "naics": "441320"},
    "bilhandel":         {"nace": "45.11", "naics": "441110"},
    "cykelverkstad":     {"nace": "95.29", "naics": "811490"},
    "tandlakare":        {"nace": "86.23", "naics": "621210"},
    "veterinar":         {"nace": "75.00", "naics": "541940"},
    "fysioterapi":       {"nace": "86.90", "naics": "621340"},
    "psykolog":          {"nace": "86.90", "naics": "621330"},
    "vardcentral":       {"nace": "86.21", "naics": "621111"},
    "apotek":            {"nace": "47.73", "naics": "446110"},
    "optiker":           {"nace": "47.78", "naics": "456130"},
    "aldreomsorg":       {"nace": "87.30", "naics": "623312"},
    "forskola":          {"nace": "85.10", "naics": "624410"},
    "stadfirma":         {"nace": "81.21", "naics": "561720"},
    "tvatteri":          {"nace": "96.01", "naics": "812320"},
    "tradgard":          {"nace": "81.30", "naics": "561730"},
    "fastighetsservice": {"nace": "81.10", "naics": "561210"},
    "lager":             {"nace": "52.10", "naics": "493110"},
    "laddinfra":         {"nace": "43.21", "naics": "237130"},
    "redovisning":       {"nace": "69.20", "naics": "541211"},
    "juridik":           {"nace": "69.10", "naics": "541110"},
    "it_support":        {"nace": "62.02", "naics": "541512"},
    "rekrytering":       {"nace": "78.10", "naics": "561311"},
    "coworking":         {"nace": "68.20", "naics": "531120"},
    "djuraffar":         {"nace": "47.76", "naics": "459910"},
}

_NAICS_COUNTRIES = ("us", "ca")


def classification_for(country: str) -> str:
    return "naics" if country in _NAICS_COUNTRIES else "nace"


def industry_code(vertical: str, country: str) -> dict | None:
    """Landvex-bransch → officiell näringsgrenskod i landets system."""
    codes = INDUSTRY_CODES.get(vertical)
    if not codes:
        return None
    scheme = classification_for(country)
    reg = REGISTERS.get(country) or {}
    return {"vertical": vertical, "country": country, "scheme": scheme.upper(),
            "code": codes[scheme],
            "classification": reg.get("classification"),
            "register": reg.get("name")}


def register_catalog() -> dict:
    """Vilka register som finns kartlagda, och vad de kan svara på."""
    return {
        "registers": [{"country": c, **r,
                       "scheme": classification_for(c).upper()}
                      for c, r in REGISTERS.items()],
        "count": len(REGISTERS),
        "industries_mapped": len(INDUSTRY_CODES),
        "activate_with": "LANDVEX_REGISTER_URL",
        "note_en": "These are the authoritative sources for how many "
                   "businesses actually operate in a trade in a place. No "
                   "register data is carried inline; connect the endpoint and "
                   "counts become real. Until then every count is labelled "
                   "as an estimate, never presented as a register figure.",
    }


def _live_enabled() -> bool:
    """LANDVEX_LIVE=0 stänger av utgående anrop (test, offline, CI)."""
    return os.environ.get("LANDVEX_LIVE", "1") != "0"


def _http_transport(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "landvex/registers"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class RegisterClient:
    """Klient mot ett register-API (eller en spegel av det).

    Kontrakt: LANDVEX_REGISTER_URL svarar på
        {base}/establishments?country=&region=&code=&scheme=
    med {"count": <int>, "year": <int>, "source": "<register>"}.
    Ej ansluten eller fel ⇒ None, och anroparen redovisar ärligt att siffran
    är en uppskattning. Hittar aldrig på ett antal.
    """

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 8.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_REGISTER_URL", "")
                         ).rstrip("/")
        self._transport = transport or _http_transport
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    @property
    def any_provider(self) -> bool:
        """Sant om NÅGON väg finns: egen spegel eller en riktig myndighet."""
        from .datasources.register_apis import PROVIDER_FOR
        return bool(self.base_url) or bool(PROVIDER_FOR)

    def establishments(self, country: str, region: str,
                       vertical: str) -> dict | None:
        """Antal arbetsställen i branschen i regionen – eller None.

        Egen spegel först (om konfigurerad), annars landets riktiga
        myndighets-API via register_apis. Ingen väg fram ⇒ None; ett antal
        hittas aldrig på.
        """
        code = industry_code(vertical, country)
        if code is None:
            return None
        if self.base_url:
            got = self._from_mirror(country, region, code)
            if got is not None:
                return got
        # Riktig myndighet: PxWeb (SE/NO/DK/FI), Census CBP (US), Eurostat.
        if not _live_enabled():
            return None
        from .datasources.register_apis import provider_for
        got = provider_for(country).count(country, region, code["code"])
        if got is None:
            return None
        return {**got, "code": code["code"], "scheme": code["scheme"]}

    def _from_mirror(self, country: str, region: str, code: dict) -> dict | None:
        url = (f"{self.base_url}/establishments?country={country}"
               f"&region={region}&code={code['code']}&scheme={code['scheme']}")
        try:
            raw = json.loads(self._transport(url, self.timeout))
        except Exception:  # noqa: BLE001 – ärlig degradering
            return None
        if not isinstance(raw, dict) or raw.get("count") is None:
            return None
        try:
            n = int(raw["count"])
        except (TypeError, ValueError):
            return None
        return {"count": n, "year": raw.get("year"),
                "source": raw.get("source") or (REGISTERS.get(country) or {}
                                                ).get("name"),
                "code": code["code"], "scheme": code["scheme"],
                "provider": "mirror", "measured": True}

    def status(self) -> dict:
        from .datasources.register_apis import PROVIDER_FOR, providers_status
        return {"name": "registers", "mirror_configured": bool(self.base_url),
                "base_url": self.base_url or None,
                "live_calls_enabled": _live_enabled(),
                "countries": sorted(REGISTERS),
                "authority_apis": {c: p for c, p in sorted(PROVIDER_FOR.items())},
                "providers": providers_status()["providers"],
                "industries_mapped": len(INDUSTRY_CODES)}
