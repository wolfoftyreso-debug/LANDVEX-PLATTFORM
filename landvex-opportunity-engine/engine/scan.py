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

from .commission import commission_for_lead
from .specialization import specialization_boost, specialization_def
from .datasources.base import Resolver
from .datasources.scb import _haversine_km
from .markets import DEFAULT_MARKET, get_market, plural_region_label
from .models import Location
from .profile import BusinessProfile, WORK_STYLE_SIGNALS
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
    "cafe": 800, "bygg": 1800, "tandlakare": 1600, "bilverkstad": 1200,
    "veterinar": 1300, "lager": 1500, "vvs": 1450,
    "forskola": 650, "apotek": 2200, "optiker": 1400, "bageri": 850,
    "livsmedel": 4500, "aldreomsorg": 550, "stadfirma": 550,
    "malare": 950, "laddinfra": 2000, "cykelverkstad": 900,
    "generisk": 1000}
_STARTUP_TKR = {
    "frisor": (150, 600), "elektriker": (100, 500), "gym": (1500, 6000),
    "restaurang": (800, 4000), "cafe": (400, 1500), "bygg": (200, 1000),
    "tandlakare": (1500, 5000), "bilverkstad": (500, 2500),
    "veterinar": (800, 3000), "lager": (1000, 10000),
    "vvs": (150, 600),
    "forskola": (500, 2500), "apotek": (1500, 4000), "optiker": (600, 2000),
    "bageri": (600, 2000), "livsmedel": (2000, 8000),
    "aldreomsorg": (200, 1000), "stadfirma": (50, 300),
    "malare": (100, 400), "laddinfra": (1000, 6000),
    "cykelverkstad": (200, 800), "generisk": (300, 2000)}
_TEAM_PERSONS = {"1": 1, "2-5": 3, "5-20": 10, "20-50": 30, "50+": 60}
_BUDGET_TKR = {"0-500k": (0, 500), "500k-2m": (500, 2000),
               "2-5m": (2000, 5000), "5-10m": (5000, 10000),
               "10m+": (10000, 100000)}

_NEXT_STEPS_EN = ["Find premises", "Financing", "Recruitment",
                  "Building permits", "Startup budget", "Suppliers",
                  "Contact the municipality"]

# ── Analysnivåer ─────────────────────────────────────────────────────
# oversikt: en punkt per kommun (centroiden).
# detaljerad: centroid + fyra kringpunkter (~3 km) → finmaskigare
# värmekarta och bästa läget inom kommunen väljs för hotspot-kortet.
SCAN_LEVELS: dict[str, tuple[tuple[float, float, str], ...]] = {
    "oversikt": ((0.0, 0.0, "centrum"),),
    "detaljerad": ((0.0, 0.0, "centrum"),
                   (0.030, 0.0, "norr"), (-0.030, 0.0, "soder"),
                   (0.0, 0.060, "oster"), (0.0, -0.060, "vaster")),
}
SCAN_LEVEL_OPTIONS = [
    {"id": "oversikt", "label_en": "Overview – one point per municipality"},
    {"id": "detaljerad", "label_en": "Detailed – five points per municipality"},
]
_POINT_LABEL_EN = {"centrum": "center", "norr": "northern part",
                   "soder": "southern part", "oster": "eastern part",
                   "vaster": "western part"}


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
    text = {"forbattras": "The market is improving – high development activity.",
            "stabil": "The market is stable.",
            "forsvagas": "The market is weakening – low development activity."}[direction]
    return {"value": value, "direction": direction, "text_en": text}


