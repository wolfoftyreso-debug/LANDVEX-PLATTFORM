"""Händelseroutning – från broadcast till "ditt beslut kan ha ändrats".

Grundtesen: **en händelse som inte ändrar ett beslut är inte en händelse, den
är brus.** Feed-lagret (`engine.feeds`) och bevakningslagret
(`engine.monitors`) upptäcker att verkligheten rört sig – men de sänder ut i
tomma intet. Det här lagret sätter en MOTTAGARE i andra änden och avgör om
rörelsen angår just henne.

Kedjan blir: signal → händelse → **intresse** → beslut att ompröva.

  * `subscribe` – en besökare registrerar sitt INTRESSE (`stakes`): en plats,
    en bransch, ett yrke, ett beslut hon äger, en bevakning hon satt upp.
    Rollen (`engine.entrypoints`) avgör var svaret hämtas när hon vill veta mer.
  * `route` – varje händelse vägs mot varje intresse. Träff → levererad post
    som svarar på tre saker: vad ändrades, **varför det angår just dig**, och
    vilket beslut som bör omprövas (med endpointen som ger om-svaret).
  * Icke-träffar SUPPRIMERAS – och redovisas i klartext (`suppressed` med
    skäl). Tyst bortsortering är hur system tappar förtroende; ett larm man
    inte fick veta att man inte fick är värre än inget larm.

Prioritetsordningen är inte magnitud utan ANSVAR: ett beslut du står bakom
väger tyngst, sedan en bevakning du äger, sedan plats/bransch/yrke. Den som
bär utfallet ska störas först.

Rent stdlib, deterministiskt (ingen klocka läses – tid skickas in).
"""
from __future__ import annotations

import threading

from .integrity import canonical_hash

# Hur tungt ett intresse väger. Ansvar före nyfikenhet: står du bakom ett
# beslut ska du störas före den som råkar följa regionen.
STAKE_WEIGHT: dict[str, float] = {
    "decision": 1.00,     # du har lovat ett utfall – du bär det
    "monitor": 0.92,      # du satte upp bevakningen
    "place": 0.75,        # du har verksamhet/ansvar här
    "sector": 0.65,       # din bransch
    "occupation": 0.65,   # ditt kompetensområde
}
SEVERITY_WEIGHT: dict[str, float] = {
    "low": 0.40, "medium": 0.70, "high": 0.90, "critical": 1.00,
    "insufficient": 0.30,
}
SEVERITY_RANK = {"insufficient": 0, "low": 1, "medium": 2, "high": 3,
                 "critical": 4}
DEFAULT_THRESHOLD = 50.0

# Vart en roll går för att få OM-svaret när något rört sig. Speglar
# entrypoints.answered_by; hålls som data så en ny roll = en ny rad.
REANSWER: dict[str, str] = {
    "citizen": "/v1/benchmark",
    "business": "/v1/report",
    "investor": "/v1/report",
    "municipality": "/v1/report",
    "journalist": "/v1/cite",
    "researcher": "/v1/event-study",
}

_SUBS: list[dict] = []
_LOCK = threading.Lock()


# ── Intresse ─────────────────────────────────────────────────────────────
def stake(kind: str, value: str, *, label: str = "") -> dict:
    """Ett intresse: vad besökaren har i potten."""
    if kind not in STAKE_WEIGHT:
        raise ValueError(f"unknown stake kind: {kind} "
                         f"(choose {', '.join(STAKE_WEIGHT)})")
    if not value:
        raise ValueError("a stake needs a value (which place, which decision…)")
    return {"kind": kind, "value": str(value), "label": label or str(value)}


