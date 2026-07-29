"""Leveransloggen: vad som LÄMNADE systemet, signerat och spårbart.

Det integrationsansvariga på en myndighet eller ett storbolag kräver av
en utgång är inte fler format — det är att kunna LITA på den och
REVIDERA den:

* **Varje utgående POST bär tre huvuden.** `X-Landvex-Delivery-Id` (en
  idempotensnyckel — mottagarens system kan deduplicera vid
  at-least-once-leverans), `X-Landvex-Signature` (HMAC-SHA256 över
  kroppen med tenantens serverhemlighet — samma hemlighet som signerar
  credentials, så mottagaren kan verifiera avsändaren) och
  `X-Landvex-Schema` (payloadslag + version — transformer byggs mot
  versioner, inte mot hopp).
* **Varje försök loggas.** Slag, mål, status, mottagarens svar, och
  kroppens SHA-256 — ALDRIG kroppen själv: loggen ska kunna läsas brett
  utan att bli en andra kopia av data (eller hemligheter) som redan
  lämnat huset.
* **Loggen ljuger inte.** En misslyckad leverans står som misslyckad;
  att raden finns betyder att försöket gjordes, inte att det lyckades.
  `delivered` är mottagarens svar, aldrig vår förhoppning.

Verifieringen sluter cirkeln: mottagarens system kan när som helst
fråga plattformen om ett leverans-id och en kroppshash hör ihop —
samma mönster som credential-verifieringen. Rent stdlib.
"""
from __future__ import annotations

import hashlib
import hmac
import time as _time
import uuid

SCHEMA_VERSION = "v1"


class DeliveryRefused(ValueError):
    """Loggposten eller verifieringen gick inte, och varför."""


def _signature(tenant: str, body: bytes) -> str:
    # Samma per-tenant-hemlighet som signerar credentials: EN hemlighet
    # att rotera, ett ställe den bor på, ingen läsväg ut.
    from engine.credentials import _secret
    return hmac.new(_secret(tenant), body, hashlib.sha256).hexdigest()


def outbound_headers(tenant: str, body: bytes, kind: str) -> dict:
    """Huvudena varje utgående leverans bär — och leverans-id:t.

    Id:t är idempotensnyckeln: levereras samma post två gånger (at-
    least-once) ser mottagaren samma id och kan deduplicera.
    """
    return {
        "X-Landvex-Delivery-Id": "lvx-del-" + uuid.uuid4().hex[:16],
        "X-Landvex-Signature": _signature(tenant, body),
        "X-Landvex-Schema": f"{kind}.{SCHEMA_VERSION}",
    }


def record(*, tenant: str, kind: str, provider: str, body: bytes,
           delivery_id: str, delivered: bool, status: object,
           why_en: str = "", source: str = "") -> dict:
    """Loggposten: försöket som gjordes och svaret som kom.

    Kroppen loggas ALDRIG — bara dess SHA-256 och storlek. Loggen är
    en revisionsyta, inte en andra kopia av det som redan lämnat.
    `source` är återskapandereferensen (jobb-id för pushar, objekt-id
    för ärenden): en omkörning bygger leveransen på nytt från källan —
    den spelar aldrig upp en sparad kropp, för det finns ingen.
    """
    if not tenant or not kind or not delivery_id:
        raise DeliveryRefused(
            "a delivery record needs tenant, kind and delivery_id — an "
            "unattributable log row audits nothing")
    global _SEQ
    _SEQ += 1
    rad = {
        "id": delivery_id, "tenant": tenant, "kind": kind,
        "provider": provider,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "delivered": bool(delivered), "status": status,
        "why_en": why_en, "source": source,
        "schema": f"{kind}.{SCHEMA_VERSION}",
        "created_at": _time.time(),
        # Monotont löpnummer: time.time() kan ge samma värde för två
        # anrop tätt efter varandra, och en stabil sortering på enbart
        # en tidsstämpel faller då tillbaka till infogningsordning —
        # fel håll för "senaste först". Löpnumret gör ordningen exakt.
        "seq": _SEQ,
    }
    save_delivery(rad)
    return rad


