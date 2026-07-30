"""Områdesspaning: en observerad brist hos NÅGON ANNANS fastighet blir
en spårbar lead — aldrig en anonymiserad aggregering.

Skiljer sig från de två grannmodulerna med flit:

  * `engine/inspections.py` kontrollerar kundens EGNA registrerade
    objekt, på ett schema, mot en rutin — resultatet är ett
    efterlevnadsregister.
  * `engine/sponsorship.py` finansierar uppdrag där sponsorn ser
    k-golvade AGGREGAT, aldrig en individuell rad — poängen är att
    ingen enskild zoomer eller plats pekas ut.
  * Den här modulen gör motsatsen till sponsorship med flit: kunden
    BER om en lista med adresser och vad som var fel med varje en,
    eftersom hela produkten ÄR den spårbara raden — ett fönsterputtar-
    företag som frågar "vilka skyltfönster i det här kvarteret är
    smutsiga" behöver just adressen, inte ett medeltal.

Det är okej att göra här av samma skäl som gör det okej för vem som
helst att gå längs en gata och skriva ner vilka skyltfönster som är
smutsiga: observationen gäller en fastighets SYNLIGA, OFFENTLIGT
SYNLIGA yttre (ett skyltfönster, en fasad, en entré) — inte en
persons skyddade uppgift, och inget tillträde till något privat sker.
k-anonymitetsspärren i `engine/sensitive.py` gäller skyddade
kategorier om PERSONER; det här är villkoret hos en BYGGNAD.

Mediet lagras ALDRIG här — exakt samma regel som inspections.py: en
dom (severity) + uppdragsreferensen, aldrig bilden. Bilden och
samtycket för besöket bor hos quiXzoom.

Dispatchen ÅTERANVÄNDER `integrations.quixzoom_dispatch.MissionDispatcher`
rakt av: en spaningsadress är ett `asset`-format objekt för den
klienten, en spaningsorder är ett `routine`-format objekt. Ingen ny
beställningskod — samma vägran (`LANDVEX_QUIXZOOM_URL` saknas ⇒
inget uppdrags-id hittas på) gäller automatiskt här också.

Rent stdlib.
"""
from __future__ import annotations

import threading as _threading
import time as _time
import uuid as _uuid

# Fyra allvarlighetsgrader delade av alla villkor — enklare än en
# skala per villkor, och jämförbara (leads() filtrerar på tröskel).
SEVERITY = ("none", "light", "moderate", "severe")
_SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITY)}

CONDITIONS: dict[str, dict] = {
    "window_cleanliness": {
        "label_en": "Window cleanliness",
        "what_en": "How clean the storefront or building windows look "
                   "from the street.",
    },
    "facade_condition": {
        "label_en": "Facade condition",
        "what_en": "Visible paint, render or masonry condition on the "
                   "street-facing wall.",
    },
    "signage_condition": {
        "label_en": "Signage condition",
        "what_en": "Whether exterior signs are intact, lit and legible.",
    },
    "landscaping_condition": {
        "label_en": "Landscaping condition",
        "what_en": "Visible upkeep of street-facing greenery, hedges or "
                   "planters.",
    },
}


class SurveyRefused(ValueError):
    """Ordern eller domen gick inte att skapa, och varför."""


