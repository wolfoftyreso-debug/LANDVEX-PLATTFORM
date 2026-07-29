"""Företagsprofilen: vem kunden ÄR, så uppdragen kan bära det.

Kunden lägger in sin företagsinformation en gång — namn, logotyp, om-
text, webbplats, profilfärg — och varje quiXzoom-uppdrag kunden
beställer bär sedan ett varumärkesblock: loggan syns på kartnålen i
quiXzoom, och den som trycker får upp vem som står bakom uppdraget och
varför. Samma block för fotokontroller som för sponsrade uppdrag —
publiken är olika, transparensen är densamma.

Gränsen är skarp: Landvex lagrar profilen och SKICKAR MED den på
uppdragskroppen. Hur quiXzoom ritar kartnålen, cachar loggan eller
klipper texten är quiXzooms — ett löfte om pixlar på någon annans
karta vore ett löfte ingen här kan hålla.

Logotypen är en URL, inte en fil: bilden bor hos kunden (eller kundens
CDN), och Landvex pekar. Samma regel som fältmediet — bilder bor inte
här. Rent stdlib.
"""
from __future__ import annotations

import time as _time
from urllib.parse import urlsplit


class ProfileRefused(ValueError):
    """Profilen gick inte att spara, och varför."""


_PRIVATA_PREFIX = ("127.", "10.", "192.168.", "169.254.", "0.")


def _publik_https(url: str, falt: str) -> str:
    """Publika https-adresser — quiXzoom ska kunna hämta loggan, och
    en privat adress i en uppdragskropp pekar in i någons nät."""
    delar = urlsplit(url)
    if delar.scheme != "https":
        raise ProfileRefused(
            f"{falt} must be https ({delar.scheme or 'no scheme'!r} "
            f"given) — it travels on every mission body and is fetched "
            f"by phones on the open internet.")
    vard = (delar.hostname or "").lower()
    if vard == "localhost" or vard.startswith(_PRIVATA_PREFIX):
        raise ProfileRefused(
            f"{falt} points at a private or loopback address ({vard}) "
            f"— a field contributor's phone could never fetch it, and "
            f"a mission body must not carry paths into anyone's "
            f"internal network.")
    return url


def profile(tenant: str, *, name: str, about_en: str = "",
            logo_url: str = "", website: str = "",
            brand_color: str = "", org_ref: str = "") -> dict:
    """Skapa/ersätt profilen — eller vägra med ett åtgärdbart skäl."""
    if not tenant:
        raise ProfileRefused("a company profile needs a tenant")
    if not name.strip():
        raise ProfileRefused(
            "the company name is what the zoomer taps to see — an "
            "unnamed mission owner is exactly the arrangement the "
            "platform refuses elsewhere, and it starts here")
    for falt, varde in (("logo_url", logo_url), ("website", website)):
        if varde:
            _publik_https(varde, falt)
    if brand_color and not (brand_color.startswith("#")
                            and len(brand_color) in (4, 7)):
        raise ProfileRefused(
            f"brand_color must be a #hex colour, got {brand_color!r}")
    return {
        "tenant": tenant, "name": name.strip(),
        "about_en": about_en.strip(), "logo_url": logo_url.strip(),
        "website": website.strip(), "brand_color": brand_color.strip(),
        "org_ref": org_ref.strip(),
        "updated_at": _time.time(),
    }


def brand_block(profil: dict) -> dict:
    """Varumärkesblocket som rider på uppdragskroppen till quiXzoom.

    Kartnålen bär loggan; att trycka öppnar den här informationen.
    Blocket är DATA på uppdraget — quiXzoom äger renderingen.
    """
    return {
        "company_en": profil["name"],
        "logo_url": profil.get("logo_url", ""),
        "about_en": profil.get("about_en", ""),
        "website": profil.get("website", ""),
        "brand_color": profil.get("brand_color", ""),
        "tap_info_en": (
            f"This mission is ordered by {profil['name']} through the "
            f"Landvex platform. Tap-through shows who ordered it and "
            f"why — a mission whose owner is hidden is refused at "
            f"creation."),
    }


def catalog() -> dict:
    return {
        "what_en": ("Your company profile: name, logo, about-text, "
                    "website and brand colour. Every mission you order "
                    "carries it — the logo marks the pin on the "
                    "quiXzoom map, and tapping it opens who ordered "
                    "the mission and why."),
        "fields": [
            {"id": "name", "label_en": "Company name", "required": True},
            {"id": "about_en", "label_en": "About (shown on tap)",
             "required": False},
            {"id": "logo_url", "label_en": "Logo URL (public https)",
             "required": False},
            {"id": "website", "label_en": "Website", "required": False},
            {"id": "brand_color", "label_en": "Brand colour (#hex)",
             "required": False},
            {"id": "org_ref", "label_en": "Org reference (internal)",
             "required": False},
        ],
        "cannot_en": ("Landvex stores the profile and sends it on the "
                      "mission body. How quiXzoom renders the pin, "
                      "caches the logo or truncates the text is "
                      "quiXzoom's — and the logo itself lives at YOUR "
                      "URL, never in this platform."),
    }


# ── Lagret (samma mönster som connections) ─────────────────────────────
_STORE = None
_PROFILER: dict[str, dict] = {}


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_profile(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_company_profile", None):
        return _STORE.save_company_profile(rec)
    _PROFILER[rec["tenant"]] = dict(rec)
    return rec["tenant"]


def get_profile(tenant: str) -> dict | None:
    if _STORE is not None and getattr(_STORE, "get_company_profile", None):
        return _STORE.get_company_profile(tenant)
    return _PROFILER.get(tenant)


def reset() -> None:
    """Endast för tester."""
    _PROFILER.clear()
