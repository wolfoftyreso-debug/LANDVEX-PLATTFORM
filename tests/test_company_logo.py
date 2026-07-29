"""Logotyp-uppladdning: sniffning på INNEHÅLLET, dom, och anpassning.

Bevakar: format avgörs av byten (aldrig filnamnet), namngivna vägranden
för kända-men-inte-stödda format, kvalitetsgrindarna (storlek, min/max-
upplösning, sidförhållande) med gränsvärdena provade exakt, BMP→PNG-
konverteringen är pixel-exakt, SVG-saneringen vägrar (aldrig städar
tyst) farligt innehåll inklusive DOCTYPE/ENTITY, och lagringsvarvet
(save/get/get_bytes/delete) samt varumärkesblockets
LANDVEX_PUBLIC_BASE_URL-grind.

Kör: python3 -m tests.test_company_logo
"""
from __future__ import annotations

import base64
import os
import struct
import zlib

from engine import company as CO


# ── Handgjorda minimala giltiga filer per format ────────────────────────
def _png(w: int, h: int, rgb=(255, 0, 0)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data)))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(rgb) * w
    idat = zlib.compress(row * h, 9)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def _jpeg(w: int, h: int) -> bytes:
    soi = b"\xff\xd8"
    app0 = (b"\xff\xe0" + struct.pack(">H", 16) +
            b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    sof0_data = (struct.pack(">BHHB", 8, h, w, 1) +
                 struct.pack(">BBB", 1, 0x11, 0))
    sof0 = b"\xff\xc0" + struct.pack(">H", len(sof0_data) + 2) + sof0_data
    return soi + app0 + sof0 + b"\xff\xd9"


def _gif(w: int, h: int) -> bytes:
    return b"GIF89a" + struct.pack("<HH", w, h) + b"\x00\x00\x00"


def _bmp24(w: int, h: int, *, bpp: int = 24, compression: int = 0,
           rgb=(255, 0, 0)) -> bytes:
    row_size = ((w * bpp + 31) // 32) * 4
    b, g, r = rgb[2], rgb[1], rgb[0]
    row = bytes([b, g, r]) * w if bpp == 24 else bytes(row_size)
    row = row[:row_size].ljust(row_size, b"\x00")
    pixel_data = row * h
    pixel_offset = 54
    header = b"BM" + struct.pack("<IHHI", pixel_offset + len(pixel_data),
                                 0, 0, pixel_offset)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, bpp, compression,
                      len(pixel_data), 2835, 2835, 0, 0)
    return header + dib + pixel_data


def _webp_vp8l(w: int, h: int) -> bytes:
    bits = ((w - 1) & 0x3FFF) | (((h - 1) & 0x3FFF) << 14)
    payload = b"VP8L" + struct.pack("<I", 5) + bytes([0x2F]) + \
        struct.pack("<I", bits)[:4]
    riff_len = 4 + len(payload)
    return b"RIFF" + struct.pack("<I", riff_len) + b"WEBP" + payload


def _svg(inner: str = '<circle cx="50" cy="50" r="40"/>',
        root_attrs: str = "") -> bytes:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 100 100"{root_attrs}>{inner}</svg>'
            ).encode("utf-8")


def _b64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


# ── Sniffning + mått: en per accepterat format ──────────────────────────
def test_each_accepted_format_is_sniffed_from_its_own_bytes():
    fall = {
        "png": (_png(64, 64), "logo.png"),
        "jpeg": (_jpeg(64, 48), "logo.jpg"),
        "gif": (_gif(80, 40), "logo.gif"),
        "webp": (_webp_vp8l(50, 50), "logo.webp"),
        "svg": (_svg(), "logo.svg"),
    }
    for vantat, (content, namn) in fall.items():
        dom = CO.validate_logo(namn, content)
        assert dom["format"] == vantat, (namn, dom)
        assert dom["content_type"] == CO._CONTENT_TYPES[vantat]


def test_format_is_never_taken_from_the_filename():
    """En PNG med .heic-ändelse ska ändå gå igenom som PNG — och en HEIC
    med .png-ändelse ska ändå vägras som HEIC. Filnamnet är metadata,
    inte en dom."""
    png_med_fel_andelse = CO.validate_logo("photo.heic", _png(64, 64))
    assert png_med_fel_andelse["format"] == "png"

    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 20
    try:
        CO.validate_logo("logo.png", heic)
    except CO.ProfileRefused as e:
        assert "HEIC" in str(e)
    else:
        raise AssertionError("HEIC med .png-ändelse gick igenom")


