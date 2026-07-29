"""Omkörning och larm: loggens misslyckade rader är en kö, inte en grav.

**Omkörningen återskapar leveransen från KÄLLAN.** Loggen lagrar aldrig
kroppar (medvetet — se engine/deliveries), så en retry spelar inte upp
en sparad kropp: den bygger leveransen på nytt ur det som fortfarande
är sant. En push körs om från sitt jobb (dagens data, inte gårdagens);
ett ärende byggs om ur avvikelseflödets NUVARANDE rad för objektet —
och har avvikelsen läkt sedan felet är svaret det, inte ett ärende om
ett problem som inte längre finns. Varje omkörning får ett NYTT
leverans-id; den gamla raden står kvar som misslyckad. Historik skrivs
aldrig om.

Kvitton (credentials) körs inte om härifrån: kvittot utfärdas EN gång
vid den godkännande domen och kroppen finns inte kvar att skicka.
Vägran säger det, med vägen framåt.

**Larmet säger aldrig mer än loggen visar.** failure_streaks räknar
misslyckanden i rad per mål sedan senaste lyckade leverans; över
tröskeln skickas ETT larm per mål till kundens Slack/Teams-koppling —
och larmleveransen loggas själv, för ett larm som försvinner tyst är
värre än inget larm. Rent stdlib.
"""
from __future__ import annotations

import json
from typing import Callable

from engine import deliveries as DL
from engine.datasources.faults import OUR_BUGS

from .llm import _http

_TIMEOUT = 15.0


def retry(delivery_id: str, *, tenant: str,
          transport: Callable | None = None) -> dict:
    """Kör om EN misslyckad leverans — från källan, med nytt id."""
    rad = next((r for r in DL.all_deliveries(tenant, limit=1000)
                if r.get("id") == delivery_id), None)
    if rad is None:
        return {"retried": False,
                "why_en": ("no such delivery id for this tenant — the "
                           "log cannot retry what it never recorded")}
    if rad.get("delivered"):
        return {"retried": False,
                "why_en": ("that delivery succeeded — the receiver "
                           "confirmed it. Re-sending confirmed content "
                           "needs a new reason, not a retry button.")}
    slag = rad.get("kind", "")
    if slag.startswith("push."):
        return _retry_push(rad, tenant, transport)
    if slag == "inspection_exception":
        return _retry_exception(rad, tenant, transport)
    if slag == "credential":
        return {"retried": False,
                "why_en": ("a credential is issued ONCE at the "
                           "approving verdict, and the log keeps no "
                           "bodies to replay. The receipt itself is "
                           "still verifiable (/v1/credentials/verify); "
                           "to send a new one, record the next "
                           "approved verdict.")}
    if slag == "alert":
        return {"retried": False,
                "why_en": ("alerts are re-raised by the alert job when "
                           "the condition still holds — replaying an "
                           "old alarm says nothing about now")}
    return {"retried": False,
            "why_en": f"no retry path for kind {slag!r}"}


def _retry_push(rad: dict, tenant: str,
                transport: Callable | None) -> dict:
    from engine.pushes import PushRefused, deliver
    from engine.scheduler import all_jobs

    jobb = next((j for j in all_jobs(tenant)
                 if j.get("id") == rad.get("source")), None)
    if jobb is None:
        return {"retried": False,
                "why_en": (f"the subscription {rad.get('source')!r} "
                           f"behind this delivery is gone — nothing "
                           f"left to rebuild from. The failed row "
                           f"stands as history.")}
    try:
        ut = deliver(jobb, **({"transport": transport}
                              if transport else {}))
    except PushRefused as e:
        return {"retried": False, "why_en": str(e)}
    return {"retried": True, "result": ut,
            "note_en": ("rebuilt from the subscription with TODAY'S "
                        "data and a new delivery id — the original "
                        "failed row stands unchanged in the log")}


def _retry_exception(rad: dict, tenant: str,
                     transport: Callable | None) -> dict:
    from engine.connections import (ConnectionRefused, feedback_target,
                                    get_connection)
    from engine.inspections import exception_feed

    from .feedback import report_exceptions

    feed = exception_feed(tenant)
    kvar = [r for r in feed.get("exceptions", [])
            if (r.get("asset") or {}).get("id") == rad.get("source")]
    if not kvar:
        return {"retried": False,
                "why_en": (f"object {rad.get('source')!r} is no longer "
                           f"in the exception feed — the condition "
                           f"healed since the failed attempt, and a "
                           f"ticket about a problem that no longer "
                           f"exists would be noise in someone's "
                           f"queue.")}
    try:
        kopp = get_connection(rad.get("provider", ""), tenant=tenant)
    except ConnectionRefused:
        # Kopplingen som stod på raden finns inte längre — ta
        # feedback-målet i stället, och säg det i resultatet.
        kopp = feedback_target(tenant)
    ut = report_exceptions({**feed, "exceptions": kvar}, kopp,
                           **({"transport": transport}
                              if transport else {}))
    return {"retried": True, "result": ut,
            "note_en": ("rebuilt from the CURRENT exception row with a "
                        "new delivery id — the original failed row "
                        "stands unchanged in the log")}


def send_alert(text: str, connection: dict | None, *, tenant: str,
               transport: Callable | None = None) -> dict:
    """Skicka ETT larm till kundens kanal — och logga larmleveransen."""
    if connection is None:
        return {"delivered": False,
                "why_en": ("no Slack/Teams connection — the alert has "
                           "nowhere to go, and an alarm nobody hears "
                           "is recorded here instead of pretended "
                           "sent. Connect slack_webhook or "
                           "teams_webhook.")}
    from engine.connections import headers_for, target_url_of
    kropp = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    extra = DL.outbound_headers(tenant, kropp, "alert")
    sand = transport or _http
    try:
        status, _ = sand(target_url_of(connection),
                         {**headers_for(connection), **extra},
                         kropp, _TIMEOUT)
        ok = 200 <= status < 300
    except OUR_BUGS:
        raise
    except Exception as e:  # noqa: BLE001 — nätranden: larmet som
        # inte kom fram bokförs som just det.
        ok, status = False, type(e).__name__
    DL.record(tenant=tenant, kind="alert",
              provider=connection.get("provider", ""), body=kropp,
              delivery_id=extra["X-Landvex-Delivery-Id"],
              delivered=ok, status=status)
    return {"delivered": ok, "status": status,
            "why_en": "" if ok else
            f"the alert itself did not get through ({status}) — "
            f"logged, so the silence is at least visible"}
