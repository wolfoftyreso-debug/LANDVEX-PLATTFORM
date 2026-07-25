"""Tester för känslig-attribut-grinden. Kör: python3 -m tests.test_sensitive"""
from __future__ import annotations

from engine import sensitive as S


def test_refuses_small_groups_kanon():
    g = S.guard("origin", group_sizes=[8, 200], confounders=["income"],
                sources=["BRA", "SCB"])
    assert g["allowed"] is False
    assert any("k-anonymity" in r for r in g["reasons"])


def test_refuses_without_confounders():
    g = S.guard("origin", group_sizes=[100, 200], confounders=[],
                sources=["BRA", "SCB"])
    assert g["allowed"] is False
    assert any("confounders" in r for r in g["reasons"])


def test_refuses_without_official_sources():
    g = S.guard("victim_status", group_sizes=[100], confounders=["age"],
                sources=["blog"])
    assert g["allowed"] is False
    assert any("sources" in r for r in g["reasons"])


def test_allowed_with_all_safeguards():
    g = S.guard("origin", group_sizes=[100, 200], confounders=["income", "age"],
                sources=["BRA", "SCB"])
    assert g["allowed"] is True and g["reasons"] == []


def test_association_shows_raw_vs_controlled_and_refuses_when_blocked():
    # blockerad: liten grupp
    blocked = S.sensitive_association(
        [1, 2, 3], [1, 2, 3], [1, 2, 3], category="origin",
        group_sizes=[3], sources=["SCB", "BRA"], confounders=["income"])
    assert blocked["status"] == "refused"

    # tillåten: sambandet förklaras av confounder c → försvinner efter kontroll
    c = list(range(1, 13))
    n1 = [0.1, -0.1] * 6
    n2 = [0.1, 0.1, -0.1, -0.1] * 3
    a = [c[i] + n1[i] for i in range(12)]
    b = [c[i] + n2[i] for i in range(12)]
    res = S.sensitive_association(
        a, b, c, category="origin", group_sizes=[120, 300],
        sources=["SCB", "BRA"], confounders=["income"],
        label_a="foreign_born_share", label_b="reported_rate", label_c="income")
    assert res["status"] == "shown_with_safeguards"
    assert res["raw_association"] > 0.9
    assert res["survives_controls"] is False        # förklaras av inkomst
    assert "largely disappears" in res["reading"]
    assert any("Ecological fallacy" in w for w in res["warnings"])


def test_sign_reversal_is_flagged():
    # Simpsons paradox: rått positivt, men negativt inom varje kontrollnivå.
    a = [1, 2, 3, 10, 11, 12]
    b = [2, 1, 0, 12, 11, 10]      # rått uppåt, men nedåt i varje grupp
    c = [1, 1, 1, 10, 10, 10]      # confounder skiljer grupperna
    res = S.sensitive_association(
        a, b, c, category="origin", group_sizes=[100, 100],
        sources=["SCB", "BRA"], confounders=["group"])
    assert res["sign_reversal"] is True and res["survives_controls"] is False
    assert "REVERSES" in res["reading"] and "Simpson" in res["reading"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
