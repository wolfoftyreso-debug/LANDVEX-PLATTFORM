"""Feed-event-buss – förändringsdetektion (dissg russin H).

Gör KPI-rörelser till deduplicerade "why-now"-händelser. Det här är exakt
det `risk_intel` flaggade som "requires monitoring history": lagret som
upptäcker att verkligheten RÖRT SIG, inte bara mäter den. Generatorer är
rena funktioner (rader → händelser); dedup via innehålls-checksumma så
samma händelse aldrig dubbleras. Leverans (SSE/webhook) hör till API-lagret.

Källa i dissg: feed_events-schema (migration 20260202032717), feed-def
(tier/min_effect_threshold/min_confidence/max_events_per_day),
generate-feed-events/index.ts:161-557. Rent stdlib, deterministiskt.
"""
from __future__ import annotations

from dataclasses import dataclass

from .integrity import canonical_hash

SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class Feed:
    code: str
    name: str
    tier: str = "open"                 # open | plus | pro
    min_effect_threshold: float = 2.0  # min |Δ%| för att räknas
    min_confidence: float = 0.7
    max_events_per_day: int = 10


FEEDS: tuple[Feed, ...] = (
    Feed("daily_top_changes", "Daily top changes", "open", 3.0, 0.6, 10),
    Feed("structural_decline", "Structural decline", "pro", 1.0, 0.7, 10),
    Feed("priority_alerts", "Priority alerts", "pro", 0.0, 0.7, 20),
    Feed("regional_anomalies", "Regional anomalies", "plus", 5.0, 0.7, 10),
)
_BY_CODE = {f.code: f for f in FEEDS}


def _event(feed: Feed, severity: str, scope_type: str, scope_code: str,
           summary: str, why_now: list[str], kpi_ids: list[str],
           confidence: str) -> dict:
    key = {"feed": feed.code, "scope": scope_code, "summary": summary,
           "kpi_ids": sorted(kpi_ids)}
    checksum = canonical_hash(key)
    return {"feed": feed.code, "severity": severity, "scope_type": scope_type,
            "scope_code": scope_code, "summary": summary, "why_now": why_now,
            "kpi_ids": kpi_ids, "confidence": confidence, "checksum": checksum}


def _dedup(events: list[dict], seen: set[str] | None = None) -> list[dict]:
    seen = set() if seen is None else seen
    out = []
    for e in events:
        if e["checksum"] in seen:
            continue
        seen.add(e["checksum"])
        out.append(e)
    return out


def generate(feed_code: str, rows: list[dict],
             seen: set[str] | None = None) -> list[dict]:
    """Generera händelser för en feed ur KPI-rader.

    rows-fält: code, region, trend_percent, value, previous, confidence
    (0–1), status, signal_strength (0–1), declining_periods (int),
    total_decline_pct. Cap per max_events_per_day; dedup via checksumma.
    """
    feed = _BY_CODE.get(feed_code)
    if feed is None:
        raise ValueError(f"okänd feed: {feed_code}")
    if feed_code == "daily_top_changes":
        ev = _gen_top(feed, rows)
    elif feed_code == "structural_decline":
        ev = _gen_decline(feed, rows)
    elif feed_code == "priority_alerts":
        ev = _gen_priority(feed, rows)
    elif feed_code == "regional_anomalies":
        ev = _gen_regional(feed, rows)
    else:
        ev = []
    return _dedup(ev, seen)[:feed.max_events_per_day]


def _conf_band(c: float) -> str:
    return "high" if c >= 0.8 else "medium" if c >= 0.6 else "low"


def _gen_top(feed: Feed, rows: list[dict]) -> list[dict]:
    picked = [r for r in rows
              if abs(r.get("trend_percent", 0)) >= feed.min_effect_threshold]
    picked.sort(key=lambda r: -abs(r.get("trend_percent", 0)))
    out = []
    for r in picked[:10]:
        d = r.get("trend_percent", 0)
        sev = "high" if abs(d) >= 5 else "medium"
        why = []
        if abs(d) >= 5:
            why.append("change exceeds 5% in the period")
        why.append(("rose" if d > 0 else "fell") + f" {abs(d):.1f}%")
        out.append(_event(feed, sev, "regional", r.get("region", "national"),
                          f"{r.get('code')} {('up' if d>0 else 'down')} "
                          f"{abs(d):.1f}%", why, [r.get("code", "")],
                          _conf_band(r.get("confidence", 0.7))))
    return out


def _gen_decline(feed: Feed, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if r.get("trend_percent", 0) > -2:
            continue
        if r.get("declining_periods", 0) < 3:
            continue
        total = r.get("total_decline_pct", r.get("trend_percent", 0))
        sev = "critical" if total <= -15 else "high"
        out.append(_event(feed, sev, "regional", r.get("region", "national"),
                          f"{r.get('code')} in sustained decline "
                          f"({r.get('declining_periods')} periods)",
                          [f"{r.get('declining_periods')} consecutive declining periods",
                           f"cumulative {total:.1f}%"],
                          [r.get("code", "")],
                          _conf_band(r.get("confidence", 0.7))))
    return out


def _gen_priority(feed: Feed, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        sig = r.get("signal_strength", 0)
        if sig < 0.7 or r.get("confidence", 0) < feed.min_confidence:
            continue
        sev = "critical" if sig >= 0.9 else "high"
        out.append(_event(feed, sev, "regional", r.get("region", "national"),
                          f"{r.get('code')} priority signal (strength {sig:.2f})",
                          [f"signal strength {sig:.2f}",
                           f"status {r.get('status','')}"],
                          [r.get("code", "")],
                          _conf_band(r.get("confidence", 0.7))))
    return out


def _gen_regional(feed: Feed, rows: list[dict]) -> list[dict]:
    # Gruppera per region; larma om ≥2 indikatorer avviker ≥ tröskel.
    by_region: dict[str, list[dict]] = {}
    for r in rows:
        if abs(r.get("trend_percent", 0)) >= feed.min_effect_threshold:
            by_region.setdefault(r.get("region", "national"), []).append(r)
    out = []
    for region, rs in by_region.items():
        if len(rs) < 2:
            continue
        sev = "high" if any(abs(r.get("trend_percent", 0)) >= 10 for r in rs) \
            else "medium"
        out.append(_event(feed, sev, "regional", region,
                          f"{len(rs)} indicators diverging in {region}",
                          [f"{len(rs)} indicators past threshold"],
                          [r.get("code", "") for r in rs],
                          _conf_band(min(r.get("confidence", 0.7) for r in rs))))
    return out


def catalog() -> list[dict]:
    return [{"code": f.code, "name": f.name, "tier": f.tier,
             "min_effect_threshold": f.min_effect_threshold,
             "min_confidence": f.min_confidence,
             "max_events_per_day": f.max_events_per_day} for f in FEEDS]
