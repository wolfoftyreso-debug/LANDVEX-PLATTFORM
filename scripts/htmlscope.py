"""Gör en fristående sidas CSS ofarlig inuti ett annat dokument.

Konsolen, ingången och rundturen är skrivna var för sig och sätter alla
regler på `body`, `*`, `h1`, `h2` och `p`. Slås deras stilblock ihop rakt
av vinner det sist inlästa, och två av de tre ytorna går sönder på ett
sätt som inte syns förrän någon klickar.

Den här modulen skriver om ett stilblock så att varje regel bara gäller
inuti en angiven container:

    body { … }                    →  #ingang { … }
    *    { … }                    →  #ingang * { … }
    .door{ … }                    →  #ingang .door { … }
    :root{ --blue:#007AFF }       →  #ingang { --blue:#007AFF }
    :root[data-theme="dark"]{ … } →  :root[data-theme="dark"] #ingang { … }

`:root`-varianterna behåller sin plats som förfader, eftersom temat sätts
på dokumentets rotelement och en omskrivning till `#ingang` hade brutit
mörkt läge.

Dessutom läggs en `all: revert` först i blocket. Utan den ärver ytan
värddokumentets regler för `p`, `h2` och `svg` — som existerar i
konsolen — och en yta som ser rätt ut ensam ser fel ut inbäddad. Regeln
ligger först så att den egna, mer specifika CSS:en vinner över den.

`@media`, `@supports` och `@container` bearbetas rekursivt.
`@keyframes` och `@font-face` lämnas orörda: deras innehåll är inte
selektorer.

Rent stdlib.
"""
from __future__ import annotations

import re

_ORORDA = ("@keyframes", "@-webkit-keyframes", "@font-face", "@import",
           "@charset", "@namespace", "@property", "@counter-style")
_REKURSIVA = ("@media", "@supports", "@container", "@layer", "@scope")


def _selektor(sel: str, container: str) -> str:
    """En selektor, begränsad till containern."""
    sel = sel.strip()
    if not sel:
        return sel
    if sel.startswith(":root"):
        rest = sel[len(":root"):].strip()
        # :root ensamt → containern själv (så att variabler ärvs).
        # :root[data-theme="dark"] → behåll som förfader.
        return container if not rest else f"{sel} {container}"
    if sel in ("body", "html", "html body"):
        return container
    if sel.startswith(("body ", "html ", "body.", "body[", "body>")):
        rest = sel.split(" ", 1)[1] if " " in sel else ""
        return f"{container} {rest}".strip() or container
    if sel == "*":
        return f"{container} *"
    return f"{container} {sel}"


def _block(css: str, container: str) -> str:
    """Skriv om alla regler i ett CSS-block."""
    ut, i, n = [], 0, len(css)
    while i < n:
        # Kommentarer och blanktecken passerar orörda.
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            j = n if j < 0 else j + 2
            ut.append(css[i:j])
            i = j
            continue
        if css[i].isspace():
            ut.append(css[i])
            i += 1
            continue

        start = i
        djup = 0
        while i < n:
            if css[i] == "{":
                djup += 1
                break
            i += 1
        if i >= n:
            ut.append(css[start:])
            break
        prelud = css[start:i].strip()
        # Hitta matchande klammer.
        j, d = i, 0
        while j < n:
            if css[j] == "{":
                d += 1
            elif css[j] == "}":
                d -= 1
                if d == 0:
                    break
            j += 1
        kropp = css[i + 1:j]

        if prelud.startswith(_ORORDA):
            ut.append(f"{prelud}{{{kropp}}}")
        elif prelud.startswith(_REKURSIVA):
            ut.append(f"{prelud}{{{_block(kropp, container)}}}")
        else:
            nya = ",".join(_selektor(s, container)
                           for s in prelud.split(","))
            ut.append(f"{nya}{{{kropp}}}")
        i = j + 1
    return "".join(ut)


def scope(html: str, container: str) -> str:
    """Skriv om varje <style>-block i `html` till att gälla i containern.

    `container` anges utan brädgård: `scope(sida, "ingang")`.
    """
    val = f"#{container}"
    aterstall = (f"{val} *,{val}::before,{val}::after{{all:revert}}"
                 f"{val}{{all:revert;display:block}}")

    def ersatt(m: re.Match) -> str:
        return (f"<style>{aterstall}"
                f"{_block(m.group(1), val)}</style>")

    return re.sub(r"<style[^>]*>(.*?)</style>", ersatt, html, flags=re.S)


def strip_title(html: str) -> str:
    """Ta bort <title> — värddokumentet äger sin egen."""
    return re.sub(r"<title[^>]*>.*?</title>\s*", "", html, flags=re.S)
