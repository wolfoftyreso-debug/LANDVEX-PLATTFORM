"""Besökaren – vem systemet talar med, och hur mycket det redan vet.

Det här lagret är SÖMMEN mot Landvex befintliga kundonboarding. Den djupa
onboardingen ägs på annat håll; här definieras bara vad motorn behöver veta
för att kunna svara, och vad som händer när den bara vet en del.

Bärande princip (kundens egen formulering): känner systemet inte besökaren
alls blir det en röra – känner det honom *lite grann* kan det börja guida.
Därför är kännedom en SKALA, inte ett ja/nej:

    unknown   → vet ingenting; kan bara fråga vem du är
    partial   → vet rollen; kan visa vad rollen brukar vilja veta
    known     → vet roll + geografi + vad du har i potten; kan svara
    routed    → vet dessutom vilka beslut du bär; kan larma när de rör sig

`completeness()` säger alltid RAKT UT vilken nivå vi är på, vad som redan
går att svara på, och exakt vilket fält som lyfter till nästa nivå. Ett
system som inte vet ska säga att det inte vet – och be om en sak i taget.

`from_onboarding()` är adaptern: den tar en kundpost i onboardingens format
och mappar den hit, tolerant mot okända fält och ärlig om vad som saknas.
ONBOARDING_CONTRACT är det dokumenterade schemat att mappa MOT, så den
externa onboardingen kan leverera utan att gissa. Ingen kunddata hittas på:
saknas ett fält rapporteras det som saknat.

Rent stdlib, ingen persistens här (prenumerationer lever i engine.inbox).
"""
from __future__ import annotations

from .entrypoints import ENTRYPOINTS
from .inbox import REANSWER, STAKE_WEIGHT

_ROLES = {e["id"]: e for e in ENTRYPOINTS}

LEVELS = ("unknown", "partial", "known", "routed")

# Det dokumenterade schemat som en extern onboarding levererar mot.
# Alias-listorna gör adaptern tolerant: onboardingen får kalla fältet vad
# den vill, så länge det finns med här.
ONBOARDING_CONTRACT: dict[str, dict] = {
    "visitor_id": {
        "required": True, "type": "string",
        "aliases": ("id", "customer_id", "user_id", "email", "subscriber"),
        "why_en": "Stable key for routing events back to this visitor."},
    "role": {
        "required": True, "type": "enum",
        "options": tuple(_ROLES),
        "aliases": ("persona", "segment", "customer_type", "entrypoint"),
        "why_en": "Decides which question the platform is answering."},
    "market": {
        "required": False, "type": "string (ISO-ish market id)",
        "aliases": ("country", "market_id", "region_country"),
        "why_en": "Which market's data and calibration applies."},
    "place": {
        "required": False, "type": "string (region/municipality code)",
        "aliases": ("region", "kommun", "municipality", "location", "city"),
        "why_en": "The place the visitor has a stake in."},
    "trade": {
        "required": False, "type": "string (vertical id)",
        "aliases": ("vertical", "vertical_id", "industry", "bransch"),
        "why_en": "The trade being decided about."},
    "occupation": {
        "required": False, "type": "string (occupation id)",
        "aliases": ("yrke", "occupation_id", "skill"),
        "why_en": "Workforce questions are asked per occupation."},
    "decisions": {
        "required": False, "type": "list of decision ids",
        "aliases": ("commitments", "decision_ids", "owned_decisions"),
        "why_en": "Decisions the visitor carries — these outrank everything "
                  "else when routing events."},
    "name": {
        "required": False, "type": "string",
        "aliases": ("full_name", "display_name", "contact"),
        "why_en": "Display only; never used in analysis."},
}

# Vad som krävs för varje nivå, och vad nivån låser upp.
_LADDER: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("partial", ("role",),
     "Show what this role usually needs to decide, with examples."),
    ("known", ("place",),
     "Answer the role's question for a real place."),
    ("routed", ("decisions",),
     "Alert the visitor when the basis of a decision they carry moves."),
)


def _pick(payload: dict, field: str):
    """Hämta ett fält ur en onboardingpost via namn eller alias."""
    spec = ONBOARDING_CONTRACT[field]
    for key in (field,) + spec["aliases"]:
        if key in payload and payload[key] not in (None, "", [], {}):
            return payload[key]
    return None


def from_onboarding(payload: dict) -> dict:
    """Mappa en kundpost från onboardingen till en besökarprofil.

    Tolerant: okända fält ignoreras, kända alias accepteras. Ärlig: allt
    som saknas listas i `missing` – ingenting antas och ingenting hittas på.
    Höjer bara om rollen finns men är okänd (ett stavfel ska inte tyst bli
    en annan roll).
    """
    if not isinstance(payload, dict):
        raise ValueError("onboarding payload must be an object")
    prof: dict = {}
    for field in ONBOARDING_CONTRACT:
        val = _pick(payload, field)
        if val is not None:
            prof[field] = val
    role = prof.get("role")
    if role is not None and role not in _ROLES:
        raise ValueError(f"unknown role: {role}. "
                         f"Known roles: {', '.join(_ROLES)}")
    if "decisions" in prof and not isinstance(prof["decisions"], list):
        prof["decisions"] = [prof["decisions"]]
    missing = [f for f, spec in ONBOARDING_CONTRACT.items()
               if f not in prof]
    prof["missing"] = missing
    prof["source"] = "onboarding"
    return prof