def _competition_gap(report) -> dict[str, Any]:
    gap = _sig(report, "provider_gap")
    ratio = round(gap["value"], 2) if gap else None
    if ratio is None:
        return {"ratio": None, "text_en": "No data available."}
    if ratio >= 1.3:
        text = "Clear shortage of providers – demand exceeds supply."
    elif ratio >= 0.95:
        text = "Supply and demand in balance."
    else:
        text = "Surplus of providers – saturated market."
    return {"ratio": ratio, "text_en": text}


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
        scored.append({"signal_id": sid, "label_en": d.label_en,
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
        fit = "The budget is below the typical startup capital for the industry."
    elif b_lo > hi_start:
        fit = "The budget covers typical startup capital with a good margin."
    else:
        fit = "The budget is within the typical startup capital range."
    return {
        "omsattningsscenario_tkr_ar": revenue,
        "startkapital_typiskt_tkr": [lo_start, hi_start],
        "budget_fit_en": fit,
        "notis_en": "Standard-estimate scenario based on industry benchmarks "
                    "and the location's score – NOT a forecast. Calibrated "
                    "against outcome data in v2.",
    }


# Publika namn (används av ask-, gap- och planmodulerna).
economy_scenario = _economy_scenario
momentum_of = _momentum
TEAM_PERSONS = _TEAM_PERSONS
STARTUP_TKR = _STARTUP_TKR

_ROI_UNAVAILABLE = {
    "status": "ej_tillgangligt",
    "notis_en": "Expected ROI is reported once outcome data exists (v2/v3). "
                "Guessing would violate the principle of explainability "
                "before prediction.",
}


def _stars(score: float) -> int:
    """Opportunity Score (0–100) → 1–5 stjärnor."""
    return max(1, min(5, int(round(score / 20.0))))


def _outlook_2y(report, momentum: dict) -> dict[str, Any]:
    """2-årsprognos för efterfrågan – tydligt märkt heuristik, aldrig
    en sanning. 'Idag X → om två år Y', med de starkaste
    tillväxtdrivarna som anledning (klickbara tillbaka via signalerna).
    """
    today = momentum["value"]
    # Tillväxtstyrka: hur långt momentum ligger från neutralt (50).
    strength = (today - 50) / 50.0                 # -1 … 1
    in_2y = int(round(max(0, min(100, today + strength * 18))))
    reasons = []
    for sid in _MOMENTUM_SIGNALS:
        sig = report.signals.get(sid)
        if not sig or sig.get("normalized", 0) < 0.55:
            continue
        d = CATALOG[sid]
        reasons.append({"signal_id": sid, "label_en": d.label_en,
                        "value": sig["value"], "unit": d.unit,
                        "source": sig["source"]})
    reasons.sort(key=lambda r: -report.signals[r["signal_id"]]["normalized"])
    return {
        "demand_today": today, "demand_in_2y": in_2y,
        "direction": momentum["direction"],
        "reasons": reasons[:5],
        "notis_en": ("Heuristic 2-year projection from current growth "
                     "signals – a scenario, not a forecast. Widens/narrows "
                     "as real time-series data connects."),
    }


def _band(score: float) -> str:
    return "gron" if score >= 70 else "gul" if score >= 45 else "rod"


def scan(profile: BusinessProfile, resolver: Resolver | None = None,
         candidates: list[tuple[str, str, float, float]] | None = None,
         top_n: int = 5, level: str = "oversikt",
         market: str = DEFAULT_MARKET) -> dict[str, Any]:
    """Analyserar kandidatorter mot profilen. Returnerar JSON-redo dict."""
    if level not in SCAN_LEVELS:
        raise ValueError(f"Unknown scan level: {level}. "
                         f"Available: {', '.join(SCAN_LEVELS)}")
    mkt = get_market(market)
    cands = candidates if candidates is not None else list(mkt.regions)
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

    points = [(code, name, plabel, round(lat + dlat, 3), round(lon + dlon, 3))
              for code, name, lat, lon in cands
              for dlat, dlon, plabel in SCAN_LEVELS[level]]

    # Specialiseringen omfördelar faktorvikterna → personlig score.
    boost = specialization_boost(profile.vertical_id, profile.specialization)
    _spec_def = specialization_def(profile.vertical_id, profile.specialization)
    spec_label = _spec_def.label_en if _spec_def else ""

    heatmap: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []
    for code, name, plabel, lat, lon in points:
        report = analyze(Location(lat, lon, address=name), profile.vertical_id,
                         resolver=resolver, factor_boost=boost)
        env = classify_environment(report)
        heatmap.append({"kommun": name, "kommun_kod": code, "punkt": plabel,
                        "lat": lat, "lon": lon,
                        "score": report.opportunity_score,
                        "band": _band(report.opportunity_score)})
        if profile.environments and not set(profile.environments) & set(env):
            excluded["miljo"] += 1
            continue

        risk_index = int(round(report.risk_score * 100))
        momentum = _momentum(report)
        # Arbetssätt tiltar rankningen mot de signaler nischen lever på
        # (aldrig grundscoren). Normaliserat signalvärde 0–1 × vikt.
        ws_tilt = 0.0
        for sid, w in WORK_STYLE_SIGNALS.get(profile.work_style or "", {}).items():
            sig = report.signals.get(sid)
            if sig and sig.get("normalized") is not None:
                ws_tilt += w * sig["normalized"]
        rank = (report.opportunity_score
                - _RISK_PENALTY[profile.risk_tolerance] * risk_index
                - _GOAL_RISK_EXTRA[profile.goal] * risk_index
                + _GOAL_MOMENTUM[profile.goal] * (momentum["value"] - 50)
                + ws_tilt)
        scored.append({"report": report, "env": env, "rank_score": round(rank, 1),
                       "risk_index": risk_index, "momentum": momentum,
                       "code": code, "name": name, "punkt": plabel,
                       "lat": lat, "lon": lon})

    # Bästa punkten per kommun representerar kommunen i rankingen.
    best_per_kommun: dict[str, dict[str, Any]] = {}
    for s in scored:
        b = best_per_kommun.get(s["code"])
        if b is None or (s["rank_score"], s["punkt"]) > (b["rank_score"], b["punkt"]):
            best_per_kommun[s["code"]] = s
    ranked = sorted(best_per_kommun.values(),
                    key=lambda x: (-x["rank_score"], x["code"]))

    # Percentil: hur stor andel av regionerna denna plats slår på
    # opportunity-score. Kärnan i "du har större chans att lyckas här
    # än X %" – en ärlig plats-percentil av de beräknade scoren (inte
    # påhittad folkstatistik).
    alla_score = sorted(s["report"].opportunity_score for s in ranked)
    n_regioner = len(alla_score)

    def _percentil(sc: float) -> int:
        lagre = sum(1 for x in alla_score if x < sc)
        return int(round(100 * lagre / n_regioner)) if n_regioner else 0

    hotspots = []
    for i, s in enumerate(ranked[:top_n], start=1):
        r = s["report"]
        gap = _competition_gap(r)
        top_factors = sorted(r.factors, key=lambda f: -f.score)[:2]
        hotspots.append({
            "rank": i,
            "kommun": s["name"], "kommun_kod": s["code"],
            "punkt": s["punkt"],
            "lage_en": f"{s['name']}, {_POINT_LABEL_EN[s['punkt']]}",
            "lat": s["lat"], "lon": s["lon"],
            "opportunity_score": r.opportunity_score,
            "stars": _stars(r.opportunity_score),
            "outlook_2y": _outlook_2y(r, s["momentum"]),
            "rank_score": s["rank_score"],
            # Percentil + personlig mening: "du slår X % av lägena".
            "percentile": _percentil(r.opportunity_score),
            "percentile_en": (
                f"Beats {_percentil(r.opportunity_score)}% of "
                f"{n_regioner} locations in {mkt.label_en} for your "
                f"profile" + (f" ({spec_label})" if spec_label else "") + "."),
            # Kommission per lead (quiXzoom QZ TOKEN), graderad av score.
            "commission": commission_for_lead(r.opportunity_score),
            "confidence": _confidence(r),
            "risk_index": s["risk_index"],
            "risk_level": r.risk_level,
            "market_momentum": s["momentum"],
            "competition_gap": gap,
            "time_window_months": _time_window(s["momentum"]["value"],
                                               gap["ratio"]),
            "environment": s["env"],
            "drivers": _drivers(r, profile.vertical_id),
            "motivering_en": [f.narrative_en for f in top_factors] + r.insights_en,
            "factors": [{"id": f.id, "label_en": f.label_en, "score": f.score}
                        for f in r.factors],
            "economy_scenario": (
                _economy_scenario(profile, r.opportunity_score)
                if mkt.calibrated else
                {"status": "ej_kalibrerad",
                 "notis_en": f"Economic standard estimates are not "
                             f"calibrated for {mkt.label_en} yet – "
                             f"not reported."}),
            "expected_roi": dict(_ROI_UNAVAILABLE),
            "data_coverage": r.data_coverage,
            "next_steps_en": list(_NEXT_STEPS_EN),
        })

    caveats = [
        f"The scan of {mkt.label_en} covers {len(mkt.regions)} "
        f"{plural_region_label(mkt.region_label_en)} in this version – more "
        f"candidate locations and a finer grid come with the geodata phase.",
        "Rank adjustment and time window are documented heuristics, "
        "not predictions.",
    ]
    if hotspots and max(h["data_coverage"] for h in hotspots) < 1.0:
        caveats.append("Parts of the underlying data are simulated – see "
                       "data_coverage per hotspot.")

    return {
        "profile": profile.to_dict(),
        "vertical_label_en": VERTICALS[profile.vertical_id].label_en,
        "specialization": ({"id": _spec_def.id, "label_en": _spec_def.label_en,
                            "notis_en": _spec_def.notis_en}
                           if _spec_def else None),
        "market": mkt.id, "market_label_en": mkt.label_en,
        "bbox": list(mkt.bbox),
        "level": level,
        "candidates_scanned": len(heatmap),
        "kommuner_scanned": len(cands),
        "excluded": excluded,
        "heatmap": heatmap,
        "hotspots": hotspots,
        "caveats_en": caveats,
    }
