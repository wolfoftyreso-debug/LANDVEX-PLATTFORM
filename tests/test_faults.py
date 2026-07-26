"""Vems fel var det — omvärldens eller vårt?

Bakgrund: `LivabilitySource` anropade `locator.nearest()` på en klass som
bara har `locate()`. AttributeError fångades av samma `except Exception`
som finns för nätverksfel, källan pausades, och Resolvern föll tyst
tillbaka på mock. Kopplingen SÅG ansluten ut och levererade påhitt.

Testerna nedan låser fast att ett fel i VÅR kod aldrig får se ut som att
omvärlden är nere.

Kör: python3 -m tests.test_faults
"""
from __future__ import annotations

from engine.datasources import adapters
from engine.datasources.faults import OUR_BUGS, is_our_bug, source_fault
from engine.models import Location

_LOC = Location(lat=59.3, lon=18.1)


def test_the_classification_is_narrow_on_purpose():
    """Bara fel som en server omöjligt kan orsaka räknas som våra."""
    # Listan ska förbli smal. Växer den in på omvärldens sida börjar en
    # trasig payload fälla anropet i stället för att pausa källan.
    assert set(OUR_BUGS) == {AttributeError, NameError, ImportError,
                             SyntaxError, IndentationError}

    for exc in (AttributeError("no attr"), NameError("x"),
                ImportError("mod")):
        assert is_our_bug(exc), exc

    # Allt som en trasig server eller konstig payload KAN ge stannar på
    # omvärldens sida — annars blir en dålig payload ett 500-fel.
    for exc in (OSError("connection refused"), TimeoutError(),
                ValueError("bad literal"), KeyError("missing"),
                TypeError("float(None)")):
        assert not is_our_bug(exc), exc


def test_source_fault_swallows_the_world_and_reraises_us():
    with source_fault() as f:
        raise OSError("connection reset by peer")
    assert f.failed and isinstance(f.error, OSError)

    try:
        with source_fault():
            raise AttributeError("locator has no attribute 'nearest'")
    except AttributeError:
        pass
    else:
        raise AssertionError("vårt eget fel svaldes")


class _NetworkDown:
    """Beter sig som en klient vars motpart är nere."""
    connected = True
    base_url = "http://example.invalid"

    def fetch_permits(self, lat, lon):
        raise OSError("connection refused")


class _TypoInOurCode:
    """Beter sig som VÅR kod med ett felstavat attributnamn."""
    connected = True
    base_url = "http://example.invalid"

    def fetch_permits(self, lat, lon):
        raise AttributeError("'PermitsClient' object has no attribute "
                             "'nearest'")


def test_a_source_that_is_down_degrades_honestly():
    s = adapters.PermitsSource(client=_NetworkDown())
    values, extras = s.fetch(_LOC, "frisor", ["building_permits"])
    assert values == {} and extras == {}          # mock tar över, ärligt


def test_a_typo_in_our_code_is_not_reported_as_a_source_being_down():
    """Kärnan: det som en gång blev tyst mock ska nu braka."""
    s = adapters.PermitsSource(client=_TypoInOurCode())
    try:
        s.fetch(_LOC, "frisor", ["building_permits"])
    except AttributeError as e:
        assert "nearest" in str(e)
    else:
        raise AssertionError(
            "En AttributeError i vår egen kod svaldes och blev 'källan är "
            "nere'. Det är exakt den bugg som gjorde att LivabilitySource "
            "såg ansluten ut medan den levererade mock.")


def test_every_adapter_with_a_pause_carries_the_guard():
    """Regeln får inte gälla bara den källa någon råkade testa."""
    import inspect
    src = inspect.getsource(adapters)
    pauses = src.count("self._down_until = self._clock() + self._retry_after_s")
    guards = src.count("except OUR_BUGS:")
    assert guards >= pauses, (
        f"{pauses} källor pausar vid fel men bara {guards} skiljer på vårt "
        f"fel och omvärldens")


def test_every_source_module_classifies_the_fault_before_degrading():
    """Strukturregel som ingen linter kan uttrycka.

    Varje `except Exception` i datakällslagret måste föregås av
    `except OUR_BUGS: raise`. Annars är nästa tysta nedgradering redan
    inskriven — det räcker att någon lägger till en källa och kopierar
    mönstret från grannen.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    unguarded = []
    for path in sorted(list((root / "engine" / "datasources").glob("*.py"))
                       + [root / "engine" / "registers.py",
                          root / "integrations" / "aamos.py"]):
        if path.name == "faults.py":
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            m = re.match(r"^(\s*)except Exception(\s+as\s+\w+)?:", line)
            if not m:
                continue
            # Sök bakåt till try:t på samma indrag — vakten får ligga var
            # som helst bland det blockets except-satser, oavsett hur många
            # kommentarrader som skiljer dem åt.
            indent = m.group(1)
            guarded = False
            for back in range(i - 1, -1, -1):
                prev = lines[back]
                if prev.strip() and not prev.startswith(indent):
                    break                       # ute ur blocket
                if prev == f"{indent}except OUR_BUGS:":
                    guarded = True
                    break
                if prev == f"{indent}try:":
                    break
            if not guarded:
                unguarded.append(f"{path.relative_to(root)}:{i + 1}")
    assert not unguarded, (
        "Dessa ställen sväljer allt, inklusive våra egna buggar, och "
        "rapporterar det som att källan är nere:\n  "
        + "\n  ".join(unguarded))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
