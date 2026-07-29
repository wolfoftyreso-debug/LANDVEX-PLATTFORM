"""Credentials: det verifierbara kvittot när ett uppdrag godkänts.

När ett uppdrag är GENOMFÖRT OCH GODKÄNT genererar systemet en
credential — ett signerat, innehållsadresserat kvitto på vad som
verifierades, när, och genom vilket uppdrag. Kvittot skickas vidare
till kundens eget system (feedback-webhooken i kopplingsmodulen), och
kundens system kan när som helst be plattformen verifiera äktheten:
loopen sluts.

Tre regler bär modulen:

* **Bara godkänt certifieras.** En underkänd kontroll får ingen
  credential — ett intyg om att någon TITTADE är inte ett intyg om att
  det såg rätt ut, och att blanda ihop dem är hela skälet att intyg
  förfalskas.
* **Signaturen är per tenant.** HMAC-SHA256 över kvittots kanoniska
  JSON med en serverhemlighet som aldrig lämnar systemet — inte ens
  maskerad. Ett manipulerat kvitto faller vid verifiering, och en
  kunds kvitton kan inte verifieras med någon annans hemlighet.
* **Aldrig person.** Kvittot bär uppdragsreferensen — vem som höll
  kameran bor hos quiXzoom, och det gäller kvittot också.

Rent stdlib.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets as _secrets
import time as _time
import uuid


class CredentialRefused(ValueError):
    """Kvittot gick inte att utfärda eller verifiera, och varför."""


# Kvittoslag som data — ett nytt slag är en rad.
KINDS: dict[str, dict] = {
    "check_passed": {
        "label_en": "Recurring check passed",
        "requires_en": "a recorded verdict of 'pass'",
    },
    "sponsored_completion": {
        "label_en": "Sponsored mission completed",
        "requires_en": "a registered completion with its mission "
                       "reference",
    },
}


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def issue(kind: str, subject: dict, *, tenant: str,
          mission_id: str, issued_at: float = 0.0) -> dict:
    """Utfärda ETT kvitto — eller vägra med skälet."""
    if kind not in KINDS:
        raise CredentialRefused(
            f"unknown credential kind {kind!r}; choose "
            f"{', '.join(sorted(KINDS))}")
    if not tenant:
        raise CredentialRefused("a credential needs a tenant — it is "
                                "signed with that tenant's own secret")
    if not mission_id:
        raise CredentialRefused(
            "a credential needs its mission reference: without it the "
            "receipt cannot be tied to the evidence, and an untied "
            "receipt certifies nothing")
    if kind == "check_passed" and subject.get("verdict") != "pass":
        raise CredentialRefused(
            f"verdict is {subject.get('verdict')!r} — only a PASS is "
            f"certified. A receipt for a failed check would read as "
            f"approval the moment it leaves the system, and receipts "
            f"travel.")
    for falt in ("zoomer_id", "name", "email", "phone"):
        if falt in subject:
            raise CredentialRefused(
                f"subject carries {falt!r}: the credential certifies "
                f"WHAT was verified and through WHICH mission — never "
                f"who. The person lives with quiXzoom.")
    payload = {
        "id": "lvx-cred-" + uuid.uuid4().hex[:16],
        "kind": kind, "tenant": tenant, "mission_id": mission_id,
        "subject": dict(subject),
        "issued_at": float(issued_at) or _time.time(),
    }
    payload["signature"] = hmac.new(
        _secret(tenant), _canonical(payload), hashlib.sha256).hexdigest()
    payload["verify_en"] = (
        "POST /v1/credentials/verify with this object — the platform "
        "recomputes the signature with the issuing tenant's secret. A "
        "single changed byte fails it.")
    return payload


def verify(credential: dict, *, tenant: str) -> dict:
    """Är kvittot äkta? Bara signaturen svarar — aldrig magkänslan."""
    if credential.get("tenant") != tenant:
        return {"valid": False,
                "why_en": ("the credential names a different tenant — "
                           "receipts are verified with the issuing "
                           "tenant's own secret, and no one else's "
                           "key can vouch for them")}
    utan = {k: v for k, v in credential.items()
            if k not in ("signature", "verify_en")}
    ratt = hmac.new(_secret(tenant), _canonical(utan),
                    hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(ratt, str(credential.get("signature", "")))
    return {"valid": ok,
            "why_en": ("the signature matches the issuing tenant's "
                       "secret — the receipt is exactly as issued."
                       if ok else
                       "the signature does not match — the receipt was "
                       "altered after issue, or was never issued here. "
                       "Either way it certifies nothing.")}


def catalog() -> dict:
    return {
        "what_en": ("A signed receipt generated when a mission is "
                    "completed AND approved. It is forwarded to the "
                    "customer's own system (the feedback_webhook "
                    "connection) and can be verified against the "
                    "platform at any time — the loop closes."),
        "kinds": {k: dict(v) for k, v in KINDS.items()},
        "cannot_en": ("A credential certifies what was verified, when, "
                      "and through which mission — never WHO performed "
                      "it (the person lives with quiXzoom), and never "
                      "that the world still looks the same: it is a "
                      "receipt for a moment, not a warranty."),
    }


# ── Tenanthemligheten: genereras en gång, lämnar aldrig systemet ───────
_STORE = None
_HEMLIGHETER: dict[str, bytes] = {}


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def _secret(tenant: str) -> bytes:
    if _STORE is not None and getattr(_STORE, "credential_secret", None):
        return _STORE.credential_secret(tenant)
    if tenant not in _HEMLIGHETER:
        _HEMLIGHETER[tenant] = _secrets.token_bytes(32)
    return _HEMLIGHETER[tenant]


def reset() -> None:
    """Endast för tester."""
    _HEMLIGHETER.clear()
