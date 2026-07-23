"""Workforce Intelligence Engine – kompetensprognoser per kommun.

Besvarar: "Vilka yrken kommer den här kommunen att behöva – baserat
på data, inte gissningar?" För kommuner, regioner, utbildningsaktörer
och investerare. Delar datakällslager (Resolver/SCB/mock) med
Opportunity Engine – samma signaler driver båda motorerna.

Modellen är transparent och regelbaserad (samma filosofi som
scoringmotorns v1 – ML kommer när utfallsdata finns):

  behov_nu       = yrkestäthet (per 1000 inv, branschschablon) × befolkning
  efterfrågetakt = viktad kombination av yrkets drivsignaler
                   (byggtakt, exploatering, demografi, ...) – dokumenterad
  behov_år(t)    = behov_nu × (1 + takt)^t
  styrka_år(t+1) = styrka_år(t) × (1 − pensionstakt) + utbildningsinflöde
  brist          = behov_horisont − styrka_horisont

VIKTIGT (ärlighetsprincipen): resultat presenteras aldrig som absoluta
sanningar. Varje prognos bär konfidensintervall (bredd växer med
horisont och sjunker med datakvalitet), konfidensnivå (märkt
heuristik) och en explicit antagandelista med de faktiska värden
modellen använde. Teknikskiften, migration, konjunktur och politik
ligger utanför modellen – det står i varje svar.

Yrkeskatalogen är data: nytt yrke = ny rad, inga motorändringar.
Schablonerna (täthet, pensionstakt, utbildningsplatser) kalibreras
mot SCB:s yrkesregister och Skolverket i produktionsfasen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.mock import MockSource
from .markets import (DEFAULT_MARKET, GROUP_BBOX, GROUP_LABEL_SV, MARKET_GROUPS,
                      get_market, get_region)
from .models import Location
from .signals import CATALOG, normalize

BASE_YEAR = 2026            # prognosens basår (dokumenterat antagande)
MAX_HORIZON_YEARS = 20
COMPLETION_RATE = 0.85      # examensgrad, schablon
_DEFAULT_RESOLVER = Resolver([MockSource()])


@dataclass(frozen=True)
class Occupation:
    id: str
    label_en: str
    sector_en: str
    per_1000: float           # sysselsatta per 1000 invånare (schablon)
    pension_rate: float       # årlig avgångstakt (schablon)
    edu_per_100k: float       # utbildningsplatser/år per 100k inv (schablon)
    salary_tkr_month: float   # medellön tkr/mån (schablon, lönestatistiknivå)
    automation_risk: float    # 0..1 automations-/AI-exponering (schablon)
    drivers: tuple            # ((signal_id, vikt), ...) – efterfrågedrivare


def _o(id, label, sector, per_1000, pension, edu, salary, autom, *drivers):
    return Occupation(id, label, sector, per_1000, pension, edu,
                      salary, autom, tuple(drivers))


OCCUPATIONS: dict[str, Occupation] = {o.id: o for o in [
    _o("elektriker", "Electrician", "Construction & installation", 3.8, 0.028, 6.0, 38, 0.20,
       ("building_permits", 0.30), ("development_m2", 0.20),
       ("infra_invest", 0.15), ("ev_per_capita", 0.15), ("pop_growth_pct", 0.20)),
    _o("vvs_montor", "Plumbing & HVAC fitter", "Construction & installation", 2.0, 0.030, 3.0, 37, 0.20,
       ("building_permits", 0.40), ("development_m2", 0.25),
       ("infra_invest", 0.15), ("pop_growth_pct", 0.20)),
    _o("snickare", "Carpenter", "Construction & installation", 6.5, 0.032, 8.0, 36, 0.30,
       ("building_permits", 0.45), ("development_m2", 0.25), ("pop_growth_pct", 0.30)),
    _o("betongarbetare", "Concrete worker", "Civil engineering", 1.2, 0.035, 1.5, 35, 0.50,
       ("development_m2", 0.40), ("infra_invest", 0.35), ("detail_plans", 0.25)),
    _o("plattsattare", "Tiler", "Construction & installation", 0.8, 0.030, 1.0, 35, 0.30,
       ("building_permits", 0.50), ("renovation_index", 0.30), ("pop_growth_pct", 0.20)),
    _o("maskinforare", "Construction equipment operator", "Civil engineering", 2.4, 0.034, 3.0, 36, 0.55,
       ("infra_invest", 0.40), ("development_m2", 0.35), ("detail_plans", 0.25)),
    _o("arkitekt", "Architect", "Urban development", 1.1, 0.022, 1.2, 47, 0.30,
       ("detail_plans", 0.40), ("development_m2", 0.35), ("pop_growth_pct", 0.25)),
    _o("ingenjor_bygg", "Construction engineer", "Urban development", 3.0, 0.025, 4.0, 48, 0.25,
       ("development_m2", 0.30), ("infra_invest", 0.30),
       ("business_density", 0.20), ("detail_plans", 0.20)),
    _o("larare", "Teacher (compulsory school)", "Education", 11.0, 0.030, 12.0, 38, 0.10,
       ("families_share", 0.50), ("pop_growth_pct", 0.50)),
    _o("forskollarare", "Preschool teacher", "Education", 5.5, 0.028, 7.0, 34, 0.08,
       ("families_share", 0.60), ("pop_growth_pct", 0.40)),
    _o("sjukskoterska", "Nurse", "Health & social care", 11.5, 0.032, 13.0, 40, 0.10,
       ("share_65plus", 0.55), ("pop_growth_pct", 0.45)),
    _o("fastighetstekniker", "Property technician", "Operations & property", 1.8, 0.033, 2.0, 35, 0.30,
       ("residential_density", 0.40), ("development_m2", 0.30), ("pop_growth_pct", 0.30)),
    _o("drifttekniker", "Operations technician", "Operations & property", 1.5, 0.030, 2.0, 38, 0.35,
       ("business_density", 0.40), ("infra_invest", 0.30), ("development_m2", 0.30)),
    _o("kyltekniker", "Refrigeration & heat pump technician", "Operations & installation",
       0.6, 0.030, 0.8, 39, 0.15,
       ("detached_homes", 0.35), ("renovation_index", 0.25),
       ("ev_per_capita", 0.20), ("pop_growth_pct", 0.20)),
    _o("underskoterska", "Assistant nurse", "Health & social care", 13.0, 0.033, 15.0, 32, 0.12,
       ("share_65plus", 0.55), ("pop_growth_pct", 0.45)),
    _o("barnskotare", "Childcare assistant", "Education", 6.0, 0.028, 8.0, 29, 0.10,
       ("families_share", 0.60), ("pop_growth_pct", 0.40)),
    _o("kock", "Chef", "Hospitality", 4.0, 0.030, 5.0, 32, 0.15,
       ("tourism_index", 0.30), ("foot_traffic", 0.30), ("pop_growth_pct", 0.40)),
    _o("lastbilsforare", "Truck driver", "Transport & logistics", 5.5, 0.035, 6.0, 35, 0.60,
       ("logistics_access", 0.40), ("business_density", 0.30), ("pop_growth_pct", 0.30)),
    _o("svetsare", "Welder", "Manufacturing", 2.2, 0.034, 2.5, 36, 0.45,
       ("business_density", 0.40), ("infra_invest", 0.30), ("development_m2", 0.30)),
    _o("malare", "Painter", "Construction & installation", 2.8, 0.031, 3.5, 34, 0.25,
       ("renovation_index", 0.40), ("building_permits", 0.30), ("pop_growth_pct", 0.30)),
    _o("it_tekniker", "IT technician", "IT & digital", 4.0, 0.020, 6.0, 42, 0.35,
       ("business_density", 0.50), ("office_workers", 0.50)),
]}


def occupation_catalog() -> list[dict[str, Any]]:
    return [{"id": o.id, "label_en": o.label_en, "sector_en": o.sector_en,
             "medellon_tkr_manad": o.salary_tkr_month,
             "automationsrisk_schablon": o.automation_risk}
            for o in OCCUPATIONS.values()]


def _needed_signals(occ_ids: list[str]) -> list[str]:
    need = {"population_total", "pop_growth_pct"}
    for oid in occ_ids:
        need.update(sid for sid, _ in OCCUPATIONS[oid].drivers)
    return sorted(need)


def _resolve(region_kod: str, occ_ids: list[str],
             resolver: Resolver | None, market: str) -> tuple[dict, dict, tuple]:
    reg = get_region(market, region_kod)
    res = resolver or _DEFAULT_RESOLVER
    values, extras = res.resolve(Location(reg[2], reg[3], address=reg[1]),
                                 "workforce", _needed_signals(occ_ids))
    return values, extras, reg


def _demand_growth(occ: Occupation, values: dict) -> tuple[float, list[dict]]:
    """Årlig efterfrågetakt + per-drivare-redovisning (transparens)."""
    parts, growth = [], 0.0
    for sid, w in occ.drivers:
        sv = values.get(sid)
        if sv is None or sv.value is None:
            continue
        if sid == "pop_growth_pct":
            g = max(-3.0, min(3.0, sv.value)) / 100.0
        else:
            # Normaliserad aktivitet kring neutralpunkt 0.5 → −2..+2 %/år.
            g = (normalize(CATALOG[sid], sv.value) - 0.5) * 0.04
        growth += w * g
        parts.append({"signal_id": sid, "label_en": CATALOG[sid].label_en,
                      "varde": sv.value, "enhet": CATALOG[sid].unit,
                      "kalla": sv.source, "bidrag_pct_ar": round(100 * w * g, 2)})
    return max(-0.02, min(0.06, growth)), parts


def _trajectory(need_now: float, growth: float, pension: float,
                edu_per_year: float, horizon: int) -> list[dict[str, float]]:
    """Årsvis behov/styrka/gap. Antagande: balans vid basåret."""
    workforce = need_now
    out = []
    for t in range(1, horizon + 1):
        need = need_now * (1 + growth) ** t
        workforce = workforce * (1 - pension) + edu_per_year
        out.append({"ar": BASE_YEAR + t, "behov": round(need),
                    "styrka": round(workforce), "gap": round(need - workforce)})
    return out


def _quality(values: dict, sids: list[str]) -> float:
    qs = [values[s].quality for s in sids if s in values]
    return sum(qs) / len(qs) if qs else 0.0


def _confidence(quality: float, horizon: int) -> int:
    """Heuristik: datakvalitet upp, horisont ner. INTE en sannolikhet."""
    return int(round(100 * (0.30 + 0.45 * quality +
                            0.25 * max(0.0, 1 - horizon / MAX_HORIZON_YEARS))))


def _band(gap: float, need: float) -> str:
    share = gap / need if need > 0 else 0.0
    if share <= 0.05:
        return "balans"
    return "okande_brist" if share <= 0.15 else "kritisk_brist"


def _demand_band(gap: float, need: float) -> str:
    """Efterfrågeband för Opportunity Map: mättad→växande→hög→extrem."""
    share = gap / need if need > 0 else 0.0
    if share <= 0.05:
        return "mattad"
    if share <= 0.15:
        return "vaxande"
    return "hog" if share <= 0.25 else "extrem"


def _trend(growth: float) -> str:
    if growth >= 0.005:
        return "rising"
    return "declining" if growth <= -0.005 else "stable"


_CAVEATS = [
    "The forecast is model-computed, not a truth: technology shifts, "
    "migration, business cycles and policy decisions are outside the model.",
    "Occupation density, retirement rates and education places are industry "
    "standard estimates until SCB's occupational register and Skolverket "
    "data are connected.",
    "The confidence level is a documented heuristic (data quality × "
    "horizon), not a statistical probability.",
]

_BAND_LABEL_EN = {"balans": "balance", "okande_brist": "growing shortage",
                  "kritisk_brist": "critical shortage"}


def _forecast_one(occ: Occupation, values: dict, horizon: int,
                  extra_places_per_year: float = 0.0) -> dict[str, Any]:
    pop_en = values.get("population_total")
    if pop_en is None or not pop_en.value:
        raise ValueError("Population data missing.")
    pop = pop_en.value
    need_now = occ.per_1000 * pop / 1000.0
    growth, driver_parts = _demand_growth(occ, values)
    edu = (occ.edu_per_100k * pop / 100000.0 + extra_places_per_year) * COMPLETION_RATE
    # Full 20-årsbana beräknas alltid → milstolpar på 1/3/5/10/20 år
    # (strategisk planering); bana/brist rapporteras för valt målår.
    full = _trajectory(need_now, growth, occ.pension_rate, edu,
                       MAX_HORIZON_YEARS)
    traj = full[:horizon]
    last = traj[-1]
    milestones = [{"horisont_ar": h, "ar": full[h - 1]["ar"],
                   "behov": full[h - 1]["behov"], "gap": full[h - 1]["gap"]}
                  for h in (1, 3, 5, 10, 20)]
    need_h, gap = last["behov"], last["gap"]

    used = ["population_total"] + [p["signal_id"] for p in driver_parts]
    q = _quality(values, used)
    half = need_h * (0.06 + 0.012 * horizon + 0.18 * (1 - q))
    assumptions = [
        {"antagande_en": "Base year and balance assumption",
         "varde_en": f"The workforce is assumed to match demand in "
                     f"{BASE_YEAR}."},
        {"antagande_en": "Population (municipality)",
         "varde_en": f"{int(pop)} residents (source: {pop_en.source})."},
        {"antagande_en": "Demand growth rate",
         "varde_en": f"{round(100 * growth, 2)}%/year, derived from the "
                     f"driver signals below."},
        {"antagande_en": "Retirement outflow",
         "varde_en": f"{round(100 * occ.pension_rate, 1)}%/year "
                     f"(standard estimate)."},
        {"antagande_en": "Education inflow",
         "varde_en": f"{round(edu)} graduates/year "
                     f"(standard estimate"
                     f"{', incl. simulated places' if extra_places_per_year else ''}, "
                     f"completion rate {int(COMPLETION_RATE * 100)}%)."},
    ]
    return {
        "occupation_id": occ.id, "label_en": occ.label_en,
        "sector_en": occ.sector_en,
        "behov_nu": round(need_now),
        "behov_prognos": need_h,
        "styrka_prognos": last["styrka"],
        "brist": gap,
        "intervall": [round(need_h - half), round(need_h + half)],
        "konfidens": _confidence(q, horizon),
        "band": _band(gap, need_h),
        "efterfragan": _demand_band(gap, need_h),
        "trend": _trend(growth),
        "pensionsavgangar": round(need_now * (1 - (1 - occ.pension_rate) ** horizon)),
        "medellon_tkr_manad": occ.salary_tkr_month,
        "automationsrisk_schablon": occ.automation_risk,
        "efterfragetakt_pct_ar": round(100 * growth, 2),
        "drivare": driver_parts,
        "antaganden": assumptions,
        "bana": traj,
        "milstolpar": milestones,
    }


def forecast(kommun_kod: str, target_year: int = 2035,
             occupation_ids: list[str] | None = None,
             resolver: Resolver | None = None,
             market: str = DEFAULT_MARKET) -> dict[str, Any]:
    """Kompetensprognos för en region, alla (eller valda) yrken."""
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= MAX_HORIZON_YEARS:
        raise ValueError(f"Target year must be between {BASE_YEAR + 1} "
                         f"and {BASE_YEAR + MAX_HORIZON_YEARS}.")
    occ_ids = occupation_ids or list(OCCUPATIONS)
    unknown = [o for o in occ_ids if o not in OCCUPATIONS]
    if unknown:
        raise ValueError(f"Unknown occupations: {unknown}")
    values, _, kom = _resolve(kommun_kod, occ_ids, resolver, market)

    forecasts = [_forecast_one(OCCUPATIONS[oid], values, horizon)
                 for oid in occ_ids]
    forecasts.sort(key=lambda f: -f["brist"])

    # Prioriterad utbildningslista: relativ brist väger tyngst,
    # absolut volym bryter lika.
    prio = sorted((f for f in forecasts if f["brist"] > 0),
                  key=lambda f: (-(f["brist"] / max(f["behov_prognos"], 1)),
                                 -f["brist"]))
    priorities = [{
        "rang": i,
        "occupation_id": f["occupation_id"], "label_en": f["label_en"],
        "brist": f["brist"], "band": f["band"],
        "motivering_en": (
            f"Estimated shortage of {f['brist']} {f['label_en'].lower()}(s) "
            f"by {target_year} ({_BAND_LABEL_EN[f['band']]}). Largest driver: "
            f"{max(f['drivare'], key=lambda d: d['bidrag_pct_ar'])['label_en'].lower()}."
            if f["drivare"] else
            f"Estimated shortage of {f['brist']} by {target_year}."),
    } for i, f in enumerate(prio[:5], start=1)]

    coverage = (sum(1 for s in values.values() if s.source != "mock") /
                max(1, len(values)))
    mkt = get_market(market)
    return {
        "kommun": kom[1], "kommun_kod": kom[0],
        "market": mkt.id, "market_label_en": mkt.label_en,
        "basar": BASE_YEAR, "malar": target_year,
        "prognoser": forecasts,
        "utbildningsprioriteringar": priorities,
        "data_coverage": round(coverage, 2),
        "caveats_en": list(_CAVEATS),
    }


def simulate(kommun_kod: str, occupation_id: str,
             extra_places_per_year: float, target_year: int = 2035,
             resolver: Resolver | None = None,
             market: str = DEFAULT_MARKET) -> dict[str, Any]:
    """Utbildningssimulering: 'om vi startar X platser/år – vad händer?'"""
    if occupation_id not in OCCUPATIONS:
        raise ValueError(f"Unknown occupation: {occupation_id}")
    if extra_places_per_year < 0:
        raise ValueError("Number of places cannot be negative.")
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= MAX_HORIZON_YEARS:
        raise ValueError(f"Target year must be between {BASE_YEAR + 1} "
                         f"and {BASE_YEAR + MAX_HORIZON_YEARS}.")
    values, _, kom = _resolve(kommun_kod, [occupation_id], resolver, market)
    occ = OCCUPATIONS[occupation_id]
    base = _forecast_one(occ, values, horizon)
    sim = _forecast_one(occ, values, horizon,
                        extra_places_per_year=extra_places_per_year)
    balanced = next((p["ar"] for p in sim["bana"] if p["gap"] <= 0), None)
    return {
        "kommun": kom[1], "kommun_kod": kom[0],
        "occupation_id": occupation_id, "label_en": occ.label_en,
        "malar": target_year,
        "extra_platser_per_ar": extra_places_per_year,
        "brist_utan_atgard": base["brist"],
        "brist_med_atgard": sim["brist"],
        "minskning": base["brist"] - sim["brist"],
        "balansar": balanced,
        "bana_utan": base["bana"], "bana_med": sim["bana"],
        "konfidens": sim["konfidens"],
        "caveats_en": list(_CAVEATS),
    }


def national_map(occupation_id: str, target_year: int = 2035,
                 resolver: Resolver | None = None,
                 market: str = DEFAULT_MARKET) -> dict[str, Any]:
    """Marknadskarta: kompetensbalans per region för ett yrke."""
    if occupation_id not in OCCUPATIONS:
        raise ValueError(f"Unknown occupation: {occupation_id}")
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= MAX_HORIZON_YEARS:
        raise ValueError(f"Target year must be between {BASE_YEAR + 1} "
                         f"and {BASE_YEAR + MAX_HORIZON_YEARS}.")
    mkt = get_market(market)
    occ = OCCUPATIONS[occupation_id]
    res = resolver or _DEFAULT_RESOLVER
    needed = _needed_signals([occupation_id])
    kommuner = []
    for code, name, lat, lon in mkt.regions:
        values, _ = res.resolve(Location(lat, lon, address=name),
                                "workforce", needed)
        f = _forecast_one(occ, values, horizon)
        kommuner.append({"kommun": name, "kommun_kod": code,
                         "market": mkt.id, "market_label_en": mkt.label_en,
                         "lat": lat, "lon": lon,
                         "behov_prognos": f["behov_prognos"],
                         "brist": f["brist"], "band": f["band"],
                         "efterfragan": f["efterfragan"],
                         "trend": f["trend"],
                         "konfidens": f["konfidens"]})
    kommuner.sort(key=lambda k: -k["brist"])
    return {"occupation_id": occupation_id, "label_en": occ.label_en,
            "market": mkt.id, "market_label_en": mkt.label_en,
            "bbox": list(mkt.bbox),
            "basar": BASE_YEAR, "malar": target_year,
            "kommuner": kommuner, "caveats_en": list(_CAVEATS)}


def global_map(occupation_id: str, target_year: int = 2035,
               group: str = "eu",
               resolver: Resolver | None = None) -> dict[str, Any]:
    """Flerlandskarta: samma modell, alla marknader i gruppen.

    Gemensam Opportunity Score över länder är möjlig eftersom
    signalkatalogen äger normaliseringen – inte länderna.
    """
    if group not in MARKET_GROUPS:
        raise ValueError(f"Unknown market group: {group}. "
                         f"Available: {', '.join(MARKET_GROUPS)}")
    regions: list[dict[str, Any]] = []
    for mid in MARKET_GROUPS[group]:
        res = national_map(occupation_id, target_year,
                           resolver=resolver, market=mid)
        regions.extend(res["kommuner"])
    regions.sort(key=lambda k: -k["brist"])

    # Landsranking: genomsnittlig relativ brist per marknad.
    per_market: dict[str, list[float]] = {}
    for r in regions:
        share = r["brist"] / max(r["behov_prognos"], 1)
        per_market.setdefault(r["market"], []).append(share)
    ranking = sorted(
        ({"market": mid, "market_label_en": get_market(mid).label_en,
          "snitt_brist_pct": round(100 * sum(sh) / len(sh), 1),
          "regioner": len(sh)}
         for mid, sh in per_market.items()),
        key=lambda x: -x["snitt_brist_pct"])

    occ = OCCUPATIONS[occupation_id]
    return {"occupation_id": occupation_id, "label_en": occ.label_en,
            "group": group, "group_label_en": GROUP_LABEL_SV[group],
            "bbox": list(GROUP_BBOX[group]),
            "basar": BASE_YEAR, "malar": target_year,
            "regioner": regions, "landsranking": ranking,
            "caveats_en": list(_CAVEATS) + [
                "Only Sweden has real data sources connected so far – "
                "other markets run on simulated data until local adapters "
                "(Destatis, Eurostat, Census, etc.) are in place."]}
