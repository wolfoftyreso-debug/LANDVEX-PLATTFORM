"""Utfallslager + kalibrering – den kompounderande hävstången (backlog #11).

Landvex princip 3: förklarbarhet före prediktion; utlova aldrig
överlevnadssannolikhet förrän UTFALLSDATA finns. Det här lagret loggar
etableringar och deras faktiska utfall och KALIBRERAR modellen mot dem:

  * logga (predikterad score → verkligt utfall) per etablering, append-only,
    innehållshashat id.
  * Brier-score för hur väl score förutsäger överlevnad (lägre = bättre).
  * reliabilitet per score-hink (predikterad vs observerad överlevnad).
  * en ärlig viktkalibrerings-signal (systematiskt över/underskattar scoren?).
  * `calibrated_survival` + `expected_roi` som förblir "ej_tillgangligt" tills
    minst `MIN_SAMPLE` utfall finns – aldrig en påhittad sannolikhet.

Rent stdlib. Modul-lokalt append-only register (`record`/`all_records`/
`reset`) delas av båda API-lagren; persistens via storage/ är uppföljning.
"""
from __future__ import annotations

from typing import Any

from .integrity import canonical_hash
from .stats import mean

MIN_SAMPLE = 30   # under detta: ingen kalibrerad sannolikhet lovas
_BUCKETS = ((0, 50, "weak"), (50, 70, "fair"), (70, 85, "strong"),
            (85, 101, "prime"))

_RECORDS: list[dict] = []


def log_outcome(location: dict, vertical: str, predicted_score: float,
                survived: bool, *, months_active: int = 0,
                revenue_index: float | None = None,
                established_at: str = "") -> dict:
    """Bygg en utfallspost (innehållshashat id). Rör inte registret."""
    rec = {
        "location": location, "vertical": vertical,
        "predicted_score": float(predicted_score),
        "survived": bool(survived), "months_active": int(months_active),
        "revenue_index": revenue_index, "established_at": established_at,
    }
    rec["id"] = canonical_hash(rec)
    return rec


def record(rec: dict) -> str:
    """Append-only: lägg en utfallspost i registret (idempotent på id)."""
    if not any(r["id"] == rec["id"] for r in _RECORDS):
        _RECORDS.append(rec)
    return rec["id"]


def all_records() -> list[dict]:
    return list(_RECORDS)


def reset() -> None:
    _RECORDS.clear()


def _bucket(score: float) -> str:
    for lo, hi, name in _BUCKETS:
        if lo <= score < hi:
            return name
    return "prime"


def brier_score(records: list[dict]) -> float | None:
    """Medelvärdet av (p − utfall)². p = predicted_score/100, utfall = 0/1."""
    if not records:
        return None
    return round(mean([(r["predicted_score"] / 100.0
                        - (1.0 if r["survived"] else 0.0)) ** 2
                       for r in records]), 4)


def calibration(records: list[dict] | None = None) -> dict:
    """Kalibreringsrapport: Brier, reliabilitet per hink, viktsignal.

    Under MIN_SAMPLE redovisas status 'insufficient' ärligt – ingen
    kalibrering låses upp förrän datan finns.
    """
    recs = all_records() if records is None else records
    n = len(recs)
    if n < MIN_SAMPLE:
        return {"status": "insufficient", "n": n, "min_sample": MIN_SAMPLE,
                "message": f"{n}/{MIN_SAMPLE} outcomes — no calibration yet."}
    buckets = []
    for lo, hi, name in _BUCKETS:
        rows = [r for r in recs if lo <= r["predicted_score"] < hi]
        if not rows:
            continue
        pred = mean([r["predicted_score"] / 100.0 for r in rows])
        obs = mean([1.0 if r["survived"] else 0.0 for r in rows])
        buckets.append({"bucket": name, "n": len(rows),
                        "predicted": round(pred, 4), "observed": round(obs, 4),
                        "gap": round(obs - pred, 4)})
    overall_gap = round(mean([b["gap"] for b in buckets]), 4) if buckets else 0.0
    signal = ("scores are well calibrated" if abs(overall_gap) < 0.05 else
              "scores are optimistic — down-weight" if overall_gap < 0 else
              "scores are conservative — up-weight")
    return {"status": "calibrated", "n": n,
            "brier_score": brier_score(recs), "reliability": buckets,
            "overall_gap": overall_gap, "weight_signal": signal}


def calibrated_survival(score: float,
                        records: list[dict] | None = None) -> dict:
    """Observerad överlevnadsfrekvens för scorens hink – eller ärligt
    'ej_tillgangligt' tills MIN_SAMPLE utfall finns i den hinken."""
    recs = all_records() if records is None else records
    name = _bucket(score)
    rows = [r for r in recs if _bucket(r["predicted_score"]) == name]
    if len(rows) < MIN_SAMPLE:
        return {"status": "ej_tillgangligt", "bucket": name,
                "n": len(rows), "min_sample": MIN_SAMPLE,
                "note": "Survival probability requires outcome data (principle 3)."}
    obs = mean([1.0 if r["survived"] else 0.0 for r in rows])
    return {"status": "calibrated", "bucket": name, "n": len(rows),
            "survival_probability": round(obs, 4)}


def expected_roi(score: float, records: list[dict] | None = None) -> dict:
    """`expected_roi` förblir låst tills kalibrering finns – låser sedan upp
    en överlevnads-grundad, ärligt märkt indikation (aldrig en garanti)."""
    surv = calibrated_survival(score, records)
    if surv["status"] != "calibrated":
        return {"status": "ej_tillgangligt",
                "reason": "Awaiting outcome calibration (backlog #11).",
                "detail": surv}
    return {"status": "indikation", "survival_probability": surv["survival_probability"],
            "bucket": surv["bucket"], "n": surv["n"],
            "caveat": "Survival-based indication from observed outcomes, "
                      "not a guarantee or a financial projection."}
