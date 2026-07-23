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
from .markets import (GROUP_BBOX, GROUP_LABEL_SV, MARKET_GROUPS,
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
    label_sv: str
    sector_sv: str
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
    _o("elektriker", "Elektriker", "Bygg & installation", 3.8, 0.028, 6.0, 38, 0.20,
       ("building_permits", 0.30), ("development_m2", 0.20),
       ("infra_invest", 0.15), ("ev_per_capita", 0.15), ("pop_growth_pct", 0.20)),
    _o("vvs_montor", "VVS-montör", "Bygg & installation", 2.0, 0.030, 3.0, 37, 0.20,
       ("building_permits", 0.40), ("development_m2", 0.25),
       ("infra_invest", 0.15), ("pop_growth_pct", 0.20)),
    _o("snickare", "Snickare", "Bygg & installation", 6.5, 0.032, 8.0, 36, 0.30,
       ("building_permits", 0.45), ("development_m2", 0.25), ("pop_growth_pct", 0.30)),
    _o("betongarbetare", "Betongarbetare", "Anläggning", 1.2, 0.035, 1.5, 35, 0.50,
       ("development_m2", 0.40), ("infra_invest", 0.35), ("detail_plans", 0.25)),
    _o("plattsattare", "Plattsättare", "Bygg & installation", 0.8, 0.030, 1.0, 35, 0.30,
       ("building_permits", 0.50), ("renovation_index", 0.30), ("pop_growth_pct", 0.20)),
    _o("maskinforare", "Anläggningsmaskinförare", "Anläggning", 2.4, 0.034, 3.0, 36, 0.55,
       ("infra_invest", 0.40), ("development_m2", 0.35), ("detail_plans", 0.25)),
    _o("arkitekt", "Arkitekt", "Samhällsbyggnad", 1.1, 0.022, 1.2, 47, 0.30,
       ("detail_plans", 0.40), ("development_m2", 0.35), ("pop_growth_pct", 0.25)),
    _o("ingenjor_bygg", "Byggnadsingenjör", "Samhällsbyggnad", 3.0, 0.025, 4.0, 48, 0.25,
       ("development_m2", 0.30), ("infra_invest", 0.30),
       ("business_density", 0.20), ("detail_plans", 0.20)),
    _o("larare", "Lärare (grundskola)", "Utbildning", 11.0, 0.030, 12.0, 38, 0.10,
       ("families_share", 0.50), ("pop_growth_pct", 0.50)),
    _o("forskollarare", "Förskollärare", "Utbildning", 5.5, 0.028, 7.0, 34, 0.08,
       ("families_share", 0.60), ("pop_growth_pct", 0.40)),
    _o("sjukskoterska", "Sjuksköterska", "Vård & omsorg", 11.5, 0.032, 13.0, 40, 0.10,
       ("share_65plus", 0.55), ("pop_growth_pct", 0.45)),
    _o("fastighetstekniker", "Fastighetstekniker", "Drift & fastighet", 1.8, 0.033, 2.0, 35, 0.30,
       ("residential_density", 0.40), ("development_m2", 0.30), ("pop_growth_pct", 0.30)),
    _o("drifttekniker", "Drifttekniker", "Drift & fastighet", 1.5, 0.030, 2.0, 38, 0.35,
       ("business_density", 0.40), ("infra_invest", 0.30), ("development_m2", 0.30)),
    _o("kyltekniker", "Kyl- & värmepumpstekniker", "Drift & installation",
       0.6, 0.030, 0.8, 39, 0.15,
       ("detached_homes", 0.35), ("renovation_index", 0.25),
       ("ev_per_capita", 0.20), ("pop_growth_pct", 0.20)),
    _o("underskoterska", "Undersköterska", "Vård & omsorg", 13.0, 0.033, 15.0, 32, 0.12,
       ("share_65plus", 0.55), ("pop_growth_pct", 0.45)),
    _o("barnskotare", "Barnskötare", "Utbildning", 6.0, 0.028, 8.0, 29, 0.10,
       ("families_share", 0.60), ("pop_growth_pct", 0.40)),
    _o("kock", "Kock", "Besöksnäring", 4.0, 0.030, 5.0, 32, 0.15,
       ("tourism_index", 0.30), ("foot_traffic", 0.30), ("pop_growth_pct", 0.40)),
    _o("lastbilsforare", "Lastbilsförare", "Transport & logistik", 5.5, 0.035, 6.0, 35, 0.60,
       ("logistics_access", 0.40), ("business_density", 0.30), ("pop_growth_pct", 0.30)),
    _o("svetsare", "Svetsare", "Industri", 2.2, 0.034, 2.5, 36, 0.45,
       ("business_density", 0.40), ("infra_invest", 0.30), ("development_m2", 0.30)),
    _o("malare", "Målare", "Bygg & installation", 2.8, 0.031, 3.5, 34, 0.25,
       ("renovation_index", 0.40), ("building_permits", 0.30), ("pop_growth_pct", 0.30)),
    _o("it_tekniker", "IT-tekniker", "IT & digitalt", 4.0, 0.020, 6.0, 42, 0.35,
       ("business_density", 0.50), ("office_workers", 0.50)),
]}


