"""Beslutsstöd – Decision Graph + krisgrind (dissg russin J).

Två delar:
1. KRISGRIND (`crisis_scan`) – en HÅRD säkerhetsgrind: frågor som rör
   suicid/självskada besvaras ALDRIG med motordata utan möts med
   lokaliserade nödresurser. Detta går före allt annat.
2. DECISION GRAPH (`evaluate`) – en strukturerad frågegraf (investering/
   sjukvård/policy) där varje nod har en svarstyp och konfidenströskel;
   motorn RÅDER ALDRIG ("gör X"), den redovisar täckning, luckor och
   antaganden. Beslut fattas utanför systemet men struktureras i det.

Källa i dissg: decision/index.ts (NEVER_PROVIDED, node-typer),
answer/index.ts (krisdetektering → nödresurser). Rent stdlib.
"""
from __future__ import annotations

import re

# --- 1. Krisgrind --------------------------------------------------------
_CRISIS_RE = re.compile(
    r"\b(suicid\w*|kill myself|end my life|self[-\s]?harm|"
    r"take my (own )?life|självmord|ta mitt liv|ta livet av mig|"
    r"skada mig själv)\b", re.I)
# Svenska formuleringar → svenska resurser (annars fick en svensk användare
# det amerikanska 988-numret; en lokaliseringsbugg med säkerhetspåverkan).
_SWEDISH_RE = re.compile(
    r"självmord|ta mitt liv|ta livet av mig|skada mig själv", re.I)

# Lokaliserade nödresurser (schablon; utökas per marknad).
_RESOURCES = {
    "us": [{"name": "988 Suicide & Crisis Lifeline", "contact": "988",
            "hours": "24/7"}],
    "se": [{"name": "Mind Självmordslinjen", "contact": "90101",
            "hours": "24/7"},
           {"name": "112 (emergency)", "contact": "112", "hours": "24/7"}],
    "_default": [{"name": "Local emergency services", "contact": "112 / 911",
                  "hours": "24/7"}],
}


def crisis_scan(text: str, country: str | None = None) -> dict | None:
    """Returnerar en nödresurs-respons om texten rör suicid/självskada,
    annars None. Ingen motordata – bara hjälp och resurser.

    `country=None` → autodetektera: svensk formulering ger svenska resurser,
    annars den amerikanska linjen. Anropare som vet marknaden kan sätta den.
    """
    if not text or not _CRISIS_RE.search(text):
        return None
    if not country:
        country = "se" if _SWEDISH_RE.search(text) else "us"
    res = _RESOURCES.get(country.lower(), _RESOURCES["_default"])
    return {
        "crisis": True,
        "message": ("It sounds like you may be going through something very "
                    "hard. You are not alone and help is available right now."),
        "resources": res,
        "note": "This request is met with support resources, not data.",
    }


# --- 2. Decision Graph ---------------------------------------------------
# Systemet TILLHANDAHÅLLER ALDRIG: rekommendationer, optimala val,
# prioritetsrangordningar, prediktioner (dissg NEVER_PROVIDED).
NEVER_PROVIDED = ("recommendation", "optimal_choice", "priority_ranking",
                  "prediction")

# Mallar: en lista noder per beslutstyp.
TEMPLATES: dict[str, tuple[dict, ...]] = {
    "investment_decision": (
        {"node_id": "demand", "question": "How has demand developed?",
         "answer_type": "TREND_CHANGE", "confidence_threshold": 0.6,
         "required": True},
        {"node_id": "competition", "question": "What is the competitive gap?",
         "answer_type": "DISTRIBUTION_STRUCTURE", "confidence_threshold": 0.5,
         "required": True},
        {"node_id": "risk", "question": "What risk factors are observed?",
         "answer_type": "CORRELATION_OVERVIEW", "confidence_threshold": 0.5,
         "required": False},
    ),
    "policy_decision": (
        {"node_id": "baseline", "question": "What is the current baseline?",
         "answer_type": "TREND_CHANGE", "confidence_threshold": 0.6,
         "required": True},
        {"node_id": "distribution", "question": "How is it distributed?",
         "answer_type": "DISTRIBUTION_STRUCTURE", "confidence_threshold": 0.5,
         "required": True},
    ),
}


def templates() -> list[dict]:
    return [{"template": k, "nodes": [n["node_id"] for n in v]}
            for k, v in TEMPLATES.items()]


def evaluate(template: str, answers: dict[str, dict]) -> dict:
    """Utvärdera en beslutsgraf mot inlämnade nod-svar.

    answers: {node_id: {confidence: 0–1, data_coverage: 0–1, summary?}}.
    Varje nod → status resolved|insufficient_data|unresolved. Aggregat:
    completeness, overall_confidence, data_gaps, assumptions_needed. Ger
    ALDRIG en rekommendation – bara beslutsunderlag.
    """
    nodes = TEMPLATES.get(template)
    if nodes is None:
        raise ValueError(f"okänd mall: {template}")
    resolved = 0
    node_out = []
    gaps = []
    confs = []
    for n in nodes:
        a = answers.get(n["node_id"])
        if a is None:
            status = "unresolved"
        elif a.get("confidence", 0) < n["confidence_threshold"]:
            status = "insufficient_data"
        else:
            status = "resolved"
            resolved += 1
            confs.append(float(a.get("confidence", 0)))
        if status != "resolved" and n["required"]:
            gaps.append(n["node_id"])
        node_out.append({"node_id": n["node_id"], "question": n["question"],
                         "answer_type": n["answer_type"], "status": status,
                         "confidence": (a or {}).get("confidence"),
                         "summary": (a or {}).get("summary", "")})
    completeness = round(resolved / len(nodes), 4) if nodes else 0.0
    overall = round(sum(confs) / len(confs), 4) if confs else 0.0
    return {
        "template": template, "nodes": node_out,
        "completeness": completeness, "overall_confidence": overall,
        "data_gaps": gaps,
        "assumptions_needed": [g + ": requires more data before conclusions"
                               for g in gaps],
        "never_provided": list(NEVER_PROVIDED),
        "disclaimer": ("Decision basis only — the system reports observed "
                       "structure and gaps, it does not recommend an action."),
    }
