"""Sverigesvepet: profilstyrd analys av kandidatorter → hotspots.

Flöde: kandidatlista (v0.4: samma 40 större kommuner som SCB-adaptern)
→ pendlings-/miljöfilter från profilen → analyze() per plats →
beslutskort per hotspot + värmekartedata.

Beslutskortet följer produktvisionen: Opportunity Score, Confidence,
Time Window, Competition Gap, Market Momentum, Risk Index och
topp-drivkrafter. Två medvetna avsteg i ärlighetens namn:

  * Förväntad ROI redovisas INTE som siffra – det vore en gissning
    tills utfallsdata finns (v2/v3, se arkitekturprincip 3). Fältet
    finns men bär status "ej_tillgangligt" + förklaring. I stället
    ges ett tydligt märkt ekonomiskt SCHABLONSCENARIO.
  * Time Window och rankjusteringar är dokumenterade heuristiker,
    inte prediktioner – de redovisas som sådana i svaret.

Allt är deterministiskt för given profil + källkedja.
"""
from __future__ import annotations

from typing import Any

from .datasources.base import Resolver
from .datasources.scb import KOMMUNER, _haversine_km
from .models import Location
from .profile import BusinessProfile
from .scoring import analyze
from .signals import CATALOG
from .verticals import VERTICALS

# ── Rankjustering (dokumenterade heuristiker) ────────────────────────
# rank_score = opportunity_score − riskstraff + måljustering.
# Riskstraff: riskindex (0..100) × faktor per tolerans.
_RISK_PENALTY = {"lag": 0.35, "normal": 0.20, "hog": 0.08, "aggressiv": 0.0}
# Måljustering: momentumkänslighet per målsättning (± kring momentum 50).
_GOAL_MOMENTUM = {"maximal_vinst": 0.12, "exit": 0.12, "bygga_kedja": 0.08,
                  "stabilitet": 0.0, "livsstil": 0.0, "passiv_inkomst": 0.0}
# Stabilitetsmål straffar risk ytterligare.
_GOAL_RISK_EXTRA = {"stabilitet": 0.10, "passiv_inkomst": 0.10, "livsstil": 0.05,
                    "maximal_vinst": 0.0, "exit": 0.0, "bygga_kedja": 0.0}

# Momentum = medel av normaliserade tillväxt-/utvecklingssignaler.
_MOMENTUM_SIGNALS = ("pop_growth_pct", "building_permits", "detail_plans",
                     "development_m2", "infra_invest")

# ── Ekonomiskt schablonscenario (INGEN prognos) ──────────────────────
# Branschschabloner: årsomsättning per sysselsatt (tkr) och typiskt
# startkapital (tkr, intervall). Grova riktvärden för scenariot –
# kalibreras mot utfallsdata i v2.
_REVENUE_PER_PERSON_TKR = {
    "frisor": 700, "elektriker": 1400, "gym": 900, "restaurang": 950,
    "cafe": 800, "bygg": 1800, "tandlakare": 1600, "generisk": 1000}
_STARTUP_TKR = {
    "frisor": (150, 600), "elektriker": (100, 500), "gym": (1500, 6000),
    "restaurang": (800, 4000), "cafe": (400, 1500), "bygg": (200, 1000),
    "tandlakare": (1500, 5000), "generisk": (300, 2000)}
_TEAM_PERSONS = {"1": 1, "2-5": 3, "5-20": 10, "20-50": 30, "50+": 60}
_BUDGET_TKR = {"0-500k": (0, 500), "500k-2m": (500, 2000),
               "2-5m": (2000, 5000), "5-10m": (5000, 10000),
               "10m+": (10000, 100000)}

_NEXT_STEPS_SV = ["Hitta lokal", "Finansiering", "Rekrytering", "Bygglov",
                  "Startbudget", "Leverantörer", "Kontakt med kommunen"]


def _sig(report, sid: str):
    s = report.signals.get(sid)
    return s if s else None


def classify_environment(report) -> list[str]:
    """Miljötaggar från signalbilden (dokumenterade trösklar)."""
    tags: list[str] = []
    dens = _sig(report, "residential_density")
    if dens is not None:
        d = dens["value"]
        tags.append("stad" if d >= 1200 else "forort" if d >= 500 else "landsbygd")
    tur = _sig(report, "tourism_index")
    if tur is not None and tur["value"] >= 40:
        tags.append("turistort")
    biz = _sig(report, "business_density")
    if biz is not None and biz["value"] >= 50:
        tags.append("industrizon")
    return tags


