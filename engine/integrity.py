"""Integritetslagret – neutralitet, citat/grounding och självrevision.

Skördat och portat ur `dissg` (Reality Index / NOGF) till Landvex
beroendefria kärna. Det som i Landvex hittills var *principer i prosa*
(ärlig täckning, förklarbarhet före prediktion, mock märks alltid) blir
här *maskin-tvingade* rena funktioner. Fyra delar, alla stdlib:

1. FRÅGEGRIND (`classify_query`) – avvisar normativa/spekulativa/
   prediktiva frågor deterministiskt med typad orsak, aldrig fritext.
2. UTFALLS-SANERING (`neutralize`) – stryker kausala/normativa ord ur
   genererad text och tvingar in en disclaimer. Modellen kan bete sig
   illa; saneraren stryker ändå.
3. CITAT / GROUNDING (`verify_citations`, `validate_provenance`,
   `derive_uncertainty`, `derive_trend`, `evidence_link`) – ett påstående
   som inte backas av ett hämtat värde avvisas INNAN det visas
   (anti-hallucination strukturellt), och varje siffra bär full proveniens.
4. SJÄLVREVISION (`audit`, `integrity_score`) – epistemiska invarianter
   som FAILAR systemet: estimat maskerat som observation, tyst utjämnad
   data, saknad osäkerhet. Blir en lint-svit för hela datalagret.

Källor i dissg (fil:rad): ai-observation 92-140, ai-answer 116-136,
cqais 77-107, masterprompt 80-97, cite 27-53, LLM_INTEGRATION_SPEC
1147-1206, generate-facts 195-200, super-audit (invarianter), API-
EVIDENCE-LINKS. Determinism: samma indata → samma utfall.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# --------------------------------------------------------------------------
# 1. FRÅGEGRIND – blockera icke-neutrala frågor på INGÅNG
# --------------------------------------------------------------------------
# Varje mönster mappar till en typad orsak + ett neutralt omdirigeringssvar.
# reason ∈ {prediction, normative, value_judgment, speculative}
_QUERY_BLOCKS: tuple[tuple[str, str, str], ...] = (
    (r"\b(predict|forecast|projection|will happen|going to (be|become|happen))\b",
     "prediction",
     "The engine describes observed patterns, not future outcomes."),
    (r"\b(should|ought to|must|recommend|advice|advise)\b",
     "normative",
     "The engine reports what is measured, it does not prescribe action."),
    (r"\b(best|worst|optimal|ideal|better than|worse than)\b",
     "value_judgment",
     "The engine reports values and deviations, not rankings of good/bad."),
    (r"\b(guess|probably|might|maybe|likely to)\b",
     "speculative",
     "The engine answers from data on record, not speculation."),
)
_QUERY_RE = tuple((re.compile(p, re.I), reason, msg)
                  for p, reason, msg in _QUERY_BLOCKS)


def classify_query(text: str) -> dict[str, str] | None:
    """Returnera ett typat block-objekt om frågan är icke-neutral, annars None.

    Deterministiskt: aldrig ett fritext-nej, alltid
    {code, reason, suggestion}. None = frågan får passera.
    """
    t = text or ""
    for rx, reason, msg in _QUERY_RE:
        if rx.search(t):
            return {"code": "query_blocked", "reason": reason, "suggestion": msg}
    return None


# --------------------------------------------------------------------------
# 2. UTFALLS-SANERING – stryk kausala/normativa ord ur genererad text
# --------------------------------------------------------------------------
_FORBIDDEN = (
    "caused by", "led to", "leads to", "results in", "resulted in",
    "because", "therefore", "thus", "proves", "obviously", "clearly",
    "should", "must", "better", "worse", "good", "bad", "best", "worst",
)
# Ordgräns-medveten, längsta först (så "leads to" matchas före "to").
_FORBIDDEN_RE = tuple(
    re.compile(r"\b" + re.escape(w) + r"\b", re.I)
    for w in sorted(_FORBIDDEN, key=len, reverse=True)
)
DISCLAIMER = "Observed patterns do not imply causation or intent."
UNABLE = "Unable to generate a neutral observation for this request."


def validate_text(text: str) -> dict[str, Any]:
    """Hitta förbjudna kausala/normativa ord. {valid, violations}."""
    hits: list[str] = []
    for rx in _FORBIDDEN_RE:
        m = rx.search(text or "")
        if m:
            hits.append(m.group(0).lower())
    # Bevara ordning efter position, unika.
    seen: set[str] = set()
    ordered = [h for h in hits if not (h in seen or seen.add(h))]
    return {"valid": not ordered, "violations": ordered}


def neutralize(text: str) -> tuple[str, list[str]]:
    """Ersätt förbjudna ord med [BLOCKED], tvinga in disclaimer.

    Returnerar (ren_text, violations). Om allt blockeras faller den
    tillbaka på UNABLE. Idempotent: en redan neutral text ändras inte
    (utom att disclaimer säkras).
    """
    if not text:
        return UNABLE, []
    report = validate_text(text)
    clean = text
    for rx in _FORBIDDEN_RE:
        clean = rx.sub("[BLOCKED]", clean)
    stripped = clean.replace("[BLOCKED]", "").strip()
    if not stripped:
        return UNABLE, report["violations"]
    if DISCLAIMER not in clean:
        clean = clean.rstrip() + "\n\n" + DISCLAIMER
    return clean, report["violations"]


# --------------------------------------------------------------------------
# 3. CITAT / GROUNDING – proveniens och anti-hallucination
# --------------------------------------------------------------------------
# 9 obligatoriska proveniensfält (masterprompt 80-97). Saknas ett → avvisa.
REQUIRED_PROVENANCE = (
    "source_id", "source_type", "update_frequency", "temporal_coverage",
    "geographic_coverage", "method", "uncertainty", "license", "last_verified",
)


def validate_provenance(record: dict[str, Any]) -> tuple[bool, list[str]]:
    """Ett dataobjekt är giltigt bara om alla 9 proveniensfält finns ifyllda."""
    missing = [f for f in REQUIRED_PROVENANCE
               if not str(record.get(f, "")).strip()]
    return (not missing, missing)


def derive_trend(value: float, previous: float | None,
                 stable_pct: float = 2.0) -> tuple[str, float]:
    """Härled trend ur värde vs föregående. |Δ%| < stable_pct → 'stable'.

    Returnerar (riktning, trend_pct). Aldrig gissad – ren aritmetik.
    """
    if previous in (None, 0):
        return "stable", 0.0
    pct = (float(value) - float(previous)) / abs(float(previous)) * 100.0
    if abs(pct) < stable_pct:
        return "stable", round(pct, 4)
    return ("up" if pct > 0 else "down"), round(pct, 4)


def derive_uncertainty(n_obs: int, confidences: list[float]) -> str:
    """Osäkerhet HÄRLEDS, gissas aldrig (generate-facts 195-200).

    low  om ≥10 observationer OCH alla konfidenser ≥ 80.
    high om  <5 observationer ELLER någon konfidens < 60.
    annars medium.
    """
    conf = [float(c) for c in confidences] if confidences else []
    if n_obs >= 10 and conf and min(conf) >= 80:
        return "low"
    if n_obs < 5 or (conf and min(conf) < 60):
        return "high"
    return "medium"


def verify_citations(claims: list[dict[str, Any]],
                     retrieved: dict[str, Any]) -> dict[str, Any]:
    """Blockera påståenden som inte backas av ett hämtat indexvärde.

    Varje claim: {index_id, value?}. retrieved: {index_id: {value: ...}}.
    Ett claim är giltigt bara om index_id finns i retrieved OCH (om ett
    värde påstås) värdet matchar källan. `all_valid` gäller endast om
    inget ogiltigt finns – det är grinden som stoppar hallucinationer
    INNAN de visas.
    """
    invalid: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    for c in claims:
        iid = c.get("index_id")
        if iid not in retrieved:
            invalid.append({**c, "problem": "index_not_in_context"})
            continue
        if "value" in c and c["value"] is not None:
            src = retrieved[iid].get("value")
            if not _value_matches(c["value"], src):
                invalid.append({**c, "problem": "value_mismatch",
                                "source_value": src})
                continue
        valid.append(c)
    return {"all_valid": not invalid, "valid": valid, "invalid": invalid}


def _value_matches(claimed: Any, source: Any, tol: float = 1e-6) -> bool:
    try:
        return abs(float(claimed) - float(source)) <= max(
            tol, abs(float(source)) * 1e-3)
    except (TypeError, ValueError):
        return str(claimed).strip() == str(source).strip()


def canonical_hash(payload: Any) -> str:
    """SHA-256 över kanonisk JSON (sort_keys) – innehållsadresserat id."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def evidence_link(payload: Any, version: int = 1) -> str:
    """Publikt verifierbart evidens-id: EL-{sha10}-v{version}.

    Samma aggregat (data+fråga+källor) ger samma länk; ändras något ändras
    länken → tamper-evident. Append-only i lagret (här bara id-genereringen).
    """
    return f"EL-{canonical_hash(payload)[:10]}-v{int(version)}"


