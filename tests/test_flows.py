"""Tester för kostnad/nytta-lagret (förväntat värde, grindat).
Kör: python3 -m tests.test_flows"""
from __future__ import annotations

from engine import flows as F


def test_insufficient_basis_when_sources_thin():
    out = F.expected_value(
        [{"label": "cost", "amount": 100}],
        [{"label": "gain", "amount": 300, "probability": 0.5}])
    assert out["status"] == "insufficient_basis"
    assert out["n_sources"] == 0 and out["needed"] == F.MIN_SOURCES
    assert "framing" in out


def test_expected_value_and_bcr():
    out = F.expected_value(
        [{"label": "protection", "amount": 100, "source": "budget"}],
        [{"label": "trade upside", "amount": 400, "probability": 0.5,
          "source": "customs"}],
        decision="fund the protection?")
    assert out["status"] == "assessed"
    assert out["total_cost"] == 100
    assert out["expected_benefit"] == 200          # 400 * 0.5
    assert out["net_expected_value"] == 100
    assert out["benefit_cost_ratio"] == 2.0
    assert out["leans"] == "favorable"
    assert out["framing"]["choices"]["not_advice"] is True


def test_break_even_probability():
    out = F.expected_value(
        [{"label": "c", "amount": 100, "source": "a"}],
        [{"label": "g", "amount": 200, "probability": 0.9, "source": "b"}])
    # p* = cost/gross = 100/200 = 0.5
    assert out["break_even_probability"] == 0.5
    # upside too small to ever cover cost
    out2 = F.expected_value(
        [{"label": "c", "amount": 500, "source": "a"}],
        [{"label": "g", "amount": 200, "probability": 1.0, "source": "b"}])
    assert out2["break_even_probability"] > 1
    assert "even at certainty" in out2["break_even_note"]


def test_data_coverage_counts_sourced_items():
    out = F.expected_value(
        [{"label": "c", "amount": 100, "source": "a"}],
        [{"label": "g1", "amount": 100, "probability": 1.0, "source": "b"},
         {"label": "g2", "amount": 50, "probability": 1.0}])  # no source
    assert out["basis"]["sourced_items"] == 2 and out["basis"]["items"] == 3
    assert out["basis"]["data_coverage"] == round(2 / 3, 4)


def test_sensitivity_ranks_the_decisive_driver():
    out = F.expected_value(
        [{"label": "small cost", "amount": 10, "source": "a"}],
        [{"label": "big bet", "amount": 1000, "probability": 0.9, "source": "b"},
         {"label": "tiny", "amount": 5, "probability": 1.0, "source": "b"}])
    assert out["sensitivity"]["most_decisive"] == "big bet"
    shares = [d["share_of_swing"] for d in out["sensitivity"]["drivers"]]
    assert shares == sorted(shares, reverse=True)


def test_zero_cost_bcr_is_none_not_crash():
    out = F.expected_value(
        [{"label": "free", "amount": 0, "source": "a"}],
        [{"label": "g", "amount": 100, "probability": 1.0, "source": "b"}])
    assert out["benefit_cost_ratio"] is None
    assert out["net_expected_value"] == 100


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