def _confidence(report) -> int:
    """0–100: hur starkt datan stöder slutsatsen (täckning × kvalitet)."""
    if not report.signals:
        return 0
    avg_q = sum(s["quality"] for s in report.signals.values()) / len(report.signals)
    return int(round(100 * (0.5 * report.data_coverage + 0.5 * avg_q)))


def _momentum(report) -> dict[str, Any]:
    ns = [report.signals[s]["normalized"] for s in _MOMENTUM_SIGNALS
          if s in report.signals]
    value = int(round(100 * sum(ns) / len(ns))) if ns else 50
    direction = ("forbattras" if value >= 60 else
                 "forsvagas" if value <= 40 else "stabil")
    text = {"forbattras": "Marknaden förbättras – hög utvecklingsaktivitet.",
            "stabil": "Marknaden är stabil.",
            "forsvagas": "Marknaden försvagas – låg utvecklingsaktivitet."}[direction]
    return {"value": value, "direction": direction, "text_sv": text}


def _competition_gap(report) -> dict[str, Any]:
    gap = _sig(report, "provider_gap")
    ratio = round(gap["value"], 2) if gap else None
    if ratio is None:
        return {"ratio": None, "text_sv": "Underlag saknas."}
    if ratio >= 1.3:
        text = "Tydligt underskott av aktörer – efterfrågan överstiger utbudet."
    elif ratio >= 0.95:
        text = "Utbud och efterfrågan i balans."
    else:
        text = "Överskott av aktörer – mättad marknad."
    return {"ratio": ratio, "text_sv": text}


def _time_window(momentum_value: int, gap_ratio: float | None) -> int:
    """Heuristik: månader möjligheten sannolikt består.

    Stort utbudsgap → längre fönster; hög marknadsfart → kortare
    (fler upptäcker samma möjlighet). Klipps till 6–36 månader.
    """
    months = 18.0
    if gap_ratio is not None:
        months += (gap_ratio - 1.0) * 12
    months -= (momentum_value - 50) * 0.15
    return int(min(36, max(6, round(months))))


