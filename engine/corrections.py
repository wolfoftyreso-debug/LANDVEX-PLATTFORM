"""Wiki-rättelser + consensus-adaptation – lokalkännedom som data.

Landvex-användare från en region kan lämna RÄTTELSER (som i Wikipedia): ett
källbelagt förslag på ett bättre värde. Får ett område tillräckligt många
OBEROENDE och SAMSTÄMMIGA rättelser adapterar systemet värdet automatiskt –
med full proveniens, reversibelt, och alltid märkt `source="community"`
(aldrig "officiellt"). Lokalkännedomen slår systemets schablon, men bara med
skydd mot manipulation:

  1. KÄLLKRAV – ingen rättelse utan källa ("citation needed").
  2. OBEROENDE – minst `MIN_SUBMITTERS` DISTINKTA inlämnare (inte 5 från en).
  3. KONVERGENS – förslagen måste vara samstämmiga (variationskoefficient
     ≤ `MAX_CV`); spridda gissningar adapterar aldrig.
  4. REVERSIBELT & SPÅRBART – adaptationen är ett versionerat claim med
     antal, inlämnare och källor; kan rullas tillbaka.

Rent stdlib. Append-only, persisteras via Store (delas över workers,
överlever omstart), annars process-minne. Återanvänder integrity-hash.
"""
from __future__ import annotations

import threading

from .integrity import canonical_hash
from .stats import mean, pstdev

MIN_SUBMITTERS = 5      # distinkta inlämnare för consensus
MAX_CV = 0.15          # max variationskoefficient (samstämmighet)

_CORRECTIONS: list[dict] = []
_LOCK = threading.Lock()
_STORE = None


def set_store(store) -> None:
    global _STORE
    _STORE = store if (store is not None
                       and getattr(store, "all_corrections", lambda: None)()
                       is not None) else None


def submit(region: str, target_key: str, proposed_value: float, source: str,
           submitter_id: str, *, current_value: float | None = None,
           note: str = "") -> dict:
    """Lämna en rättelse. KRÄVER en källa (annars ValueError – citation needed)."""
    if not str(source).strip():
        raise ValueError("a correction requires a source (citation needed)")
    if not str(submitter_id).strip():
        raise ValueError("a correction requires a submitter id")
    rec = {"region": region, "target_key": target_key,
           "proposed_value": float(proposed_value), "source": source,
           "submitter_id": submitter_id, "current_value": current_value,
           "note": note, "status": "pending"}
    rec["id"] = canonical_hash({k: rec[k] for k in
                                ("region", "target_key", "submitter_id",
                                 "proposed_value")})
    _save(rec)
    return rec


def _for(target_key: str, region: str) -> list[dict]:
    return [c for c in _all()
            if c["target_key"] == target_key and c["region"] == region]


def consensus(target_key: str, region: str) -> dict:
    """Sammanväg rättelser för ett mål i ett område mot alla skydd."""
    rows = _for(target_key, region)
    submitters = {c["submitter_id"] for c in rows}
    vals = [c["proposed_value"] for c in rows]
    all_sourced = all(str(c.get("source", "")).strip() for c in rows)
    m = mean(vals) if vals else 0.0
    cv = (pstdev(vals) / abs(m)) if (vals and m) else (0.0 if len(vals) <= 1 else 1.0)
    converged = cv <= MAX_CV
    med = sorted(vals)[len(vals) // 2] if vals else None
    met = (len(submitters) >= MIN_SUBMITTERS and converged and all_sourced
           and len(vals) >= MIN_SUBMITTERS)
    needed = []
    if len(submitters) < MIN_SUBMITTERS:
        needed.append(f"{MIN_SUBMITTERS - len(submitters)} more distinct submitters")
    if not converged:
        needed.append(f"convergence (CV {cv:.2f} > {MAX_CV})")
    if not all_sourced:
        needed.append("all corrections sourced")
    return {"target_key": target_key, "region": region,
            "n_corrections": len(rows), "distinct_submitters": len(submitters),
            "all_sourced": all_sourced, "cv": round(cv, 4),
            "converged": converged, "consensus_value": med,
            "threshold_met": met, "needed": needed}


def adapt(target_key: str, region: str) -> dict:
    """Adaptera om consensus-tröskeln är nådd. Annars 'not_yet' med vad som
    saknas. Adaptationen är ett versionerat, källbelagt community-claim."""
    c = consensus(target_key, region)
    if not c["threshold_met"]:
        return {"status": "not_yet", **c,
                "note": "System adapts only on enough independent, converging, "
                        "sourced corrections — this is how it resists brigading."}
    rows = _for(target_key, region)
    sources = sorted({r["source"] for r in rows})
    adaptation = {
        "status": "adapted", "target_key": target_key, "region": region,
        "value": c["consensus_value"], "source": "community",
        "provenance": {"n_corrections": c["n_corrections"],
                       "distinct_submitters": c["distinct_submitters"],
                       "cv": c["cv"], "sources": sources},
        "reversible": True,
        "note": "Community-adapted from converging local corrections — labelled "
                "community, never official; reversible and fully traceable.",
    }
    adaptation["id"] = canonical_hash({"target_key": target_key, "region": region,
                                       "value": c["consensus_value"],
                                       "n": c["n_corrections"]})
    return adaptation


# --- lager -----------------------------------------------------------------
def _save(rec: dict) -> str:
    if _STORE is not None:
        return _STORE.save_correction(rec)
    with _LOCK:
        if not any(c["id"] == rec["id"] for c in _CORRECTIONS):
            _CORRECTIONS.append(rec)
    return rec["id"]


def _all() -> list[dict]:
    return _STORE.all_corrections() if _STORE is not None else list(_CORRECTIONS)


def reset() -> None:
    _CORRECTIONS.clear()
