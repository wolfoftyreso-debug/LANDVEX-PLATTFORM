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

Logotypen kan vara ANTINGEN en extern URL (bilden bor hos kunden eller
kundens CDN, Landvex pekar — som förut) ELLER en uppladdad fil som
Landvex tar emot, dömer och lagrar självt. Det senare är ett medvetet
undantag från regeln att bilder inte bor här: fältmediet (foton från
en kontroll) är BEVIS och stannar hos quiXzoom; varumärkestillgången
(en logotyp kunden själv laddar upp) är något helt annat — en resurs
kunden explicit gett plattformen för att den ska synas på kundens
EGNA uppdrag. Godkänd fil, dömd och lagrad, är fortfarande bara
fetchbar utåt om LANDVEX_PUBLIC_BASE_URL är satt — annars vore
logo_url ett löfte om en adress ingen kan nå.

Uppladdningen sniffas på INNEHÅLLET, aldrig på filnamnet eller
ändelsen: en .png som egentligen är text vägras precis lika hårt som
en ärlig .txt. Kända-men-inte-stödda format (HEIC/HEIF från iPhone,
TIFF, PDF, ICO, PSD) vägras med namn och en väg framåt, aldrig som ett
anonymt "unsupported". Mått läses ur filens egna byte (PNG/JPEG/GIF/
BMP/WEBP-headrarna, struct, inget bibliotek) och döms mot minsta/
största upplösning och sidförhållande — för litet går inte att läsa
som logotyp, för avlångt är ett baner, inte en logotyp. SVG saneras
med en tillåtelselista av taggar: farligt innehåll (script, event-
hanterare, externa referenser) VÄGRAS, städas aldrig tyst bort — samma
doktrin som allt annat i den här plattformen.

Den enda faktiska formatanpassningen är BMP → PNG (24-bitars,
okomprimerad BMP; ren zlib-hopackning, ingen extern kodare) — det är
den enda konverteringen som går att göra korrekt och pixel-exakt utan
ett bildbibliotek. Övriga accepterade format (PNG/JPEG/GIF/WEBP/SVG)
är redan webblämpliga och lagras som de kom. Rent stdlib.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
import struct
import time as _time
import xml.etree.ElementTree as ET
import zlib
from urllib.parse import urlsplit


