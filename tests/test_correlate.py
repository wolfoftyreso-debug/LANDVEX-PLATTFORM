"""Tester för tvärdomän-korrelation. Kör: python3 -m tests.test_correlate"""
from __future__ import annotations

from engine import correlate as C


def test_confidence_tiers():
    assert C.confidence_tier(0.9, 5) == "insufficient"     # för lite data
    assert C.confidence_tier(0.1, 12) == "not_significant"  # svagt
    assert C.confidence_tier(0.9, 40) == "high"


def test_cross_domain_reports_association_never_causation():
    a = list(range(20)); b = [x * 2 + 1 for x in a]
    res = C.cross_domain(a, b, label_a="sugar", label_b="disease")
    assert res["pearson"] == 1.0 and res["direction"] == "positive"
    assert "NOT causation" in res["caveat"]
    assert "one framing" in res["framing"]["note"]


def test_spurious_warning_on_small_n():
    a = [1, 2, 3, 4, 5]; b = [1, 2.1, 2.9, 4.2, 5.1]   # |r|>0.8, n<20
    assert C.cross_domain(a, b)["spurious_warning"] is True


def test_partial_correlation_kills_confounder():
    # a och b drivs båda av c, med OBEROENDE brus (n1 ⟂ n2) → naivt r_ab högt,
    # men partial ~0 när c hålls konstant.
    c = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    n1 = [0.1, -0.1] * 6                 # period 2
    n2 = [0.1, 0.1, -0.1, -0.1] * 3      # period 4 → okorrelerad med n1
    a = [c[i] + n1[i] for i in range(12)]
    b = [c[i] + n2[i] for i in range(12)]
    res = C.partial_correlation(a, b, c, label_c="income")
    assert res["pearson"] > 0.9
    assert abs(res["partial"]) < 0.5           # sambandet kollapsar
    assert res["confounder_suspected"] is True
    assert "income" in res["interpretation"]


def test_partial_correlation_persists_when_independent():
    # a–b samband som INTE förklaras av c (c oberoende).
    a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    b = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    c = [5, 1, 4, 1, 5, 9, 2, 6, 5, 3]
    res = C.partial_correlation(a, b, c)
    assert abs(res["partial"]) > 0.8 and res["confounder_suspected"] is False


def test_cross_market_replication():
    # samma positiva samband i 3 av 4 marknader.
    pos_a = list(range(15)); pos_b = [x * 1.5 for x in pos_a]
    flat_a = list(range(15)); flat_b = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9]
    ds = [{"market": m, "a": pos_a, "b": pos_b} for m in ("us", "se", "de")]
    ds.append({"market": "noise", "a": flat_a, "b": flat_b})
    res = C.cross_market(ds, label_a="uspp", label_b="chronic")
    assert res["n_markets"] == 4 and res["n_significant"] >= 3
    assert res["replication"]["dominant_direction"] == "positive"
    assert "Replicates" in res["verdict"]
    assert "not establish cause" in res["framing"]["choices"]["note"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
