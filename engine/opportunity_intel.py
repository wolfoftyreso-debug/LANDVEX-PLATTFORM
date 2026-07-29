"""Opportunity Intelligence – osynliga möjligheter, inte bara var kunderna finns.

Tre lager ovanpå Opportunity Score:

  1. Support programs  – vilka stöd/bidrag/program som PASSAR verksamheten
     och platsen (laddinfra, energieffektivisering, EU:s gröna omställning,
     offentlig upphandling, regionalt etableringsstöd, kompetensstöd,
     exportstöd). Programmen är ARKETYPER som data; passform och
     schablonbelopp härleds ur de verkliga signalerna på platsen.
  2. Hidden opportunities – affärsmöjligheter användaren inte tänkt på:
     signalmönster (t.ex. hög infrastrukturinvestering + bygglov + få
     leverantörer) → föreslagen nisch med motivering och bevis.
  3. Expansion advisor – för den som redan driver företag: anställa fler,
     öppna filial, köpa upp konkurrent, byta inriktning, rikta in sig på
     offentliga projekt, vilka certifieringar som ger störst effekt.

ÄRLIGHET (arkitekturprincip 3 & 4): motorn hittar ALDRIG på ett specifikt
levande bidrag med riktigt belopp eller sista ansökningsdatum. Belopp är
schabloner (märkta), passform/sannolikhet är heuristik (märkt), och varje
svar bär en caveat om att ett live-programregister (EU Funding & Tenders,
Vinnova, Energimyndigheten, Tillväxtverket, regionala fonder) är den
adapter som gör belopp och deadlines verkliga – samma Resolver-mönster
som SCB. Determinism: samma plats + profil → samma svar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.faults import OUR_BUGS
from .markets import DEFAULT_MARKET, get_market
from .models import Location
from .scoring import analyze
from .signals import CATALOG
from .specialization import specialization_boost, specializations_for
from .verticals import VERTICALS


# ── 1. Support programs (arketyper som data) ─────────────────────────
@dataclass(frozen=True)
class ProgramDef:
    id: str
    label_en: str
    verticals: tuple[str, ...]          # tom = alla verksamheter
    driver_signals: tuple[tuple[str, float], ...]   # (signal_id, vikt)
    amount_band_local: tuple[int, int]  # schablon, lokal valuta (heltal)
    process_months: tuple[int, int]
    documents_en: tuple[str, ...]
    combinable: bool
    fokus_specialiseringar: tuple[str, ...] = ()    # nischer där passform lyfter
    source_hint_en: str = ""
    notis_en: str = ""


SUPPORT_PROGRAMS: tuple[ProgramDef, ...] = (
    ProgramDef(
        "ev_charging_infra", "EV charging infrastructure grant",
        ("elektriker", "laddinfra"),
        (("ev_per_capita", 1.0), ("building_permits", 0.6),
         ("infra_invest", 0.6), ("business_density", 0.4)),
        (150_000, 2_800_000), (2, 6),
        ("Installation quote", "Property/utility connection details",
         "Company registration", "Project timeline"),
        True, fokus_specialiseringar=("laddboxar",),
        source_hint_en="National energy agency / regional climate funds.",
        notis_en="Charger-infrastructure support tracks the local EV fleet "
                 "and new construction."),
    ProgramDef(
        "energy_efficiency", "Energy efficiency retrofit program",
        ("elektriker", "vvs", "bygg", "malare"),
        (("avg_building_age", 0.9), ("detached_homes", 0.7),
         ("renovation_index", 0.7), ("residential_density", 0.3)),
        (100_000, 1_500_000), (3, 9),
        ("Energy declaration", "Renovation scope", "Company registration",
         "Cost estimate"),
        True, fokus_specialiseringar=("solceller", "varmepump", "renovering"),
        source_hint_en="National energy agency / housing renovation funds.",
        notis_en="Retrofit support tracks the ageing, detached housing stock."),
    ProgramDef(
        "eu_green_transition", "EU green-transition funding",
        (),  # alla verksamheter
        (("infra_invest", 0.9), ("development_m2", 0.7),
         ("pop_growth_pct", 0.4)),
        (200_000, 2_500_000), (4, 12),
        ("Project plan", "Co-financing statement", "Environmental impact",
         "Company registration"),
        True,
        source_hint_en="EU Funding & Tenders portal (regional/national body).",
        notis_en="EU green-deal instruments follow regional development and "
                 "infrastructure investment."),
    ProgramDef(
        "public_procurement_energy", "Public procurement – energy & facilities",
        ("elektriker", "vvs", "bygg", "stadfirma"),
        (("infra_invest", 0.9), ("business_density", 0.6),
         ("building_permits", 0.5)),
        (300_000, 5_000_000), (2, 8),
        ("Qualification documents", "References", "Certifications",
         "Insurance"),
        False, fokus_specialiseringar=("industri", "offentligt", "fastigheter"),
        source_hint_en="National/municipal procurement portal.",
        notis_en="Public contracts scale with municipal investment and the "
                 "local business base."),
    ProgramDef(
        "regional_establishment", "Regional establishment support",
        (),
        (("infra_invest", 0.7), ("development_m2", 0.6),
         ("business_density", 0.5)),
        (50_000, 1_200_000), (2, 6),
        ("Business plan", "Budget", "Company registration"),
        True,
        source_hint_en="Regional growth agency / county administrative board.",
        notis_en="Establishment support follows regional development zones."),
    ProgramDef(
        "competence_support", "Competence & training support",
        (),
        (("business_density", 0.7), ("building_permits", 0.4),
         ("infra_invest", 0.4)),
        (40_000, 600_000), (1, 4),
        ("Training plan", "Employee list", "Company registration"),
        True,
        source_hint_en="National labour-market / skills agency.",
        notis_en="Skills support scales with hiring pressure in the area."),
    ProgramDef(
        "export_support", "Export & internationalization support",
        (),
        (("business_density", 0.8), ("logistics_access", 0.5),
         ("income_index", 0.3)),
        (50_000, 800_000), (2, 6),
        ("Export plan", "Financial statements", "Company registration"),
        True,
        source_hint_en="National export/trade promotion agency.",
        notis_en="Export support fits established firms with logistics access."),
)


def _norm(sid: str, sig: dict | None) -> float | None:
    """Normaliserat 0..1 för en signal ur en rapports signalbild."""
    if sig is None:
        return None
    return sig.get("normalized")


def _fit(report, drivers: tuple[tuple[str, float], ...]) -> tuple[int, list[dict]]:
    """Passform 0–100 = viktat normaliserat drivsignalvärde + bevisrader."""
    num, den = 0.0, 0.0
    evidence: list[dict] = []
    for sid, w in drivers:
        sig = report.signals.get(sid)
        n = _norm(sid, sig)
        if n is None:
            continue
        num += w * n
        den += w
        d = CATALOG.get(sid)
        evidence.append({"signal_id": sid,
                         "label_en": d.label_en if d else sid,
                         "value": sig["value"],
                         "unit": d.unit if d else "",
                         "source": sig["source"]})
    fit = int(round(100 * num / den)) if den else 0
    evidence.sort(key=lambda e: -abs(report.signals[e["signal_id"]]["normalized"]))
    return fit, evidence[:4]


def _amount_estimate(band: tuple[int, int], fit: int) -> int:
    """Schablonbelopp skalat av passform inom bandet (avrundat)."""
    lo, hi = band
    est = lo + (hi - lo) * (fit / 100.0)
    return int(round(est, -3))


def _process_band(pb: tuple[int, int]) -> str:
    return f"{pb[0]}–{pb[1]} months"


def support_programs(report, vertical_id: str,
                     specialization: str | None = None,
                     programs=None) -> dict[str, Any]:
    """Vilka stöd/program som passar verksamheten + platsen.

    `programs` (a datasources.programs.ProgramsClient) is optional: when
    connected it prepends REAL registry programs (real amounts/deadlines,
    marked source="registry") above the signal-derived archetypes (marked
    source="archetype"). A registry error never breaks the response."""
    matches = []
    total_lo = total_hi = 0
    for p in SUPPORT_PROGRAMS:
        if p.verticals and vertical_id not in p.verticals:
            continue
        fit, evidence = _fit(report, p.driver_signals)
        # Nisch-lyft: en fokuserad specialisering höjer passformen.
        if specialization and specialization in p.fokus_specialiseringar:
            fit = min(100, int(round(fit * 1.15)))
        if fit < 25:                    # för svag passform → visa inte som möjlighet
            continue
        est = _amount_estimate(p.amount_band_local, fit)
        # Sannolikhet att uppfylla kraven: konservativ funktion av passform.
        prob = int(round(min(90, 25 + fit * 0.6)))
        total_lo += int(p.amount_band_local[0] * fit / 100.0)
        total_hi += est
        matches.append({
            "id": p.id, "label_en": p.label_en,
            "fit": fit,
            "eligibility_probability_pct": prob,
            "amount_estimate_local": est,
            "amount_band_local": list(p.amount_band_local),
            "process_time_en": _process_band(p.process_months),
            "documents_en": list(p.documents_en),
            "combinable": p.combinable,
            "evidence": evidence,
            "source_hint_en": p.source_hint_en,
            "notis_en": p.notis_en,
            "source": "archetype",
        })
    matches.sort(key=lambda m: (-m["fit"], -m["amount_estimate_local"]))

    # Live registry programs (real amounts/deadlines) prepended, if connected.
    live: list[dict] = []
    live_connected = bool(programs is not None and getattr(programs, "connected", False))
    if live_connected:
        try:
            loc = report.location
            for rec in programs.fetch_programs(loc.lat, loc.lon, vertical_id):
                amt = rec.get("amount_local")
                live.append({
                    "id": rec["id"], "label_en": rec["label_en"],
                    "fit": report.opportunity_score,   # generic local strength
                    "eligibility_probability_pct": None,
                    "amount_estimate_local": (amt[1] if isinstance(amt, list)
                                              and amt else None),
                    "amount_band_local": amt if isinstance(amt, list) else None,
                    "process_time_en": None,
                    "documents_en": rec.get("documents_en") or [],
                    "combinable": True,
                    "evidence": [],
                    "source_hint_en": rec.get("provider") or "registry",
                    "notis_en": rec.get("raw_summary_en") or "",
                    "deadline": rec.get("deadline"),
                    "url": rec.get("url") or "",
                    "source": "registry",
                })
        except OUR_BUGS:
            # Ett AttributeError i VÅR mappningskod lästes som "registret
            # är nere" — arketyper visades, felet försvann. Vår bugg ska
            # upp, inte kläs ut till nätfel.
            raise
        except Exception:                                # noqa: BLE001
            live_connected = False       # honest degradation → archetypes only

    all_programs = live + matches
    notis = ("Live registry programs (real amounts/deadlines) shown first; "
             "the rest are signal-derived archetype estimates."
             if live else
             "Program fit and amounts are heuristics derived from local "
             "signals. Real amounts, deadlines and eligibility come from a "
             "live programs registry (EU Funding & Tenders, national "
             "energy/growth agencies, regional funds) connected as an adapter "
             "– set LANDVEX_PROGRAMS_URL to enable.")
    return {
        "programs": all_programs,
        "count": len(all_programs),
        "live_count": len(live),
        "combinable_total_estimate_local": [int(round(total_lo, -3)),
                                            int(round(total_hi, -3))],
        "horizon_note_en": "Combinable standard-estimate total over a typical "
                           "3-year window – NOT a live figure.",
        "notis_en": notis,
    }


# ── 2. Hidden opportunities (signalmönster → nisch) ──────────────────
@dataclass(frozen=True)
class HiddenRule:
    id: str
    title_en: str
    verticals: tuple[str, ...]
    trigger_signals: tuple[tuple[str, float], ...]   # (signal, min_normaliserat)
    suggested_specialization: str | None
    action_en: str
    market_signal_en: str


HIDDEN_RULES: tuple[HiddenRule, ...] = (
    HiddenRule(
        "backup_power", "Backup power & energy storage is underserved",
        ("elektriker",),
        (("infra_invest", 0.6), ("building_permits", 0.5),
         ("business_density", 0.5)),
        "industri",
        "Consider specializing in backup power and energy storage.",
        "Heavy infrastructure investment and few specialized installers – the "
        "market is expected to grow strongly here over the next five years."),
    HiddenRule(
        "ev_wave", "The EV charging wave is ahead of supply",
        ("elektriker", "laddinfra"),
        (("ev_per_capita", 0.55), ("building_permits", 0.4)),
        "laddboxar",
        "Consider adding EV charging installation.",
        "A rising electric fleet and new construction outpace the number of "
        "charger installers."),
    HiddenRule(
        "retrofit_wave", "An ageing housing stock needs energy retrofits",
        ("elektriker", "vvs", "bygg", "malare"),
        (("avg_building_age", 0.55), ("detached_homes", 0.5)),
        "renovering",
        "Consider positioning for energy-retrofit and renovation work.",
        "The local housing stock is old and detached – retrofit demand builds "
        "as efficiency requirements tighten."),
    HiddenRule(
        "public_pipeline", "A public construction pipeline is opening",
        ("elektriker", "vvs", "bygg", "stadfirma"),
        (("infra_invest", 0.6), ("detail_plans", 0.5)),
        None,
        "Position for public procurement and larger contracts.",
        "Municipal investment and new detailed plans signal public projects "
        "(schools, facilities, grid) coming to tender."),
    HiddenRule(
        "growth_influx", "In-migration is running ahead of local supply",
        (),
        (("pop_growth_pct", 0.6), ("provider_gap", 0.55)),
        None,
        "Establish early – demand is outgrowing the current providers.",
        "Population growth combined with a supply gap means demand is "
        "outrunning the businesses serving it."),
)


def hidden_opportunities(report, vertical_id: str) -> dict[str, Any]:
    """Affärsmöjligheter användaren kanske inte tänkt på."""
    found = []
    specs = {s["id"]: s["label_en"] for s in specializations_for(vertical_id)}
    for r in HIDDEN_RULES:
        if r.verticals and vertical_id not in r.verticals:
            continue
        evidence, ok = [], True
        strength = 0.0
        for sid, min_n in r.trigger_signals:
            sig = report.signals.get(sid)
            n = _norm(sid, sig)
            if n is None or n < min_n:
                ok = False
                break
            strength += n
            d = CATALOG.get(sid)
            evidence.append({"signal_id": sid,
                             "label_en": d.label_en if d else sid,
                             "value": sig["value"],
                             "unit": d.unit if d else "",
                             "source": sig["source"]})
        if not ok:
            continue
        strength = strength / len(r.trigger_signals)
        spec_label = specs.get(r.suggested_specialization) \
            if r.suggested_specialization else None
        found.append({
            "id": r.id, "title_en": r.title_en,
            "action_en": r.action_en,
            "market_signal_en": r.market_signal_en,
            "suggested_specialization": r.suggested_specialization,
            "suggested_specialization_label_en": spec_label,
            "strength": int(round(100 * strength)),
            "evidence": evidence,
        })
    found.sort(key=lambda x: -x["strength"])
    return {
        "opportunities": found,
        "count": len(found),
        "notis_en": "Pattern-based suggestions from the local signal picture "
                    "– a strategic prompt, not a guarantee. Confidence follows "
                    "data coverage.",
    }


# ── 3. Expansion advisor (för befintligt företag) ────────────────────
_TEAM_ORDER = ["1", "2-5", "5-20", "20-50", "50+"]


def _verdict(score: float) -> str:
    return "yes" if score >= 66 else "consider" if score >= 45 else "not_now"


def expansion_advisor(report, vertical_id: str, team_size: str = "1",
                      specialization: str | None = None) -> dict[str, Any]:
    """Tillväxtråd för en som redan driver företag – härlett ur signalerna."""
    S = report.signals

    def n(sid: str) -> float:
        return _norm(sid, S.get(sid)) or 0.0

    momentum = report.opportunity_score / 100.0
    gap = n("provider_gap")
    comp = n("competition_pressure")          # högt = hård konkurrens
    infra = n("infra_invest")
    biz = n("business_density")

    recs = []

    # Anställa fler: hög efterfrågan + utbudsgap.
    hire = 100 * (0.6 * momentum + 0.4 * gap)
    recs.append({
        "question_en": "Should you hire another person?",
        "verdict": _verdict(hire), "score": int(round(hire)),
        "rationale_en": ("Demand and the supply gap support taking on more "
                         "capacity." if hire >= 55 else
                         "Demand does not yet clearly support another hire.")})

    # Öppna filial: stark plats + tillväxt.
    branch = 100 * (0.7 * momentum + 0.3 * n("pop_growth_pct"))
    recs.append({
        "question_en": "Should you open a branch here?",
        "verdict": _verdict(branch), "score": int(round(branch)),
        "rationale_en": ("The location scores well and is growing – a branch "
                         "could capture it." if branch >= 55 else
                         "The location does not yet justify a dedicated "
                         "branch.")})

    # Köpa upp konkurrent: hård konkurrens = konsolideringsläge.
    acquire = 100 * (0.6 * comp + 0.4 * momentum)
    recs.append({
        "question_en": "Should you acquire a competitor?",
        "verdict": _verdict(acquire), "score": int(round(acquire)),
        "rationale_en": ("The market is competitive – consolidation could buy "
                         "share faster than organic growth." if acquire >= 55
                         else "The market is not crowded enough to make "
                         "acquisition the fastest path.")})

    # Offentliga projekt: infrastrukturinvestering + näringsliv.
    public = 100 * (0.6 * infra + 0.4 * biz)
    recs.append({
        "question_en": "Should you target public projects?",
        "verdict": _verdict(public), "score": int(round(public)),
        "rationale_en": ("Municipal investment and the business base point to "
                         "a public-procurement pipeline." if public >= 55 else
                         "Public investment here is limited right now.")})

    # Byta/skärpa inriktning: starkaste dolda möjligheten.
    hidden = hidden_opportunities(report, vertical_id)["opportunities"]
    top_hidden = hidden[0] if hidden else None
    refocus = top_hidden["strength"] if top_hidden else 0
    recs.append({
        "question_en": "Should you shift or sharpen your focus?",
        "verdict": _verdict(refocus), "score": int(round(refocus)),
        "rationale_en": (f"{top_hidden['title_en']} – {top_hidden['action_en']}"
                         if top_hidden else
                         "No strong adjacent niche stands out here yet.")})

    # Certifiering: vilken specialisering lyfter scoren mest på platsen.
    cert = _best_certification(report, vertical_id)
    recs.append({
        "question_en": "Which certification would raise revenue most?",
        "verdict": "consider" if cert else "not_now",
        "score": cert["uplift"] if cert else 0,
        "rationale_en": (f"Specializing toward {cert['label_en']} re-weights "
                         f"this location most in your favour (+{cert['uplift']} "
                         f"score points)." if cert else
                         "No specialization clearly outperforms the generic "
                         "profile here.")})

    recs.sort(key=lambda x: -x["score"])
    return {
        "team_size": team_size,
        "recommendations": recs,
        "notis_en": "Growth advice derived from the location's signals – a "
                    "decision prompt weighing demand, competition, public "
                    "investment and adjacent niches. Not a directive.",
    }


def _best_certification(report, vertical_id: str) -> dict | None:
    """Vilken specialisering som lyfter platsens score mest (certifieringsvärde)."""
    base = report.opportunity_score
    best = None
    prof = VERTICALS[vertical_id]
    for s in specializations_for(vertical_id):
        boost = specialization_boost(vertical_id, s["id"])
        if not boost:
            continue
        # Räkna om score med boostade vikter ur befintlig signalbild.
        num = den = 0.0
        for f in prof.factors:
            fnum = fden = 0.0
            for sid, w in f.signals:
                sig = report.signals.get(sid)
                if sig is None:
                    continue
                fnum += w * sig["normalized"]
                fden += w
            if fden == 0:
                continue
            fscore = 100.0 * fnum / fden
            eff = f.weight * boost.get(f.id, 1.0)
            num += fscore * eff
            den += eff
        if den == 0:
            continue
        score = num / den
        uplift = int(round(score - base))
        if uplift > 0 and (best is None or uplift > best["uplift"]):
            best = {"id": s["id"], "label_en": s["label_en"], "uplift": uplift}
    return best


# ── 4. Legal & compliance guide (regelkategorier som data) ───────────
# Regelverk skiljer sig mellan marknader; vi modellerar KATEGORIER som
# gäller per verksamhet, med vad de innebär i praktiken – aldrig en
# specifik paragraf som om den vore verifierad. En jurisdiktionsadapter
# (per marknad) fyller i exakta författningar.
@dataclass(frozen=True)
class RegCategory:
    id: str
    label_en: str
    practice_en: str


_REG_GENERIC = (
    RegCategory("work_environment", "Work-environment rules",
                "You must document risk assessments and keep the workplace "
                "safe – applies from your first employee."),
    RegCategory("consumer_services", "Consumer-services rules",
                "Quotes, complaints and liability toward private customers "
                "follow consumer-protection rules."),
    RegCategory("documentation", "Documentation & record-keeping",
                "Jobs, invoices and safety checks must be documented and "
                "retained."),
    RegCategory("insurance", "Insurance requirements",
                "Liability (and often professional) insurance is expected – "
                "and required to bid for public contracts."),
)
_REG_BY_VERTICAL: dict[str, tuple[RegCategory, ...]] = {
    "elektriker": (
        RegCategory("electrical_safety", "Electrical-safety regulation",
                    "Installation work requires a registered electrical-"
                    "installation company and certified staff."),
        RegCategory("installer_registration", "Installer registration",
                    "The company must be registered with the electrical-"
                    "safety authority for the work categories you take on."),
    ),
    "vvs": (
        RegCategory("water_safety", "Water & heating safety rules",
                    "Certified installation and approved products are "
                    "required for water, heating and gas work."),
    ),
    "bygg": (
        RegCategory("building_permits", "Building & permit rules",
                    "Permits, control plans and a certified control officer "
                    "are required for many works."),
    ),
    "restaurang": (
        RegCategory("food_safety", "Food-safety & hygiene rules",
                    "You need food-hygiene registration and documented "
                    "self-monitoring (HACCP)."),
        RegCategory("alcohol", "Alcohol-serving permit",
                    "Serving alcohol requires a separate licence and staff "
                    "training."),
    ),
    "cafe": (
        RegCategory("food_safety", "Food-safety & hygiene rules",
                    "Food-hygiene registration and documented self-monitoring "
                    "are required."),
    ),
    "tandlakare": (
        RegCategory("health_care", "Health-care regulation",
                    "Licensed staff, patient-record and hygiene requirements "
                    "apply."),
    ),
    "veterinar": (
        RegCategory("animal_care", "Animal-care regulation",
                    "Licensed veterinary staff and animal-welfare records are "
                    "required."),
    ),
    "bilverkstad": (
        RegCategory("vehicle_env", "Vehicle & environmental rules",
                    "Handling of oils, refrigerants and waste is regulated "
                    "and must be documented."),
    ),
    "aldreomsorg": (
        RegCategory("care_permit", "Care-provider authorization",
                    "Operating care requires authorization and staffing/"
                    "quality requirements."),
    ),
    "forskola": (
        RegCategory("childcare_permit", "Childcare authorization",
                    "A permit, staff ratios and safety requirements apply."),
    ),
    "apotek": (
        RegCategory("pharmacy_permit", "Pharmacy licence",
                    "Dispensing requires a pharmacy permit and a licensed "
                    "pharmacist."),
    ),
}


def legal_guide(vertical_id: str, bidding_public: bool = False) -> dict[str, Any]:
    """Regelkategorier som gäller verksamheten – vad de innebär i praktiken."""
    cats = list(_REG_BY_VERTICAL.get(vertical_id, ())) + list(_REG_GENERIC)
    if bidding_public:
        cats.append(RegCategory(
            "procurement_rules", "Public-procurement rules",
            "Bidding for public contracts adds qualification, transparency "
            "and appeal rules you must follow."))
    return {
        "vertical_id": vertical_id,
        "regulations": [{"id": c.id, "label_en": c.label_en,
                         "practice_en": c.practice_en} for c in cats],
        "count": len(cats),
        "notis_en": "Regulation CATEGORIES that apply to this business type, "
                    "with what they mean in practice. Exact statutes, numbers "
                    "and thresholds require a per-market legal adapter – not "
                    "legal advice.",
    }


# ── 5. Lifecycle advisor (var företaget befinner sig) ────────────────
_LIFECYCLE_STAGES = ("start", "grow", "expand", "mature")
_LIFECYCLE_CHECKLIST_EN: dict[str, list[str]] = {
    "start": ["Company registration", "Tax & VAT registration",
              "Business insurance", "Required certifications/permits"],
    "grow": ["First employees", "Equipment leasing vs. buy",
             "Additional certifications", "Working-capital financing"],
    "expand": ["Public procurement", "Regional & EU support",
               "Export readiness", "A second location"],
    "mature": ["Automation & efficiency", "Acquisition of a competitor",
               "Internationalization", "Succession planning"],
}


def _lifecycle_stage(company_form: str, team_size: str) -> str:
    idx = _TEAM_ORDER.index(team_size) if team_size in _TEAM_ORDER else 0
    if company_form in ("anstalld",) or (idx == 0 and company_form ==
                                         "enskild_firma"):
        return "start"
    if idx <= 1:
        return "grow"
    if idx <= 2:
        return "expand"
    return "mature"


def lifecycle_advisor(company_form: str = "aktiebolag",
                      team_size: str = "1") -> dict[str, Any]:
    """Var i livscykeln företaget är + vad som är nästa naturliga steg."""
    stage = _lifecycle_stage(company_form, team_size)
    nxt = _LIFECYCLE_STAGES[min(len(_LIFECYCLE_STAGES) - 1,
                                _LIFECYCLE_STAGES.index(stage) + 1)]
    return {
        "stage": stage,
        "company_form": company_form,
        "team_size": team_size,
        "focus_now_en": _LIFECYCLE_CHECKLIST_EN[stage],
        "next_stage": nxt,
        "prepare_next_en": _LIFECYCLE_CHECKLIST_EN[nxt],
        "notis_en": "Stage inferred from company form and team size – a "
                    "checklist prompt, not a mandate.",
    }


# ── Sammansatt ingång ────────────────────────────────────────────────
def opportunity_intel(location: Location, vertical_id: str,
                      resolver: Resolver | None = None,
                      specialization: str | None = None,
                      team_size: str = "1",
                      company_form: str = "aktiebolag",
                      market: str = DEFAULT_MARKET,
                      include_expansion: bool = True,
                      programs_client=None) -> dict[str, Any]:
    """Hela Opportunity Intelligence-lagret för en plats + verksamhet.

    `programs_client` (datasources.programs.ProgramsClient) is optional: when
    connected, real registry programs are merged into support_programs."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    mkt = get_market(market)
    boost = specialization_boost(vertical_id, specialization)
    report = analyze(location, vertical_id, resolver=resolver, factor_boost=boost)

    programs = support_programs(report, vertical_id, specialization,
                                programs=programs_client)
    # "You're missing money": kombinerbara stöd som ännu inte sökts.
    missing = {
        "unclaimed_programs": [{"id": p["id"], "label_en": p["label_en"],
                                "amount_estimate_local": p["amount_estimate_local"],
                                "eligibility_probability_pct":
                                    p["eligibility_probability_pct"]}
                               for p in programs["programs"] if p["combinable"]],
        "estimated_value_local": programs["combinable_total_estimate_local"],
        "notis_en": "Standard-estimate value of combinable support you may be "
                    "eligible for but have not applied to – not a live figure.",
    }

    out: dict[str, Any] = {
        "vertical_id": vertical_id,
        "vertical_label_en": VERTICALS[vertical_id].label_en,
        "specialization": specialization,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "location": {"lat": location.lat, "lon": location.lon,
                     "address": location.address},
        "opportunity_score": report.opportunity_score,
        "data_coverage": report.data_coverage,
        "support_programs": programs,
        "missing_money": missing,
        "hidden_opportunities": hidden_opportunities(report, vertical_id),
        "legal_guide": legal_guide(vertical_id, bidding_public=True),
        "lifecycle": lifecycle_advisor(company_form, team_size),
    }
    if include_expansion:
        out["expansion_advisor"] = expansion_advisor(
            report, vertical_id, team_size, specialization)
    out["caveats_en"] = [
        "Support amounts and probabilities are standard estimates derived from "
        "local signals – real figures, deadlines and eligibility require a live "
        "programs registry (adapter backlog).",
        "Hidden opportunities and expansion advice are strategic prompts, not "
        "guarantees; confidence follows data coverage.",
    ]
    if report.data_coverage < 1.0:
        out["caveats_en"].append(
            "Parts of the underlying data are simulated – see data_coverage.")
    return out


def program_catalog() -> dict[str, Any]:
    """Maskinläsbar katalog över programarketyperna (för /v1/catalog-klienter)."""
    return {
        "programs": [{"id": p.id, "label_en": p.label_en,
                      "verticals": list(p.verticals) or ["(all)"],
                      "combinable": p.combinable,
                      "source_hint_en": p.source_hint_en} for p in SUPPORT_PROGRAMS],
        "hidden_rules": [{"id": r.id, "title_en": r.title_en,
                          "verticals": list(r.verticals) or ["(all)"]}
                         for r in HIDDEN_RULES],
        "notis_en": "Program archetypes and detection rules are data. A live "
                    "registry adapter makes amounts and deadlines real.",
    }