def test_named_refusals_for_recognized_but_unsupported_formats():
    fall = {
        "heic": b"\x00\x00\x00\x18ftypheic" + b"\x00" * 20,
        "tiff": b"II*\x00" + b"\x00" * 20,
        "pdf": b"%PDF-1.4\n" + b"\x00" * 20,
        "ico": b"\x00\x00\x01\x00" + b"\x00" * 20,
        "psd": b"8BPS" + b"\x00" * 20,
    }
    for slag, content in fall.items():
        try:
            CO.validate_logo(f"x.{slag}", content)
        except CO.ProfileRefused as e:
            assert slag in str(e).lower() or slag.upper() in str(e), \
                (slag, str(e))
        else:
            raise AssertionError(f"{slag} gick igenom oemotsagt")


def test_unrecognized_bytes_are_named_unknown_not_guessed_at():
    try:
        CO.validate_logo("mystery.bin", b"not an image at all, just text" * 5)
    except CO.ProfileRefused as e:
        assert "isn't a recognized image format" in str(e)
    else:
        raise AssertionError("okänt innehåll accepterades")


def test_empty_upload_is_refused():
    try:
        CO.validate_logo("empty.png", b"")
    except CO.ProfileRefused as e:
        assert "empty" in str(e)
    else:
        raise AssertionError("tom fil accepterades")


# ── Kvalitetsgrindar: gränsvärdena provade EXAKT ────────────────────────
def test_the_minimum_resolution_boundary_is_exact():
    """Precis under minimum vägras; precis på minimum går igenom. Ett
    naivt mutationstest (bara ta bort grinden) hade missat en off-by-
    one — det här tvingar exakt gränsen."""
    for_liten = CO.MIN_LOGO_PX - 1
    try:
        CO.validate_logo("x.png", _png(for_liten, for_liten))
    except CO.ProfileRefused as e:
        assert "too small" in str(e)
    else:
        raise AssertionError(f"{for_liten}px gick igenom under minimum")
    # Exakt på minimum: går igenom.
    dom = CO.validate_logo("x.png", _png(CO.MIN_LOGO_PX, CO.MIN_LOGO_PX))
    assert dom["width"] == CO.MIN_LOGO_PX


def test_the_maximum_resolution_boundary_is_exact():
    # Kvadratiskt (1:1) så sidförhållandegrinden aldrig kan störa den
    # här gränsen — bara storleksgränsen prövas.
    for_stor = CO.MAX_LOGO_PX + 1
    try:
        CO.validate_logo("x.png", _png(for_stor, for_stor))
    except CO.ProfileRefused as e:
        assert "larger than a logo needs" in str(e)
    else:
        raise AssertionError(f"{for_stor}px gick igenom över maximum")
    dom = CO.validate_logo("x.png", _png(CO.MAX_LOGO_PX, CO.MAX_LOGO_PX))
    assert dom["width"] == CO.MAX_LOGO_PX


def test_the_aspect_ratio_boundary_is_exact():
    kort = 100
    exakt = int(kort * CO.MAX_LOGO_ASPECT)          # exakt på gränsen: OK
    over = exakt + 1                                # en pixel över: vägras
    dom = CO.validate_logo("x.png", _png(exakt, kort))
    assert dom["width"] == exakt
    try:
        CO.validate_logo("x.png", _png(over, kort))
    except CO.ProfileRefused as e:
        assert "banner shape" in str(e)
    else:
        raise AssertionError(f"{over}x{kort} (över {CO.MAX_LOGO_ASPECT}:1) "
                             f"gick igenom")


def test_the_byte_size_boundary_is_exact():
    """Storleksgrinden prövas FÖRE formatsniffningen — så en godtycklig
    kropp med rätt PNG-signatur i fronten räcker för att tvinga exakt
    gränsen, oavsett om resten är en giltig bild."""
    over = b"\x89PNG\r\n\x1a\n" + b"\x00" * (CO.MAX_LOGO_BYTES + 1 - 8)
    assert len(over) == CO.MAX_LOGO_BYTES + 1
    try:
        CO.validate_logo("big.png", over)
    except CO.ProfileRefused as e:
        assert "over the" in str(e) and "byte limit" in str(e)
    else:
        raise AssertionError("fil över gränsen accepterades")


