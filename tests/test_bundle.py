"""Tre ytor i en fil, utan att deras CSS slår ihjäl varandra.

Konsolen, ingången och rundturen är skrivna var för sig och sätter alla
regler på `body`, `*`, `h1` och `p`. Vävs de ihop rakt av vinner det sist
inlästa stilblocket, och två av de tre går sönder på ett sätt som inte
syns förrän någon klickar.

`scripts/htmlscope.py` skriver om varje regel till att gälla inuti en
container. Testerna här håller fast vid de tre omskrivningar som är
lätta att göra fel, och som alla tre gör sidan trasig på olika sätt:

  * `body`-regler måste bli containerns, annars försvinner sidans
    typografi.
  * `:root[data-theme="dark"]` måste behålla sin plats som FÖRFADER,
    eftersom temat sätts på dokumentets rotelement. Skrivs den om till
    containern slutar mörkt läge fungera.
  * `@keyframes` innehåller inte selektorer och får inte röras.

Kör: python3 -m tests.test_bundle
"""
from __future__ import annotations

from scripts.htmlscope import scope, strip_title


def _css(html: str) -> str:
    import re
    return "".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))


def test_body_rules_become_the_container():
    """Annars ärver ytan värddokumentets typografi och ser fel ut."""
    ut = _css(scope("<style>body{font:16px serif;max-width:880px}</style>",
                    "yta"))
    assert "#yta{font:16px serif;max-width:880px}" in ut
    assert "body{" not in ut


def test_the_theme_override_keeps_its_place_as_an_ancestor():
    """Temat sätts på dokumentets rotelement. Skrivs regeln om till
    containern slutar mörkt läge gälla — och felet syns bara för den som
    råkar ha mörkt tema påslaget."""
    ut = _css(scope('<style>:root[data-theme="dark"]{--bg:#000}</style>',
                    "yta"))
    assert ':root[data-theme="dark"] #yta{--bg:#000}' in ut


def test_bare_root_becomes_the_container_so_variables_are_inherited():
    ut = _css(scope("<style>:root{--blue:#007AFF}</style>", "yta"))
    assert "#yta{--blue:#007AFF}" in ut


def test_ordinary_selectors_are_confined():
    ut = _css(scope("<style>.door{gap:1px}h2,p{margin:0}</style>", "yta"))
    assert "#yta .door{gap:1px}" in ut
    assert "#yta h2,#yta p{margin:0}" in ut


def test_the_universal_selector_does_not_escape():
    ut = _css(scope("<style>*{box-sizing:border-box}</style>", "yta"))
    assert "#yta *{box-sizing:border-box}" in ut
    assert not ut.count("}*{")


def test_media_queries_are_rewritten_inside():
    ut = _css(scope("<style>@media (max-width:560px){h1{font-size:1rem}}"
                    "</style>", "yta"))
    assert "@media (max-width:560px){#yta h1{font-size:1rem}}" in ut


def test_keyframes_are_left_alone():
    """De innehåller inte selektorer. Prefixas `from`/`to` slutar
    animationen fungera utan att något felmeddelande syns."""
    ut = _css(scope("<style>@keyframes in{from{opacity:0}to{opacity:1}}"
                    "</style>", "yta"))
    assert "@keyframes in{from{opacity:0}to{opacity:1}}" in ut
    assert "#yta from" not in ut


def test_a_reset_comes_first_so_the_host_does_not_leak_in():
    """Värddokumentet stylar `p`, `h2` och `svg`. Utan återställning ärver
    den inbäddade ytan dem, och en yta som ser rätt ut ensam ser fel ut
    inbäddad."""
    ut = _css(scope("<style>.a{color:red}</style>", "yta"))
    assert ut.index("all:revert") < ut.index(".a{color:red}")


def test_the_title_is_dropped_because_the_host_owns_it():
    assert "<title>" not in strip_title("<title>X</title><p>hej</p>")


# ── Vävningen ───────────────────────────────────────────────────────────
def test_the_weave_puts_the_tabs_in_the_existing_bar():
    """Konsolen har redan en flikrad och en MODE-växling. Att bygga en
    andra navigering bredvid hade gett två sätt att byta vy."""
    from scripts.bundle_demo import vav
    konsol = "<html><body><nav id='tabs'></nav><div class='layout'></div></body></html>"
    ut = vav(konsol, [("ytaIngang", "<p>a</p>"), ("ytaBevis", "<p>b</p>")])
    assert ut.count('data-mode="ingang"') == 1
    assert ut.count('data-mode="bevis"') == 1
    assert ut.index('data-mode="ingang"') < ut.index("</nav>")


def test_the_weave_refuses_a_document_it_cannot_place_things_in():
    """Hellre ett tydligt fel än en fil som ser byggd ut och saknar
    hälften."""
    from scripts.bundle_demo import vav
    for trasig in ("<html><body></body></html>", "<nav id='tabs'></nav>"):
        try:
            vav(trasig, [("a", "x")])
        except SystemExit:
            continue
        raise AssertionError(f"vävde in i ett dokument utan fäste: {trasig}")


def test_the_switch_stops_the_console_handler_for_its_own_modes():
    """Konsolens hanterare slår upp LAGEN[MODE], som saknar poster för de
    två nya lägena. Fångas klicket inte i capture-fasen kraschar den."""
    from scripts.bundle_demo import _VAXLARE
    assert "true);" in _VAXLARE, "lyssnaren måste ligga i capture-fasen"
    assert "stopPropagation" in _VAXLARE
    assert "EGNA[mode]" in _VAXLARE, "bara de egna lägena får stoppas"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
