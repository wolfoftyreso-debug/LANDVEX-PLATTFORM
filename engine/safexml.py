"""XML från en källa vi inte styr över.

Plattformen tar emot XML/RSS på två ställen: AAMOS Core svarar ibland med
RSS i ett `contents`-fält, och programfeeden kan vara en ren RSS-kanal.
Båda parsades med `xml.etree.ElementTree.fromstring` rakt av.

Två saker mättes upp på Python 3.11 innan den här modulen skrevs:

  * Externa entiteter (XXE, `file:///etc/passwd`) AVVISAS redan av
    stdlib. Den vägen var alltså aldrig öppen.
  * Interna entiteter EXPANDERAS. 347 byte in gav 1 000 000 tecken ut —
    en förstärkning på 2881 gånger med sex nivåer. Nio nivåer ger en
    gigabyte. En komprometterad eller bara illvillig feed kunde alltså
    ta minnet i processen med några hundra byte.

`defusedxml` löser det här, men plattformens kärna är beroendefri med
flit. Samma skydd får plikta med två stdlib-regler:

  1. Ett tak på indata. En feed som är större än taket är inte en feed.
  2. Ingen DOCTYPE. Entiteter kan bara DEFINIERAS i en DTD, så utan
     DOCTYPE finns det ingenting att expandera. Det är samma regel som
     defusedxml kallar `forbid_dtd`, och den kostar inget för riktig
     RSS — ingen legitim feed behöver en intern DTD.

Rent stdlib.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

# En RSS-kanal på över 8 MiB är inte en RSS-kanal.
MAX_XML_BYTES = 8 << 20

# <!DOCTYPE ...  — även med inledande blanktecken/kommentarer före.
_DOCTYPE = re.compile(r"<!DOCTYPE", re.IGNORECASE)


class UnsafeXml(ValueError):
    """Indata avvisad innan parsning, inte efter."""


def parse(text: str, *, max_bytes: int = MAX_XML_BYTES) -> ET.Element:
    """Tolka XML från en opålitlig källa. UnsafeXml om den vägrar.

    Kastar ET.ParseError precis som fromstring för trasig XML — den
    här funktionen ändrar bara VAD som släpps fram till parsern.
    """
    if len(text.encode("utf-8", "replace")) > max_bytes:
        raise UnsafeXml(f"XML document exceeds {max_bytes} bytes and was "
                        f"not parsed.")
    if _DOCTYPE.search(text):
        raise UnsafeXml("XML document declares a DOCTYPE. Entity "
                        "definitions are refused: a small document can "
                        "expand to gigabytes, and no legitimate feed "
                        "needs an internal DTD.")
    return ET.fromstring(text)   # noqa: S314 – DTD:n är redan avvisad ovan
