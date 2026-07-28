"""Körningar utan människa — och en ärlig gräns för vad de kan uppnå.

Beslutet `scheduled_runs` stod som `planned` med motiveringen "the cron
ENTRY POINT exists (/v1/monitors/run) but nothing calls it on a timer".
Det var sant, och en produkt som säljs som bevakning men bara svarar när
någon frågar är en rapport.

**En kadensdialekt, inte två.** Förfallologiken är `engine/monitors.due`
— samma ord (`hourly` / `daily` / `weekly` / `interval`), samma
epoch-disciplin där tiden skickas in och aldrig härleds. Ett andra
cron-språk i samma kodbas hade garanterat glidit isär.

**Jobbtyperna är data.** Ny typ = en rad i `JOB_KINDS` med en `run`.

**Det schemaläggaren INTE kan göra** står i klartext på varje körning:
en bevakning som vaknar har fortfarande ingenting att titta på förrän
det finns en historik att jämföra mot. Jobbtypen `monitors` hoppar
därför över med angivet skäl i stället för att utvärdera en tom serie
och rapportera "inga avvikelser" — vilket hade sett ut som lugn.
Jobbtypen `scan_refresh` är det som bygger historiken: varje körning
sparar en rapport, och det är dessa rapporter som en framtida bevakning
har att jämföra mot.

**Dubbelkörning.** Kör två processer samma jobb får kunden två
beställda fältuppdrag för samma objekt. Jobbet CLAIMAS därför i lagret
(atomisk UPDATE med förfallovillkor). Utan lager sker samma sak i
processminne, och körningen säger att den bara talar för sin egen
process i stället för att låtsas vara en klusterlås.

Rent stdlib.
"""
from __future__ import annotations

import threading as _threading
import time as _time
from typing import Any

from engine.monitors import cadence_minutes, due


class ScheduleRefused(ValueError):
    """Jobbet gick inte att skapa eller köra, och varför."""


# ── Jobbtyperna ─────────────────────────────────────────────────────────
def _run_dispatch(job: dict, now: float) -> dict:
    """Beställ fältuppdrag för allt som förfaller hos kunden."""
    from integrations.quixzoom_dispatch import dispatch_due

    r = dispatch_due(job["tenant"], job["params"].get("today", ""))
    return {"ordered": r["ordered_count"], "refused": r["refused_count"],
            "detail_en": (f"{r['ordered_count']} mission(s) ordered, "
                          f"{r['refused_count']} refused"),
            "refusals": [x["why_en"] for x in r["refused"][:3]]}


def _run_exceptions(job: dict, now: float) -> dict:
    """Räkna om registret och lista det som behöver någon."""
    from engine import inspections as I

    r = I.exception_feed(job["tenant"], job["params"].get("today", ""))
    return {"exceptions": r["count"], "of_total": r["of_total"],
            "detail_en": (f"{r['count']} of {r['of_total']} object(s) need "
                          f"someone" if r["count"] else r["quiet_en"])}


def _run_scan(job: dict, now: float) -> dict:
    """Kör om ett svep och SPARA rapporten — det är så historiken blir till."""
    from engine.profile import profile_from_dict
    from engine.scan import scan

    p = job["params"]
    r = scan(profile_from_dict(p.get("profile") or
                               {"vertical_id": p.get("vertical", "gym")}),
             top_n=int(p.get("top_n", 5)), market=p.get("market") or "")
    sparade = 0
    if _STORE is not None and getattr(_STORE, "save_report", None):
        for h in r["hotspots"]:
            _STORE.save_report({
                "vertical_id": p.get("vertical", ""),
                "opportunity_score": h["opportunity_score"],
                "data_coverage": h["data_coverage"],
                "location": {"lat": h["lat"], "lon": h["lon"],
                             "address": h["lage_en"]},
            }, now, tenant=job["tenant"])
            sparade += 1
    return {"hotspots": len(r["hotspots"]), "reports_saved": sparade,
            "detail_en": (f"{len(r['hotspots'])} location(s) re-scanned, "
                          f"{sparade} report(s) stored"
                          if sparade else
                          f"{len(r['hotspots'])} location(s) re-scanned; no "
                          f"store configured, so nothing was kept and no "
                          f"history is being built")}


