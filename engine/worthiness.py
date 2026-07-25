"""Signifikans-väljare ("worthiness") – dissg russin I (Reality Wrapped-motorn).

En generell motor som avgör VILKA förändringar som är värda att lyfta, och
rangordnar dem hero/primary/secondary/mention. Långt bortom retrospektiv:
återanvänds för digests, alert-triage och feed-urval. Fem faktorer med hårda
poängtak; brus (L0) och otillräcklig data exkluderas hårt.

Källa i dissg: src/lib/wrapped/worthinessEngine.ts:106-401 (speglad i
wrapped-api). Rent stdlib, deterministiskt.
"""
from __future__ import annotations

RELEVANCE_POINTS = {"L0": 0, "L1": 10, "L2": 20, "L3": 30, "L4": 40}
WORTHINESS_THRESHOLD = 50.0
PRIORITY = ((85.0, "hero"), (70.0, "primary"), (55.0, "secondary"),
            (50.0, "mention"))
CAPS = {"hero": 2, "primary": 5, "secondary": 10, "mention": 20}


def _magnitude(change_pct: float) -> float:
    a = abs(change_pct)
    for thr, pts in ((50, 25), (25, 20), (10, 15), (5, 10), (2, 5)):
        if a >= thr:
            return float(pts)
    return 0.0


def worthiness(snap: dict) -> dict:
    """Poängsätt en indikator-ögonblicksbild. Returnerar {total, worthy,
    priority, factors, reason}.

    snap-fält (alla valfria utom change_percent): relevance_level ('L0'..'L4'),
    data_availability ('verified'|'partial'|'insufficient'|…), change_percent,
    trend_acceleration, is_breaking_pattern (bool), consecutive_months (int),
    confidence (0–1), source_count (int), affected_population_percent,
    cross_domain_links (int).
    """
    lvl = snap.get("relevance_level", "L1")
    avail = snap.get("data_availability", "verified")
    if lvl == "L0" or avail == "insufficient":
        return {"total": 0.0, "worthy": False, "priority": None,
                "factors": {}, "reason": "excluded (noise or insufficient data)"}

    relevance = min(40.0, RELEVANCE_POINTS.get(lvl, 10)
                    + min(5.0, snap.get("affected_population_percent", 0) / 20.0))
    magnitude = _magnitude(snap.get("change_percent", 0.0))
    velocity = 0.0
    if abs(snap.get("trend_acceleration", 0.0)) > 0.5:
        velocity += 5
    if snap.get("is_breaking_pattern"):
        velocity += 7
    cm = snap.get("consecutive_months", 0)
    velocity += 3 if cm >= 6 else (1 if cm >= 3 else 0)
    velocity = min(15.0, velocity)
    quality = min(1.0, snap.get("confidence", 0.0)) * 5.0
    quality += {"verified": 3, "partial": 1}.get(avail, 0)
    sc = snap.get("source_count", 0)
    quality += 2 if sc >= 3 else (1 if sc >= 2 else 0)
    quality = min(10.0, quality)
    links = snap.get("cross_domain_links", 0)
    impact = 10.0 if links >= 5 else 7.0 if links >= 3 else \
        4.0 if links >= 2 else 2.0 if links >= 1 else 0.0

    factors = {"relevance": round(relevance, 2), "magnitude": magnitude,
               "velocity": velocity, "quality": round(quality, 2),
               "impact": impact}
    total = round(sum(factors.values()), 2)
    priority = None
    for thr, name in PRIORITY:
        if total >= thr:
            priority = name
            break
    top = max(factors, key=factors.get)
    return {"total": total, "worthy": total >= WORTHINESS_THRESHOLD,
            "priority": priority, "factors": factors,
            "reason": f"driven by {top}"}


def select_for_wrap(snaps: list[dict]) -> dict:
    """Poängsätt, filtrera värdiga, och fyll hero/primary/secondary/mention
    med tak (2/5/10/20). Returnerar {buckets, ranked}."""
    scored = []
    for s in snaps:
        w = worthiness(s)
        if w["worthy"]:
            scored.append({**s, "worthiness": w})
    scored.sort(key=lambda x: -x["worthiness"]["total"])
    buckets: dict[str, list] = {"hero": [], "primary": [], "secondary": [],
                                "mention": []}
    for item in scored:
        pr = item["worthiness"]["priority"]
        if pr and len(buckets[pr]) < CAPS[pr]:
            buckets[pr].append(item)
    return {"buckets": buckets, "ranked": scored}