class ProfileRefused(ValueError):
    """Profilen (eller loggan) gick inte att spara, och varför."""


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

    En uppladdad logga vinner över logo_url-fältet, men ENDAST om
    LANDVEX_PUBLIC_BASE_URL är satt — annars vore adressen ett löfte om
    en fetch ingen utanför den här processen kan göra, och den regeln
    är densamma som _publik_https tillämpar på det inskrivna fältet.
    """
    logo_url = profil.get("logo_url", "")
    bas = os.environ.get("LANDVEX_PUBLIC_BASE_URL", "").rstrip("/")
    if bas and get_logo(profil.get("tenant", "")):
        logo_url = f"{bas}/v1/company/logo/raw?tenant={profil['tenant']}"
    return {
        "company_en": profil["name"],
        "logo_url": logo_url,
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
                    "the mission and why. The logo can be either an "
                    "external https URL, or a file uploaded straight "
                    "into this platform (POST /v1/company/logo) — "
                    "sniffed by content, dimension-checked, and "
                    "adapted to a suitable format where that can be "
                    "done losslessly."),
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
        "logo_upload_en": {
            "what": ("POST /v1/company/logo with {filename, "
                     "content_b64} — accepts PNG, JPEG, GIF, WEBP, BMP "
                     "and SVG, detected from the file's own bytes, "
                     "never from the filename."),
            "limits": {"max_bytes": MAX_LOGO_BYTES,
                       "min_px": MIN_LOGO_PX, "max_px": MAX_LOGO_PX,
                       "max_aspect_ratio": MAX_LOGO_ASPECT},
            "adapts": "24-bit uncompressed BMP is converted to PNG.",
            "refuses_by_name": ["heic/heif", "tiff", "pdf", "ico",
                                "psd"],
        },
        "cannot_en": ("Landvex stores the profile and sends it on the "
                      "mission body. How quiXzoom renders the pin, "
                      "caches the logo or truncates the text is "
                      "quiXzoom's. An uploaded logo is only advertised "
                      "as fetchable (logo_url on the mission body) when "
                      "LANDVEX_PUBLIC_BASE_URL is configured — this "
                      "platform never claims a reachability it cannot "
                      "back."),
    }


# ── Logotyp-uppladdning: sniffning, mått, dom, anpassning ──────────────
MAX_LOGO_BYTES = 500_000        # base64 ≈ 667 kB, ryms i MAX_BODY_BYTES
MIN_LOGO_PX = 32                 # mindre än så går inte att läsa
MAX_LOGO_PX = 4096                # större än så är inte en logotyp
MAX_LOGO_ASPECT = 4.0             # längsta:kortaste sidan — mer är ett baner

_CONTENT_TYPES = {
    "png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif",
    "webp": "image/webp", "bmp": "image/bmp", "svg": "image/svg+xml",
}

_NAMED_REFUSALS = {
    "heic": ("this is a HEIC/HEIF file (the iPhone camera default) — "
             "it isn't a web image format. Export or convert it to PNG "
             "or JPEG on the phone first (Share → Options → 'Most "
             "Compatible' on iOS), then upload that."),
    "tiff": ("this is a TIFF file — not a web image format. Export it "
             "as PNG or JPEG first."),
    "pdf": ("this is a PDF, not an image — export the logo artwork as "
            "PNG or SVG from whatever made the PDF, then upload that."),
    "ico": ("this is a Windows .ico icon file — upload the PNG or SVG "
            "the icon was made from instead."),
    "psd": ("this is a Photoshop .psd file — export a flattened PNG or "
            "JPEG from it first; this platform doesn't read layered "
            "editor formats."),
}


def _sniff(content: bytes) -> str:
    """Formatet ur de FAKTISKA byten — aldrig ur ett filnamn."""
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content[:2] == b"BM":
        return "bmp"
    if content[:4] == b"\x00\x00\x01\x00":
        return "ico"
    if content[:4] == b"8BPS":
        return "psd"
    if content[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if content[:5] == b"%PDF-":
        return "pdf"
    if content[4:8] == b"ftyp" and content[8:12] in (
            b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevm",
            b"hevs", b"mif1", b"msf1"):
        return "heic"
    kort = content.lstrip(b"\xef\xbb\xbf \t\r\n")[:512]
    if kort.startswith(b"<?xml") or kort.startswith(b"<svg") \
            or b"<svg" in kort[:200]:
        return "svg"
    return "unknown"


def _dims_png(b: bytes) -> tuple[int, int]:
    return (int.from_bytes(b[16:20], "big"),
            int.from_bytes(b[20:24], "big"))


def _dims_jpeg(b: bytes) -> tuple[int, int]:
    i, n = 2, len(b)
    while i + 4 <= n:
        if b[i] != 0xFF:
            i += 1
            continue
        marker = b[i + 1]
        if marker == 0xD8:
            i += 2
            continue
        if marker == 0xD9:
            break
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            i += 2
            continue
        seglen = int.from_bytes(b[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 9 > n:
                break
            return (int.from_bytes(b[i + 7:i + 9], "big"),
                    int.from_bytes(b[i + 5:i + 7], "big"))
        i += 2 + seglen
    raise ProfileRefused(
        "no JPEG SOF marker found — the file is truncated or corrupt")


def _dims_gif(b: bytes) -> tuple[int, int]:
    return (int.from_bytes(b[6:8], "little"),
            int.from_bytes(b[8:10], "little"))


def _dims_bmp(b: bytes) -> tuple[int, int]:
    w = int.from_bytes(b[18:22], "little", signed=True)
    h = int.from_bytes(b[22:26], "little", signed=True)
    return abs(w), abs(h)


def _dims_webp(b: bytes) -> tuple[int, int]:
    fourcc = b[12:16]
    if fourcc == b"VP8X":
        if len(b) < 30:
            raise ProfileRefused("WEBP (VP8X) header is truncated")
        return (int.from_bytes(b[24:27], "little") + 1,
                int.from_bytes(b[27:30], "little") + 1)
    if fourcc == b"VP8L":
        if len(b) < 25 or b[20] != 0x2F:
            raise ProfileRefused("WEBP (VP8L) signature is wrong")
        bits = int.from_bytes(b[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if fourcc == b"VP8 ":
        if len(b) < 30 or b[23:26] != b"\x9d\x01\x2a":
            raise ProfileRefused("WEBP (VP8 lossy) start code is wrong")
        return (int.from_bytes(b[26:28], "little") & 0x3FFF,
                int.from_bytes(b[28:30], "little") & 0x3FFF)
    raise ProfileRefused(f"unrecognized WEBP sub-format {fourcc!r}")


_DIM_PARSERS = {"png": _dims_png, "jpeg": _dims_jpeg, "gif": _dims_gif,
                "bmp": _dims_bmp, "webp": _dims_webp}


def _bmp_to_png(content: bytes) -> bytes:
    """Den enda faktiska formatanpassningen: 24-bitars okomprimerad BMP
    → PNG, pixel-exakt, med zlib (stdlib) som enda packare. Andra BMP-
    varianter (palett, komprimering, andra bitdjup) vägras med namn i
    stället för att gissas fel."""
    if len(content) < 54:
        raise ProfileRefused("BMP file is too short to be valid")
    dib_size = int.from_bytes(content[14:18], "little")
    if dib_size < 40:
        raise ProfileRefused(
            "this BMP uses a header variant this platform doesn't "
            "convert — save as a plain 24-bit uncompressed BMP, or "
            "upload PNG/JPEG/GIF/WEBP directly")
    width = int.from_bytes(content[18:22], "little", signed=True)
    height_raw = int.from_bytes(content[22:26], "little", signed=True)
    bpp = int.from_bytes(content[28:30], "little")
    compression = int.from_bytes(content[30:34], "little")
    pixel_offset = int.from_bytes(content[10:14], "little")
    if bpp != 24 or compression != 0:
        raise ProfileRefused(
            f"this BMP is {bpp}-bit with compression mode "
            f"{compression} — only plain 24-bit uncompressed BMP is "
            f"converted; save it that way, or upload PNG/JPEG/GIF/WEBP "
            f"directly")
    top_down = height_raw < 0
    height = abs(height_raw)
    if width <= 0 or height <= 0:
        raise ProfileRefused("BMP declares a non-positive width or height")
    row_size = ((width * 24 + 31) // 32) * 4
    if len(content) < pixel_offset + row_size * height:
        raise ProfileRefused(
            "BMP pixel data is shorter than its own header promises — "
            "the file is truncated or corrupt")
    rows = []
    for r in range(height):
        src_row = r if top_down else (height - 1 - r)
        start = pixel_offset + src_row * row_size
        row = content[start:start + width * 3]
        rgb = bytearray(len(row))
        rgb[0::3] = row[2::3]
        rgb[1::3] = row[1::3]
        rgb[2::3] = row[0::3]
        rows.append(b"\x00" + bytes(rgb))
    compressed = zlib.compress(b"".join(rows), 9)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data)))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", compressed) + _chunk(b"IEND", b""))


# SVG: tillåtelselista, inte städning. Ett element eller attribut som
# inte känns igen som ofarligt VÄGRAR hela filen — samma doktrin som
# resten av plattformen: aldrig tyst ändra eller strippa något och låtsas
# att det gick bra.
_SVG_TAG_ALLOW = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "defs", "lineargradient", "radialgradient", "stop",
    "clippath", "mask", "symbol", "use", "title", "desc", "metadata",
    "text", "tspan",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _sanitize_svg(content: bytes) -> None:
    # xml.etree has no XXE/entity-expansion protection of its own (no
    # defusedxml here — Rent stdlib holds for this platform too). A
    # DOCTYPE is what a billion-laughs or external-entity attack NEEDS
    # to define its entities, so refusing one outright — before the
    # parser ever sees it — closes that class without a dependency.
    lower = content.lower()
    if b"<!doctype" in lower or b"<!entity" in lower:
        raise ProfileRefused(
            "SVG contains a DOCTYPE or ENTITY declaration — that's an "
            "XML attack vector (external entity expansion), not a "
            "styling feature. Re-export without it.")
    try:
        root = ET.fromstring(content)  # noqa: S314 — DOCTYPE/ENTITY refused above
    except ET.ParseError as e:
        raise ProfileRefused(
            f"not well-formed SVG/XML ({e}) — the file is corrupt or "
            f"not really an SVG") from None
    if _local(root.tag) != "svg":
        raise ProfileRefused("the root element isn't <svg> — not an SVG file")
    for el in root.iter():
        tag = _local(el.tag)
        if tag not in _SVG_TAG_ALLOW:
            raise ProfileRefused(
                f"SVG contains a <{tag}> element outside the allowed "
                f"set (shapes, groups, gradients) — this platform "
                f"refuses rather than silently strips content it "
                f"doesn't trust; re-export without it")
        for attr, val in el.attrib.items():
            aloc = _local(attr)
            lower = val.strip().lower()
            if aloc.startswith("on"):
                raise ProfileRefused(
                    f"SVG has an event-handler attribute ({attr}) — "
                    f"that runs code, and logos don't need to")
            if "javascript:" in lower or "expression(" in lower:
                raise ProfileRefused(
                    f"SVG attribute {attr} contains a script trigger "
                    f"({val!r}), not styling")
            if aloc == "href" and not val.startswith("#"):
                raise ProfileRefused(
                    f"SVG references an external resource ({val!r}) "
                    f"via {attr} — only internal references (#id) are "
                    f"allowed")
            if "url(" in lower:
                idx = lower.find("url(")
                slut = lower.find(")", idx)
                inre = val[idx + 4:slut].strip().strip("'\"") \
                    if slut != -1 else ""
                if not inre.startswith("#"):
                    raise ProfileRefused(
                        f"SVG attribute {attr} references an external "
                        f"resource via url(...) ({inre!r}) — only "
                        f"internal references (url(#id)) are allowed")


def validate_logo(filename: str, content: bytes) -> dict:
    """Sniffa, mät och döm en uppladdad fil — eller vägra den, med skäl.

    Returnerar {format, content_type, width, height, content, bytes,
    sha256, adapted_from} för den lagringsklara filen. `content` är
    ALLTID den fil som ska lagras — original, eller den anpassade PNG:n
    om BMP konverterades.
    """
    if not content:
        raise ProfileRefused("the upload is empty — no bytes arrived")
    if len(content) > MAX_LOGO_BYTES:
        raise ProfileRefused(
            f"the file is {len(content):,} bytes, over the "
            f"{MAX_LOGO_BYTES:,}-byte limit for a logo — compress it "
            f"or shrink the resolution and try again")
    fmt = _sniff(content)
    if fmt in _NAMED_REFUSALS:
        raise ProfileRefused(_NAMED_REFUSALS[fmt])
    if fmt == "unknown":
        raise ProfileRefused(
            f"{filename or 'the file'!r} isn't a recognized image "
            f"format — its own bytes match none of PNG, JPEG, GIF, "
            f"BMP, WEBP or SVG (checked by content, never by file "
            f"extension)")
    if fmt == "svg":
        _sanitize_svg(content)
        return {"format": "svg", "content_type": _CONTENT_TYPES["svg"],
                "width": None, "height": None, "content": content,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "adapted_from": ""}
    try:
        width, height = _DIM_PARSERS[fmt](content)
    except (struct.error, IndexError) as e:
        raise ProfileRefused(
            f"the file sniffs as {fmt.upper()} but its dimensions "
            f"can't be read ({e}) — it's truncated or corrupt") from None
    if width < MIN_LOGO_PX or height < MIN_LOGO_PX:
        raise ProfileRefused(
            f"{width}x{height}px is too small to read as a logo — "
            f"minimum is {MIN_LOGO_PX}x{MIN_LOGO_PX}px")
    if width > MAX_LOGO_PX or height > MAX_LOGO_PX:
        raise ProfileRefused(
            f"{width}x{height}px is larger than a logo needs — "
            f"maximum is {MAX_LOGO_PX}x{MAX_LOGO_PX}px, shrink it first")
    lang, kort = max(width, height), min(width, height)
    if kort == 0 or (lang / kort) > MAX_LOGO_ASPECT:
        raise ProfileRefused(
            f"{width}x{height}px is a banner shape, not a logo shape "
            f"(over {MAX_LOGO_ASPECT:.0f}:1) — crop it closer to square")
    if fmt == "bmp":
        stored = _bmp_to_png(content)
        return {"format": "png", "content_type": _CONTENT_TYPES["png"],
                "width": width, "height": height, "content": stored,
                "bytes": len(stored),
                "sha256": hashlib.sha256(stored).hexdigest(),
                "adapted_from": "bmp"}
    return {"format": fmt, "content_type": _CONTENT_TYPES[fmt],
            "width": width, "height": height, "content": content,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "adapted_from": ""}


def save_logo(tenant: str, filename: str, content_b64: str) -> dict:
    """Ta emot, döm och lagra — base64 är den enda vägen in, för båda
    API-lagren pratar bara JSON."""
    if not tenant:
        raise ProfileRefused("a logo upload needs a tenant")
    if not content_b64:
        raise ProfileRefused("no file content received")
    try:
        raw = base64.b64decode(content_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ProfileRefused(
            f"the upload isn't valid base64 ({e})") from None
    dom = validate_logo(filename, raw)
    rad = {
        "tenant": tenant,
        "filename": (filename or "logo").strip()[:200],
        "format": dom["format"], "content_type": dom["content_type"],
        "width": dom["width"], "height": dom["height"],
        "bytes": dom["bytes"], "sha256": dom["sha256"],
        "adapted_from": dom["adapted_from"],
        "content_b64": base64.b64encode(dom["content"]).decode("ascii"),
        "uploaded_at": _time.time(),
    }
    _save_logo_rec(rad)
    return {k: v for k, v in rad.items() if k != "content_b64"}


def get_logo(tenant: str) -> dict | None:
    """Metadata om den lagrade loggan — aldrig byten själva (se
    get_logo_bytes för det, ett separat och medvetet val: /v1/company
    ska inte svälla till megabyte varje gång någon läser profilen)."""
    rad = _logo_record(tenant)
    if rad is None:
        return None
    return {k: v for k, v in rad.items() if k != "content_b64"}


def get_logo_bytes(tenant: str) -> tuple[bytes, str] | None:
    """De faktiska byten + content-type, för /v1/company/logo/raw."""
    rad = _logo_record(tenant)
    if rad is None:
        return None
    return base64.b64decode(rad["content_b64"]), rad["content_type"]


def delete_logo(tenant: str) -> bool:
    if _STORE is not None and getattr(_STORE, "delete_company_logo", None):
        return _STORE.delete_company_logo(tenant)
    return _LOGOR.pop(tenant, None) is not None


# ── Lagret (samma mönster som connections) ─────────────────────────────
_STORE = None
_PROFILER: dict[str, dict] = {}
_LOGOR: dict[str, dict] = {}


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


def _save_logo_rec(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_company_logo", None):
        return _STORE.save_company_logo(rec)
    _LOGOR[rec["tenant"]] = dict(rec)
    return rec["tenant"]


def _logo_record(tenant: str) -> dict | None:
    if _STORE is not None and getattr(_STORE, "get_company_logo", None):
        return _STORE.get_company_logo(tenant)
    return _LOGOR.get(tenant)


def reset() -> None:
    """Endast för tester."""
    _PROFILER.clear()
    _LOGOR.clear()