def subscribe(subscriber: str, role: str, stakes: list[dict], *,
              min_severity: str = "medium",
              threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Registrera en besökares intressen. Kräver minst ett intresse –
    en prenumeration utan insats är just den broadcast vi vill bort från."""
    if not subscriber:
        raise ValueError("subscription needs a subscriber")
    if not stakes:
        raise ValueError("subscription needs at least one stake — without one "
                         "this is a broadcast, not event routing")
    if min_severity not in SEVERITY_RANK:
        raise ValueError(f"unknown severity: {min_severity}")
    for s in stakes:
        stake(s.get("kind", ""), s.get("value", ""))   # validera tidigt
    rec = {"subscriber": subscriber, "role": role,
           "stakes": [dict(s) for s in stakes],
           "min_severity": min_severity, "threshold": float(threshold),
           "reanswer": REANSWER.get(role, "/v1/report")}
    rec["id"] = canonical_hash({"subscriber": subscriber, "role": role,
                                "stakes": rec["stakes"]})
    with _LOCK:
        for i, s in enumerate(_SUBS):
            if s["id"] == rec["id"]:
                _SUBS[i] = rec
                return rec
        _SUBS.append(rec)
    return rec


def subscriptions(subscriber: str = "") -> list[dict]:
    return [dict(s) for s in _SUBS
            if not subscriber or s["subscriber"] == subscriber]


# ── Normalisering: feed-händelser och bevakningsfynd blir samma sak ──────
def from_feed_event(e: dict) -> dict:
    """En feed-händelse (engine.feeds) → gemensam händelseform."""
    return {"origin": "feed", "source_id": e.get("feed", ""),
            "severity": e.get("severity", "low"),
            "scope": e.get("scope_code", ""), "scope_type": e.get("scope_type", ""),
            "summary": e.get("summary", ""), "why": list(e.get("why_now", [])),
            "metrics": list(e.get("kpi_ids", [])), "owner": "",
            "checksum": e.get("checksum", "")}


def from_finding(f: dict) -> dict:
    """Ett bevakningsfynd (engine.monitors) → gemensam händelseform."""
    return {"origin": "monitor", "source_id": f.get("monitor_id", ""),
            "severity": f.get("severity", "low"),
            "scope": f.get("scope", ""), "scope_type": "monitor",
            "summary": f.get("detail", ""), "why": [f.get("rule", "")],
            "metrics": [f.get("metric", "")], "owner": f.get("owner", ""),
            "checksum": f.get("checksum", "")}


# ── Routning ─────────────────────────────────────────────────────────────
def _matches(st: dict, ev: dict, decisions: dict) -> tuple[bool, str]:
    """Träffar händelsen detta intresse? Returnerar (träff, skäl på engelska)."""
    kind, val = st["kind"], st["value"]
    if kind == "monitor":
        hit = ev.get("origin") == "monitor" and ev.get("source_id") == val
        return hit, ("this is the watch you set up" if hit else "")
    if kind == "decision":
        d = decisions.get(val)
        if not d:
            return False, ""
        # Beslutets grund rör sig: någon av dess KPI:er, eller dess metrik.
        keys = set(d.get("kpi_ids") or [])
        exp = (d.get("expected") or {}).get("metric")
        if exp:
            keys.add(exp)
        hit = bool(keys & set(ev.get("metrics") or []))
        return hit, ("the basis of a decision you committed to has moved"
                     if hit else "")
    if kind == "place":
        sc = str(ev.get("scope") or "")
        hit = sc == val or sc.endswith("-" + val) or val in sc
        return hit, ("this is a place you have a stake in" if hit else "")
    # sector/occupation matchar mot metriker eller scope-text
    hay = " ".join(list(ev.get("metrics") or []) + [str(ev.get("summary") or "")])
    hit = val.lower() in hay.lower()
    return hit, (f"it touches your {kind} ({val})" if hit else "")


def route(events: list[dict], subs: list[dict] | None = None, *,
          decisions: list[dict] | None = None, now: object = "") -> dict:
    """Dirigera händelser till dem som har något i potten.

    events: gemensam form (se from_feed_event / from_finding).
    decisions: åtagna beslut (engine.accountability) så ett beslut vars grund
    rört sig kan pekas ut explicit.

    Returnerar per prenumerant: levererade poster (rankade, med "varför just
    du" och vilket beslut som bör omprövas) plus en ÄRLIG suppressionsrapport.
    """
    subs = subscriptions() if subs is None else subs
    dec_by_id = {d["id"]: d for d in (decisions or [])}
    out = []
    for sub in subs:
        delivered, suppressed = [], []
        for ev in events:
            if SEVERITY_RANK.get(ev.get("severity", "low"), 0) < \
                    SEVERITY_RANK[sub["min_severity"]]:
                suppressed.append({"summary": ev.get("summary", ""),
                                   "reason": "below your severity floor "
                                             f"({sub['min_severity']})"})
                continue
            best = None
            for st in sub["stakes"]:
                hit, why = _matches(st, ev, dec_by_id)
                if not hit:
                    continue
                score = round(100.0 * STAKE_WEIGHT[st["kind"]] *
                              SEVERITY_WEIGHT.get(ev.get("severity", "low"), .4), 2)
                if best is None or score > best["relevance"]:
                    best = {"relevance": score, "stake": st, "why_you": why}
            if best is None:
                suppressed.append({"summary": ev.get("summary", ""),
                                   "reason": "no stake of yours is affected"})
                continue
            if best["relevance"] < sub["threshold"]:
                suppressed.append({"summary": ev.get("summary", ""),
                                   "reason": f"relevance {best['relevance']} "
                                             f"below your threshold {sub['threshold']}"})
                continue
            item = dict(ev)
            item.update({
                "relevance": best["relevance"],
                "matched_stake": best["stake"],
                "why_it_matters_to_you": best["why_you"],
                "reanswer_with": sub["reanswer"],
                "delivered_at": now,
            })
            if best["stake"]["kind"] == "decision":
                d = dec_by_id.get(best["stake"]["value"], {})
                item["revisit_decision"] = {
                    "id": d.get("id", ""), "decision": d.get("decision", ""),
                    "owner": (d.get("owners") or {}).get("formellt", ""),
                    "expected": d.get("expected", {}),
                    "action_en": "Re-check whether the expected outcome still "
                                 "holds, or resolve it against the actual."}
            delivered.append(item)
        delivered.sort(key=lambda i: -i["relevance"])
        out.append({
            "subscriber": sub["subscriber"], "role": sub["role"],
            "subscription_id": sub["id"], "reanswer_with": sub["reanswer"],
            "delivered": delivered, "delivered_count": len(delivered),
            # Ingen tyst bortsortering: vad som INTE nådde fram, och varför.
            "suppressed": suppressed, "suppressed_count": len(suppressed),
            "note_en": "Only movements that touch something you have at stake "
                       "are delivered. Everything held back is listed with its "
                       "reason — silence is never unexplained.",
        })
    return {"routed": out, "events_in": len(events),
            "subscriptions": len(subs), "now": now}


def brief(subscriber: str, events: list[dict], *,
          decisions: list[dict] | None = None, now: object = "") -> dict:
    """Vad en enskild besökare behöver veta nu – hennes rutade lista."""
    subs = subscriptions(subscriber)
    if not subs:
        return {"subscriber": subscriber, "status": "no_subscription",
                "note_en": "No stakes registered — nothing to route. "
                           "Subscribe with what you actually have at stake."}
    r = route(events, subs, decisions=decisions, now=now)
    # En besökare kan ha flera prenumerationer som matchar SAMMA händelse.
    # Leverera den då EN gång, med den starkaste kopplingen – dubbletter är
    # precis det brus det här lagret finns för att stoppa.
    best: dict[str, dict] = {}
    for row in r["routed"]:
        for i in row["delivered"]:
            key = i.get("checksum") or canonical_hash(
                {"s": i.get("summary"), "o": i.get("source_id")})
            if key not in best or i["relevance"] > best[key]["relevance"]:
                best[key] = i
    items = list(best.values())
    items.sort(key=lambda i: -i["relevance"])
    held = sum(row["suppressed_count"] for row in r["routed"])
    return {"subscriber": subscriber, "status": "brief",
            "items": items, "count": len(items), "held_back": held,
            "reanswer_with": subs[0]["reanswer"],
            "headline_en": (f"{len(items)} movement(s) touch what you have at "
                            f"stake; {held} held back as not yours to act on.")
            if items else
            ("Nothing you have a stake in has moved. "
             f"{held} movement(s) were held back."),
            "now": now}


def reset() -> None:
    """Nollställ prenumerationer (test)."""
    _SUBS.clear()
