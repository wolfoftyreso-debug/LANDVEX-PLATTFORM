"""Fråga Landvex – naturligt språk in, motordata ut.

Plattformens startsida: användaren skriver som i en chatt
("Vilka är de fem största affärsmöjligheterna i Örebro just nu?")
och får svar byggda på motorerna – aldrig på fri textgenerering.

Arkitektur i två lager, medvetet separerade:

  1. TOLKNING (denna modul): deterministisk, regelbaserad svensk
     parser – extraherar intent + entiteter (kommun, yrke, bransch,
     antal, tidshorisont). Testbar offline, inga beroenden. Kan i
     produktionsfasen ersättas/kompletteras av ett LLM-lager i api/
     (aldrig i kärnan, princip 2) som producerar samma Query-objekt.
  2. SVAR: routning till befintliga motorer (scan, workforce, risk,
     scoring). All fakta i svaret kommer därifrån, med samma
     konfidens, intervall, antaganden och caveats som motorerna bär.

Systemet svarar inte "var finns jobben idag?" utan "var uppstår
behoven innan alla andra ser dem?" – och redovisar alltid hur säker
slutsatsen är.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .datasources.base import Resolver
from .datasources.scb import KOMMUNER
from .models import Location
from .profile import BusinessProfile
from .risk import assess
from .scan import economy_scenario, scan
from .scoring import analyze
from .verticals import VERTICALS
from .workforce import (BASE_YEAR, MAX_HORIZON_YEARS, OCCUPATIONS,
                        forecast, national_map)

# ── Entitetslexikon (svenska synonymer → id) ─────────────────────────

_VERTICAL_SYNONYMS: dict[str, str] = {
    "frisör": "frisor", "frisörsalong": "frisor", "salong": "frisor",
    "barberare": "frisor",
    "elektrikerfirma": "elektriker", "elfirma": "elektriker",
    "gym": "gym", "träningscenter": "gym", "träningsanläggning": "gym",
    "restaurang": "restaurang", "krog": "restaurang",
    "café": "cafe", "cafe": "cafe", "kafé": "cafe", "fik": "cafe",
    "kaffebar": "cafe", "konditori": "cafe",
    "byggföretag": "bygg", "byggfirma": "bygg",
    "tandläkare": "tandlakare", "tandläkarpraktik": "tandlakare",
    "tandvård": "tandlakare",
    "bilverkstad": "bilverkstad", "verkstad": "bilverkstad",
    "veterinär": "veterinar", "veterinärklinik": "veterinar",
    "djurklinik": "veterinar",
    "lager": "lager", "logistik": "lager", "logistikcenter": "lager",
}

_OCCUPATION_SYNONYMS: dict[str, str] = {
    "elektriker": "elektriker",
    "vvs": "vvs_montor", "vvs-montör": "vvs_montor",
    "vvs-installatör": "vvs_montor", "rörmokare": "vvs_montor",
    "snickare": "snickare",
    "betongarbetare": "betongarbetare",
    "plattsättare": "plattsattare",
    "maskinförare": "maskinforare", "anläggningsförare": "maskinforare",
    "anläggningsmaskinförare": "maskinforare",
    "arkitekt": "arkitekt",
    "ingenjör": "ingenjor_bygg", "byggnadsingenjör": "ingenjor_bygg",
    "byggingenjör": "ingenjor_bygg",
    "lärare": "larare",
    "förskollärare": "forskollarare",
    "sjuksköterska": "sjukskoterska",
    "fastighetstekniker": "fastighetstekniker",
    "drifttekniker": "drifttekniker",
}

_NUMBER_WORDS = {"en": 1, "ett": 1, "två": 2, "tre": 3, "fyra": 4,
                 "fem": 5, "sex": 6, "sju": 7, "åtta": 8, "nio": 9,
                 "tio": 10}

_SHORTAGE_WORDS = ("brist", "saknas", "behov", "behövs", "efterfråg",
                   "yrke", "yrkesgrupp", "kompetens", "pension", "rekryter")
_START_WORDS = ("starta", "öppna", "etablera", "affärsmöjlighet",
                "möjligheter", "investera", "driva")
_RISK_WORDS = ("risk", "riskabelt", "riskfyllt", "farligt", "vågar")


@dataclass
class Query:
    intent: str
    kommun: tuple | None = None            # (kod, namn, lat, lon)
    occupation_id: str | None = None
    vertical_id: str | None = None
    top_n: int = 5
    target_year: int = 2035
    unmatched_kommun: str | None = None
    raw: str = ""
    tokens: list = field(default_factory=list)


def _fold(s: str) -> str:
    return s.lower().replace("é", "e")


def _find_kommun(q: str) -> tuple | None:
    for k in KOMMUNER:
        name = _fold(k[1])
        if re.search(rf"\b{re.escape(name)}s?\b", q):
            return k
    return None


def _find_unmatched_kommun(q: str) -> str | None:
    m = re.search(r"\bi\s+([a-zåäö]+?)s?\s+kommun\b", q)
    return m.group(1).capitalize() if m else None


def _find_in_lexicon(q: str, lexicon: dict[str, str]) -> str | None:
    hits = []
    for syn, vid in lexicon.items():
        stem = _fold(syn)
        if stem.endswith("a"):               # sjuksköterska → sjuksköterskor
            stem = stem[:-1]
        if re.search(rf"\b{re.escape(stem)}\w*", q):
            hits.append((len(syn), vid))
    return max(hits)[1] if hits else None    # längsta synonym vinner


def _find_top_n(q: str) -> int:
    m = re.search(r"\b(\d{1,2})\b(?!\s*(år|km|min))", q)
    if m and 1 <= int(m.group(1)) <= 20:
        return int(m.group(1))
    for word, n in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b\s+(största|bästa|viktigaste|hetaste)", q):
            return n
    return 5


def _find_year(q: str) -> int:
    m = re.search(r"\b(20[2-4]\d)\b", q)
    if m:
        return max(BASE_YEAR + 1,
                   min(BASE_YEAR + MAX_HORIZON_YEARS, int(m.group(1))))
    m = re.search(r"(?:kommande|närmaste|nästa|inom)\s+(\d{1,2}|"
                  + "|".join(_NUMBER_WORDS) + r")\s+åren?", q)
    if m:
        n = m.group(1)
        years = int(n) if n.isdigit() else _NUMBER_WORDS[n]
        return BASE_YEAR + max(1, min(MAX_HORIZON_YEARS, years))
    return 2035


def parse(question: str) -> Query:
    q = _fold(question.strip())
    kommun = _find_kommun(q)
    occ = _find_in_lexicon(q, _OCCUPATION_SYNONYMS)
    vert = _find_in_lexicon(q, _VERTICAL_SYNONYMS)
    # "elektriker" är både yrke och bransch – kontext avgör.
    if occ and vert is None and occ in VERTICALS:
        if any(w in q for w in _START_WORDS) or any(w in q for w in _RISK_WORDS):
            vert, occ = occ, None
    shortage = any(w in q for w in _SHORTAGE_WORDS)
    start = any(w in q for w in _START_WORDS)
    risky = any(w in q for w in _RISK_WORDS)

    query = Query(intent="hjalp", kommun=kommun,
                  occupation_id=occ, vertical_id=vert,
                  top_n=_find_top_n(q), target_year=_find_year(q),
                  unmatched_kommun=None if kommun else _find_unmatched_kommun(q),
                  raw=question)

    if kommun is None and query.unmatched_kommun:
        query.intent = "okand_kommun"
    elif risky and vert and kommun:
        query.intent = "riskprofil"
    elif occ and not kommun and (shortage or "var " in q + " " or q.startswith("var")):
        query.intent = "nationell_brist"
    elif kommun and (shortage or occ) and not start:
        query.intent = "bristyrken_kommun"
    elif vert and not kommun and start:
        query.intent = "basta_lage_vertikal"
    elif kommun and start:
        query.intent = "mojligheter_kommun"
    elif kommun and vert:
        query.intent = "mojligheter_kommun"
    return query


# ── Svarsbyggare per intent ──────────────────────────────────────────

_HELP = {
    "svar_sv": "Jag förstår frågor om affärsmöjligheter, kompetensbrist och "
               "risk – kopplade till en kommun, ett yrke eller en bransch.",
    "forslag_sv": [
        "Vilka är de fem största affärsmöjligheterna i Örebro just nu?",
        "Vilka yrkesgrupper saknas mest i Umeå de kommande fem åren?",
        "Var i Sverige är behovet av elektriker störst?",
        "Var ska jag öppna café?",
        "Hur riskabelt är det att starta gym i Solna?",
    ],
}


def _rows_mojligheter(query: Query, resolver) -> dict[str, Any]:
    kod, namn, lat, lon = query.kommun
    loc = Location(lat, lon, address=namn)
    verts = ([query.vertical_id] if query.vertical_id
             else [v for v in VERTICALS if v != "generisk"])
    rows = []
    for vid in verts:
        r = analyze(loc, vid, resolver=resolver)
        rp = assess(loc, vid, resolver=resolver)
        eko = economy_scenario(BusinessProfile(vertical_id=vid,
                                               team_size="2-5"), r.opportunity_score)
        rows.append({
            "typ": "affarsmojlighet", "id": vid,
            "label_sv": VERTICALS[vid].label_sv,
            "score": r.opportunity_score,
            "trend": ("stigande" if any(f.id == "tillvaxt" and f.score >= 60
                                        for f in r.factors) else "stabil"),
            "detalj": {
                "risk_total": rp["total_risk"], "risk_band": rp["band"],
                "faktorer": [{"label_sv": f.label_sv, "score": f.score,
                              "narrativ_sv": f.narrative_sv} for f in r.factors],
                "insikter_sv": r.insights_sv,
                "ekonomi_schablon": eko,
                "data_coverage": r.data_coverage,
            }})
    rows.sort(key=lambda x: -x["score"])
    rows = rows[:query.top_n]
    topp = rows[0]
    return {
        "svar_sv": f"Största affärsmöjligheterna i {namn} just nu – starkast är "
                   f"{topp['label_sv'].lower()} ({int(topp['score'])}/100).",
        "rader": rows,
        "forslag_sv": [f"Vilka yrkesgrupper saknas mest i {namn}?",
                       f"Hur riskabelt är det att starta "
                       f"{topp['label_sv'].lower()} i {namn}?"],
    }


def _rows_bristyrken(query: Query, resolver) -> dict[str, Any]:
    kod, namn, *_ = query.kommun
    occ_ids = [query.occupation_id] if query.occupation_id else None
    res = forecast(kod, query.target_year, occ_ids, resolver=resolver)
    rows = [{
        "typ": "bristyrke", "id": f["occupation_id"], "label_sv": f["label_sv"],
        "score": min(100, round(100 * f["brist"] / max(f["behov_prognos"], 1) * 4)),
        "brist": f["brist"], "efterfragan": f["efterfragan"],
        "trend": f["trend"],
        "detalj": {
            "behov_nu": f["behov_nu"], "behov_prognos": f["behov_prognos"],
            "intervall": f["intervall"], "konfidens": f["konfidens"],
            "pensionsavgangar": f["pensionsavgangar"],
            "medellon_tkr_manad": f["medellon_tkr_manad"],
            "automationsrisk_schablon": f["automationsrisk_schablon"],
            "drivare": f["drivare"], "antaganden": f["antaganden"],
        }} for f in res["prognoser"] if f["brist"] > 0][:query.top_n]
    if not rows:
        return {"svar_sv": f"Modellen ser ingen beräknad kompetensbrist i "
                           f"{namn} till {query.target_year}.", "rader": []}
    return {
        "svar_sv": f"Yrkesgrupper med störst beräknad brist i {namn} "
                   f"till {query.target_year}:",
        "rader": rows,
        "forslag_sv": [f"Var i Sverige är behovet av "
                       f"{rows[0]['label_sv'].lower()} störst?",
                       f"Vilka är de största affärsmöjligheterna i {namn}?"],
    }


def _rows_nationell(query: Query, resolver) -> dict[str, Any]:
    res = national_map(query.occupation_id, query.target_year,
                       resolver=resolver)
    rows = [{
        "typ": "kommun_brist", "id": k["kommun_kod"], "label_sv": k["kommun"],
        "score": min(100, round(100 * k["brist"] /
                                max(k["behov_prognos"], 1) * 4)),
        "brist": k["brist"], "efterfragan": k["efterfragan"],
        "trend": k["trend"],
        "detalj": {"behov_prognos": k["behov_prognos"],
                   "konfidens": k["konfidens"]},
    } for k in res["kommuner"][:query.top_n]]
    return {
        "svar_sv": f"Störst beräknat behov av "
                   f"{res['label_sv'].lower()} till {query.target_year}: "
                   f"{', '.join(r['label_sv'] for r in rows[:3])}.",
        "rader": rows,
        "karta": {"typ": "efterfragan", "kommuner": res["kommuner"],
                  "label_sv": res["label_sv"], "malar": res["malar"]},
        "forslag_sv": [f"Vilka yrkesgrupper saknas mest i "
                       f"{rows[0]['label_sv']}?"],
    }


def _rows_basta_lage(query: Query, resolver) -> dict[str, Any]:
    res = scan(BusinessProfile(vertical_id=query.vertical_id),
               resolver=resolver, top_n=query.top_n)
    rows = [{
        "typ": "hotspot", "id": h["kommun_kod"], "label_sv": h["lage_sv"],
        "score": h["opportunity_score"], "trend": h["market_momentum"]["direction"],
        "detalj": {"confidence": h["confidence"], "risk_index": h["risk_index"],
                   "competition_gap": h["competition_gap"],
                   "time_window_months": h["time_window_months"],
                   "motivering_sv": h["motivering_sv"],
                   "ekonomi_schablon": h["economy_scenario"]},
    } for h in res["hotspots"]]
    return {
        "svar_sv": f"Bästa lägena för {res['vertical_label_sv'].lower()} "
                   f"enligt Sverigesvepet – toppkandidat "
                   f"{rows[0]['label_sv']} ({int(rows[0]['score'])}/100).",
        "rader": rows,
        "karta": {"typ": "heatmap", "heatmap": res["heatmap"],
                  "hotspots": res["hotspots"], "level": res["level"]},
        "forslag_sv": [f"Hur riskabelt är det att starta "
                       f"{res['vertical_label_sv'].lower()} i "
                       f"{rows[0]['label_sv'].split(',')[0]}?"],
    }


def _rows_risk(query: Query, resolver) -> dict[str, Any]:
    kod, namn, lat, lon = query.kommun
    rp = assess(Location(lat, lon, address=namn), query.vertical_id,
                resolver=resolver)
    rows = [{
        "typ": "riskdimension", "id": d["id"], "label_sv": d["label_sv"],
        "score": d["risk"], "trend": None,
        "detalj": {"band": d["band"], "narrativ_sv": d["narrativ_sv"],
                   "atgard_sv": d["atgard_sv"], "signaler": d["signaler"]},
    } for d in rp["dimensioner"]]
    return {"svar_sv": rp["narrativ_sv"] + f" Gäller "
                       f"{rp['vertical_label_sv'].lower()} i {namn}.",
            "rader": rows,
            "forslag_sv": [f"Vilka är de största affärsmöjligheterna i {namn}?"]}


def ask(question: str, resolver: Resolver | None = None) -> dict[str, Any]:
    """Huvudingång: fråga på svenska → strukturerat, motorbaserat svar."""
    if not question or not question.strip():
        return {"fraga": question, "intent": "hjalp", **_HELP,
                "rader": [], "caveats_sv": []}
    query = parse(question)
    base = {"fraga": question, "intent": query.intent, "rader": [],
            "malar": query.target_year}

    if query.intent == "okand_kommun":
        exempel = ", ".join(k[1] for k in KOMMUNER[:6])
        return {**base,
                "svar_sv": f"{query.unmatched_kommun} kommun ingår inte ännu – "
                           f"kartunderlaget täcker {len(KOMMUNER)} större "
                           f"kommuner i denna version (t.ex. {exempel}). "
                           f"Fler tillkommer i geodatafasen.",
                "caveats_sv": []}
    if query.intent == "hjalp":
        return {**base, **_HELP, "caveats_sv": []}

    handler = {"mojligheter_kommun": _rows_mojligheter,
               "bristyrken_kommun": _rows_bristyrken,
               "nationell_brist": _rows_nationell,
               "basta_lage_vertikal": _rows_basta_lage,
               "riskprofil": _rows_risk}[query.intent]
    result = handler(query, resolver)
    caveats = result.pop("caveats_sv", []) + [
        "Svaret är beräknat av Landvex motorer på aktuellt dataunderlag – "
        "beslutsunderlag, inte garanti. Konfidens och antaganden redovisas "
        "per rad."]
    return {**base, **result, "caveats_sv": caveats}
