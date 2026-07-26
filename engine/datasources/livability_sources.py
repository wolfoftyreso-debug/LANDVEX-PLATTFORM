"""Källor till livsvillkorssignalerna – Kolada (SE) och Eurostat (EU).

Livsvillkorsmotorn vägde förskola, skola, trygghet, sjukvård och
levnadskostnad – men varje värde kom från mock. Det här lagret kopplar
dem till de myndighetskällor som faktiskt för statistiken:

  Kolada    Sveriges kommunala nyckeltal (RKA). Barn per årsarbetare i
            förskolan, elever som når kunskapskraven, anmälda brott per
            invånare, vårdtillgänglighet – på KOMMUNNIVÅ, vilket är exakt
            den upplösning frågan ställs i.
  Eurostat  EU-brett: prisnivåindex, boendekostnadsandel, polisanmälda
            brott, vårdbehov som inte tillgodosetts – på lands- och
            NUTS-nivå.

ÄRLIGHET OM KODERNA: Kolada-id:n i `KPI_IDS` (engine/datasources/kolada.py)
bekräftades i skörden. De som läggs till här är KANDIDATER – de följer
Kolada:s N#####-form men är inte live-verifierade härifrån, eftersom
utgående nät är spärrat. Samma sak gäller Eurostat-dataseten. Därför bär
varje kandidat `verified=False` och `scripts/livability_probe.py` avgör
saken där nätet är öppet. En kandidat som inte svarar ger INGET värde –
signalen faller då tillbaka på mock, märkt som mock.

Rent stdlib, injicerbar transport.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Callable
from .faults import OUR_BUGS

_UA = "landvex-opportunity-engine/livability"


def _http(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ── Kolada: signal → KPI ────────────────────────────────────────────────
# `transform` är EXPLICIT, aldrig en gissning:
#   direct      KPI:ts enhet matchar signalens redan
#   pct_invert  procenttal där högt = dåligt, signal där högt = bra (100−x)
# Viktigt: crime_index normaliseras redan INVERST i signalkatalogen (högt
# råvärde = otryggare). Att invertera Kolada-talet också hade vänt tillbaka
# det och gjort de mest brottsutsatta kommunerna till de tryggaste.
KOLADA_SIGNALS: dict[str, dict] = {
    "care_supply": {
        "kpi": "N11102", "label_en": "Children per full-time staff, preschool",
        "transform": "direct", "verified": False,
        "why_en": "Group size decides whether childcare actually works. The "
                  "signal is banded (3–7 children per adult), so the KPI "
                  "maps straight onto it."},
    "education_outcomes": {
        "kpi": "N15428", "label_en": "Pupils meeting requirements, year 9",
        "transform": "direct", "verified": True,
        "why_en": "Confirmed in the harvest; percent, higher is better."},
    "crime_index": {
        "kpi": "N07403", "label_en": "Reported violent crime per 100k",
        "transform": "direct", "verified": True,
        "why_en": "Confirmed in the harvest. NOT inverted here — the signal "
                  "catalogue already normalises crime_index inversely."},
    "healthcare_access": {
        "kpi": "N20401", "label_en": "Primary care availability",
        "transform": "direct", "verified": True,
        "why_en": "Confirmed in the harvest; percent available."},
    "life_satisfaction": {
        "kpi": "N00956", "label_en": "Self-reported good health",
        "transform": "direct", "verified": False,
        "why_en": "Candidate — percent reporting good health."},
    "social_trust": {
        "kpi": "N00979", "label_en": "Trust in the municipality",
        "transform": "direct", "verified": False,
        "why_en": "Candidate — index, higher is more trust."},
    "housing_affordability": {
        "kpi": "N07907", "label_en": "Housing cost burden",
        "transform": "pct_invert", "verified": False,
        "why_en": "Candidate — percent overburdened; flipped because the "
                  "signal means affordability, not burden."},
}

# ── Eurostat: signal → dataset ──────────────────────────────────────────
EUROSTAT_SIGNALS: dict[str, dict] = {
    "housing_affordability": {
        "dataset": "ilc_lvho05a", "label_en": "Housing cost overburden rate",
        "transform": "pct_invert",
        "params": {"incgrp": "TOTAL", "tenure": "TOTAL"},
        "verified": False},
    "cost_level": {
        "dataset": "prc_ppp_ind", "label_en": "Price level index",
        "transform": "direct",
        "params": {"na_item": "PLI_EU27_2020", "ppp_cat": "A01"},
        "verified": False},
    "crime_index": {
        "dataset": "crim_off_cat", "label_en": "Police-recorded offences",
        "transform": "direct",
        "params": {"iccs": "ICCS0101", "unit": "P_HTHAB"},
        "verified": False},
    "healthcare_access": {
        "dataset": "hlth_silc_08", "label_en": "Unmet medical need",
        "transform": "pct_invert",
        "params": {"reason": "TOOEXP", "sex": "T"},
        "verified": False},
}


class Unreachable(Exception):
    """Värden gick inte att nå alls – skilt från 'KPI:t saknas'."""


def _classify(exc: Exception) -> bool:
    """True om felet betyder ONÅBAR värd (nät/policy), inte tomt svar."""
    import socket
    import urllib.error
    if isinstance(exc, urllib.error.HTTPError):
        # Servern svarade – 404 på ett KPI är ett riktigt svar, 5xx/407 inte.
        return exc.code in (403, 407, 502, 503, 504)
    return isinstance(exc, (urllib.error.URLError, socket.timeout, OSError,
                            ConnectionError))


# ── Verifieringsläge på disk ────────────────────────────────────────────
# Proben skriver hit när den körts mot de riktiga API:erna. Filen är
# systemets minne av VAD SOM FAKTISKT SVARADE – utan den står kandidaterna
# kvar som kandidater, vilket är den säkra defaulten.
VERIFIED_PATH = os.path.join(os.path.dirname(__file__), "verified.json")


def load_verification(path: str | None = None) -> dict:
    try:
        with open(path or VERIFIED_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OUR_BUGS:
        raise        # vårt fel, inte omvärldens – se faults.py
    except Exception:  # noqa: BLE001 – ingen fil = inget verifierat
        return {}


def apply_verification(state: dict | None = None) -> int:
    """Lägg probens resultat ovanpå tabellerna. Returnerar antal ändrade."""
    state = state if state is not None else load_verification()
    n = 0
    for family, table in (("kolada", KOLADA_SIGNALS),
                          ("eurostat", EUROSTAT_SIGNALS)):
        for sid, row in (state.get(family) or {}).items():
            if sid in table and "verified" in row:
                if table[sid]["verified"] != bool(row["verified"]):
                    n += 1
                table[sid]["verified"] = bool(row["verified"])
                table[sid]["checked_at"] = row.get("checked_at")
                if row.get("answered") is False:
                    table[sid]["answered"] = False
    return n


def save_verification(results: dict, checked_at: str,
                      path: str | None = None) -> str:
    """Skriv probens utfall. results: {family: {signal: bool_answered}}."""
    state = load_verification(path)
    for family, sigs in results.items():
        fam = state.setdefault(family, {})
        for sid, answered in sigs.items():
            fam[sid] = {"verified": bool(answered), "answered": bool(answered),
                        "checked_at": checked_at}
    target = path or VERIFIED_PATH
    with open(target, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    return target


def apply_transform(value: float, transform: str) -> float:
    """För in myndighetens tal på signalens skala – explicit, aldrig gissat."""
    if transform == "pct_invert":
        return round(100.0 - float(value), 4)
    if transform == "direct":
        return float(value)
    raise ValueError(f"unknown transform: {transform}")


class KoladaLivability:
    """Kolada v2 – kommunala nyckeltal per kommunkod.

    {base}/data/kpi/{kpi}/municipality/{kommun}   (senaste år)
    Svaret: {"values":[{"period":2024,"values":[{"gender":"T","value":5.3}]}]}
    """

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 8.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get("LANDVEX_KOLADA_URL", "")
                         ).rstrip("/")
        self._transport = transport or _http
        self.timeout = timeout

    @property
    def connected(self) -> bool:
        return bool(self.base_url)

    def reachable(self) -> tuple[bool, str]:
        """Nås värden överhuvudtaget? Avgör om ett uteblivet svar betyder
        'KPI:t finns inte' eller 'jag kom aldrig fram'."""
        if not self.connected:
            return False, "not configured"
        try:
            self._transport(f"{self.base_url}/kpi", self.timeout)
            return True, "ok"
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception as e:  # noqa: BLE001
            if _classify(e):
                return False, f"{type(e).__name__}: {e}"
            return True, "reachable (endpoint responded)"

    def value(self, signal_id: str, kommun: str) -> dict | None:
        spec = KOLADA_SIGNALS.get(signal_id)
        if not (self.connected and spec):
            return None
        url = f"{self.base_url}/data/kpi/{spec['kpi']}/municipality/{kommun}"
        try:
            raw = json.loads(self._transport(url, self.timeout))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001 – ärlig degradering
            return None
        pick = _kolada_total(raw)
        if pick is None:
            return None
        return {"signal_id": signal_id,
                "value": apply_transform(pick["value"], spec["transform"]),
                "raw_value": pick["value"], "transform": spec["transform"],
                "year": pick["year"], "kpi": spec["kpi"],
                "label_en": spec["label_en"], "source": "kolada"}


def _kolada_total(raw: dict) -> dict | None:
    """Plocka totalvärdet (gender == 'T') från senaste perioden."""
    if not isinstance(raw, dict):
        return None
    best = None
    for row in raw.get("values") or []:
        period = row.get("period")
        for v in row.get("values") or []:
            if v.get("gender") == "T" and v.get("value") is not None:
                if best is None or (period or 0) > (best["year"] or 0):
                    best = {"value": float(v["value"]), "year": period}
    return best


class EurostatLivability:
    """Eurostat dissemination API – JSON-stat per land/NUTS-region."""

    def __init__(self, base_url: str | None = None,
                 transport: Callable[[str, float], str] | None = None,
                 timeout: float = 10.0):
        self.base_url = (base_url if base_url is not None
                         else os.environ.get(
                             "LANDVEX_EUROSTAT_BASE",
                             "https://ec.europa.eu/eurostat/api/dissemination"
                             "/statistics/1.0/data")).rstrip("/")
        self._transport = transport or _http
        self.timeout = timeout
        self.enabled = os.environ.get("LANDVEX_EUROSTAT_LIVE", "0") == "1"

    @property
    def connected(self) -> bool:
        return bool(self.base_url) and self.enabled

    def reachable(self) -> tuple[bool, str]:
        if not self.connected:
            return False, "not enabled"
        try:
            self._transport(f"{self.base_url}/ilc_lvho05a?format=JSON&geo=SE",
                            self.timeout)
            return True, "ok"
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception as e:  # noqa: BLE001
            if _classify(e):
                return False, f"{type(e).__name__}: {e}"
            return True, "reachable (endpoint responded)"

    def value(self, signal_id: str, geo: str) -> dict | None:
        spec = EUROSTAT_SIGNALS.get(signal_id)
        if not (self.connected and spec):
            return None
        params = {"format": "JSON", "lang": "EN", "geo": geo,
                  **spec.get("params", {})}
        url = (f"{self.base_url}/{spec['dataset']}?"
               + urllib.parse.urlencode(params))
        try:
            raw = json.loads(self._transport(url, self.timeout))
        except OUR_BUGS:
            raise        # vårt fel, inte omvärldens – se faults.py
        except Exception:  # noqa: BLE001
            return None
        got = _jsonstat_latest(raw)
        if got is None:
            return None
        return {"signal_id": signal_id,
                "value": apply_transform(got["value"], spec["transform"]),
                "raw_value": got["value"], "transform": spec["transform"],
                "year": got["year"], "dataset": spec["dataset"],
                "label_en": spec["label_en"], "source": "eurostat"}


def _jsonstat_latest(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    val = raw.get("value")
    nums = []
    if isinstance(val, list):
        nums = [v for v in val if isinstance(v, (int, float))]
    elif isinstance(val, dict):
        nums = [v for v in val.values() if isinstance(v, (int, float))]
    if not nums:
        return None
    year = None
    idx = (((raw.get("dimension") or {}).get("time") or {}).get("category")
           or {}).get("index") or {}
    if idx:
        year = sorted(idx, key=lambda k: idx[k])[-1]
    return {"value": float(nums[-1]), "year": year}


def catalog() -> dict:
    """Vad som är kopplat, vad som är kandidat, och hur det slås på."""
    state = load_verification()
    return {
        "verification": {
            "file": VERIFIED_PATH,
            "present": bool(state),
            "checked_at": (next(iter((state.get("kolada") or {}).values()), {})
                           .get("checked_at") if state else None),
            "how_en": "Run scripts/livability_probe.py --apply where the "
                      "network is open; it records which KPIs actually "
                      "answered. Without that file every candidate stays a "
                      "candidate — the safe default."},
        "kolada": {
            "activate_with": "LANDVEX_KOLADA_URL",
            "granularity": "municipality (kommunkod)",
            "signals": [{"signal_id": s, **v} for s, v in
                        KOLADA_SIGNALS.items()],
            "verified_count": sum(1 for v in KOLADA_SIGNALS.values()
                                  if v["verified"]),
            "candidate_count": sum(1 for v in KOLADA_SIGNALS.values()
                                   if not v["verified"])},
        "eurostat": {
            "activate_with": "LANDVEX_EUROSTAT_LIVE=1",
            "granularity": "country / NUTS region",
            "signals": [{"signal_id": s, **v} for s, v in
                        EUROSTAT_SIGNALS.items()],
            "verified_count": 0,
            "candidate_count": len(EUROSTAT_SIGNALS)},
        "note_en": "KPI and dataset identifiers marked verified=false are "
                   "candidates: they follow the right form but have NOT been "
                   "live-verified from this environment. A candidate that "
                   "does not answer yields no value at all — the signal then "
                   "falls back to mock and is labelled mock. Nothing is "
                   "invented to fill a gap.",
        "probe": "python3 -m scripts.livability_probe <kommun>",
    }


# Probens utfall gäller över tabellernas defaultvärden – finns ingen fil
# ändras ingenting och allt förblir kandidat.
apply_verification()