def _run_monitors(job: dict, now: float) -> dict:
    """Väck bevakningarna — och säg vad de faktiskt hade att titta på."""
    from engine import monitors as M

    serier = job["params"].get("series_by_id") or {}
    bevakningar = M.all_monitors(job["tenant"])
    if not serier:
        return {"ran": 0, "checked": len(bevakningar), "skipped": True,
                "detail_en": (
                    "Woken, but skipped: no series was supplied and the "
                    "platform keeps no metric history yet. Evaluating an "
                    "empty series would report 'nothing triggered', which "
                    "reads as calm rather than as blind. Run scan_refresh "
                    "on a schedule first — that is what builds the "
                    "history a watch can compare against.")}
    r = M.run_due(bevakningar, now, serier)
    return {"ran": len(r["ran"]), "checked": r["checked"],
            "fired": r["fired"],
            "detail_en": f"{len(r['ran'])} watch(es) run, {r['fired']} fired"}


def _run_harvest(job: dict, now: float) -> dict:
    """Läs in en öppen källa för en marknad och lagra den.

    Ett anrop per region och dygn. Att i stället fråga i
    förfrågningsvägen hade varit långsamt, ovänligt mot en gratistjänst
    och oreproducerbart.
    """
    from engine import harvest
    from engine.markets import MARKETS

    p = job["params"]
    kalla = p.get("source", "osm")
    marknad = p.get("market", "")
    if kalla not in harvest.SOURCES:
        raise ValueError(f"unknown harvest source {kalla!r}; choose "
                         f"{', '.join(sorted(harvest.SOURCES))}")
    if not harvest.url_for(kalla):
        return {"harvested": 0, "regions": 0, "skipped": True,
                "detail_en": (
                    f"{kalla} is not switched on. Set "
                    f"{harvest.SOURCES[kalla]['env']}, or "
                    f"LANDVEX_OPEN_DATA=on for every keyless source at "
                    f"once. Nothing was fetched and nothing was stored.")}
    marknader = [marknad] if marknad in MARKETS else list(MARKETS)
    rader, regioner = 0, 0
    for mid in marknader:
        for region in MARKETS[mid].regions[:int(p.get("limit", 0)) or None]:
            regioner += 1
            rader += harvest.store_rows(
                harvest.harvest_region(kalla, region, mid))
    return {"harvested": rader, "regions": regioner,
            "detail_en": (f"{rader} row(s) stored from {regioner} region(s) "
                          f"via {kalla}")}


def _run_analyse(job: dict, now: float) -> dict:
    """Svep en marknad efter motsägelser och samband, lägg fynden i
    registret. Dedup på checksumma: samma motsägelse två dygn i rad är
    ett fynd, inte två."""
    from engine import analysis

    p = job["params"]
    r = analysis.run(p.get("market", "se"), limit=int(p.get("limit", 0)),
                     as_of=p.get("as_of", ""))
    return {"new_findings": r["new_findings"], "found": r["found"],
            "detail_en": (
                f"{r['found']} finding(s), {r['new_findings']} new. "
                f"{r['relationships']['skipped_all_mock']} pair(s) skipped "
                f"where both signals were simulated.")}


