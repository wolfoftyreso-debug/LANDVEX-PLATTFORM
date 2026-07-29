"""Risk Intelligence / Business Signals™ – affärsradar bredvid Opportunity Score.

Nästan alla företagssystem är bakåtblickande (bokföring, statistik). Det
här lagret är framåtblickande: det upptäcker FÖRÄNDRINGAR och väger samman
dem till ett beslutsstöd. Landvex behöver inte avgöra vad som är sant –
den upptäcker signaler, väger dem, beskriver möjliga konsekvenser och
föreslår konkreta åtgärder (data → signal → rekommendation → beslut).

Tre delar:

  1. Risk Score (0–100, LÄGRE = mindre risk) bredvid Opportunity Score –
     nedbruten i tio kategorier. Kategorier som går att härleda ur platsens
     signaler beräknas; övriga redovisas ärligt som "monitoring" (kräver en
     live-flödesadapter) i stället för en påhittad siffra.
  2. Business Signals – signalramverket grupperat i kategorier (finansiella,
     kund-, personal-, affärs-, projekt-, marknads-, offentliga,
     leverantörssignaler). En enskild signal betyder lite; flera samman
     mycket. Varje signaltyp är märkt beräknad-nu eller monitoring.
  3. Counterparty Health – ett FÖRSIKTIGT ramverk: objektiva risksignaler
     hos en motpart + försiktighetsåtgärder. Systemet drar ALDRIG juridiska
     slutsatser och säger ALDRIG att en affär inte får göras – det pekar på
     signaler och föreslår att man ser över betalningsvillkor/säkerheter.
     Att bedöma en SPECIFIK motpart kräver en kredit-/registeradapter.

Ärlighet (princip 3 & 4): trend/förändring kräver historik – utan
monitoring-flöde redovisas trend som "requires monitoring history", aldrig
en påhittad pil. Determinism: samma plats + vertikal → samma Risk Score.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datasources.base import Resolver
from .datasources.defaults import default_resolver
from .datasources.faults import OUR_BUGS
from .markets import DEFAULT_MARKET, get_market
from .models import Location
from .scoring import analyze
from .signals import CATALOG, normalize
from .specialization import specialization_boost
from .verticals import VERTICALS



# ── Risk-kategorier (tio) ────────────────────────────────────────────
# En kategori med driver_signals beräknas ur signalbilden; en med tom
# driver_signals är "monitoring" – den kräver ett live-flöde (kredit-,
# konkurrent-, recensions-, lag- eller upphandlingsdata).
@dataclass(frozen=True)
class RiskCategory:
    id: str
    label_en: str
    weight: float
    driver_signals: tuple[tuple[str, float], ...]   # tom = monitoring-only
    watch_en: str                                   # vad radarn bevakar
    mitigation_en: str


RISK_CATEGORIES: tuple[RiskCategory, ...] = (
    RiskCategory(
        "market", "Market risk", 0.16,
        (("competition_pressure", 0.5), ("provider_gap", 0.3),
         ("pop_growth_pct", 0.2)),
        "New competitors, a national chain establishing, demand shifts.",
        "Differentiate, secure a niche, and watch competitor moves nearby."),
    RiskCategory(
        "competition", "Competition risk", 0.12,
        (("competition_pressure", 0.7), ("business_density", 0.3)),
        "Competitor hiring, price changes, rating swings, closures.",
        "Track competitor capacity and pricing; defend on service quality."),
    RiskCategory(
        "financial", "Financial risk", 0.14,
        (("rent_index", 0.5), ("vacancy_rate", 0.3), ("income_index", 0.2)),
        "Rent pressure, weak local purchasing power, high vacancy.",
        "Negotiate stepped rent; keep a liquidity buffer for slow quarters."),
    RiskCategory(
        "geographic", "Geographic risk", 0.10,
        (("climate_risk_index", 0.6), ("crime_index", 0.4)),
        "Climate exposure and area safety.",
        "Insure against climate exposure; factor security into premises."),
    RiskCategory(
        "project", "Project risk", 0.10,
        (("building_permits", 0.5), ("detail_plans", 0.5)),
        "Construction pauses, financing pulled, permits appealed, "
        "procurements cancelled.",
        "Stage contracts, verify financing and use milestone billing."),
    RiskCategory(
        "supplier", "Supplier risk", 0.08,
        (("logistics_access", 1.0),),
        "Supplier credit weakening, longer lead times, price hikes, "
        "product discontinuations.",
        "Qualify a second source; watch lead-time and credit changes."),
    RiskCategory(
        "customer", "Customer / counterparty risk", 0.12, (),
        "Counterparty debts, reconstruction filings, worsening accounts, "
        "board churn, payment defaults.",
        "Consider advance payment, shorter terms or added security; spread "
        "future work across more customers."),
    RiskCategory(
        "regulatory", "Regulatory risk", 0.08, (),
        "New work-environment, installation, ROT, VAT or procurement rules.",
        "Track rule changes for your trade and prepare before they apply."),
    RiskCategory(
        "staffing", "Staffing risk", 0.06, (),
        "Key people leaving, hard-to-fill roles, large recruitment drives.",
        "Build a bench for key roles; monitor the local skills shortage."),
    RiskCategory(
        "legal", "Legal & permit risk", 0.04, (),
        "Certifications expiring, authorizations to renew, missing "
        "inspections or insurance.",
        "Keep a permit/certification calendar; renew before expiry."),
)

_MONITORING_NOTE_EN = ("Monitoring category – needs a live feed (credit, "
                       "competitor, review, law or procurement data) to score "
                       "a specific case. The watchlist shows what it tracks.")


def _band(risk: float) -> str:
    if risk < 30:
        return "gron"
    if risk < 55:
        return "gul"
    return "rod" if risk < 75 else "rod"


def _band_en(risk: float) -> str:
    return "Low" if risk < 30 else "Medium" if risk < 55 else \
        "High" if risk < 75 else "Very high"


_OBSERVED_NOTE_EN = (
    "Raised by CORROBORATED REPORTING — at least two independent owners "
    "said it — not by a computed signal. It carries no number and is not "
    "part of risk_score, which aggregates only categories derived from "
    "signals. The outlets are named so the basis can be checked or "
    "dismissed.")


def _category_risk(signals: dict, cat: RiskCategory,
                   observed: dict | None = None) -> dict[str, Any]:
    """Beräknad risk 0–100 för en kategori — eller observerad, eller
    monitoring.

    Tre lägen, inte två. En kategori utan drivsignaler kunde tidigare
    bara vara `monitoring`; en bekräftad nyhetsuppgift som rör den gör
    den `observed`. Skillnaden mot `computed` är avgörande: observed bär
    ett BAND och sina utgivare, aldrig ett tal, och räknas aldrig in i
    risk_score.
    """
    rapporter = (observed or {}).get(cat.id) or []
    if not cat.driver_signals:
        if rapporter:
            return {"id": cat.id, "label_en": cat.label_en,
                    "status": "observed", "band_en": "Elevated",
                    "basis": rapporter, "sources_en": sorted(
                        {o for r in rapporter for o in r["owners"]}),
                    "watch_en": cat.watch_en,
                    "mitigation_en": cat.mitigation_en,
                    "notis_en": _OBSERVED_NOTE_EN}
        return {"id": cat.id, "label_en": cat.label_en, "status": "monitoring",
                "watch_en": cat.watch_en, "mitigation_en": cat.mitigation_en,
                "notis_en": _MONITORING_NOTE_EN}
    num, den, parts = 0.0, 0.0, []
    for sid, w in cat.driver_signals:
        sig = signals.get(sid)
        if sig is None:
            continue
        n = sig["normalized"]
        num += w * n
        den += w
        d = CATALOG.get(sid)
        parts.append({"signal_id": sid, "label_en": d.label_en if d else sid,
                      "value": sig["value"], "unit": d.unit if d else "",
                      "source": sig["source"],
                      "risk_contribution": int(round(100 * (1 - n)))})
    if den == 0:
        return {"id": cat.id, "label_en": cat.label_en, "status": "monitoring",
                "watch_en": cat.watch_en, "mitigation_en": cat.mitigation_en,
                "notis_en": _MONITORING_NOTE_EN}
    risk = int(round(100 * (1 - num / den)))
    parts.sort(key=lambda p: -p["risk_contribution"])
    ut = {"id": cat.id, "label_en": cat.label_en, "status": "computed",
          "risk": risk, "band": _band(risk), "band_en": _band_en(risk),
          "watch_en": cat.watch_en,
          "drivers": parts,
          "mitigation_en": cat.mitigation_en if risk >= 55 else None}
    if rapporter:
        # En beräknad kategori BEHÅLLER sitt tal. Rapporteringen läggs
        # bredvid som en notering, aldrig i talet: ett Risk Score som
        # kunde flyttas av en rubrik vore inte längre härlett.
        ut["reported_alongside"] = rapporter
        ut["reported_note_en"] = (
            "Corroborated reporting touches this category. It is shown "
            "beside the computed risk and did NOT change it.")
    return ut


# ── Business Signals™ ramverk (signaltyper som data) ─────────────────
BUSINESS_SIGNAL_CATEGORIES: dict[str, dict[str, Any]] = {
    "financial": {
        "label_en": "Financial signals",
        "signals_en": ["Credit rating change", "Sharp revenue drop",
                       "Worsening result", "Deteriorating liquidity",
                       "New payment defaults", "Rising debts",
                       "Reconstruction or bankruptcy filing"],
        "source_needed_en": "Credit-registry adapter (history for change "
                            "detection)."},
    "customer": {
        "label_en": "Customer signals",
        "signals_en": ["Google rating falls (e.g. 4.7 → 3.8)",
                       "Surge in negative reviews",
                       "Complaints about late payment or quality",
                       "Fewer returning customers", "Falling digital visibility"],
        "source_needed_en": "Reviews/visibility adapter."},
    "staffing": {
        "label_en": "Staffing signals",
        "signals_en": ["CEO replaced", "Board changes", "New CFO",
                       "Key people leaving", "Large staff cuts",
                       "Big recruitment drives"],
        "source_needed_en": "Company-registry / job-ad adapter."},
    "business": {
        "label_en": "Business signals",
        "signals_en": ["Opens a branch", "Closes an office", "Changes address",
                       "Change of ownership", "Name change",
                       "New activities registered", "Acquires a company"],
        "source_needed_en": "Company-registry adapter."},
    "project": {
        "label_en": "Project signals",
        "signals_en": ["Construction paused", "Financing withdrawn",
                       "Permit appealed", "Procurement cancelled",
                       "Contractor replaced"],
        "source_needed_en": "Permits / procurement adapter."},
    "market": {
        "label_en": "Market signals",
        "signals_en": ["New competitor establishes", "Competitor closes",
                       "Competitor expands", "Price changes",
                       "New technology", "Demand rises or falls"],
        "source_needed_en": "Competitor / market adapter.",
        "partially_computed_en": "Demand and competition proxies are computed "
                                 "today from local signals."},
    "public": {
        "label_en": "Public signals",
        "signals_en": ["New comprehensive plan", "New detail plan",
                       "New investment decision", "New hospital/school",
                       "New industrial park", "New railway",
                       "New environmental requirements", "New grants/support"],
        "source_needed_en": "Municipal open-data adapter.",
        "partially_computed_en": "Building permits, detail plans and "
                                 "infrastructure investment are computed today."},
    "supplier": {
        "label_en": "Supplier signals",
        "signals_en": ["Supplier credit worsens", "Longer lead times",
                       "Price increases", "Distributor change",
                       "Product discontinued", "Ownership change"],
        "source_needed_en": "Supplier credit / catalog adapter."},
}


def business_signals_framework() -> dict[str, Any]:
    """Signalramverket – vad varje kategori bevakar och vad den kräver."""
    return {
        "categories": BUSINESS_SIGNAL_CATEGORIES,
        "principle_en": "A single signal means little; several together can be "
                        "very meaningful. Landvex detects changes, weighs them "
                        "and suggests actions – it does not judge truth.",
        "notis_en": "Signal DEFINITIONS are data. Detecting live changes and "
                    "trends requires the listed feed adapters with history.",
    }


# ── Counterparty Health (försiktigt ramverk) ─────────────────────────
_COUNTERPARTY_SIGNALS_EN = [
    {"signal_en": "Debts registered with the enforcement authority",
     "weight": 15},
    {"signal_en": "Reconstruction / insolvency filing", "weight": 20},
    {"signal_en": "Sharply worsening annual accounts", "weight": 12},
    {"signal_en": "Unusually many board changes", "weight": 8},
    {"signal_en": "Sharply rising supplier debts", "weight": 10},
    {"signal_en": "Many payment injunctions", "weight": 12},
    {"signal_en": "Late VAT or tax payments", "weight": 10},
    {"signal_en": "Stalled construction projects", "weight": 8},
    {"signal_en": "Several subcontractors leaving the project", "weight": 5},
]


def counterparty_health_framework() -> dict[str, Any]:
    """Ramverk för motpartsrisk – objektiva signaler + försiktighetsåtgärder.

    Beräknar INGET om en specifik motpart (kräver kreditdata). Levererar
    modellen: vilka objektiva signaler som väger, hur ett Health Score skulle
    byggas, och försiktiga handlingsalternativ – aldrig en juridisk slutsats,
    aldrig 'gör inte affären'."""
    return {
        "model": "counterparty_health_score",
        "base_score": 100,
        "objective_signals": _COUNTERPARTY_SIGNALS_EN,
        "precautions_en": [
            "Consider advance or partial payment.",
            "Consider shorter payment terms.",
            "Consider additional security before larger deliveries.",
            "Spread future work across more customers.",
        ],
        "guardrail_en": "The system never concludes that a deal must not be "
                        "done and never draws legal conclusions – it flags "
                        "objective signals and suggests caution. A specific "
                        "counterparty score requires a credit/registry adapter.",
    }


def _observations(location: Location, market: str, res) -> dict:
    """Bekräftade nyhetsuppgifter per riskkategori för den här platsen.

    Tomt när nyhetsskörden inte är påslagen — och det är rätt: en
    kategori utan rapportering ska stå kvar som `monitoring`, inte som
    lugn.
    """
    try:
        from engine import news as N
        from engine.markets import MARKETS
    except OUR_BUGS:
        # ImportError STÅR i OUR_BUGS: en trasig nyhetsmodul är vår bugg,
        # och att svälja den här gjorde varje importfel till "ingen
        # rapportering" — kategorierna stod kvar som lugn monitoring
        # medan koden var sönder. Revisionens fynd D1.
        raise
    except Exception:                                   # noqa: BLE001
        return {}
    poster = N.all_items(market=market, max_age_days=N_MAX_AGE_DAYS)
    if not poster:
        return {}
    regioner = MARKETS[market].regions if market in MARKETS else []
    kod = _narmaste_region(location, regioner)
    kluster = N.cluster(poster)
    for k in kluster:
        koder = {i.get("region_code", "") for i in k["items"]}
        k["region_code"] = next((c for c in koder if c), "")
    return N.observations_for(kluster, region_code=kod)["by_category"]


# Nyheter äldre än så här räknas inte som "vad som hänt".
N_MAX_AGE_DAYS = 7.0


def _narmaste_region(location: Location, regioner) -> str:
    """Vilken region punkten ligger i. Nyheter knyts till region, inte
    till koordinat — en artikel har ingen position."""
    bast, bast_kod = None, ""
    for kod, _namn, lat, lon in regioner:
        d = (lat - location.lat) ** 2 + (lon - location.lon) ** 2
        if bast is None or d < bast:
            bast, bast_kod = d, kod
    return bast_kod


# ── Sammansatt Risk Intelligence ─────────────────────────────────────
def _recommendations(opportunity: float, categories: list[dict]) -> list[dict]:
    """Data → signal → rekommendation. Konkreta handlingsalternativ."""
    recs = []
    computed = [c for c in categories if c.get("status") == "computed"]
    for c in sorted(computed, key=lambda x: -x.get("risk", 0))[:3]:
        if c["risk"] >= 55 and c.get("mitigation_en"):
            recs.append({"trigger_en": f"{c['label_en']} is elevated "
                                       f"({c['risk']}/100).",
                         "action_en": c["mitigation_en"],
                         "category": c["id"]})
    if opportunity >= 70 and not any(c.get("risk", 0) >= 60 for c in computed):
        recs.append({
            "trigger_en": f"Strong opportunity ({int(opportunity)}/100) with "
                          f"no elevated computed risk.",
            "action_en": "A good moment to increase marketing or recruit "
                         "ahead of demand.",
            "category": "opportunity"})
    if not recs:
        recs.append({"trigger_en": "No elevated computed risk at this location.",
                     "action_en": "Maintain normal terms; enable monitoring to "
                                  "catch changes early.",
                     "category": "none"})
    return recs


def risk_intelligence(location: Location, vertical_id: str,
                      resolver: Resolver | None = None,
                      specialization: str | None = None,
                      market: str = DEFAULT_MARKET) -> dict[str, Any]:
    """Dual Opportunity/Risk-radar för en plats + verksamhet."""
    if vertical_id not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical_id}. "
                         f"Available: {', '.join(sorted(VERTICALS))}")
    mkt = get_market(market)
    res = resolver or default_resolver()
    boost = specialization_boost(vertical_id, specialization)
    report = analyze(location, vertical_id, resolver=res, factor_boost=boost)

    # Risk-kategorierna behöver signaler utanför vertikalens faktorer
    # (t.ex. klimat-/brottsindex). Resolva dem och komplettera signalbilden
    # så att fler kategorier kan beräknas i stället för att falla till
    # monitoring – samma källkedja, samma ärliga source-märkning.
    signals = dict(report.signals)
    need = {sid for c in RISK_CATEGORIES for sid, _ in c.driver_signals
            if sid not in signals}
    if need:
        values, _ = res.resolve(location, vertical_id, sorted(need))
        for sid, sv in values.items():
            if sv is not None and sv.value is not None and sid not in signals:
                signals[sid] = {"value": sv.value, "source": sv.source,
                                "quality": sv.quality,
                                "normalized": round(
                                    normalize(CATALOG[sid], sv.value), 3)}

    observed = _observations(location, market, res)
    categories = [_category_risk(signals, c, observed) for c in RISK_CATEGORIES]
    computed = [(c, cat) for c, cat in zip(categories, RISK_CATEGORIES, strict=False)
                if c.get("status") == "computed"]
    # Sammanvägd Risk Score – endast beräknade kategorier (ärlig täckning).
    num = sum(c["risk"] * cat.weight for c, cat in computed)
    den = sum(cat.weight for _, cat in computed) or 1.0
    risk_score = int(round(num / den))
    monitoring = [c["id"] for c in categories if c.get("status") == "monitoring"]

    return {
        "vertical_id": vertical_id,
        "vertical_label_en": VERTICALS[vertical_id].label_en,
        "specialization": specialization,
        "market": mkt.id, "market_label_en": mkt.label_en,
        "location": {"lat": location.lat, "lon": location.lon,
                     "address": location.address},
        # Dual meters.
        "opportunity_score": report.opportunity_score,
        "risk_score": risk_score,
        "risk_band_en": _band_en(risk_score),
        "trend": {"status": "requires_monitoring_history",
                  "notis_en": "Trend/change detection needs a monitoring feed "
                              "with history – not shown as a guessed arrow."},
        "risk_categories": categories,
        "monitoring_categories": monitoring,
        "observed_categories": [c["id"] for c in categories
                                if c.get("status") == "observed"],
        "computed_coverage": round(len(computed) / len(RISK_CATEGORIES), 2),
        "business_signals": business_signals_framework(),
        "counterparty_health": counterparty_health_framework(),
        "recommendations": _recommendations(report.opportunity_score, categories),
        "data_coverage": report.data_coverage,
        "caveats_en": [
            "Risk Score aggregates only the categories computable from local "
            "signals; the rest are monitoring categories that need live feeds.",
            "Change and trend detection require a monitoring adapter with "
            "history – this is a point-in-time picture.",
            "Counterparty guidance flags objective signals and suggests "
            "caution; it is never a legal conclusion or a 'do not deal'.",
        ],
    }


def risk_intel_catalog() -> dict[str, Any]:
    """Maskinläsbar katalog över risk-kategorier och signalramverket."""
    return {
        "risk_categories": [{"id": c.id, "label_en": c.label_en,
                             "mode": "computed" if c.driver_signals
                             else "monitoring", "watch_en": c.watch_en}
                            for c in RISK_CATEGORIES],
        "business_signal_categories": list(BUSINESS_SIGNAL_CATEGORIES),
        "notis_en": "Categories and signal definitions are data; live change "
                    "detection needs feed adapters.",
    }
