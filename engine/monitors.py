"""Kontroll-infrastrukturlagret – bevakningar, schemalagd avvikelsedetektion
och eskalering till ansvarsloopen.

Det här är Landvex ursprungliga uppdrag gjort *operativt*: en stark motor som
HITTAR FEL OCH AVVIKELSER, körd på schema (cron), och som stänger cirkeln mot
ansvar. Tre steg, allt-är-data hela vägen:

  1. `define`  – en användare registrerar en bevakning: en metrik + ett scope
     + en REGEL (tröskel, brytpunkt, anomali, ihållande nedgång) + en kadens
     (hourly/daily/weekly/interval). En bevakning MÅSTE ha en ägare – ingen
     avvikelse utan någon som är satt att agera på den (samma NOGF-disciplin
     som beslut). Innehållshashat id, persisteras via Store.

  2. `evaluate` / `run_due` – motorn. `evaluate` kör regeln mot en serie och
     ger ett `Finding` (triggat? allvarsgrad? detalj?). `run_due` är cron-
     ingången: vilka bevakningar är förfallna vid `now`, kör dem, dedup via
     checksumma. Tid skickas ALLTID in (aldrig härledd i lagret) → determin-
     istiskt och testbart, överlever omstarter.

  3. `escalate` – bygger en bro från ett triggat Finding till
     `accountability.commit`: avvikelsen blir ett ägar-signerat beslut med ett
     förväntat utfall. "Något är fel" → "vem äger åtgärden och vad förväntar
     vi oss". Kontroll-intelligens som faktiskt leder till beslut.

Reglerna komponerar `engine.stats` (cusum, z-score, linreg) – nya regler är
DATA, ingen motorändring. Rent stdlib. Aldrig kausalitet; rapporterar
data_coverage; ärlig degradering till process-minne när Store saknas.
"""
from __future__ import annotations

import threading
from typing import Any

from . import stats
from .integrity import canonical_hash, framing_disclosure

# ── Kadens (cron) – deterministisk, tid skickas in ───────────────────────
_CADENCE_MINUTES: dict[str, int] = {
    "hourly": 60,
    "daily": 60 * 24,
    "weekly": 60 * 24 * 7,
}


def cadence_minutes(cadence: dict) -> int:
    """Minuter mellan körningar. cadence = {"every": "daily"} eller
    {"every": "interval", "interval_minutes": 15}. 0 = alltid förfallen."""
    every = cadence.get("every", "daily")
    if every == "interval":
        return max(1, int(cadence.get("interval_minutes", 60)))
    if every not in _CADENCE_MINUTES:
        raise ValueError(f"okänd kadens: {every} "
                         f"(välj {', '.join(_CADENCE_MINUTES)} eller interval)")
    return _CADENCE_MINUTES[every]


def _epoch(iso_or_epoch: Any) -> float:
    """Acceptera epoch-sekunder (float/int) direkt. Strängar tolkas som
    epoch om numeriska; annars 0 (kadensen faller tillbaka på 'alltid')."""
    if isinstance(iso_or_epoch, (int, float)):
        return float(iso_or_epoch)
    try:
        return float(iso_or_epoch)
    except (TypeError, ValueError):
        return 0.0


def due(cadence: dict, last_run: Any, now: Any) -> bool:
    """Är en bevakning med `cadence` förfallen vid `now` givet `last_run`?

    last_run tomt/None ⇒ aldrig körd ⇒ förfallen. Tider i epoch-sekunder,
    inskickade (aldrig härledda) → samma disciplin som usage_window_key.
    """
    if last_run in (None, "", 0):
        return True
    gap_s = cadence_minutes(cadence) * 60
    return (_epoch(now) - _epoch(last_run)) >= gap_s


# ── Regelkatalog (allt-är-data: detektorer komponerar stats) ─────────────
def _rule_threshold(series: list[float], p: dict) -> dict:
    """Sista värdet bryter en nivå. p: {level, direction: above|below}."""
    v = series[-1]
    level = float(p["level"])
    direction = p.get("direction", "above")
    breached = v >= level if direction == "above" else v <= level
    dist = abs(v - level) / abs(level) * 100.0 if level else 0.0
    # Beskriv det som FAKTISKT hände. Att alltid skriva "62 ≥ 60" gör att ett
    # lugnt utfall läses som "41 ≥ 60" – ett påstående som är falskt. Ett larm
    # som ljuger i sin egen förklaring är värre än inget larm.
    if breached:
        detail = (f"latest {v:g} {'≥' if direction == 'above' else '≤'} "
                  f"level {level:g} ({dist:.1f}% past)")
    else:
        side = "below" if direction == "above" else "above"
        detail = (f"latest {v:g} has not crossed level {level:g} "
                  f"({dist:.1f}% {side})")
    return {"triggered": breached,
            "severity": "high" if breached and dist >= 10 else
                        "medium" if breached else "low",
            "detail": detail,
            "measure": round(v, 6)}