def failure_streaks(tenant: str, *, window_hours: float = 24.0,
                    now: float = 0.0) -> list[dict]:
    """Felsviter per mål: hur många misslyckanden i rad SEDAN senaste
    lyckade leverans, inom fönstret.

    Det är sviten som larmar — ett enstaka nätfel är brus, fem raka
    mot samma system är ett system som inte tar emot. En lyckad
    leverans nollar sviten; larmet säger aldrig mer än loggen visar.
    """
    nu = now or _time.time()
    fran = nu - window_hours * 3600.0
    per_mal: dict[str, dict] = {}
    # all_deliveries är nyast-först; sviten räknas tills första lyckade.
    for r in all_deliveries(tenant, limit=1000):
        if r.get("created_at", 0) < fran:
            break
        mal = r.get("provider") or "webhook"
        rad = per_mal.setdefault(mal, {"provider": mal, "streak": 0,
                                       "sealed": False,
                                       "last_status": r.get("status"),
                                       "kinds": set()})
        if rad["sealed"]:
            continue
        if r.get("delivered"):
            rad["sealed"] = True
            continue
        rad["streak"] += 1
        rad["kinds"].add(r.get("kind", ""))
    ut = []
    for rad in per_mal.values():
        if rad["streak"] > 0:
            ut.append({"provider": rad["provider"],
                       "streak": rad["streak"],
                       "last_status": rad["last_status"],
                       "kinds": sorted(rad["kinds"])})
    ut.sort(key=lambda r: -r["streak"])
    return ut


def verify_delivery(delivery_id: str, body_sha256: str, *,
                    tenant: str) -> dict:
    """Mottagarens fråga: hör det här id:t och den här kroppen ihop?

    Svaret kommer ur LOGGEN — det plattformen faktiskt skickade — inte
    ur vad någon påstår. Okänt id och fel hash är olika svar.
    """
    rad = next((r for r in all_deliveries(tenant)
                if r.get("id") == delivery_id), None)
    if rad is None:
        return {"known": False, "match": False,
                "why_en": ("no such delivery id for this tenant — "
                           "either it was never sent from here, or it "
                           "belongs to someone else. Either way this "
                           "log cannot vouch for it.")}
    ok = hmac.compare_digest(rad.get("body_sha256", ""),
                             str(body_sha256 or ""))
    return {"known": True, "match": ok,
            "kind": rad.get("kind"), "schema": rad.get("schema"),
            "delivered": rad.get("delivered"),
            "why_en": ("the body hash matches what actually left this "
                       "platform under that id." if ok else
                       "the delivery id exists but the body hash does "
                       "not match what left this platform — the "
                       "payload was altered in transit or paired with "
                       "the wrong id.")}


def catalog() -> dict:
    return {
        "what_en": ("The outbound audit log: every delivery attempt — "
                    "pushes, credentials, filed exceptions — with the "
                    "receiver's actual answer. Every outbound POST "
                    "carries X-Landvex-Delivery-Id (idempotency), "
                    "X-Landvex-Signature (HMAC over the body with the "
                    "tenant's server secret) and X-Landvex-Schema "
                    "(payload kind + version to build transforms "
                    "against)."),
        "schema_version": SCHEMA_VERSION,
        "verify_en": ("POST /v1/deliveries/verify with a delivery_id "
                      "and the SHA-256 of the body you received — the "
                      "answer comes from the log of what actually "
                      "left, not from what anyone claims."),
        "cannot_en": ("The log records attempts and answers — never "
                      "the payload body itself (the log must be "
                      "readable without becoming a second copy of "
                      "data that already left), and never what the "
                      "receiving system did after answering. "
                      "'delivered' is the receiver's word; a row's "
                      "existence means the attempt happened, not that "
                      "it succeeded."),
    }


# ── Lagret (samma mönster som connections) ─────────────────────────────
_STORE = None
_RADER: list[dict] = []
_MINNESTAK = 500
_SEQ = 0


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_delivery(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_delivery", None):
        return _STORE.save_delivery(rec)
    _RADER.append(dict(rec))
    del _RADER[:-_MINNESTAK]
    return rec["id"]


def all_deliveries(tenant: str | None = None,
                   limit: int = 100) -> list[dict]:
    if _STORE is not None and getattr(_STORE, "all_deliveries", None):
        rader = _STORE.all_deliveries()
    else:
        rader = list(_RADER)
    if tenant is not None:
        rader = [r for r in rader if r.get("tenant") == tenant]
    # seq som tiebreaker: created_at kan tvillinga vid snabba anrop,
    # och en stabil sort på bara tiden lämnar tvillingade rader i
    # infogningsordning i stället för nyast-först.
    rader.sort(key=lambda r: (-r.get("created_at", 0), -r.get("seq", 0)))
    return rader[:limit]


def reset() -> None:
    """Endast för tester."""
    _RADER.clear()