def survey(id: str, label_en: str, condition: str,
          addresses: list[dict], *, tenant: str = "") -> dict:
    """En spaningsorder: villkoret att leta efter, över namngivna
    adresser. Adresserna är TREDJE PARTS fastigheter — kunden anger
    dem explicit, plattformen geokodar ingenting åt någon."""
    if not tenant:
        raise SurveyRefused("a survey needs a tenant")
    if condition not in CONDITIONS:
        raise SurveyRefused(
            f"unknown condition {condition!r} — choose from "
            f"{sorted(CONDITIONS)}. Naming an unlisted condition would "
            f"leave a zoomer guessing what to look for.")
    if not addresses:
        raise SurveyRefused("a survey needs at least one address")
    for a in addresses:
        if not a.get("id") or not a.get("address"):
            raise SurveyRefused(
                f"every address needs an id and a text address: {a!r}")
        if a.get("lat") is None or a.get("lon") is None:
            raise SurveyRefused(
                f"address {a.get('id')!r} has no coordinates — a field "
                f"contributor cannot be sent to a place without one")
    return {
        "id": id, "tenant": tenant, "label_en": label_en,
        "condition": condition,
        "condition_label_en": CONDITIONS[condition]["label_en"],
        "addresses": list(addresses),
        "created_at": _time.time(),
        "scope_en": ("Exterior, street-visible observation only — the "
                     "same thing anyone walking this street could note "
                     "by eye. No entry, no interior access, and nothing "
                     "about who owns or occupies the address."),
    }


def dispatch_survey(surv: dict, *, dispatcher=None,
                    radius_m: int = 30) -> dict:
    """Beställ ETT uppdrag per adress hos quiXzoom.

    Återanvänder MissionDispatcher rakt av: en adress i spaningen ÄR
    ett asset-format objekt för den klienten, spaningsordern ÄR ett
    routine-format objekt. Vägran per adress räknas som ett svar, inte
    ett fel — samma regel som dispatch_due().
    """
    from integrations.quixzoom_dispatch import DispatchRefused, MissionDispatcher

    d = dispatcher or MissionDispatcher()
    rut = {"id": surv["id"], "label_en": f"Survey: {surv['label_en']}",
          "checks": [surv["condition"]], "audience": {"pool": "open"}}
    due_at = _time.strftime("%Y-%m-%d")
    bestallda, vagrade = [], []
    for a in surv["addresses"]:
        asset = {"id": a["id"], "lat": a["lat"], "lon": a["lon"],
                "address": a["address"], "tenant": surv["tenant"],
                "label_en": a["address"]}
        try:
            bestallda.append({**d.dispatch(asset, rut, due_at,
                                          radius_m=radius_m),
                             "address": a["address"]})
        except DispatchRefused as e:
            vagrade.append({"address_id": a["id"], "why_en": str(e)})
    return {
        "survey_id": surv["id"], "ordered": bestallda, "refused": vagrade,
        "ordered_count": len(bestallda), "refused_count": len(vagrade),
        "connected": d.connected,
        "note_en": ("Refusals are answers, not errors — each names the "
                    "address and the reason a mission could not be "
                    "placed."),
    }


def verdict(survey_id: str, address_id: str, severity: str, *,
           mission_id: str = "", evidence_ref: str = "",
           note_en: str = "", tenant: str = "") -> dict:
    """Registrera en observerad allvarlighetsgrad. Kräver bevis för
    allt utom "none" — en severity utan bevis går inte att försvara
    i efterhand, exakt samma regel som inspections.record()."""
    if severity not in SEVERITY:
        raise SurveyRefused(
            f"unknown severity {severity!r}; choose from {SEVERITY}")
    if severity != "none" and not (mission_id or evidence_ref):
        raise SurveyRefused(
            f"severity {severity!r} needs evidence (mission_id or "
            f"evidence_ref) — an unsupported severity is a claim, not "
            f"an observation")
    return {
        "id": _uuid.uuid4().hex[:16],
        "survey_id": survey_id, "address_id": address_id, "tenant": tenant,
        "severity": severity,
        "performed_at": _time.strftime("%Y-%m-%d"),
        # Mediet lagras ALDRIG här — bara pekaren, exakt som inspections.py.
        "mission_id": mission_id, "evidence_ref": evidence_ref,
        "note_en": note_en,
        "basis_en": ("One observation from one field visit at one "
                     "moment. It says what the exterior looked like "
                     "that day; it does not say how long it has looked "
                     "that way, and it says nothing about who occupies "
                     "the address."),
    }