JOB_KINDS: dict[str, dict] = {
    "inspections_dispatch": {
        "label_en": "Order field missions for what falls due",
        "capability": "asset_inspections",
        "params_en": "today (optional)",
        "run": _run_dispatch,
        "note_en": "Refusals are counted, not hidden: a run that ordered "
                   "nothing because the endpoint is unset must not look "
                   "like a run with nothing due."},
    "inspections_exceptions": {
        "label_en": "Recompute the compliance record and list exceptions",
        "capability": "asset_inspections",
        "params_en": "today (optional)",
        "run": _run_exceptions,
        "note_en": "Reads only. A quiet day is reported as a quiet day."},
    "scan_refresh": {
        "label_en": "Re-run a market sweep and store the result",
        "capability": "opportunity",
        "params_en": "profile (or vertical), market, top_n",
        "run": _run_scan,
        "note_en": "This is the job that creates history. Without stored "
                   "results over time there is nothing for a watch to "
                   "compare against, and no outcome data to calibrate on."},
    "harvest": {
        "label_en": "Read an open source once and store it",
        "capability": "core",
        "params_en": "source, market (optional), limit (optional)",
        "run": _run_harvest,
        "note_en": "Open reference data is the same for every customer, "
                   "so it is stored without a tenant. The request path "
                   "reads the store and never calls a third party."},
    "analyse": {
        "label_en": "Search a market for contradictions and relationships",
        "capability": "opportunity",
        "params_en": "market, limit (optional)",
        "run": _run_analyse,
        "note_en": "Never reports a pair where both signals are "
                   "simulated: two mock series correlate exactly as the "
                   "generator built them."},
    "monitors": {
        "label_en": "Wake the registered watches",
        "capability": "monitoring",
        "params_en": "series_by_id (required — see note)",
        "run": _run_monitors,
        "note_en": "Skips honestly when no series is supplied. Waking a "
                   "watch is not the same as having something to look at."},
}


# ── Jobben ──────────────────────────────────────────────────────────────
def job(id: str, kind: str, *, cadence: dict | None = None,
        params: dict | None = None, tenant: str = "",
        enabled: bool = True) -> dict:
    """Skapa ett jobb, eller vägra med ett skäl som går att åtgärda."""
    if not id:
        raise ScheduleRefused("a job needs an id")
    if kind not in JOB_KINDS:
        raise ScheduleRefused(
            f"unknown job kind {kind!r}; choose {', '.join(sorted(JOB_KINDS))}")
    kad = dict(cadence or {"every": "daily"})
    cadence_minutes(kad)                      # validerar tidigt, samma dialekt
    if not tenant:
        raise ScheduleRefused(
            f"job {id!r} has no tenant. A scheduled run acts on a "
            f"customer's own data — without a tenant it would act on "
            f"everyone's, unattended, with nobody watching.")
    return {"id": id, "kind": kind, "tenant": tenant, "cadence": kad,
            "params": dict(params or {}), "enabled": bool(enabled),
            "last_run": 0.0, "last_status": "", "last_summary": {}}


def catalog() -> dict:
    return {
        "kinds": [{"id": k, **{x: y for x, y in v.items() if x != "run"}}
                  for k, v in JOB_KINDS.items()],
        "cadences_en": ["hourly", "daily", "weekly",
                        "interval + interval_minutes"],
        "principle_en": (
            "The cadence vocabulary is the one monitors already use — one "
            "cron dialect in the codebase, not two. Time is passed in, "
            "never derived, so a scheduled run is as reproducible as any "
            "other engine call."),
        "cannot_en": (
            "A schedule makes the platform wake up. It does not create "
            "data that is not there: a watch with no history still has "
            "nothing to compare against, and says so instead of reporting "
            "calm."),
    }


