"""Tester för löneregistret. Kör: python3 -m tests.test_wages"""
from __future__ import annotations

from engine import wages as W


def test_catalog_covers_occupations():
    cat = W.wage_catalog()
    codes = {c["code"] for c in cat}
    assert "elektriker" in codes and len(cat) >= 20
    assert all(c["se_monthly_sek"] > 0 for c in cat)


def test_wage_se_anchor():
    w = W.wage("elektriker", "se")
    assert w["currency"] == "SEK" and w["monthly_wage"] == 38000
    assert w["source"] == "schablon" and "NOT real local wages" in w["caveat"]


def test_wage_fx_converted_and_labelled():
    us = W.wage("elektriker", "us")
    assert us["currency"] == "USD" and 0 < us["monthly_wage"] < 38000
    assert us["framing"]["choices"]["ppp_adjusted"] is False


def test_unknown_inputs_raise():
    for bad in (lambda: W.wage("nope", "se"), lambda: W.wage("elektriker", "zz")):
        try:
            bad(); assert False
        except ValueError:
            pass


def test_compare_sorts_by_usd_with_ppp_caveat():
    r = W.compare("sjukskoterska", ["se", "us", "de"])
    usd = [m["monthly_usd"] for m in r["markets"]]
    assert usd == sorted(usd, reverse=True)
    assert "PPP" in r["note"] and r["framing"]["choices"]["ppp_adjusted"] is False


def test_compensation_context_changes_real_position():
    us_mech = W.compensation_context("bilmechanic", "us")
    assert any(f["factor"] == "tools_self_provided" for f in us_mech["factors"])
    assert us_mech["net_real_vs_nominal"] == "lower"
    cn_fac = W.compensation_context("factory worker", "cn")
    assert any(f["factor"] == "housing_included" for f in cn_fac["factors"])
    assert cn_fac["net_real_vs_nominal"] == "higher"
    do_wait = W.compensation_context("waitress", "do")
    assert {f["factor"] for f in do_wait["factors"]} == {"pays_to_work", "tips_commission"}
    assert "not real compensation" in do_wait["caveat"]


def test_compensation_context_none_on_record():
    assert W.compensation_context("astronaut", "se")["net_real_vs_nominal"] == "no context on record"


def test_labor_intensity_axis():
    # Thailand-restaurang: mest väntan → låg intensitet.
    th = W.compensation_context("waiter", "th")
    assert th["labor_intensity"] == "low" and th["intensity_notes"]
    # USA-kedja: producera varje minut → hög intensitet.
    us = W.compensation_context("waiter", "us")
    assert us["labor_intensity"] == "high"
    assert "wage-per-effort" in th["caveat"]


def test_rank_by_wage():
    r = W.rank_by_wage("se")
    wages = [o["monthly_wage"] for o in r["occupations"]]
    assert wages == sorted(wages, reverse=True)
    assert r["occupations"][0]["percentile"] >= r["occupations"][-1]["percentile"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
