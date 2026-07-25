"""Påståendelager – verifierbara indexerade påståenden (dissg russin J + K).

Landvex lagrar inte "data" utan VERIFIERBARA PÅSTÅENDEN om verkligheten:
varje påstående bär källa, tid, jurisdiktion, konfidens, en typad
relationsgraf och innehållsadresserad SHA-256-versionering. Ovanpå det
NOGF-governance: varje indikator måste bära tre ansvarsroller (formellt/
operativt/uppföljning) – "om ingen ansvarar får indikatorn inte finnas".

Rent stdlib. `id` och `checksum` är hash av det kanoniska innehållet
(sort_keys) → samma innehåll ger samma id (tamper-evident), och en
revision länkar bakåt via `previous_version`. Append-only i praktiken:
revidera skapar en NY version, muterar aldrig den gamla.

Källor i dissg: UNIVERSAL_INDEX_OBJECT_SPEC.md, SYSTEM-CONTRACT.md,
NOGF-FRAMEWORK.md, LEGAL_POLITICAL_SHIELD_SPEC.md, cite/index.ts.
"""
from __future__ import annotations

import copy
from typing import Any

from .integrity import canonical_hash

# Governance: obligatoriska ansvarsroller per indikator (NOGF).
OWNER_ROLES = ("formellt", "operativt", "uppfoljning")

# Tillåtna relationstyper (delmängd av UIO:s ~25).
RELATION_TYPES = (
    "supersedes", "derived_from", "depends_on", "conflicts_with",
    "correlates_with", "regulated_by", "part_of", "same_as",
)


def _content(claim: dict[str, Any]) -> dict[str, Any]:
    """Den identitetsbärande delen (allt utom härledda meta-fält)."""
    return {k: claim[k] for k in
            ("statement", "value", "unit", "source", "jurisdiction", "time")
            if k in claim}


def build_claim(statement: str, value: Any, source: dict, jurisdiction: dict,
                time: dict, *, unit: str = "", confidence: float | None = None,
                method: str = "observed", uncertainty: str = "",
                owners: dict | None = None,
                relations: list | None = None) -> dict:
    """Skapa version 1 av ett påstående. `id`=`checksum`=hash(innehåll).

    owners: {formellt, operativt, uppfoljning}. method ∈ observed|estimated|
    calculated. Ingen validering av governance här – använd
    `validate_governance` (fail-fast där systemet kräver det).
    """
    claim: dict[str, Any] = {
        "statement": statement, "value": value, "unit": unit,
        "source": source, "jurisdiction": jurisdiction, "time": time,
        "confidence": {"score": confidence, "method": method,
                       "uncertainty": uncertainty},
        "relations": list(relations or []),
        "owners": dict(owners or {}),
        "version": 1, "previous_version": None,
    }
    h = canonical_hash(_content(claim))
    claim["id"] = h
    claim["checksum"] = h
    return claim


def revise(prev: dict, **changes: Any) -> dict:
    """Skapa nästa version. Muterar ALDRIG `prev` – append-only lineage.

    `changes` kan sätta statement/value/unit/source/jurisdiction/time/
    owners/relations. version++, previous_version = prev['id'], nya id/checksum.
    """
    nxt = copy.deepcopy(prev)
    for k, v in changes.items():
        if k in ("confidence_score", "method", "uncertainty"):
            key = {"confidence_score": "score"}.get(k, k)
            nxt.setdefault("confidence", {})[key] = v
        else:
            nxt[k] = v
    nxt["version"] = prev.get("version", 1) + 1
    nxt["previous_version"] = prev["id"]
    h = canonical_hash(_content(nxt))
    nxt["id"] = h
    nxt["checksum"] = h
    return nxt


def verify(claim: dict) -> bool:
    """Innehållsintegritet: checksum måste matcha hashen av innehållet."""
    return claim.get("checksum") == canonical_hash(_content(claim))


def add_relation(claim: dict, rel_type: str, target_id: str, *,
                 strength: float = 0.0, confidence: float | None = None,
                 origin: str = "declared") -> dict:
    """Lägg en typad relation (skapar ny version – grafen är del av innehållet
    endast om du vill; här hålls relationer utanför identiteten så att en
    korrelation inte ändrar påståendets id). Returnerar samma claim, muterat
    relations-listan (icke-identitetsbärande)."""
    if rel_type not in RELATION_TYPES:
        raise ValueError(f"okänd relationstyp: {rel_type}")
    claim.setdefault("relations", []).append({
        "type": rel_type, "target_id": target_id,
        "strength": max(-1.0, min(1.0, float(strength))),
        "confidence": confidence, "origin": origin})
    return claim


def validate_governance(claim: dict) -> tuple[bool, list[str]]:
    """NOGF: alla tre ansvarsroller måste finnas ifyllda, annars får
    indikatorn inte finnas i systemet. Returnerar (ok, saknade_roller)."""
    owners = claim.get("owners") or {}
    missing = [r for r in OWNER_ROLES if not str(owners.get(r, "")).strip()]
    return (not missing, missing)


def k_anonymity_ok(n_observations: int, min_n: int = 5) -> bool:
    """Integritetsgrind: en datapunkt får inte bygga på färre än min_n obs."""
    return n_observations >= min_n


_STYLES = ("text", "apa", "bibtex")


def cite(claim: dict, style: str = "text") -> str:
    """Formatera ett påstående som citat. Språkskölden i praktiken: neutralt,
    tidsbundet, hänvisar till källan – gör aldrig anspråk å systemets vägnar.
    """
    src = claim.get("source") or {}
    authority = src.get("authority") or src.get("origin") or "Unknown source"
    when = (claim.get("time") or {}).get("observed_at", "")
    year = str(when)[:4] if when else "n.d."
    ident = claim.get("id", "")[:12]
    ver = claim.get("version", 1)
    url = f"/v1/claims/{claim.get('id','')}"
    stmt = claim.get("statement", "")
    if style == "bibtex":
        return ("@misc{landvex_%s,\n  title={%s},\n  author={%s},\n"
                "  year={%s},\n  note={LANDVEX indexed claim %s v%s},\n"
                "  url={%s}\n}" % (ident, stmt, authority, year, ident, ver, url))
    if style == "apa":
        return f"{authority} ({year}). {stmt}. LANDVEX [{ident}, v{ver}]. {url}"
    return (f"{stmt}. Source: {authority} ({year}). "
            f"Indexed claim {ident} v{ver} — {url}. This is an indexed "
            f"reference to published data; LANDVEX does not originate or "
            f"endorse this claim.")


class ClaimLog:
    """Append-only lager: versioner läggs till, muteras aldrig; lineage per id."""

    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}
        self._latest: dict[str, str] = {}   # lineage-rot → senaste id

    def append(self, claim: dict) -> str:
        cid = claim["id"]
        if cid in self._by_id:
            return cid   # idempotent: samma innehåll, samma id
        self._by_id[cid] = copy.deepcopy(claim)
        root = self._root(claim)
        self._latest[root] = cid
        return cid

    def _root(self, claim: dict) -> str:
        prev = claim.get("previous_version")
        while prev and prev in self._by_id:
            claim = self._by_id[prev]
            prev = claim.get("previous_version")
        return claim["id"]

    def get(self, cid: str) -> dict | None:
        return self._by_id.get(cid)

    def latest(self, cid: str) -> dict | None:
        root = self._root(self._by_id[cid]) if cid in self._by_id else cid
        return self._by_id.get(self._latest.get(root, ""))

    def __len__(self) -> int:
        return len(self._by_id)