# ── Lagret ──────────────────────────────────────────────────────────────
_LOCK = _threading.Lock()
_JOBS: list[dict] = []
_STORE = None
_CLAIMS: dict[str, float] = {}      # in-memory-fallback, per process


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_job(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_job", None):
        return _STORE.save_job(rec)
    with _LOCK:
        for i, r in enumerate(_JOBS):
            if r["id"] == rec["id"] and r["tenant"] == rec["tenant"]:
                _JOBS[i] = rec
                return rec["id"]
        _JOBS.append(rec)
    return rec["id"]


def all_jobs(tenant: str | None = None) -> list[dict]:
    rader = (_STORE.all_jobs() if _STORE is not None
             and getattr(_STORE, "all_jobs", None) else list(_JOBS))
    if tenant is None:
        return rader
    return [r for r in rader if r.get("tenant", "") == tenant]


def reset() -> None:
    """Endast för tester."""
    with _LOCK:
        _JOBS.clear()
        _CLAIMS.clear()


def _claim(rec: dict, now: float) -> bool:
    """Ta jobbet, eller lämna det åt den som redan tagit det.

    Två processer som kör samma jobb ger kunden två beställda fältuppdrag
    för samma objekt. Med lager är villkoret atomiskt i databasen; utan
    lager gäller det bara den här processen, och körningen säger det.
    """
    gap = cadence_minutes(rec["cadence"]) * 60
    if _STORE is not None and getattr(_STORE, "claim_job", None):
        return bool(_STORE.claim_job(rec["id"], rec.get("tenant", ""),
                                     now, gap))
    with _LOCK:
        nyckel = f"{rec.get('tenant', '')}:{rec['id']}"
        forra = _CLAIMS.get(nyckel, rec.get("last_run") or 0.0)
        if forra and (now - forra) < gap:
            return False
        _CLAIMS[nyckel] = now
        return True


# ── Körningen ───────────────────────────────────────────────────────────
def run_due(tenant: str | None = None, now: Any = None,
            allowed_kinds: set | None = None) -> dict:
    """Kör allt som förfaller. Ingången en timer (eller EventBridge) slår på.

    Returnerar vad som kördes, vad som hoppades över och varför — en
    körning som inte gjorde något ska gå att skilja från en körning som
    inte skedde.
    """
    nu = float(now) if now is not None else _time.time()
    kord, hoppade, fel = [], [], []
    for rec in all_jobs(tenant):
        if not rec.get("enabled", True):
            hoppade.append({"id": rec["id"], "why_en": "disabled"})
            continue
        # Ett jobb skapades en gång med rätt paket. Paketet kan ha ändrats
        # sedan dess, och ett schemalagt jobb är just det som ingen tittar
        # på — det får inte fortsätta köra på en behörighet som gått ut.
        if allowed_kinds is not None and rec["kind"] not in allowed_kinds:
            hoppade.append({
                "id": rec["id"],
                "why_en": (f"the current package no longer includes "
                           f"{rec['kind']!r} "
                           f"({JOB_KINDS[rec['kind']]['capability']}) — the "
                           f"job is kept, not deleted, and resumes if the "
                           f"package does")})
            continue
        if not due(rec["cadence"], rec.get("last_run"), nu):
            hoppade.append({"id": rec["id"], "why_en": "not due yet"})
            continue
        if not _claim(rec, nu):
            hoppade.append({"id": rec["id"],
                            "why_en": "already claimed by another run"})
            continue
        kind = JOB_KINDS[rec["kind"]]
        try:
            resultat = kind["run"](rec, nu)
            status = "ok"
        except Exception as e:                                # noqa: BLE001
            # Ett jobb som faller får aldrig fälla körningen: nästa jobb
            # gäller en annan kund. Felet skrivs in i jobbet i stället, så
            # det syns i registret i stället för i en logg ingen läser.
            resultat = {"detail_en": f"{type(e).__name__}: {e}"}
            status = "error"
            fel.append({"id": rec["id"], "why_en": resultat["detail_en"]})
        rec["last_run"] = nu
        rec["last_status"] = status
        rec["last_summary"] = resultat
        save_job(rec)
        kord.append({"id": rec["id"], "kind": rec["kind"],
                     "status": status, **resultat})
    return {
        "ran": kord, "ran_count": len(kord),
        "skipped": hoppade, "errors": fel, "now": nu,
        "claim_en": ("Jobs are claimed in the store, so two workers cannot "
                     "run the same job twice."
                     if _STORE is not None and getattr(_STORE, "claim_job",
                                                       None)
                     else "No store configured: claims hold within THIS "
                          "process only. Run a single instance, or "
                          "configure a store before scaling out."),
        "means_en": ("A run that did nothing is not the same as a run that "
                     "never happened — everything skipped is listed with "
                     "its reason."),
    }