def completeness(profile: dict) -> dict:
    """Hur väl systemet känner besökaren – och vad som lyfter det ett steg.

    Säger alltid rakt ut vad som redan går att svara på och vilket ENDA
    fält som behövs härnäst. Att veta lite är inte ett fel; att låtsas veta
    mer än man gör är det.
    """
    level = "unknown"
    unlocked: list[str] = []
    for name, needed, gives in _LADDER:
        if all(profile.get(f) for f in needed):
            level = name
            unlocked.append(gives)
        else:
            nxt = [f for f in needed if not profile.get(f)][0]
            return {"level": level, "unlocked_en": unlocked,
                    "next_field": nxt,
                    "next_unlocks_en": gives,
                    "ask_en": _ask_for(nxt, profile),
                    "known_fields": [f for f in ONBOARDING_CONTRACT
                                     if profile.get(f)],
                    "note_en": "The platform states what it does not know "
                               "instead of guessing — one question at a time."}
    return {"level": "routed", "unlocked_en": unlocked, "next_field": None,
            "next_unlocks_en": None, "ask_en": None,
            "known_fields": [f for f in ONBOARDING_CONTRACT
                             if profile.get(f)],
            "note_en": "Everything needed to answer and to route events is "
                       "known."}


def _ask_for(field: str, profile: dict) -> str:
    """Frågan att ställa för att fylla nästa lucka – på besökarens språk."""
    if field == "role":
        return "Which of these are you? It decides which question we answer."
    if field == "place":
        role = profile.get("role", "")
        if role == "business":
            return "Where are you considering establishing?"
        if role == "municipality":
            return "Which municipality or region do you answer for?"
        return "Which place are you asking about?"
    if field == "decisions":
        return ("Is there a decision you are carrying? Register it and we "
                "will tell you when its basis moves.")
    return f"We still need: {field}."


def guide(profile: dict) -> dict:
    """Vad besökaren ska se just nu, givet hur mycket vi vet om honom.

    Returnerar rollens beslutsfråga och den endpoint som SVARAR på den så
    fort vi vet nog – annars nästa fråga att ställa. Aldrig en verktygslåda
    att leta i.
    """
    c = completeness(profile)
    role_id = profile.get("role")
    role = _ROLES.get(role_id) if role_id else None
    out = {"visitor_id": profile.get("visitor_id", ""),
           "completeness": c, "role": role_id,
           "stakes_suggested": suggested_stakes(profile)}
    if role is None:
        out.update({"status": "identify",
                    "question_en": "Who are you?",
                    "options": [{"id": e["id"], "label_en": e["label_en"],
                                 "visitor_en": e.get("visitor_en", ""),
                                 "question_en": e["question_en"]}
                                for e in ENTRYPOINTS]})
        return out
    out.update({
        "status": "answer" if c["level"] in ("known", "routed") else "ask",
        "your_question_en": role["question_en"],
        "your_decision_en": role["decision_en"],
        "deliverable_en": role["deliverable_en"],
        "answered_by": role["answered_by"],
        "reanswer_with": REANSWER.get(role_id, role["answered_by"]),
        "evidence": list(role["tools"]),
        "event_feeds": list(role["event_feeds"]),
    })
    if c["level"] not in ("known", "routed"):
        out["ask_en"] = c["ask_en"]
    return out


def suggested_stakes(profile: dict) -> list[dict]:
    """Vad besökaren rimligen bör bevaka, härlett ur det vi redan vet.

    Föreslår bara sådant profilen faktiskt innehåller – aldrig påhittade
    platser eller branscher. Matar rakt in i engine.inbox.subscribe.
    """
    out = []
    if profile.get("place"):
        out.append({"kind": "place", "value": str(profile["place"]),
                    "label": str(profile["place"])})
    if profile.get("trade"):
        out.append({"kind": "sector", "value": str(profile["trade"]),
                    "label": str(profile["trade"])})
    if profile.get("occupation"):
        out.append({"kind": "occupation", "value": str(profile["occupation"]),
                    "label": str(profile["occupation"])})
    for d in profile.get("decisions") or []:
        out.append({"kind": "decision", "value": str(d), "label": "decision"})
    return [s for s in out if s["kind"] in STAKE_WEIGHT]


def contract() -> dict:
    """Det dokumenterade schemat en extern onboarding levererar mot."""
    return {
        "fields": [{"field": f, **{k: (list(v) if isinstance(v, tuple) else v)
                                   for k, v in spec.items()}}
                   for f, spec in ONBOARDING_CONTRACT.items()],
        "levels": list(LEVELS),
        "ladder": [{"level": lvl, "requires": list(req), "unlocks_en": gives}
                   for lvl, req, gives in _LADDER],
        "roles": [{"id": e["id"], "label_en": e["label_en"]}
                  for e in ENTRYPOINTS],
        "note_en": "Landvex already owns a full customer onboarding; this is "
                   "only the seam it delivers into. Post a customer record to "
                   "/v1/visitor in any shape that uses these field names or "
                   "aliases — unknown fields are ignored, missing ones are "
                   "reported, nothing is inferred.",
    }