def occupation_catalog() -> list[dict[str, Any]]:
    return [{"id": o.id, "label_sv": o.label_sv, "sector_sv": o.sector_sv,
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
        parts.append({"signal_id": sid, "label_sv": CATALOG[sid].label_sv,
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
        return "stigande"
    return "minskande" if growth <= -0.005 else "stabil"


_CAVEATS = [
    "Prognosen är modellberäknad, inte en sanning: teknikskiften, migration, "
    "konjunktur och politiska beslut ligger utanför modellen.",
    "Yrkestäthet, pensionstakt och utbildningsplatser är branschschabloner "
    "tills SCB:s yrkesregister och Skolverkets data kopplats in.",
    "Konfidensnivån är en dokumenterad heuristik (datakvalitet × horisont), "
    "inte en statistisk sannolikhet.",
]


def _forecast_one(occ: Occupation, values: dict, horizon: int,
                  extra_places_per_year: float = 0.0) -> dict[str, Any]:
    pop_sv = values.get("population_total")
    if pop_sv is None or not pop_sv.value:
        raise ValueError("Befolkningsunderlag saknas.")
    pop = pop_sv.value
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
        {"antagande_sv": "Basår och balansläge",
         "varde_sv": f"Arbetsstyrkan antas motsvara behovet {BASE_YEAR}."},
        {"antagande_sv": "Befolkning (kommun)",
         "varde_sv": f"{int(pop)} invånare (källa: {pop_sv.source})."},
        {"antagande_sv": "Efterfrågetakt",
         "varde_sv": f"{round(100 * growth, 2)} %/år, härledd ur drivsignalerna nedan."},
        {"antagande_sv": "Pensionsavgångar",
         "varde_sv": f"{round(100 * occ.pension_rate, 1)} %/år (schablon)."},
        {"antagande_sv": "Utbildningsinflöde",
         "varde_sv": f"{round(edu)} examinerade/år "
                     f"(schablon{', inkl. simulerade platser' if extra_places_per_year else ''}, "
                     f"examensgrad {int(COMPLETION_RATE * 100)} %)."},
    ]
    return {
        "occupation_id": occ.id, "label_sv": occ.label_sv,
        "sector_sv": occ.sector_sv,
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
             market: str = "se") -> dict[str, Any]:
    """Kompetensprognos för en region, alla (eller valda) yrken."""
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= MAX_HORIZON_YEARS:
        raise ValueError(f"Målår måste ligga {BASE_YEAR + 1}–"
                         f"{BASE_YEAR + MAX_HORIZON_YEARS}.")
    occ_ids = occupation_ids or list(OCCUPATIONS)
    unknown = [o for o in occ_ids if o not in OCCUPATIONS]
    if unknown:
        raise ValueError(f"Okända yrken: {unknown}")
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
        "occupation_id": f["occupation_id"], "label_sv": f["label_sv"],
        "brist": f["brist"], "band": f["band"],
        "motivering_sv": (
            f"Beräknad brist på {f['brist']} {f['label_sv'].lower()} till "
            f"{target_year} ({f['band'].replace('_', ' ')}). Största drivkraft: "
            f"{max(f['drivare'], key=lambda d: d['bidrag_pct_ar'])['label_sv'].lower()}."
            if f["drivare"] else
            f"Beräknad brist på {f['brist']} till {target_year}."),
    } for i, f in enumerate(prio[:5], start=1)]

    coverage = (sum(1 for s in values.values() if s.source != "mock") /
                max(1, len(values)))
    mkt = get_market(market)
    return {
        "kommun": kom[1], "kommun_kod": kom[0],
        "market": mkt.id, "market_label_sv": mkt.label_sv,
        "basar": BASE_YEAR, "malar": target_year,
        "prognoser": forecasts,
        "utbildningsprioriteringar": priorities,
        "data_coverage": round(coverage, 2),
        "caveats_sv": list(_CAVEATS),
    }


def simulate(kommun_kod: str, occupation_id: str,
             extra_places_per_year: float, target_year: int = 2035,
             resolver: Resolver | None = None,
             market: str = "se") -> dict[str, Any]:
    """Utbildningssimulering: 'om vi startar X platser/år – vad händer?'"""
    if occupation_id not in OCCUPATIONS:
        raise ValueError(f"Okänt yrke: {occupation_id}")
    if extra_places_per_year < 0:
        raise ValueError("Antal platser kan inte vara negativt.")
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= MAX_HORIZON_YEARS:
        raise ValueError(f"Målår måste ligga {BASE_YEAR + 1}–"
                         f"{BASE_YEAR + MAX_HORIZON_YEARS}.")
    values, _, kom = _resolve(kommun_kod, [occupation_id], resolver, market)
    occ = OCCUPATIONS[occupation_id]
    base = _forecast_one(occ, values, horizon)
    sim = _forecast_one(occ, values, horizon,
                        extra_places_per_year=extra_places_per_year)
    balanced = next((p["ar"] for p in sim["bana"] if p["gap"] <= 0), None)
    return {
        "kommun": kom[1], "kommun_kod": kom[0],
        "occupation_id": occupation_id, "label_sv": occ.label_sv,
        "malar": target_year,
        "extra_platser_per_ar": extra_places_per_year,
        "brist_utan_atgard": base["brist"],
        "brist_med_atgard": sim["brist"],
        "minskning": base["brist"] - sim["brist"],
        "balansar": balanced,
        "bana_utan": base["bana"], "bana_med": sim["bana"],
        "konfidens": sim["konfidens"],
        "caveats_sv": list(_CAVEATS),
    }


def national_map(occupation_id: str, target_year: int = 2035,
                 resolver: Resolver | None = None,
                 market: str = "se") -> dict[str, Any]:
    """Marknadskarta: kompetensbalans per region för ett yrke."""
    if occupation_id not in OCCUPATIONS:
        raise ValueError(f"Okänt yrke: {occupation_id}")
    horizon = target_year - BASE_YEAR
    if not 1 <= horizon <= MAX_HORIZON_YEARS:
        raise ValueError(f"Målår måste ligga {BASE_YEAR + 1}–"
                         f"{BASE_YEAR + MAX_HORIZON_YEARS}.")
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
                         "market": mkt.id, "market_label_sv": mkt.label_sv,
                         "lat": lat, "lon": lon,
                         "behov_prognos": f["behov_prognos"],
                         "brist": f["brist"], "band": f["band"],
                         "efterfragan": f["efterfragan"],
                         "trend": f["trend"],
                         "konfidens": f["konfidens"]})
    kommuner.sort(key=lambda k: -k["brist"])
    return {"occupation_id": occupation_id, "label_sv": occ.label_sv,
            "market": mkt.id, "market_label_sv": mkt.label_sv,
            "bbox": list(mkt.bbox),
            "basar": BASE_YEAR, "malar": target_year,
            "kommuner": kommuner, "caveats_sv": list(_CAVEATS)}