def _rule_changepoint(series: list[float], p: dict) -> dict:
    """Strukturellt brott (CUSUM). p: {threshold}."""
    r = stats.cusum_changepoint(series, float(p.get("threshold", 2.5)))
    return {"triggered": r["detected"],
            "severity": "high" if r["significance"] >= 80 else
                        "medium" if r["detected"] else "low",
            "detail": f"CUSUM {r['max_cusum']:g} at index {r['index']} "
                      f"(significance {r['significance']:g})",
            "measure": r["max_cusum"]}


def _rule_anomaly(series: list[float], p: dict) -> dict:
    """Sista punkten är en z-score-anomali. p: {z_threshold}."""
    r = stats.zscore_anomaly(series, None, float(p.get("z_threshold", 2.0)))
    return {"triggered": r["is_anomaly"],
            "severity": "high" if r["z"] >= 3 else
                        "medium" if r["is_anomaly"] else "low",
            "detail": f"z {r['z']:g} (confidence {r['confidence']:g})",
            "measure": r["z"]}


def _rule_sustained_decline(series: list[float], p: dict) -> dict:
    """Ihållande nedgång: linreg-lutning ned med tillräcklig förklaringsgrad.
    p: {min_r2, significance_pct}."""
    r = stats.linreg_trend(series, float(p.get("significance_pct", 2.0)))
    min_r2 = float(p.get("min_r2", 0.5))
    hit = r["direction"] == "down" and r["r2"] >= min_r2
    return {"triggered": hit,
            "severity": "high" if hit and r["r2"] >= 0.8 else
                        "medium" if hit else "low",
            "detail": f"slope {r['slope']:g}/step, R² {r['r2']:g} "
                      f"(need down & R²≥{min_r2})",
            "measure": r["slope"]}


RULES: dict[str, dict] = {
    "threshold": {
        "label_en": "Threshold breach",
        "desc_en": "Latest value crosses a set level (above/below).",
        "params": {"level": "number", "direction": "above|below"},
        "min_points": 1, "_fn": _rule_threshold},
    "changepoint": {
        "label_en": "Structural change-point",
        "desc_en": "CUSUM detects a regime break in the series.",
        "params": {"threshold": "number (≈2.5 = 95%)"},
        "min_points": 3, "_fn": _rule_changepoint},
    "anomaly": {
        "label_en": "Outlier / anomaly",
        "desc_en": "Latest point is a z-score outlier vs its own history.",
        "params": {"z_threshold": "number (default 2.0)"},
        "min_points": 2, "_fn": _rule_anomaly},
    "sustained_decline": {
        "label_en": "Sustained decline",
        "desc_en": "Regression trend is down with enough explained variance.",
        "params": {"min_r2": "0-1 (default 0.5)",
                   "significance_pct": "number (default 2.0)"},
        "min_points": 4, "_fn": _rule_sustained_decline},
}


def rules_catalog() -> list[dict]:
    return [{"id": rid, **{k: v for k, v in r.items() if not k.startswith("_")}}
            for rid, r in RULES.items()]


# ── Bevakningar ──────────────────────────────────────────────────────────
_MONITORS: list[dict] = []
_FINDINGS: list[dict] = []
_LOCK = threading.Lock()
_STORE = None


def set_store(store) -> None:
    """Backa lagret med ett Store (läsande stödprov, ingen skräpskrivning)."""
    global _STORE
    _STORE = store if (store is not None
                       and getattr(store, "all_monitors", lambda: None)()
                       is not None) else None


def define(metric: str, scope: str, rule: str, owner: str, *,
           params: dict | None = None, cadence: dict | None = None,
           label: str = "") -> dict:
    """Registrera en bevakning. Kräver en ägare (ingen avvikelse utan någon
    satt att agera). rule ∈ RULES. Innehållshashat id; idempotent."""
    if rule not in RULES:
        raise ValueError(f"okänd regel: {rule} "
                         f"(välj {', '.join(RULES)})")
    if not owner:
        raise ValueError("a monitor needs an owner — no alert without "
                         "someone accountable for acting on it")
    cadence = cadence or {"every": "daily"}
    cadence_minutes(cadence)  # validera tidigt
    rec = {"metric": metric, "scope": scope, "rule": rule,
           "params": dict(params or {}), "cadence": dict(cadence),
           "owner": owner, "label": label or f"{metric} · {rule}",
           "enabled": True, "last_run": None}
    rec["id"] = canonical_hash({"metric": metric, "scope": scope,
                                "rule": rule, "params": rec["params"],
                                "owner": owner})
    _save_monitor(rec)
    return rec


def evaluate(monitor: dict, series: list[float], *, evaluated_at: Any = "",
             ) -> dict:
    """Kör bevakningens regel mot en serie → ett Finding.

    Ärligt: rapporterar data_coverage (antal punkter mot regelns minimum);
    om underlaget är för tunt triggar den inte utan flaggar `insufficient`.
    Aldrig kausalitet – bara "detta AVVIKER", med ramen som gjorde det.
    """
    spec = RULES[monitor["rule"]]
    n = len(series)
    coverage = {"points": n, "min_points": spec["min_points"],
                "sufficient": n >= spec["min_points"]}
    if not coverage["sufficient"]:
        return _finding(monitor, False, "insufficient",
                        f"only {n} points, rule needs {spec['min_points']}",
                        None, coverage, evaluated_at)
    r = spec["_fn"]([float(x) for x in series], monitor["params"])
    return _finding(monitor, bool(r["triggered"]), r["severity"],
                    r["detail"], r["measure"], coverage, evaluated_at)


