"""XML från en källa vi inte styr över.

Mätt på Python 3.11 innan engine/safexml.py skrevs:

    externa entiteter (XXE)   avvisas redan av stdlib
    interna entiteter         EXPANDERAS: 347 byte in → 1 000 000 tecken
                              ut, en förstärkning på 2881 gånger med sex
                              nivåer. Nio nivåer ger en gigabyte.

Plattformen tar emot XML på två ställen — AAMOS Core svarar ibland med
RSS, och programfeeden kan vara en RSS-kanal — och båda parsade rakt av.

Kör: python3 -m tests.test_safexml
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from engine.safexml import MAX_XML_BYTES, UnsafeXml, parse


def _bomb(levels: int = 6) -> str:
    ents = ['<!ENTITY a0 "AAAAAAAAAA">']
    ents += [f'<!ENTITY a{i} "' + f"&a{i - 1};" * 10 + '">'
             for i in range(1, levels)]
    return ('<?xml version="1.0"?><!DOCTYPE b [' + "".join(ents)
            + f']><b>&a{levels - 1};</b>')


def test_the_bomb_really_does_expand_in_plain_stdlib():
    """Utan skyddet är hotet verkligt — testet vilar inte på en teori."""
    raw = _bomb()
    root = ET.fromstring(raw)          # noqa: S314 – detta ÄR poängen
    grown = len(root.text or "")
    assert grown > 100 * len(raw), (
        f"{len(raw)} byte blev {grown} tecken — om detta inte längre "
        f"expanderar har stdlib ändrats och skyddet kan omprövas")


def test_a_document_that_declares_a_doctype_is_refused():
    try:
        parse(_bomb())
    except UnsafeXml as e:
        assert "DOCTYPE" in str(e)
    else:
        raise AssertionError("entitetsbomben tolkades")


def test_the_refusal_is_not_case_sensitive():
    for form in ("<!doctype x []><x/>", "<!DocType x []><x/>"):
        try:
            parse(form)
        except UnsafeXml:
            pass
        else:
            raise AssertionError(f"DOCTYPE släpptes igenom: {form}")


def test_a_document_over_the_ceiling_is_not_parsed_at_all():
    try:
        parse("<r>" + "x" * 5000 + "</r>", max_bytes=1024)
    except UnsafeXml as e:
        assert "exceeds" in str(e)
    else:
        raise AssertionError("för stort dokument tolkades")
    assert MAX_XML_BYTES >= 1 << 20      # riktiga feeds ska rymmas


def test_real_rss_still_parses():
    """Skyddet får inte kosta det legitima fallet."""
    root = parse("<rss version='2.0'><channel><title>Programs</title>"
                 "<item><title>Elektriker</title></item></channel></rss>")
    assert root.tag == "rss"
    assert root.find("./channel/title").text == "Programs"


def test_broken_xml_still_raises_a_parse_error_not_a_refusal():
    """UnsafeXml betyder 'vägrad', ParseError betyder 'trasig'. Två olika
    saker som inte får glida ihop."""
    try:
        parse("<r><unclosed></r>")
    except ET.ParseError:
        pass
    except UnsafeXml as e:
        raise AssertionError("trasig XML rapporterades som osäker") from e


def test_both_entry_points_go_through_the_guard():
    """Regeln får inte gälla bara det ställe någon råkade testa."""
    import inspect

    from engine.datasources import programs
    from integrations import aamos
    for mod in (aamos, programs):
        src = inspect.getsource(mod)
        assert "safexml" in src, f"{mod.__name__} parsar XML förbi skyddet"
        assert "ET.fromstring" not in src, \
            f"{mod.__name__} anropar fortfarande ET.fromstring direkt"


def test_the_aamos_decoder_returns_raw_instead_of_expanding():
    from integrations.aamos import _decode_body
    out = _decode_body(_bomb())
    assert set(out) == {"raw"}, out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
