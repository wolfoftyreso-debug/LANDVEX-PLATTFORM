"""Loopens sista ben: kvittot POSTas in i kundens eget system.

När en credential utfärdats skickas den till kundens feedback-webhook
(kopplingsmodulen). Resultatet redovisas som det blev: levererad med
mottagarens statuskod, eller inte levererad med skälet — och UTAN
koppling är svaret en redovisad icke-leverans, aldrig ett tyst hopp
över. Kundens system verifierar äktheten mot /v1/credentials/verify;
det är det som gör loopen till en loop och inte en megafon.

Transporten är injicerbar; webhook-URL:en är en hemlighet och ingår
aldrig i felmeddelanden. Rent stdlib.
"""
from __future__ import annotations

import json
from typing import Callable

from engine.datasources.faults import OUR_BUGS

from .llm import _http

_TIMEOUT = 15.0


def forward(credential: dict, connection: dict | None, *,
            transport: Callable | None = None) -> dict:
    """Skicka kvittot till kundens system — och säg som det gick."""
    if connection is None:
        return {"delivered": False,
                "why_en": ("no feedback_webhook or enterprise-system "
                           "connection for this tenant — the credential "
                           "was issued and is verifiable, but nothing "
                           "was sent anywhere. Connect your system "
                           "(POST /v1/connections: feedback_webhook, "
                           "sap, servicenow, dynamics365 or salesforce) "
                           "and the loop closes.")}
    from engine.connections import headers_for, target_url_of
    url = target_url_of(connection)
    sand = transport or _http
    try:
        status, _ = sand(url, headers_for(connection),
                         json.dumps(credential,
                                    ensure_ascii=False).encode("utf-8"),
                         _TIMEOUT)
    except OUR_BUGS:
        raise
    except Exception as e:  # noqa: BLE001 — nätranden: felet ÄR
        # resultatet, och det får aldrig se ut som en leverans.
        return {"delivered": False,
                "why_en": (f"never got there ({type(e).__name__}) — "
                           f"the credential was issued and remains "
                           f"verifiable, but the customer's system has "
                           f"not seen it. Nothing is reported as "
                           f"delivered.")}
    ok = 200 <= status < 300
    return {"delivered": ok, "status": status,
            "why_en": ("the customer's system answered — the receipt "
                       "is theirs now." if ok else
                       f"the customer's system answered HTTP {status} "
                       f"— that is their word, and it stands.")}
