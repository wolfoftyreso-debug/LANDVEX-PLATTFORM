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
from .markets import DEFAULT_MARKET, FX_PER_SEK, get_market, get_region
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
    leverantorer_en: tuple    # leverantörs-/avtalskategorier


PLAN_DATA: dict[str, PlanSpec] = {
    "frisor": PlanSpec((40, 90), (150, 400), (0.08, 0.15), (),
                       ("Salon furnishings", "Product wholesaler",
                        "Booking system", "POS system")),
    "elektriker": PlanSpec((0, 150), (300, 900), (0.08, 0.14), ("elektriker",),
                           ("Electrical wholesaler", "Vehicle leasing",
                            "Tools & measuring instruments",
                            "Certification & authorization")),
    "vvs": PlanSpec((0, 200), (300, 900), (0.08, 0.14), ("vvs_montor",),
                    ("Plumbing & HVAC wholesaler", "Vehicle leasing", "Tools",
                     "Authorization (Säker Vatten)")),
    "gym": PlanSpec((400, 1500), (1500, 5000), (0.10, 0.20), (),
                    ("Training equipment (purchase/leasing)",
                     "Access control system",
                     "Membership system", "Cleaning & operations")),
    "restaurang": PlanSpec((120, 350), (800, 2500), (0.04, 0.10), (),
                           ("Commercial kitchen equipment", "Food wholesaler",
                            "POS system", "Alcohol serving license")),
    "cafe": PlanSpec((60, 150), (400, 1200), (0.05, 0.12), (),
                     ("Coffee machines (often leased)",
                      "Ingredient wholesaler",
                      "Furnishings", "POS system")),
    "bygg": PlanSpec((0, 300), (400, 1500), (0.06, 0.12),
                     ("snickare", "betongarbetare"),
                     ("Building materials supplier", "Machine rental",
                      "Vehicle leasing", "Insurance & warranties")),
    "tandlakare": PlanSpec((90, 200), (1500, 4000), (0.15, 0.25), (),
                           ("Dental equipment (often leased)", "Dental lab",
                            "Records system", "Insurance agreements")),
    "bilverkstad": PlanSpec((250, 800), (800, 2500), (0.08, 0.15),
                            ("fastighetstekniker",),
                            ("Lifts & workshop equipment (often leased)",
                             "Spare parts wholesaler", "Tire supplier",
                             "Brand authorization")),
    "veterinar": PlanSpec((100, 250), (1000, 3000), (0.12, 0.20), (),
                          ("Medical equipment", "Pharmaceutical wholesaler",
                           "Records system", "Laboratory services")),
    "lager": PlanSpec((1000, 10000), (1500, 8000), (0.05, 0.10),
                      ("maskinforare", "drifttekniker"),
                      ("Forklifts & automation (often leased)", "WMS system",
                       "Transport agreements", "Energy contracts")),
    "forskola": PlanSpec((200, 600), (300, 1200), (0.04, 0.08),
                         ("barnskotare", "forskollarare"),
                         ("Educational materials",
                          "Commercial kitchen/catering",
                          "Outdoor environment & safety", "Municipal permit")),
    "apotek": PlanSpec((80, 200), (800, 2000), (0.03, 0.06), (),
                       ("Pharmaceutical wholesaler", "Prescription system",
                        "Cold chain",
                        "License from Läkemedelsverket")),
    "optiker": PlanSpec((60, 150), (400, 1500), (0.10, 0.18), (),
                        ("Lens & frame supplier",
                         "Eye examination equipment", "Records system")),
    "bageri": PlanSpec((80, 250), (600, 1800), (0.05, 0.10), ("kock",),
                       ("Ovens & dough machines (often leased)",
                        "Ingredient wholesaler", "POS system",
                        "Food business registration")),
    "livsmedel": PlanSpec((400, 1500), (1500, 5000), (0.02, 0.04), (),
                          ("Grocery wholesaler", "Refrigeration & freezers",
                           "POS system", "Food business registration")),
    "aldreomsorg": PlanSpec((0, 150), (100, 500), (0.05, 0.09),
                            ("underskoterska", "sjukskoterska"),
                            ("Care/records system", "Staff scheduling",
                             "Vehicles", "IVO permit")),
    "stadfirma": PlanSpec((0, 100), (100, 400), (0.08, 0.15), (),
                          ("Cleaning supplies wholesaler", "Vehicle leasing",
                           "Scheduling system")),
    "malare": PlanSpec((0, 150), (100, 500), (0.08, 0.14), ("malare",),
                       ("Paint wholesaler", "Scaffolding & lifts (rental)",
                        "Vehicle leasing")),
    "laddinfra": PlanSpec((0, 50), (2000, 8000), (0.05, 0.12),
                          ("elektriker", "it_tekniker"),
                          ("Charging hardware", "Grid connection",
                           "Payment/software platform", "Land agreements")),
    "cykelverkstad": PlanSpec((60, 150), (150, 500), (0.08, 0.15), (),
                              ("Bicycle wholesaler", "Tools & workshop space",
                               "POS system")),
    "generisk": PlanSpec((50, 300), (300, 1500), (0.06, 0.12), (),
                         ("Industry wholesaler", "POS system", "Furnishings")),
}

