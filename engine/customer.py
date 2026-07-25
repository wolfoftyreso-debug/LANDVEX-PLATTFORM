"""Kundresan: KYC → onboarding → uppsättning → aktiv.

En Landvexkund har mer att ställa in än "systemet". Kedjan börjar med KYC,
går vidare till onboarding och först därefter till uppsättningen av
plattformen. Det här lagret håller ordning på VAR i kedjan en kund är, VEM
som äger varje steg, och vad som är spärrat tills steget är klart.

Den viktigaste regeln gäller KYC: **plattformen utför aldrig KYC och
intygar den aldrig själv.** Status kommer från den externa KYC/AML-
leverantören eller finns inte alls. Saknas den är svaret `not_verified` –
aldrig ett antagande om att det nog är i sin ordning. Ett system som
gissar på kundkännedom är inte ett hjälpsamt system, det är en
compliance-risk.

Ansvarsfördelning, explicit i data (`STAGES[i]["owner"]`):

    kyc         extern KYC/AML-leverantör   → verifierad identitet/enhet
    onboarding  Landvex kundonboarding       → kundposten (eget repo)
    setup       den här plattformen          → roll, plats, bransch, insatser
    active      löpande drift                → routade händelser, beslut

Uppsättningssteget delegerar till `engine.visitor` – samma kännedomsskala,
samma ärlighet om vad som saknas. Rent stdlib.
"""
from __future__ import annotations

from . import visitor as _visitor

# Vad KYC låser upp när den är klar. Allt som rör pengar, känsliga uppgifter
# eller utlämning till tredje part står här – aldrig tillgängligt på ett
# obekräftat konto.
KYC_GATED: tuple[str, ...] = (
    "billing & commission payouts",
    "live data layers (subscription)",
    "partner API and agent access",
    "sensitive-category analysis",
    "data export to third parties",
)

STAGES: tuple[dict, ...] = (
    {"id": "kyc", "label_en": "Know Your Customer",
     "owner": "external KYC/AML provider",
     "owned_by_platform": False,
     "produces_en": "A verified legal identity and entity for the customer.",
     "requires": ("kyc_status",),
     "gates_en": list(KYC_GATED),
     "note_en": "Landvex never performs or self-attests KYC. Status is "
                "supplied by the provider; absent it, the answer is "
                "not_verified — never an assumption."},
    {"id": "onboarding", "label_en": "Customer onboarding",
     "owner": "Landvex customer onboarding",
     "owned_by_platform": False,
     "produces_en": "The customer record: who they are, what they bought, "
                    "which market and role applies.",
     "requires": ("visitor_id", "role"),
     "gates_en": ["any answer tailored to this customer"],
     "note_en": "Owned outside this repository. It delivers into the "
                "documented seam (GET /v1/visitor/contract); this platform "
                "does not duplicate it."},
    {"id": "setup", "label_en": "Platform setup",
     "owner": "this platform",
     "owned_by_platform": True,
     "produces_en": "Place, trade and the stakes the customer wants watched.",
     "requires": ("place",),
     "gates_en": ["routed events", "decision alerts"],
     "note_en": "Guided one question at a time (engine.visitor): the "
                "platform states what it does not know instead of guessing."},
    {"id": "active", "label_en": "Active",
     "owner": "this platform",
     "owned_by_platform": True,
     "produces_en": "Answers on demand plus events routed to what the "
                    "customer has at stake.",
     "requires": (),
     "gates_en": [],
     "note_en": "Steady state. Decisions the customer carries outrank "
                "everything else when routing."},
)
_BY_ID = {s["id"]: s for s in STAGES}

KYC_STATES = ("not_verified", "pending", "verified", "rejected", "expired")


def kyc_status(record: dict) -> dict:
    """KYC-läget för en kund – aldrig härlett, alltid från leverantören.

    Okänt eller okänt värde ⇒ not_verified. Det är den säkra defaulten:
    plattformen ska hellre spärra en verifierad kund av misstag än släppa
    igenom en overifierad.
    """
    raw = str(record.get("kyc_status") or "").strip().lower()
    state = raw if raw in KYC_STATES else "not_verified"
    verified = state == "verified"
    return {"state": state, "verified": verified,
            "provider": record.get("kyc_provider") or None,
            "verified_at": record.get("kyc_verified_at") or None,
            "unlocks_en": list(KYC_GATED) if verified else [],
            "blocked_en": [] if verified else list(KYC_GATED),
            "source_en": ("Supplied by the KYC provider."
                          if raw in KYC_STATES else
                          "No status supplied — treated as not verified. "
                          "The platform never assumes clearance."),
            "note_en": "Landvex does not perform KYC; it only records the "
                       "provider's verdict and enforces what it gates."}


def stage(record: dict) -> dict:
    """Var i kedjan kunden är, vad som saknas och vem som äger nästa steg."""
    prof = _visitor.from_onboarding(record) if record else {"missing": []}
    kyc = kyc_status(record or {})
    # Kunden är I det steg som blockerar. Passerar alla steg är hon "active".
    blocker = None
    for st in STAGES:
        if st["id"] == "kyc":
            if not kyc["verified"]:
                blocker = {"stage": "kyc", "missing": "kyc_status=verified",
                           "owner": st["owner"],
                           "action_en": "Complete verification with the KYC "
                                        "provider; the platform cannot do "
                                        "this step."}
                break
            continue
        missing = [f for f in st["requires"] if not prof.get(f)]
        if missing:
            blocker = {"stage": st["id"], "missing": missing[0],
                       "owner": st["owner"],
                       "action_en": _visitor._ask_for(missing[0], prof)
                       if missing[0] in _visitor.ONBOARDING_CONTRACT
                       else f"Provide {missing[0]}."}
            break
    reached = blocker["stage"] if blocker else "active"
    guide = _visitor.guide(prof) if prof.get("role") else _visitor.guide({})
    return {
        "stage": reached, "stage_label_en": _BY_ID[reached]["label_en"],
        "owner": _BY_ID[reached]["owner"],
        "owned_by_platform": _BY_ID[reached]["owned_by_platform"],
        "kyc": kyc,
        "blocked_by": blocker,
        "complete": blocker is None,
        "profile": prof,
        "guide": guide,
        "next_en": (blocker["action_en"] if blocker
                    else "Nothing outstanding — answers and routing are live."),
        "note_en": "Each step names its owner. Two of the four are not this "
                   "platform's to complete, and it says so rather than "
                   "pretending to progress them.",
    }


def journey() -> dict:
    """Hela kedjan som data – för dokumentation och för klienter."""
    return {"stages": [dict(s) for s in STAGES],
            "kyc_states": list(KYC_STATES),
            "kyc_gated_en": list(KYC_GATED),
            "seam": "GET /v1/visitor/contract",
            "note_en": "KYC and onboarding are owned outside this platform. "
                       "Setup and active operation are owned here."}