# ── BMP → PNG: den enda faktiska formatanpassningen ─────────────────────
def test_bmp_is_adapted_to_png_pixel_exact():
    bmp = _bmp24(40, 40, rgb=(255, 0, 0))
    dom = CO.validate_logo("logo.bmp", bmp)
    assert dom["format"] == "png"
    assert dom["adapted_from"] == "bmp"
    assert dom["content"][:8] == b"\x89PNG\r\n\x1a\n"
    w, h = CO._dims_png(dom["content"])
    assert (w, h) == (40, 40)
    # Färgen ska överleva BGR (BMP:s ordning) → RGB (PNG:s ordning).
    # Packa upp PNG:n för hand: en IDAT-ström, en filterbyte per rad.
    raw = zlib.decompress(_only_idat(dom["content"]))
    assert tuple(raw[1:4]) == (255, 0, 0), "röd överlevde inte BGR->RGB"


def test_bmp_with_compression_or_indexed_colour_is_named_refused_not_guessed():
    """Bara 24-bitars okomprimerad BMP konverteras — andra varianter
    vägras med namn i stället för att gissas fel."""
    indexerad = _bmp24(40, 40, bpp=8)
    try:
        CO.validate_logo("x.bmp", indexerad)
    except CO.ProfileRefused as e:
        assert "8-bit" in str(e)
    else:
        raise AssertionError("indexerad BMP konverterades ändå")

    komprimerad = _bmp24(40, 40, compression=1)
    try:
        CO.validate_logo("x.bmp", komprimerad)
    except CO.ProfileRefused as e:
        assert "compression mode 1" in str(e)
    else:
        raise AssertionError("komprimerad BMP konverterades ändå")


def _only_idat(png: bytes) -> bytes:
    i = 8
    out = b""
    while i < len(png):
        clen = int.from_bytes(png[i:i + 4], "big")
        ctag = png[i + 4:i + 8]
        cdata = png[i + 8:i + 8 + clen]
        i += 8 + clen + 4
        if ctag == b"IDAT":
            out += cdata
        if ctag == b"IEND":
            break
    return out


# ── SVG: tillåtelselista, aldrig tyst städning ──────────────────────────
def test_clean_svg_is_accepted():
    dom = CO.validate_logo("logo.svg", _svg())
    assert dom["format"] == "svg"
    assert dom["content"] == _svg()


def test_svg_with_a_disallowed_element_is_refused_by_name():
    for tag, inner in (
            ("script", "<script>alert(1)</script>"),
            ("foreignObject", '<foreignObject><div/></foreignObject>'),
            ("style", "<style>*{fill:red}</style>"),
            ("a", '<a href="https://evil.example"><rect width="1" '
                  'height="1"/></a>'),
            ("image", '<image href="https://evil.example/x.png"/>')):
        try:
            CO.validate_logo("evil.svg", _svg(inner=inner))
        except CO.ProfileRefused as e:
            assert tag.lower() in str(e).lower(), (tag, str(e))
        else:
            raise AssertionError(f"<{tag}> gick igenom osanerat")


def test_svg_event_handler_attributes_are_refused():
    evil = _svg(root_attrs=' onload="alert(1)"')
    try:
        CO.validate_logo("evil.svg", evil)
    except CO.ProfileRefused as e:
        assert "event-handler" in str(e)
    else:
        raise AssertionError("onload gick igenom")


def test_svg_external_references_are_refused_internal_ones_pass():
    intern = _svg(inner='<use xlink:href="#a"/>',
                  root_attrs=' xmlns:xlink="http://www.w3.org/1999/xlink"')
    CO.validate_logo("ok.svg", intern)  # ska INTE kasta

    extern = _svg(
        inner='<use xlink:href="https://evil.example/x.svg#y"/>',
        root_attrs=' xmlns:xlink="http://www.w3.org/1999/xlink"')
    try:
        CO.validate_logo("evil.svg", extern)
    except CO.ProfileRefused as e:
        assert "external resource" in str(e)
    else:
        raise AssertionError("extern href gick igenom")


def test_svg_external_url_reference_in_an_attribute_is_refused():
    intern = _svg(inner='<circle cx="1" cy="1" r="1" fill="url(#g)"/>')
    CO.validate_logo("ok.svg", intern)  # internt url(#id): OK

    extern = _svg(inner='<circle cx="1" cy="1" r="1" '
                        'fill="url(https://evil.example/x)"/>')
    try:
        CO.validate_logo("evil.svg", extern)
    except CO.ProfileRefused as e:
        assert "url(" in str(e)
    else:
        raise AssertionError("externt url() gick igenom")


