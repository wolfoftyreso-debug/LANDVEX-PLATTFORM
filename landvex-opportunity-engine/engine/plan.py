"""Etableringsplan – från "här finns en möjlighet" till beslutsunderlag.

Bygger en konkret plan för en vertikal på en plats: lokal, investering,
finansieringsvägar, personalbehov med VERKLIGT rekryteringsläge (från
Workforce-motorn – bristyrken flaggas), omsättningsscenario,
återbetalningstid och riskbild (från Risk-motorn). Fyra motorer, ett
svar.

ÄRLIGHET: alla belopp är branschschabloner (PLAN_DATA) skalade mot
platsens signalbild – ett räkneunderlag att utmana, ingen prognos.
Återbetalningstiden redovisas som intervall och bara på kalibrerade
marknader. Planen märker själv vad som är schablon.

Plandata är data per vertikal – ny bransch = ny rad.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .markets import get_market, get_region
from .models import Location
from .profile import BusinessProfile
from .risk import assess
from .scan import STARTUP_TKR, TEAM_PERSONS, economy_scenario
from .scoring import analyze
from .verticals import VERTICALS
from .workforce import OCCUPATIONS, forecast


@dataclass(frozen=True)
class PlanSpec:
    m2: tuple                 # typisk lokalstorlek (min, max)
    utrustning_tkr: tuple     # utrustningsinvestering (min, max)
    marginal: tuple           # rörelsemarginal-schablon (min, max)
    yrken: tuple              # occupation-id:n för rekryteringsläget
    leverantorer_sv: tuple    # leverantörs-/avtalskategorier


PLAN_DATA: dict[str, PlanSpec] = {
    "frisor": PlanSpec((40, 90), (150, 400), (0.08, 0.15), (),
                       ("Salongsinredning", "Produktgrossist",
                        "Bokningssystem", "Kassasystem")),
    "elektriker": PlanSpec((0, 150), (300, 900), (0.08, 0.14), ("elektriker",),
                           ("Elgrossist", "Fordonsleasing", "Verktyg & mätinstrument",
                            "Certifiering & behörighet")),
    "vvs": PlanSpec((0, 200), (300, 900), (0.08, 0.14), ("vvs_montor",),
                    ("VVS-grossist", "Fordonsleasing", "Verktyg",
                     "Auktorisation (Säker Vatten)")),
    "gym": PlanSpec((400, 1500), (1500, 5000), (0.10, 0.20), (),
                    ("Träningsutrustning (köp/leasing)", "Passersystem",
                     "Medlemssystem", "Städ & drift")),
    "restaurang": PlanSpec((120, 350), (800, 2500), (0.04, 0.10), (),
                           ("Storköksutrustning", "Livsmedelsgrossist",
                            "Kassasystem", "Serveringstillstånd")),
    "cafe": PlanSpec((60, 150), (400, 1200), (0.05, 0.12), (),
                     ("Kaffemaskiner (ofta leasing)", "Råvarugrossist",
                      "Inredning", "Kassasystem")),
    "bygg": PlanSpec((0, 300), (400, 1500), (0.06, 0.12),
                     ("snickare", "betongarbetare"),
                     ("Byggmaterialhandel", "Maskinuthyrning",
                      "Fordonsleasing", "Försäkring & garantier")),
    "tandlakare": PlanSpec((90, 200), (1500, 4000), (0.15, 0.25), (),
                           ("Dentalutrustning (ofta leasing)", "Dentallabb",
                            "Journalsystem", "Försäkringsavtal")),
    "bilverkstad": PlanSpec((250, 800), (800, 2500), (0.08, 0.15),
                            ("fastighetstekniker",),
                            ("Lyftar & verkstadsutrustning (ofta leasing)",
                             "Reservdelsgrossist", "Däckleverantör",
                             "Märkesauktorisation")),
    "veterinar": PlanSpec((100, 250), (1000, 3000), (0.12, 0.20), (),
                          ("Medicinteknisk utrustning", "Läkemedelsgrossist",
                           "Journalsystem", "Laboratorietjänster")),
    "lager": PlanSpec((1000, 10000), (1500, 8000), (0.05, 0.10),
                      ("maskinforare", "drifttekniker"),
                      ("Truckar & automation (ofta leasing)", "WMS-system",
                       "Transportavtal", "Energiavtal")),
    "generisk": PlanSpec((50, 300), (300, 1500), (0.06, 0.12), (),
                         ("Branschgrossist", "Kassasystem", "Inredning")),
}

_FINANSIERING_SV = [
    {"alternativ_sv": "Banklån med företagsinteckning",
     "notis_sv": "Vanligast för etableringar med fysisk lokal; kräver "
                 "normalt 20–30 % eget kapital."},
    {"alternativ_sv": "Almi företagslån",
     "notis_sv": "Kompletterar bank vid högre risk; högre ränta men "
                 "mindre säkerhetskrav."},
    {"alternativ_sv": "Leasing av utrustning",
     "notis_sv": "Frigör startkapital – vanligast för maskiner, "
                 "kaffemaskiner, lyftar och dentalutrustning."},
    {"alternativ_sv": "Leverantörskredit",
     "notis_sv": "Förhandla betalningsvillkor med grossist vid start."},
    {"alternativ_sv": "Eget kapital / delägare",
     "notis_sv": "Stärker låneförmågan och sänker återbetalningsrisken."},
]


def establishment_plan(kommun_kod: str, vertical_id: str,
                       market: str = "se", team_size: str = "2-5",
                       budget_band: str = "500k-2m",
                       resolver: Resolver | None = None) -> dict[str, Any]:
    """Konkret etableringsplan för vertikal + region. JSON-redo dict."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Okänd vertikal: {vertical_id}. "
                         f"Tillgängliga: {', '.join(sorted(VERTICALS))}")
    if team_size not in TEAM_PERSONS:
        raise ValueError(f"Ogiltig team_size: {team_size}.")
    mkt = get_market(market)
    kod, namn, lat, lon = get_region(market, kommun_kod)
    spec = PLAN_DATA[vertical_id]
    loc = Location(lat, lon, address=namn)

    report = analyze(loc, vertical_id, resolver=resolver)
    riskprofil = assess(loc, vertical_id, resolver=resolver)
    persons = TEAM_PERSONS[team_size]

    # Lokal: storlek skalas med teamet; hyresläge ur signalbilden.
    m2_lo, m2_hi = spec.m2
    skala = max(1.0, persons / 3.0)
    lokal_m2 = [int(m2_lo * skala), int(m2_hi * skala)]
    rent = report.signals.get("rent_index")
    hyreslage = ("Hyresnivå över rikssnittet – förhandla hyrestrappa."
                 if rent and rent["value"] > 110 else
                 "Hyresnivå under rikssnittet – kostnadsläget är en fördel."
                 if rent and rent["value"] < 95 else
                 "Hyresnivå kring rikssnittet.")

    # Investering: startkapital + utrustning (schabloner).
    start_lo, start_hi = STARTUP_TKR[vertical_id]
    utr_lo, utr_hi = spec.utrustning_tkr
    tot_lo, tot_hi = start_lo + utr_lo, start_hi + utr_hi

    # Personal: verkligt rekryteringsläge från Workforce-motorn.
    personal_yrken = []
    for occ_id in spec.yrken:
        f = forecast(kod, 2031, [occ_id], resolver=resolver,
                     market=market)["prognoser"][0]
        laget = (f"Brist på {f['brist']} till 2031 – räkna med lång "
                 f"rekryteringstid och lönepress."
                 if f["brist"] > 0 else "Balanserat rekryteringsläge.")
        personal_yrken.append({"occupation_id": occ_id,
                               "label_sv": OCCUPATIONS[occ_id].label_sv,
                               "medellon_tkr_manad":
                                   OCCUPATIONS[occ_id].salary_tkr_month,
                               "rekryteringslage_sv": laget})

    # Ekonomi: scenario + återbetalningstid, endast kalibrerad marknad.
    if mkt.calibrated:
        eko = economy_scenario(
            BusinessProfile(vertical_id=vertical_id, team_size=team_size,
                            budget_band=budget_band),
            report.opportunity_score)
        oms = eko["omsattningsscenario_tkr_ar"]
        m_lo, m_hi = spec.marginal
        res_lo, res_hi = int(oms * m_lo), int(oms * m_hi)
        payback = ([round(tot_lo / res_hi, 1), round(tot_hi / max(res_lo, 1), 1)]
                   if res_lo > 0 else None)
        ekonomi = {
            "omsattningsscenario_tkr_ar": oms,
            "budget_fit_sv": eko["budget_fit_sv"],
            "marginal_schablon_pct": [round(100 * m_lo), round(100 * m_hi)],
            "rorelseresultat_tkr_ar": [res_lo, res_hi],
            "aterbetalningstid_ar": payback,
            "notis_sv": "Schablonkalkyl (branschriktvärden × platsens score) "
                        "– räkneunderlag att utmana, ingen prognos.",
        }
    else:
        ekonomi = {"status": "ej_kalibrerad",
                   "notis_sv": f"Ekonomischabloner ej kalibrerade för "
                               f"{mkt.label_sv} – redovisas inte."}

    risker = [{"label_sv": d["label_sv"], "risk": d["risk"],
               "band": d["band"], "atgard_sv": d["atgard_sv"]}
              for d in sorted(riskprofil["dimensioner"],
                              key=lambda d: -d["risk"])[:3]]

    return {
        "vertical_id": vertical_id,
        "vertical_label_sv": VERTICALS[vertical_id].label_sv,
        "kommun": namn, "kommun_kod": kod,
        "market": mkt.id, "market_label_sv": mkt.label_sv,
        "opportunity_score": report.opportunity_score,
        "risk_total": riskprofil["total_risk"],
        "lokal": {"storlek_m2": lokal_m2, "hyreslage_sv": hyreslage},
        "investering_tkr": {"startkapital": [start_lo, start_hi],
                            "utrustning": [utr_lo, utr_hi],
                            "totalt": [tot_lo, tot_hi],
                            "notis_sv": "Branschschabloner – offertläge "
                                        "avgör de verkliga beloppen."},
        "finansiering": _FINANSIERING_SV,
        "personal": {"antal": persons, "team_size": team_size,
                     "yrken": personal_yrken,
                     "notis_sv": ("Rekryteringsläget kommer från "
                                  "Workforce-motorns prognos till 2031."
                                  if personal_yrken else
                                  "Rekryteringsläge för branschens yrken är "
                                  "inte modellerat ännu.")},
        "leverantorer_sv": list(spec.leverantorer_sv),
        "ekonomi": ekonomi,
        "risker": risker,
        "nasta_steg_sv": ["Platsbesök och lokalsökning", "Offert på utrustning",
                          "Bankmöte med denna kalkyl som underlag",
                          "Kontakt med kommunens näringslivskontor",
                          "Registrering och tillstånd"],
        "caveats_sv": [
            "Planen är ett beslutsunderlag byggt på schabloner och platsens "
            "signalbild – validera med offerter, platsbesök och egen kalkyl.",
        ] + (["Delar av underlaget är simulerat – se data_coverage."]
             if report.data_coverage < 1.0 else []),
        "data_coverage": report.data_coverage,
    }