def leads(survey_id: str, *, min_severity: str = "light",
         tenant: str = "") -> dict:
    """Adresserna som mötte tröskeln — verdikt + uppdragsreferens,
    ALDRIG bilden. Det är hela produkten: en spårbar rad per adress."""
    if min_severity not in SEVERITY:
        raise SurveyRefused(f"unknown severity {min_severity!r}")
    troskel = _SEVERITY_ORDER[min_severity]
    surv = next((s for s in all_surveys(tenant) if s["id"] == survey_id),
               None)
    if surv is None:
        return {"survey_id": survey_id, "leads": [], "count": 0,
                "why_en": "no such survey for this tenant"}
    adresser = {a["id"]: a for a in surv["addresses"]}
    trafflista = []
    for v in all_verdicts(tenant):
        if v["survey_id"] != survey_id:
            continue
        if _SEVERITY_ORDER.get(v["severity"], -1) < troskel:
            continue
        a = adresser.get(v["address_id"], {})
        trafflista.append({
            "address_id": v["address_id"], "address": a.get("address", ""),
            "lat": a.get("lat"), "lon": a.get("lon"),
            "severity": v["severity"], "performed_at": v["performed_at"],
            "mission_id": v["mission_id"], "note_en": v["note_en"],
        })
    trafflista.sort(key=lambda r: -_SEVERITY_ORDER[r["severity"]])
    return {
        "survey_id": survey_id, "condition": surv["condition"],
        "condition_label_en": surv["condition_label_en"],
        "min_severity": min_severity, "leads": trafflista,
        "count": len(trafflista),
        "scope_en": surv["scope_en"],
        "cannot_en": ("Each row is one field visit's observation, not a "
                      "guarantee of current condition — a lead is worth "
                      "checking, not worth assuming."),
    }


def catalog() -> dict:
    return {
        "what_en": ("Order a field survey for an observable exterior "
                    "condition (dirty windows, a tired facade, broken "
                    "signage) across named addresses, and get back the "
                    "addresses that actually met the threshold — a "
                    "sales lead list, not an aggregate."),
        "conditions": [{"id": k, **v} for k, v in CONDITIONS.items()],
        "severity_scale": list(SEVERITY),
        "scope_en": ("Exterior, street-visible observation of named "
                     "third-party addresses the customer supplies — no "
                     "entry, no interior access. This is the opposite "
                     "of sponsorship's k-floored aggregates on purpose: "
                     "the product IS the traceable row."),
        "cannot_en": ("The photo is never stored here — only the "
                      "severity verdict and the mission reference, "
                      "exactly like asset inspections. A lead names a "
                      "place and what a field visit saw there once; it "
                      "names no person."),
    }


# ── Lagret (samma mönster som inspections.py) ──────────────────────────
_LOCK = _threading.Lock()
_SURVEYS: list[dict] = []
_VERDICTS: list[dict] = []
_STORE = None


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_survey(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_survey", None):
        return _STORE.save_survey(rec)
    with _LOCK:
        for i, r in enumerate(_SURVEYS):
            if r["id"] == rec["id"]:
                _SURVEYS[i] = rec
                return rec["id"]
        _SURVEYS.append(dict(rec))
    return rec["id"]


def save_verdict(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_lead_verdict", None):
        return _STORE.save_lead_verdict(rec)
    with _LOCK:
        _VERDICTS.append(dict(rec))
    return rec["id"]


def all_surveys(tenant: str | None = None) -> list[dict]:
    rader = (_STORE.all_surveys() if _STORE is not None
            and getattr(_STORE, "all_surveys", None) else list(_SURVEYS))
    return [r for r in rader if tenant is None or r.get("tenant") == tenant]


def all_verdicts(tenant: str | None = None) -> list[dict]:
    rader = (_STORE.all_lead_verdicts() if _STORE is not None
            and getattr(_STORE, "all_lead_verdicts", None)
            else list(_VERDICTS))
    return [r for r in rader if tenant is None or r.get("tenant") == tenant]


def reset() -> None:
    """Endast för tester."""
    with _LOCK:
        _SURVEYS.clear()
        _VERDICTS.clear()
