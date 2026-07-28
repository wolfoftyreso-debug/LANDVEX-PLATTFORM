"""Indexet måste vägra oftare än det betygsätter.

Det finns exakt ett sätt att göra ett landsindex av det här slaget
skadligt: räkna det på underlag vi inte har. Ett land med svag
statistikmyndighet får då låg alignment för att VI inte kan se, och talet
läses som ett omdöme om deras press.

Sviten prövar därför spärrarna före allt annat.

Kör: python3 -m tests.test_mrai
"""
from __future__ import annotations

import json

from engine import mrai as M


def test_a_market_we_cannot_see_gets_no_value_rather_than_a_low_one():
    """Den viktigaste regeln i modulen."""
    r = M.mrai("us")
    assert r["status"] == "insufficient"
    assert r["index"] is None
    assert "OUR blindness" in r["refusal_en"]
    assert r["gate"]["required"] == M.MIN_REFERENCE_COVERAGE
    # och den säger vad som skulle åtgärda det
    assert r["how_to_fix_en"] and "/v1/coverage" in r["how_to_fix_en"]


def test_the_gate_scores_nothing_itself():
    """Referenstäckningen är ett besked om OSS, inte ett betyg på landet.
    Den får därför vikt noll."""
    grind = {c["id"]: c for c in M.COMPONENTS}["reference_coverage"]
    assert grind["weight"] == 0.0
    assert "statement about US" in grind["cannot_en"]


def test_an_index_built_on_a_quarter_of_itself_is_not_published():
    """Ett tal ur en fjärdedel av vikten ser likadant ut som ett ur hela,
    och läsaren kan inte se skillnaden utan att öppna det."""
    r = M.mrai("se", limit=4)
    if r["of_weight"] < M.MIN_WEIGHT_COMPUTED:
        assert r["index"] is None
        assert "quarter of itself" in r["refusal_en"] or \
            "below the" in r["refusal_en"]
        # komponenterna visas ändå — vägran är inte tystnad
        assert len(r["components"]) == len(M.COMPONENTS)


def test_every_component_can_be_opened():
    """Ett index som inte går att öppna är ett omdöme med en siffra på."""
    r = M.mrai("se", limit=4)
    for c in r["components"]:
        assert c["what_en"] and c["cannot_en"], c["id"]
        assert "basis" in c
        assert c["status"] in ("computed", "refused")
        if c["status"] == "refused":
            assert c["refusal_en"], c["id"]
            assert c["value"] is None


def test_a_refused_component_is_named_not_averaged_away():
    """Ett index som tyst viktar om när en komponent saknas döljer hur
    mycket av det som faktiskt finns."""
    r = M.mrai("se", limit=4)
    saknade = set(r["refused_components"])
    raknade = {c["id"] for c in r["components"]
               if c["status"] == "computed" and c["weight"]}
    assert not (saknade & raknade)
    assert r["of_weight"] == round(
        sum(c["weight"] for c in r["components"]
            if c["status"] == "computed"), 2)


def test_no_reporting_harvested_is_an_absence_of_input_not_a_finding():
    from engine import news as N

    N.reset()
    varde, _basis, vagran = M._independent_verification("se")
    assert varde is None
    assert "absence of INPUT" in vagran
    assert "not a finding about the press" in vagran


def test_a_contradiction_index_built_only_on_mock_scores_nothing():
    varde, _b, vagran = M._public_data_alignment("us", 4)
    assert varde is None
    assert "simulated" in vagran and "says nothing about this country" in vagran


def test_the_comparison_keeps_the_unscorable_in_the_list():
    """En ranking som tyst tappar det den inte kan mäta ser fullständig
    ut och är det inte."""
    j = M.compare(["se", "us", "de"], limit=4)
    assert j["count"] == 3
    namngivna = {r["market"] for r in j["ranked"]} | \
        {r["market"] for r in j["insufficient"]}
    assert namngivna == {"se", "us", "de"}
    for r in j["insufficient"]:
        assert r["refusal_en"]
    assert "looks complete and is not" in j["summary_en"]


def test_it_says_out_loud_that_it_is_not_a_press_freedom_ranking():
    for text in (M.catalog()["cannot_en"], M.mrai("us")["cannot_en"]):
        assert "cannot rank press freedom" in text
        assert "cannot tell those apart" in text


def test_the_weights_are_data_and_say_they_are_a_heuristic():
    assert "documented heuristic" in M.catalog()["weights_en"]
    assert abs(sum(c["weight"] for c in M.COMPONENTS) - 1.0) < 1e-9
    assert json.dumps(M.catalog())


def test_an_unknown_market_is_refused():
    try:
        M.mrai("atlantis")
    except ValueError as e:
        assert "atlantis" in str(e)
    else:
        raise AssertionError("okänd marknad tilläts")


def test_the_index_is_reachable_without_buying_anything():
    """Ett index som bara betalande kan öppna är ett omdöme med en
    siffra på."""
    from api.licensing import required_capability

    assert required_capability("/v1/mrai") == "core"
    assert required_capability("/v1/mrai/compare") == "core"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