def test_svg_doctype_and_entity_declarations_are_refused_xxe_style():
    xxe = (b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM '
           b'"file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg">'
           b'<text>&xxe;</text></svg>')
    try:
        CO.validate_logo("evil.svg", xxe)
    except CO.ProfileRefused as e:
        assert "DOCTYPE" in str(e) or "ENTITY" in str(e)
    else:
        raise AssertionError("DOCTYPE/ENTITY gick igenom")


def test_malformed_svg_xml_is_refused_not_crashed_on():
    try:
        CO.validate_logo("broken.svg", b"<svg><unclosed></svg>")
    except CO.ProfileRefused as e:
        assert "not well-formed" in str(e)
    else:
        raise AssertionError("trasig XML accepterades")


# ── Uppladdning end-to-end: base64, lagring, hämtning, radering ────────
def test_save_logo_refuses_invalid_base64_and_missing_content():
    CO.reset()
    try:
        try:
            CO.save_logo("t1", "x.png", "not valid base64!!!")
        except CO.ProfileRefused as e:
            assert "base64" in str(e)
        else:
            raise AssertionError("ogiltig base64 accepterades")
        try:
            CO.save_logo("t1", "x.png", "")
        except CO.ProfileRefused as e:
            assert "no file content" in str(e)
        else:
            raise AssertionError("tom kropp accepterades")
    finally:
        CO.reset()


def test_the_upload_round_trip_is_lossless_and_tenant_scoped():
    CO.reset()
    try:
        content = _png(64, 64, rgb=(10, 20, 30))
        rec = CO.save_logo("t1", "brand.png", _b64(content))
        assert rec["format"] == "png" and rec["width"] == 64
        assert "content_b64" not in rec, \
            "save_logo:s svar ska inte bära hela filen igen"

        meta = CO.get_logo("t1")
        assert meta == rec
        assert "content_b64" not in meta

        raw, content_type = CO.get_logo_bytes("t1")
        assert raw == content
        assert content_type == "image/png"

        # En annan tenant ser ingenting.
        assert CO.get_logo("t2") is None
        assert CO.get_logo_bytes("t2") is None

        assert CO.delete_logo("t1") is True
        assert CO.get_logo("t1") is None
        assert CO.delete_logo("t1") is False, "radera en andra gång: inget att ta bort"
    finally:
        CO.reset()


def test_uploading_again_replaces_not_accumulates():
    CO.reset()
    try:
        CO.save_logo("t1", "first.png", _b64(_png(64, 64)))
        CO.save_logo("t1", "second.png", _b64(_png(100, 100)))
        meta = CO.get_logo("t1")
        assert meta["filename"] == "second.png"
        assert meta["width"] == 100
    finally:
        CO.reset()


# ── brand_block: en uppladdad logga syns bara om plattformen kan nås ────
def test_brand_block_only_advertises_an_uploaded_logo_when_publicly_reachable():
    CO.reset()
    gammal = os.environ.pop("LANDVEX_PUBLIC_BASE_URL", None)
    try:
        profil = CO.profile("t1", name="Flaggservice AB")
        CO.save_logo("t1", "logo.png", _b64(_png(64, 64)))

        # Utan LANDVEX_PUBLIC_BASE_URL: ingen logo_url alls — plattformen
        # ska inte påstå en nåbarhet den inte kan hålla.
        block = CO.brand_block(profil)
        assert block["logo_url"] == ""

        os.environ["LANDVEX_PUBLIC_BASE_URL"] = "https://api.landvex.io"
        block2 = CO.brand_block(profil)
        assert block2["logo_url"] == (
            "https://api.landvex.io/v1/company/logo/raw?tenant=t1")
    finally:
        CO.reset()
        if gammal is None:
            os.environ.pop("LANDVEX_PUBLIC_BASE_URL", None)
        else:
            os.environ["LANDVEX_PUBLIC_BASE_URL"] = gammal


def test_brand_block_still_prefers_the_explicit_logo_url_when_no_upload_exists():
    CO.reset()
    gammal = os.environ.get("LANDVEX_PUBLIC_BASE_URL")
    os.environ["LANDVEX_PUBLIC_BASE_URL"] = "https://api.landvex.io"
    try:
        profil = CO.profile("t1", name="Flaggservice AB",
                            logo_url="https://cdn.flaggservice.se/l.png")
        block = CO.brand_block(profil)
        assert block["logo_url"] == "https://cdn.flaggservice.se/l.png"
    finally:
        CO.reset()
        if gammal is None:
            os.environ.pop("LANDVEX_PUBLIC_BASE_URL", None)
        else:
            os.environ["LANDVEX_PUBLIC_BASE_URL"] = gammal


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
