"""Tester för det trovärdighets-grindade scenariolagret.
Kör: python3 -m tests.test_scenario"""
from __future__ import annotations

from engine import scenario as S


def test_refuses_without_enough_sources():
    series = [1, 2, 3, 4, 5, 6, 7, 8]
    r = S.project(series, sources=["SCB"], horizon=3)   # 1 källa < 2
    assert r["status"] == "insufficient_basis"
    assert any("sources" in x for x in r["reasons"])


def test_refuses_without_history():
    r = S.project([1, 2], sources=["SCB", "Kolada"], horizon=3)
    assert r["status"] == "insufficient_basis"
    assert any("historical" in x for x in r["reasons"])


def test_refuses_without_systematic_tendency():
    noise = [5, 1, 6, 2, 5, 1, 6, 2]      # ingen signifikant trend
    r = S.project(noise, sources=["SCB", "Kolada"], horizon=3)
    assert r["status"] == "insufficient_basis"
    assert any("tendency" in x for x in r["reasons"])


def test_credible_basis_yields_scenario():
    series = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
    r = S.project(series, sources=["SCB", "Kolada", "Eurostat"], horizon=3,
                  metric="demand")
    assert r["status"] == "scenario"
    assert r["scenario"]["baseline"] > 28          # trenden fortsätter uppåt
    assert r["basis"]["n_sources"] == 3
    assert r["confidence"] in ("low", "medium", "high")
    assert "NOT a prediction" in r["caveat"]
    assert len(r["assumptions"]) >= 3


def test_band_widens_with_horizon():
    series = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
    r = S.project(series, sources=["SCB", "Kolada"], horizon=5)
    widths = [m["band_width"] for m in r["milestones"]]
    assert widths == sorted(widths)                 # 1<3<5<10 → allt bredare
    assert widths[-1] > widths[0]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
