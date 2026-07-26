"""Tester för parameterhärkomsten – plattformens egna siffror granskade.
Kör: python3 -m tests.test_provenance"""
from __future__ import annotations

from engine import provenance as P


def test_every_parameter_declares_class_basis_and_effect():
    for name, p in P.PARAMETERS.items():
        assert p["class"] in P.CLASSES, name
        assert p["basis_en"] and len(p["basis_en"]) > 30, name
        assert p["affects_en"], name
        assert "value" in p, name


def test_every_gate_that_silences_the_system_is_registered():
    """Trösklarna som avgör OM systemet får uttala sig måste stå med."""
    must = {"sensitive.MIN_CELL", "scenario.MIN_SOURCES", "scenario.MIN_R2",
            "scenario.MIN_HISTORY", "saturation.MIN_PEERS",
            "merit.MIN_COVERAGE", "outcomes.MIN_SAMPLE",
            "corrections.MIN_SUBMITTERS", "flows.MIN_SOURCES"}
    assert must <= set(P.PARAMETERS)


def test_registered_values_match_the_code():
    """Registret får inte glida ifrån verkligheten."""
    from engine import (corrections, flows, merit, outcomes, saturation,
                        scenario, sensitive)
    live = {
        "sensitive.MIN_CELL": sensitive.MIN_CELL,
        "sensitive.MIN_SOURCES": sensitive.MIN_SOURCES,
        "scenario.MIN_SOURCES": scenario.MIN_SOURCES,
        "scenario.MIN_HISTORY": scenario.MIN_HISTORY,
        "scenario.MIN_R2": scenario.MIN_R2,
        "saturation.MIN_PEERS": saturation.MIN_PEERS,
        "merit.MIN_PEERS": merit.MIN_PEERS,
        "merit.MIN_COVERAGE": merit.MIN_COVERAGE,
        "outcomes.MIN_SAMPLE": outcomes.MIN_SAMPLE,
        "corrections.MIN_SUBMITTERS": corrections.MIN_SUBMITTERS,
        "corrections.MAX_CV": corrections.MAX_CV,
        "flows.MIN_SOURCES": flows.MIN_SOURCES,
    }
    for name, actual in live.items():
        assert P.PARAMETERS[name]["value"] == actual, (
            f"{name}: registret säger {P.PARAMETERS[name]['value']}, "
            f"koden säger {actual}")


def test_the_honest_headline_is_not_flattering():
    s = P.summary()
    assert s["total"] == len(P.PARAMETERS)
    assert sum(s["by_class"].values()) == s["total"]
    # Merparten ÄR omdömen, och det ska stå i klartext.
    assert s["by_class"]["assumed"] > s["by_class"]["sourced"]
    assert "judgement calls" in s["headline_en"]
    assert str(s["by_class"]["assumed"]) in s["headline_en"]


def test_sourced_means_a_named_authority():
    for p in P.parameters("sourced"):
        b = p["basis_en"]
        assert any(k in b for k in ("Maastricht", "OECD", "EU", "standard")), \
            p["parameter"]


def test_nothing_claims_to_be_calibrated_yet():
    """Ingen tröskel är härledd ur utfallsdata ännu – påstå inte det."""
    assert P.parameters("calibrated") == []


def test_unknown_class_is_rejected():
    try:
        P.parameters("vibes")
        raise AssertionError("okänd klass tilläts")
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
