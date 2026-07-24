"""Kommissionsmodell (quiXzoom QZ TOKEN per lead).

Bekräftad av AAMOS-dev: Growth-planen är INTE månadsavgift utan en
per-lead-kommission. En "lead" = en motorgenererad affärsmöjlighet
(ett beslutskort / en identifierad opportunity). Beloppet graderas av
opportunity-score:

    score 0.80–1.00 → 0.15 QZ TOKEN
    score 0.50–0.80 → 0.10 QZ TOKEN
    score 0.00–0.50 → 0.05 QZ TOKEN   (svag lead)

Ren, deterministisk datamodell – tabellen är data (ny nivå = ny rad),
ingen affärsregel gömd i motorlogiken. 1 QZ TOKEN ≈ 0.15 USD (schablon,
märks som sådan; växelkurs sätts av quiXzoom, inte här).
"""
from __future__ import annotations

# (undre gräns inklusive, övre exklusive utom sista, qz_token)
TIERS: tuple[tuple[float, float, float], ...] = (
    (0.80, 1.01, 0.15),
    (0.50, 0.80, 0.10),
    (0.00, 0.50, 0.05),
)
QZ_TOKEN_USD_SCHABLON = 0.15   # 1 QZ ≈ $0.15 (quiXzoom sätter kursen)


def _score01(score: float) -> float:
    """Normalisera en opportunity-score till 0–1 (motorerna ger 0–100)."""
    s = float(score)
    if s > 1.0:
        s = s / 100.0
    return max(0.0, min(1.0, s))


def commission_qz(score: float) -> float:
    """QZ TOKEN för en lead med given opportunity-score (0–1 eller 0–100)."""
    s = _score01(score)
    for lo, hi, qz in TIERS:
        if lo <= s < hi:
            return qz
    return TIERS[-1][2]


def commission_for_lead(score: float) -> dict:
    """Full kommissionspost för ett beslutskort (leadet)."""
    qz = commission_qz(score)
    return {
        "modell": "per_lead",
        "qz_token": qz,
        "usd_schablon": round(qz * QZ_TOKEN_USD_SCHABLON, 4),
        "notis_en": ("quiXzoom commission for this lead, graded by "
                     "opportunity score. 1 QZ ≈ $0.15 (standard estimate; "
                     "quiXzoom sets the rate)."),
    }


def commission_catalog() -> dict:
    """Prislistans kommissionsstruktur (för /v1/plans)."""
    return {
        "modell": "per_lead",
        "enhet": "QZ TOKEN",
        "usd_schablon_per_qz": QZ_TOKEN_USD_SCHABLON,
        "lead_definition_en": ("An engine-identified business opportunity "
                               "(a delivered decision card)."),
        "nivaer": [{"score_min": lo, "score_max": round(hi - 0.01, 2),
                    "qz_token": qz} for lo, hi, qz in TIERS],
    }