def _finding(monitor: dict, triggered: bool, severity: str, detail: str,
             measure: float | None, coverage: dict, evaluated_at: Any) -> dict:
    checksum = canonical_hash({"monitor": monitor["id"], "detail": detail,
                               "triggered": triggered})
    return {"monitor_id": monitor["id"], "metric": monitor["metric"],
            "scope": monitor["scope"], "rule": monitor["rule"],
            "owner": monitor["owner"], "triggered": triggered,
            "severity": severity, "detail": detail, "measure": measure,
            "data_coverage": coverage, "evaluated_at": evaluated_at,
            "checksum": checksum,
            # avvikelse ≠ orsak; regeln + parametrarna är ramen som gjorde
            # detta till ett larm (statistik ljuger alltid).
            "framing": framing_disclosure({"rule": monitor["rule"],
                                           "params": monitor["params"],
                                           "not_causal": True})}


def run_due(monitors: list[dict], now: Any, series_by_id: dict[str, list],
            *, seen: set[str] | None = None) -> dict:
    """Cron-ingång: kör alla förfallna, aktiverade bevakningar vid `now`.

    series_by_id mappar monitor-id → dataserie (hämtad av anroparen från
    signal-/index-lagret). Dedup av findings via checksumma. Returnerar
    firings (triggade), all findings, och en lista över körda id:n så
    anroparen kan persistera `last_run`.
    """
    seen = set() if seen is None else seen
    findings, firings, ran = [], [], []
    for m in monitors:
        if not m.get("enabled", True):
            continue
        if not due(m.get("cadence", {"every": "daily"}),
                   m.get("last_run"), now):
            continue
        series = series_by_id.get(m["id"], [])
        f = evaluate(m, series, evaluated_at=now)
        _save_finding(f)
        ran.append(m["id"])
        if f["checksum"] in seen:
            continue
        seen.add(f["checksum"])
        findings.append(f)
        if f["triggered"]:
            firings.append(f)
    firings.sort(key=lambda f: -{"low": 0, "medium": 1, "high": 2,
                                 "critical": 3}.get(f["severity"], 0))
    return {"ran": ran, "checked": len(monitors), "findings": findings,
            "firings": firings, "fired": len(firings), "now": now}


def escalate(finding: dict, owners: dict, expected: dict, *,
             committed_at: str = "", horizon_months: int = 0) -> dict:
    """Bro till ansvarsloopen: ett triggat Finding → ett ägar-signerat beslut.

    "Något är fel" blir "vem äger åtgärden och vad förväntar vi oss". Importeras
    lat för att undvika cirkulärt beroende. Höjer om find&inget trigg.
    """
    if not finding.get("triggered"):
        raise ValueError("only a triggered finding can be escalated")
    from . import accountability
    decision = (f"Respond to {finding['metric']} @ {finding['scope']}: "
                f"{finding['detail']}")
    commitment = accountability.commit(
        decision, owners, expected, kpi_ids=[finding["metric"]],
        horizon_months=horizon_months, committed_at=committed_at)
    return {"finding": finding, "decision": commitment,
            "note_en": "Anomaly detected by a monitor is now an owned "
                       "decision with an expected outcome — the "
                       "control loop is closed against accountability."}


# ── lager (store eller process-minne) -------------------------------------
def _save_monitor(rec: dict) -> str:
    if _STORE is not None:
        return _STORE.save_monitor(rec)
    with _LOCK:
        for i, m in enumerate(_MONITORS):
            if m["id"] == rec["id"]:
                _MONITORS[i] = rec
                return rec["id"]
        _MONITORS.append(rec)
    return rec["id"]


def _save_finding(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_finding", None):
        out = _STORE.save_finding(rec)
        if out is not None:
            return out
    with _LOCK:
        if not any(f["checksum"] == rec["checksum"]
                   and f["monitor_id"] == rec["monitor_id"]
                   for f in _FINDINGS):
            _FINDINGS.append(rec)
    return rec["checksum"]


def all_monitors() -> list[dict]:
    return _STORE.all_monitors() if _STORE is not None else list(_MONITORS)


def all_findings() -> list[dict]:
    if _STORE is not None and getattr(_STORE, "all_findings", None):
        out = _STORE.all_findings()
        if out is not None:
            return out
    return list(_FINDINGS)


def get_monitor(monitor_id: str) -> dict | None:
    for m in all_monitors():
        if m["id"] == monitor_id:
            return m
    return None


def catalog() -> dict:
    """Öppna registret: regler + registrerade bevakningar (utan interna fält)."""
    return {"rules": rules_catalog(),
            "monitors": [{k: v for k, v in m.items()} for m in all_monitors()],
            "cadences": list(_CADENCE_MINUTES) + ["interval"]}


def reset() -> None:
    """Nollställ process-minnet (test). Rör inte ett persistent store."""
    _MONITORS.clear()
    _FINDINGS.clear()
