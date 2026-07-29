"""Kundens egna zoomers: anställda som tar riktade uppdrag.

Två vägar in, samma hårda gräns:

* **Koppla ett befintligt konto** — den anställde har redan quiXzoom,
  och kunden lägger in KONTOREFERENSEN (qz-...). Aldrig namn, aldrig
  e-post: referensen är adressen uppdrag riktas till, personen bakom
  den bor hos quiXzoom med sitt eget samtycke.
* **Bjud in** — den anställde har inget konto än. Kunden skapar en
  inbjudningskod med en ROLLETIKETT ("Store staff, Gamla stan" — en
  arbetsroll, inte en identitet). Koden ges till den anställde som
  onboardar hos quiXzoom; när quiXzoom bekräftar löses koden in mot
  kontoreferensen. Landvex ser aldrig personen — bara att en kod blev
  en referens.

Registret är det publiken i rutiner och stående beställningar pekar
på: "egna anställda fotar hyrbilarna" är en rad här plus en rutin med
namngiven publik. Rent stdlib.
"""
from __future__ import annotations

import secrets as _secrets
import time as _time


class StaffRefused(ValueError):
    """Raden gick inte att lägga till, och varför."""


def _ren_ref(ref: str) -> str:
    ref = (ref or "").strip()
    if not ref.startswith("qz-"):
        raise StaffRefused(
            f"{ref!r} is not a quiXzoom account reference (they start "
            f"with 'qz-'). The reference is the address missions are "
            f"targeted to — the person behind it lives with quiXzoom.")
    if "@" in ref or " " in ref:
        raise StaffRefused(
            "that looks like a name or an email address — refused. "
            "Landvex stores account references only; identity and "
            "consent live with quiXzoom, which is why they cannot "
            "leak from here.")
    return ref


def member(zoomer_ref: str, *, tenant: str,
           role_label_en: str = "") -> dict:
    """Koppla ett befintligt quiXzoom-konto till kundens register."""
    if not tenant:
        raise StaffRefused("a staff row needs a tenant")
    return {"id": _ren_ref(zoomer_ref), "kind": "member",
            "tenant": tenant, "zoomer_ref": _ren_ref(zoomer_ref),
            "role_label_en": role_label_en.strip(),
            "added_at": _time.time()}


def invite(*, tenant: str, role_label_en: str) -> dict:
    """Skapa en inbjudan: en kod och en arbetsroll — ingen person.

    Koden ges till den anställde; onboarding, identitet och samtycke
    sker hos quiXzoom. När quiXzoom bekräftat löses koden in
    (claim_invite) mot kontoreferensen.
    """
    if not tenant:
        raise StaffRefused("an invite needs a tenant")
    if not role_label_en.strip():
        raise StaffRefused(
            "an invite needs a role label (a job, like 'Store staff, "
            "Gamla stan') — it is what the routine will say about who "
            "may take the mission. It must not be a person's name; "
            "identity lives with quiXzoom.")
    return {"id": "lvx-inv-" + _secrets.token_hex(4),
            "kind": "invite", "tenant": tenant,
            "role_label_en": role_label_en.strip(),
            "status": "pending", "added_at": _time.time(),
            "hand_to_employee_en": (
                "Give this code to the employee. They enter it during "
                "quiXzoom onboarding; identity and consent are handled "
                "there, and only the account reference comes back "
                "here.")}


def claim_invite(invite_id: str, zoomer_ref: str, *,
                 tenant: str) -> dict:
    """Lös in koden mot kontoreferensen — inbjudan blir medlem."""
    rad = next((r for r in all_staff(tenant)
                if r["id"] == invite_id and r["kind"] == "invite"), None)
    if rad is None:
        raise StaffRefused(
            f"unknown invite {invite_id!r} for this tenant — codes are "
            f"single-use and tenant-bound")
    if rad.get("status") != "pending":
        raise StaffRefused(
            f"invite {invite_id!r} is {rad.get('status')!r} — a code is "
            f"used once; a reusable code would let anyone who saw it "
            f"join the roster")
    ny = member(zoomer_ref, tenant=tenant,
                role_label_en=rad["role_label_en"])
    rad = dict(rad)
    rad["status"] = "claimed"
    rad["claimed_ref"] = ny["zoomer_ref"]
    save_staff(rad)
    save_staff(ny)
    return ny


def refs(tenant: str) -> list[str]:
    """Kontoreferenserna — det rutinernas namngivna publik pekar på."""
    return [r["zoomer_ref"] for r in all_staff(tenant)
            if r["kind"] == "member"]


def catalog() -> dict:
    return {
        "what_en": ("Your own staff as zoomers: link an existing "
                    "quiXzoom account by its reference, or create an "
                    "invite code the employee redeems during quiXzoom "
                    "onboarding. The roster is what named-audience "
                    "routines point at — 'own staff photograph the "
                    "rental cars' is a row here plus a routine."),
        "cannot_en": ("Landvex stores account references and role "
                      "labels — never names, emails or identities. "
                      "Onboarding, identity and consent live with "
                      "quiXzoom; a reference row here cannot say who "
                      "the person is, and that is the point. Removing "
                      "a row stops future targeting; it does not touch "
                      "the person's quiXzoom account."),
    }


# ── Lagret (samma mönster som connections) ─────────────────────────────
_STORE = None
_RADER: dict[tuple[str, str], dict] = {}


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_staff(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_staff", None):
        return _STORE.save_staff(rec)
    _RADER[(rec["tenant"], rec["id"])] = dict(rec)
    return rec["id"]


def all_staff(tenant: str | None = None) -> list[dict]:
    if _STORE is not None and getattr(_STORE, "all_staff", None):
        rader = _STORE.all_staff()
    else:
        rader = list(_RADER.values())
    if tenant is not None:
        rader = [r for r in rader if r.get("tenant") == tenant]
    return sorted(rader, key=lambda r: r.get("added_at", 0))


def remove_staff(row_id: str, *, tenant: str) -> bool:
    if _STORE is not None and getattr(_STORE, "delete_staff", None):
        return _STORE.delete_staff(row_id, tenant)
    return _RADER.pop((tenant, row_id), None) is not None


def reset() -> None:
    """Endast för tester."""
    _RADER.clear()
