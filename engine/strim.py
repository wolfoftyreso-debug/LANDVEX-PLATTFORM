"""STRIM – citerbar, versionerad, neutral entitetsgraf (dissg russin M).

I dissg är domänen missbruk; för Landvex är MÖNSTRET russinet: en
kunskapsgraf av entiteter (substanser, diagnoser, behandlingar, lag,
statistik, begrepp) exponerad som schema.org/JSON-LD för AI-grounding och
citat, med odödliga slugs, innehålls-checksumma per version och en
neutralitets-validator som blockerar imperativ/värdeord.

Rent stdlib. Återanvänder `claims.canonical_hash` för versionering.
Källa i dissg: strim-api/index.ts, STRIM-EDITORIAL-PROCESS.md:71-90.
"""
from __future__ import annotations

import re

from .claims import cite as _claim_cite
from .integrity import canonical_hash

# Entitetstyp → schema.org-typ.
SCHEMA_ORG = {
    "substance": "Drug", "diagnosis": "MedicalCondition",
    "treatment": "MedicalTherapy", "legal": "Legislation",
    "statistic": "Dataset", "term": "DefinedTerm",
}
RELATION_TYPES = (
    "causes", "treated_by", "regulated_by", "affects", "measures",
    "defines", "related_to", "replaced_by", "part_of", "contraindicates",
)
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")
# Redaktionell neutralitet: imperativ + värdeord + spekulativa mönster.
_FORBIDDEN = (
    r"\bbör\b", r"\bska\b", r"\bmåste\b", r"\bbra\b", r"\bdålig\w*\b",
    r"\bbäst\w*\b", r"\bsämst\w*\b", r"\bom du\b", r"\bstudier visar\b",
    r"\bshould\b", r"\bmust\b", r"\bbest\b", r"\bworst\b", r"!",
)
_FORBIDDEN_RE = tuple(re.compile(p, re.I) for p in _FORBIDDEN)


def validate_neutral(text: str) -> dict:
    """Redaktionell grind: hitta imperativ/värdeord. {valid, violations}."""
    hits = []
    for rx in _FORBIDDEN_RE:
        m = rx.search(text or "")
        if m:
            hits.append(m.group(0).lower())
    seen: set = set()
    ordered = [h for h in hits if not (h in seen or seen.add(h))]
    return {"valid": not ordered, "violations": ordered}


def build_entity(entity_type: str, slug: str, name_en: str, *,
                 name_sv: str = "", definition: str = "",
                 sources: list | None = None, status: str = "active",
                 fields: dict | None = None) -> dict:
    """Skapa v1 av en STRIM-entitet. Kräver giltig slug, ≥1 källa och
    neutral definition. Höjer ValueError vid brott (redaktionellt kontrakt)."""
    if entity_type not in SCHEMA_ORG:
        raise ValueError(f"okänd entitetstyp: {entity_type}")
    if not _SLUG_RE.match(slug or ""):
        raise ValueError("slug måste matcha ^[a-z0-9-]+$")
    srcs = list(sources or [])
    if not srcs:
        raise ValueError("minst en källa krävs")
    neu = validate_neutral(definition)
    if not neu["valid"]:
        raise ValueError(f"icke-neutral definition: {neu['violations']}")
    ent = {"type": entity_type, "schema_org": SCHEMA_ORG[entity_type],
           "canonical_slug": slug, "name_en": name_en, "name_sv": name_sv,
           "definition": definition, "status": status,
           "sources": srcs, "relations": [], "fields": dict(fields or {}),
           "version": 1, "previous_version": None}
    ent["checksum"] = canonical_hash(_content(ent))
    return ent


def _content(ent: dict) -> dict:
    return {k: ent[k] for k in
            ("type", "canonical_slug", "name_en", "name_sv", "definition",
             "status", "sources", "fields") if k in ent}


def revise(prev: dict, **changes) -> dict:
    """Ny version; odödlig slug (får inte ändras), version++, länkar bakåt."""
    import copy
    if "canonical_slug" in changes and changes["canonical_slug"] != prev["canonical_slug"]:
        raise ValueError("canonical_slug är odödlig och får inte ändras")
    nxt = copy.deepcopy(prev)
    if "definition" in changes:
        neu = validate_neutral(changes["definition"])
        if not neu["valid"]:
            raise ValueError(f"icke-neutral definition: {neu['violations']}")
    nxt.update(changes)
    nxt["version"] = prev.get("version", 1) + 1
    nxt["previous_version"] = prev["checksum"]
    nxt["checksum"] = canonical_hash(_content(nxt))
    return nxt


def add_relation(ent: dict, rel_type: str, target_slug: str) -> dict:
    if rel_type not in RELATION_TYPES:
        raise ValueError(f"okänd relationstyp: {rel_type}")
    ent.setdefault("relations", []).append(
        {"type": rel_type, "target": target_slug})
    return ent


def to_jsonld(ent: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": ent["schema_org"],
        "@id": f"/strim/{ent['type']}/{ent['canonical_slug']}",
        "name": ent["name_en"],
        "alternateName": ent.get("name_sv") or None,
        "description": ent.get("definition", ""),
        "identifier": ent["canonical_slug"],
        "version": ent.get("version", 1),
        "citation": [s if isinstance(s, str) else s.get("title", "")
                     for s in ent.get("sources", [])],
    }


def cite(ent: dict, style: str = "text") -> str:
    """Citat i STRIM-form (strim:{type}:{slug}) via påstående-citatlagret."""
    claim_like = {
        "statement": ent.get("definition") or ent["name_en"],
        "id": f"strim:{ent['type']}:{ent['canonical_slug']}",
        "version": ent.get("version", 1),
        "source": {"authority": (ent.get("sources") or ["STRIM"])[0]
                   if isinstance((ent.get("sources") or [""])[0], str)
                   else "STRIM"},
        "time": {"observed_at": ""},
    }
    return _claim_cite(claim_like, style)


def entity_types() -> list[dict]:
    return [{"type": t, "schema_org": s} for t, s in SCHEMA_ORG.items()]