def _drivers(report, vertical_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Topp-datapunkter som driver (eller hämmar) rekommendationen."""
    weights: dict[str, float] = {}
    for f in VERTICALS[vertical_id].factors:
        for sid, w in f.signals:
            weights[sid] = weights.get(sid, 0.0) + f.weight * w
    scored = []
    for sid, w in weights.items():
        s = report.signals.get(sid)
        if s is None:
            continue
        n = s["normalized"]
        impact = w * (n - 0.5)                     # + driver, − hämmar
        d = CATALOG[sid]
        scored.append({"signal_id": sid, "label_sv": d.label_sv,
                       "value": s["value"], "unit": d.unit,
                       "source": s["source"],
                       "direction": "driver" if impact >= 0 else "hammar",
                       "impact": round(impact, 4)})
    scored.sort(key=lambda x: abs(x["impact"]), reverse=True)
    return scored[:limit]


def _economy_scenario(profile: BusinessProfile, opportunity_score: float) -> dict[str, Any]:
    persons = _TEAM_PERSONS[profile.team_size]
    rev = _REVENUE_PER_PERSON_TKR[profile.vertical_id]
    lo_start, hi_start = _STARTUP_TKR[profile.vertical_id]
    b_lo, b_hi = _BUDGET_TKR[profile.budget_band]
    # Platsjustering: score 0 → 0.75x, score 100 → 1.25x branschsnittet.
    local = 0.75 + 0.5 * opportunity_score / 100.0
    revenue = int(round(persons * rev * local, -1))
    if b_hi < lo_start:
        fit = "Budgeten ligger under typiskt startkapital för branschen."
    elif b_lo > hi_start:
        fit = "Budgeten täcker typiskt startkapital med god marginal."
    else:
        fit = "Budgeten ligger inom typiskt startkapitalintervall."
    return {
        "omsattningsscenario_tkr_ar": revenue,
        "startkapital_typiskt_tkr": [lo_start, hi_start],
        "budget_fit_sv": fit,
        "notis_sv": "Schablonscenario utifrån branschriktvärden och platsens "
                    "score – INTE en prognos. Kalibreras mot utfallsdata i v2.",
    }


_ROI_UNAVAILABLE = {
    "status": "ej_tillgangligt",
    "notis_sv": "Förväntad ROI redovisas när utfallsdata finns (v2/v3). "
                "Att gissa vore att bryta mot principen förklarbarhet "
                "före prediktion.",
}


def _band(score: float) -> str:
    return "gron" if score >= 70 else "gul" if score >= 45 else "rod"


def scan(profile: BusinessProfile, resolver: Resolver | None = None,
         candidates: list[tuple[str, str, float, float]] | None = None,
         top_n: int = 5) -> dict[str, Any]:
    """Analyserar kandidatorter mot profilen. Returnerar JSON-redo dict."""
    cands = candidates if candidates is not None else KOMMUNER
    excluded = {"pendling": 0, "miljo": 0}

    if profile.commute_km is not None:
        within = []
        for c in cands:
            if _haversine_km(profile.home_lat, profile.home_lon,
                             c[2], c[3]) <= profile.commute_km:
                within.append(c)
            else:
                excluded["pendling"] += 1
        cands = within

    heatmap: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []
    for code, name, lat, lon in cands:
        report = analyze(Location(lat, lon, address=name), profile.vertical_id,
                         resolver=resolver)
        env = classify_environment(report)
        heatmap.append({"kommun": name, "kommun_kod": code, "lat": lat,
                        "lon": lon, "score": report.opportunity_score,
                        "band": _band(report.opportunity_score)})
        if profile.environments and not set(profile.environments) & set(env):
            excluded["miljo"] += 1
            continue

        risk_index = int(round(report.risk_score * 100))
        momentum = _momentum(report)
        rank = (report.opportunity_score
                - _RISK_PENALTY[profile.risk_tolerance] * risk_index
                - _GOAL_RISK_EXTRA[profile.goal] * risk_index
                + _GOAL_MOMENTUM[profile.goal] * (momentum["value"] - 50))
        scored.append({"report": report, "env": env, "rank_score": round(rank, 1),
                       "risk_index": risk_index, "momentum": momentum,
                       "code": code, "name": name, "lat": lat, "lon": lon})

    scored.sort(key=lambda x: (-x["rank_score"], x["code"]))

    hotspots = []
    for i, s in enumerate(scored[:top_n], start=1):
        r = s["report"]
        gap = _competition_gap(r)
        top_factors = sorted(r.factors, key=lambda f: -f.score)[:2]
        hotspots.append({
            "rank": i,
            "kommun": s["name"], "kommun_kod": s["code"],
            "lat": s["lat"], "lon": s["lon"],
            "opportunity_score": r.opportunity_score,
            "rank_score": s["rank_score"],
            "confidence": _confidence(r),
            "risk_index": s["risk_index"],
            "risk_level": r.risk_level,
            "market_momentum": s["momentum"],
            "competition_gap": gap,
            "time_window_months": _time_window(s["momentum"]["value"],
                                               gap["ratio"]),
            "environment": s["env"],
            "drivers": _drivers(r, profile.vertical_id),
            "motivering_sv": [f.narrative_sv for f in top_factors] + r.insights_sv,
            "factors": [{"id": f.id, "label_sv": f.label_sv, "score": f.score}
                        for f in r.factors],
            "economy_scenario": _economy_scenario(profile, r.opportunity_score),
            "expected_roi": dict(_ROI_UNAVAILABLE),
            "data_coverage": r.data_coverage,
            "next_steps_sv": list(_NEXT_STEPS_SV),
        })

    caveats = [
        "Sverigesvepet omfattar i denna version 40 större kommuner – "
        "fler kandidatorter och finmaskigare rutnät kommer med geodatafasen.",
        "Rankjustering och tidsfönster är dokumenterade heuristiker, "
        "inte prediktioner.",
    ]
    if hotspots and max(h["data_coverage"] for h in hotspots) < 1.0:
        caveats.append("Delar av underlaget bygger på simulerad data – se "
                       "data_coverage per hotspot.")

    return {
        "profile": profile.to_dict(),
        "vertical_label_sv": VERTICALS[profile.vertical_id].label_sv,
        "candidates_scanned": len(heatmap),
        "excluded": excluded,
        "heatmap": heatmap,
        "hotspots": hotspots,
        "caveats_sv": caveats,
    }
