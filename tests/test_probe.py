"""Ett spärrat nät är inte en trasig adapter.

Skillnaden är hela poängen med en probe, och den är lätt att tappa: den
som kör probeningen ser bara ett kryss, drar slutsatsen "adaptern är
trasig" och letar efter felet i koden i stället för i nätverkspolicyn.

Den här filen håller fast vid tre saker som gick fel i praktiken:

  1. `register_probe` skrev "unreachable, path wrong, or the response
     shape differs" — tre möjligheter i en mening. Utfallet gick inte att
     tolka, varken för en människa eller för sammanställningen, och
     `RegisterProvider.fetch` kastade dessutom bort felet så att svaret
     inte fanns kvar någonstans.
  2. Sammanställningen läste ordet "unreachable" ur just den brasklappen
     och kallade det ett verdikt — en gissning som såg ut som ett
     mätvärde.
  3. `livability_probe` avslutar med 0 utan att prova något. Räknat som
     "svarade" hade det blivit en avbockad verifiering som aldrig skett.

Kör: python3 -m tests.test_probe
"""
from __future__ import annotations

import socket
import urllib.error


# ── unreachable() ───────────────────────────────────────────────────────
def test_unreachable_has_exactly_one_implementation():
    """Två kopior av samma regel glider isär — samma skäl som att
    `percentile` bor på ett ställe."""
    import pathlib
    rot = pathlib.Path(__file__).resolve().parent.parent
    definitioner = []
    for f in list((rot / "scripts").glob("*.py")) + \
            list((rot / "engine").rglob("*.py")):
        if "def unreachable(" in f.read_text(encoding="utf-8"):
            definitioner.append(str(f.relative_to(rot)))
    assert definitioner == ["engine/datasources/faults.py"], definitioner


def test_a_server_that_answered_is_not_unreachable():
    """404 är ett riktigt svar: värden finns, sökvägen gör det inte.
    Att kalla det 'onåbar' hade dolt ett verkligt adapterfel."""
    from engine.datasources.faults import unreachable
    svarade = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    assert not unreachable(svarade)
    for kod in (403, 407, 502, 503, 504):
        nekad = urllib.error.HTTPError("u", kod, "no", {}, None)
        assert unreachable(nekad), kod


def test_a_blocked_tunnel_is_unreachable():
    """Exakt det fel den här miljön ger: proxyn nekar CONNECT."""
    from engine.datasources.faults import unreachable
    assert unreachable(urllib.error.URLError(
        "Tunnel connection failed: 403 Forbidden"))
    assert unreachable(socket.timeout("timed out"))
    assert unreachable(ConnectionRefusedError(111, "refused"))
    assert not unreachable(None)
    assert not unreachable(ValueError("svaret saknade fältet count"))


# ── Providern måste BEHÅLLA felet ───────────────────────────────────────
def test_the_register_provider_keeps_the_error_it_swallowed():
    """Utan det finns svaret inte kvar att läsa, och proben kan bara
    räkna upp vad som KAN ha hänt."""
    from engine.datasources.register_apis import RegisterProvider

    def faller(url, payload, timeout):
        raise urllib.error.URLError("Tunnel connection failed: 403")

    p = RegisterProvider(transport=faller)
    assert p.fetch("https://example/x") is None
    assert isinstance(p.last_error, urllib.error.URLError)

    def svarar(url, payload, timeout):
        return b"{}"

    q = RegisterProvider(transport=svarar)
    q.last_error = urllib.error.URLError("gammalt")
    assert q.fetch("https://example/x") == b"{}"
    assert q.last_error is None, "ett gammalt fel får inte ligga kvar"


def test_our_own_bugs_still_propagate_through_the_provider():
    """En strömbrytare som sväljer AttributeError döljer vår egen kod."""
    from engine.datasources.register_apis import RegisterProvider

    def buggig(url, payload, timeout):
        raise AttributeError("stavfel i parsern")

    p = RegisterProvider(transport=buggig)
    try:
        p.fetch("https://example/x")
    except AttributeError:
        return
    raise AssertionError("vår egen bugg svaldes")