_FINANSIERING_SV = [
    {"alternativ_en": "Bank loan with a business mortgage",
     "notis_en": "Most common for establishments with physical premises; "
                 "normally requires 20–30% equity."},
    {"alternativ_en": "Almi business loan",
     "notis_en": "Complements bank financing at higher risk; higher "
                 "interest but lower collateral requirements."},
    {"alternativ_en": "Equipment leasing",
     "notis_en": "Frees up startup capital – most common for machinery, "
                 "coffee machines, lifts and dental equipment."},
    {"alternativ_en": "Supplier credit",
     "notis_en": "Negotiate payment terms with wholesalers at launch."},
    {"alternativ_en": "Equity / co-owners",
     "notis_en": "Strengthens borrowing capacity and lowers repayment "
                 "risk."},
]


def establishment_plan(kommun_kod: str, vertical_id: str,
                       market: str = DEFAULT_MARKET, team_size: str = "2-5",
                       budget_band: str = "500k-2m",
                       resolver: Resolver | None = None) -> dict[str, Any]:
    """Konkret etableringsplan för vertikal + region. JSON-redo dict."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    if team_size not in TEAM_PERSONS:
        raise ValueError(f"Invalid team_size: {team_size}.")
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
    hyreslage = ("Rent level above the national average – negotiate a "
                 "stepped rent."
                 if rent and rent["value"] > 110 else
                 "Rent level below the national average – the cost "
                 "position is an advantage."
                 if rent and rent["value"] < 95 else
                 "Rent level around the national average.")

    # Investering: startkapital + utrustning (schabloner).
    fx = FX_PER_SEK[mkt.currency]
    start_lo, start_hi = (max(0, round(v * fx))
                          for v in STARTUP_TKR[vertical_id])
    utr_lo, utr_hi = (round(v * fx) for v in spec.utrustning_tkr)
    tot_lo, tot_hi = start_lo + utr_lo, start_hi + utr_hi

    # Personal: verkligt rekryteringsläge från Workforce-motorn.
    personal_yrken = []
    for occ_id in spec.yrken:
        f = forecast(kod, 2031, [occ_id], resolver=resolver,
                     market=market)["prognoser"][0]
        laget = (f"Shortage of {f['brist']} by 2031 – expect long "
                 f"recruitment lead times and wage pressure."
                 if f["brist"] > 0 else "Balanced recruitment market.")
        personal_yrken.append({"occupation_id": occ_id,
                               "label_en": OCCUPATIONS[occ_id].label_en,
                               "medellon_tkr_manad":
                                   round(OCCUPATIONS[occ_id].salary_tkr_month
                                         * fx, 1),
                               "rekryteringslage_en": laget})

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
            "budget_fit_en": eko["budget_fit_en"],
            "marginal_schablon_pct": [round(100 * m_lo), round(100 * m_hi)],
            "rorelseresultat_tkr_ar": [res_lo, res_hi],
            "aterbetalningstid_ar": payback,
            "notis_en": "Standard-estimate calculation (industry benchmarks "
                        "× the location's score) – a working figure to "
                        "challenge, not a forecast.",
        }
    else:
        ekonomi = {"status": "ej_kalibrerad",
                   "notis_en": f"Economic standard estimates are not "
                               f"calibrated for {mkt.label_en} – "
                               f"not reported."}

    risker = [{"label_en": d["label_en"], "risk": d["risk"],
               "band": d["band"], "atgard_en": d["atgard_en"]}
              for d in sorted(riskprofil["dimensioner"],
                              key=lambda d: -d["risk"])[:3]]

    return {
        "vertical_id": vertical_id,
        "vertical_label_en": VERTICALS[vertical_id].label_en,
        "kommun": namn, "kommun_kod": kod,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "opportunity_score": report.opportunity_score,
        "risk_total": riskprofil["total_risk"],
        "currency": mkt.currency,
        "lokal": {"storlek_m2": lokal_m2, "hyreslage_en": hyreslage},
        "investering_tkr": {"startkapital": [start_lo, start_hi],
                            "utrustning": [utr_lo, utr_hi],
                            "totalt": [tot_lo, tot_hi],
                            "notis_en": "Industry standard estimates – "
                                        "actual amounts depend on quotes."
                                        + ("" if mkt.currency == "SEK" else
                                           " Converted from Swedish "
                                           "benchmarks at a standard rate – "
                                           "local cost levels are not "
                                           "calibrated yet.")},
        "finansiering": _FINANSIERING_SV,
        "personal": {"antal": persons, "team_size": team_size,
                     "yrken": personal_yrken,
                     "notis_en": ("The recruitment outlook comes from the "
                                  "Workforce engine's forecast to 2031."
                                  if personal_yrken else
                                  "The recruitment outlook for this "
                                  "industry's occupations is not modeled "
                                  "yet.")},
        "leverantorer_en": list(spec.leverantorer_en),
        "ekonomi": ekonomi,
        "risker": risker,
        "nasta_steg_en": ["Site visit and premises search",
                          "Equipment quotes",
                          "Bank meeting with this calculation as material",
                          "Contact the municipality's business office",
                          "Registration and permits"],
        "caveats_en": [
            "The plan is decision support built on standard estimates and "
            "the location's signal picture – validate with quotes, site "
            "visits and your own calculations.",
        ] + (["Parts of the underlying data are simulated – see "
              "data_coverage."]
             if report.data_coverage < 1.0 else []),
        "data_coverage": report.data_coverage,
    }