def global_map(occupation_id: str, target_year: int = 2035,
               group: str = "eu",
               resolver: Resolver | None = None) -> dict[str, Any]:
    """Flerlandskarta: samma modell, alla marknader i gruppen.

    Gemensam Opportunity Score över länder är möjlig eftersom
    signalkatalogen äger normaliseringen – inte länderna.
    """
    if group not in MARKET_GROUPS:
        raise ValueError(f"Okänd marknadsgrupp: {group}. "
                         f"Tillgängliga: {', '.join(MARKET_GROUPS)}")
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
        ({"market": mid, "market_label_sv": get_market(mid).label_sv,
          "snitt_brist_pct": round(100 * sum(sh) / len(sh), 1),
          "regioner": len(sh)}
         for mid, sh in per_market.items()),
        key=lambda x: -x["snitt_brist_pct"])

    occ = OCCUPATIONS[occupation_id]
    return {"occupation_id": occupation_id, "label_sv": occ.label_sv,
            "group": group, "group_label_sv": GROUP_LABEL_SV[group],
            "bbox": list(GROUP_BBOX[group]),
            "basar": BASE_YEAR, "malar": target_year,
            "regioner": regions, "landsranking": ranking,
            "caveats_sv": list(_CAVEATS) + [
                "Endast Sverige har verkliga datakällor kopplade ännu – "
                "övriga marknader körs på simulerad data tills lokala "
                "adaptrar (Destatis, Eurostat, Census m.fl.) finns."]}