# ── Sammanställningens verdikt ──────────────────────────────────────────
def test_a_disclaimer_is_not_a_verdict():
    """Att plocka ordet 'unreachable' ur en mening som räknar upp tre
    möjligheter är att låta en gissning se ut som ett mätvärde."""
    from scripts.probe_all import bedom
    brasklapp = ("✗ no count returned — endpoint unreachable, path wrong, "
                 "or the response shape differs. Nothing was invented.")
    verdikt, skal = bedom(1, brasklapp, rich_codes=True)
    assert verdikt == "unclear", (verdikt, skal)
    assert "säger det själv" in skal


def test_exit_zero_without_probing_anything_is_not_an_answer():
    """livability_probe gör exakt detta. Räknat som 'answered' hade det
    blivit en avbockad verifiering som aldrig skett."""
    from scripts.probe_all import bedom
    verdikt, _ = bedom(0, "Kolada: LANDVEX_KOLADA_URL not set — nothing "
                          "to probe.\n(dry run)", rich_codes=False)
    assert verdikt in ("not_configured", "nothing_probed"), verdikt
    assert bedom(0, "✓ 412 establishments (2023) — SCB",
                 rich_codes=True)[0] == "answered"


def test_a_blocked_call_is_never_reported_as_an_adapter_defect():
    from scripts.probe_all import bedom
    for text in ("Tunnel connection failed: 403 Forbidden",
                 "URLError: Name or service not known",
                 "·· never got there: ConnectionRefusedError"):
        verdikt, _ = bedom(1, text, rich_codes=False)
        assert verdikt == "blocked", (text, verdikt)
    assert bedom(3, "", rich_codes=True)[0] == "blocked"


def test_our_own_crash_outranks_everything_else():
    """En traceback i en probe är vårt fel och får inte försvinna bland
    fjorton rader 'not configured'."""
    from scripts.probe_all import bedom
    verdikt, skal = bedom(1, "Traceback (most recent call last):\n"
                             "AttributeError: 'NoneType' has no 'get'",
                          rich_codes=True)
    assert verdikt == "our_bug"
    assert "AttributeError" in skal


def test_a_bad_argument_is_our_mistake_not_the_adapters():
    from scripts.probe_all import bedom
    verdikt, _ = bedom(1, "✗ no industry code mapped for this trade/country",
                       rich_codes=True)
    assert verdikt == "bad_args"


def test_nothing_is_ticked_off_unless_something_answered():
    """Kärnregeln: verified_live sätts bara för en källa som svarat."""
    from scripts.probe_all import rapport
    r = rapport([
        {"id": "a", "group": "sensor", "classes": ["SmhiWeather"],
         "cmd": "x", "exit": 3, "verdict": "blocked", "why": "", "tail": ""},
        {"id": "b", "group": "sensor", "classes": ["OpenAqAir"],
         "cmd": "y", "exit": 0, "verdict": "not_configured", "why": "",
         "tail": ""}])
    assert r["set_verified_live"] == []
    r2 = rapport([{"id": "c", "group": "sensor", "classes": ["SmhiWeather"],
                   "cmd": "z", "exit": 0, "verdict": "answered", "why": "",
                   "tail": ""}])
    assert [x["class"] for x in r2["set_verified_live"]] == ["SmhiWeather"]
    assert "sensor_apis.py:" in r2["set_verified_live"][0]["at"], \
        "raden att ändra ska pekas ut med file:line"


def test_each_client_can_be_verified_on_its_own():
    """Fältet satt bara på basklassen, så en enda ändrad rad hade bockat
    av alla tio klienterna samtidigt. En bock som inte går att sätta för
    en källa i taget betyder ingenting."""
    from engine.datasources.sensor_apis import PROVIDERS
    klasser = {c for grupp in PROVIDERS.values() for c in grupp}
    saknar = sorted(c.__name__ for c in klasser
                    if "verified_live" not in vars(c))
    assert not saknar, f"ärver verified_live från basklassen: {saknar}"
    for c in klasser:
        assert c.verified_live is False, (
            f"{c.__name__} är markerad verifierad — den bocken får bara "
            f"sättas efter en probe som svarat")


def test_every_probe_in_the_sweep_exists():
    """En probe som inte finns blir en rad som alltid ser trasig ut."""
    import pathlib
    from scripts.probe_all import _prober
    rot = pathlib.Path(__file__).resolve().parent.parent
    for p in _prober():
        modul = p["argv"][0].replace(".", "/") + ".py"
        assert (rot / modul).exists(), modul


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