# --------------------------------------------------------------------------
# 4. SJÄLVREVISION – epistemiska invarianter som failar systemet
# --------------------------------------------------------------------------
def audit(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Granska en post-mängd mot ärlighetsinvarianterna.

    Varje post kan bära: value, uncertainty, method ('observed'|'estimated'|
    'calculated'), estimation_method, source, series (lista värden).
    Returnerar typade fynd {severity, category, description, index}.
    severity ∈ {critical, high, medium}.
    """
    findings: list[dict[str, Any]] = []

    def add(sev: str, cat: str, desc: str, i: int) -> None:
        findings.append({"severity": sev, "category": cat,
                         "description": desc, "index": i})

    for i, r in enumerate(records):
        # Invariant 1: varje observation MÅSTE deklarera osäkerhet.
        if not str(r.get("uncertainty", "")).strip():
            add("critical", "missing_uncertainty",
                "Observation without declared uncertainty (truth-engine "
                "violation).", i)
        # Invariant 2: estimat MÅSTE bära estimation_method, annars är det
        # ett estimat maskerat som observation.
        if r.get("method") == "estimated" and not str(
                r.get("estimation_method", "")).strip():
            add("critical", "estimate_as_observation",
                "Estimated value without estimation_method (inferred value "
                "presented as observed).", i)
        # Invariant 3: misstänkt stabilitet – ≥5 identiska värden i rad kan
        # vara tyst utjämnad/inaktuell data.
        series = r.get("series") or []
        if _has_flat_run(series, 5):
            add("high", "suspicious_stability",
                "5+ identical consecutive values – possibly silently smoothed "
                "or stale; show gaps explicitly.", i)
        # Invariant 4: kalkylerat värde utan källa.
        if r.get("method") in ("observed", "calculated") and not str(
                r.get("source", "")).strip():
            add("medium", "missing_source",
                "Observed/calculated value without a source reference.", i)
    return findings


def _has_flat_run(series: list[Any], n: int) -> bool:
    run = 1
    for a, b in zip(series, series[1:], strict=False):
        if a == b:
            run += 1
            if run >= n:
                return True
        else:
            run = 1
    return False


def integrity_score(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregat: score = max(0, 100 − antal_fynd·20); pass = noll criticals."""
    criticals = sum(1 for f in findings if f["severity"] == "critical")
    score = max(0, 100 - len(findings) * 20)
    return {"integrity_score": score, "passed": criticals == 0,
            "critical_count": criticals, "finding_count": len(findings)}


# --------------------------------------------------------------------------
# 5. INRAMNING – "statistik ljuger alltid": ett resultat är alltid ett svar
# --------------------------------------------------------------------------
FRAMING_NOTE = ("A statistical result is always presented as an answer, "
                "whatever the outcome — this figure is one framing, "
                "contingent on the choices below, not a truth.")


def framing_disclosure(choices: dict[str, Any] | None = None) -> dict[str, Any]:
    """Binder en inramnings-not till ett resultat: aldrig en siffra utan de
    val (mål, riktning, täckning, urval) som gjorde den till "ett svar".
    Motmedlet mot siffrans falska auktoritet – redovisa ramen, inte bara talet.
    """
    return {"note": FRAMING_NOTE, "choices": choices or {}}
