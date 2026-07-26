"""Tester för Daily Brief – proaktiv upptäckt utan påhitt.
Kör: python3 -m tests.test_brief"""
from __future__ import annotations

from engine import brief as B


def _snap(**kw):
    base = {"relevance_level": "L3", "change_percent": 340.0,
            "data_availability": "verified", "confidence": 0.8,
            "source_count": 3, "affected_population_percent": 4,
            "consecutive_months": 4, "cross_domain_links": 2,
            "is_breaking_pattern": True}
    base.update(kw)
    return base


def _rep(kind="land_use_change", areas=("se", "se-14"), **kw):
    return B.report(
        kind, title=kw.get("title", "Unusual number of new yards"),
        summary_en="Surface use changed at 12 parcels in the period.",
        areas=list(areas), evidence=[{"source": "satellite", "measured": True},
                                     {"source": "permit register",
                                      "measured": False}],
        confidence_inputs=kw.get("ci", {"source_count": 3,
                                        "sources_measured": 2,
                                        "corroboration": 0.7,
                                        "history_points": 8,
                                        "resolution": 0.8}),
        snapshot=kw.get("snap", _snap()),
        discrepancy_en="No corresponding permit found in the register.",
        options=kw.get("options", ["watch", "verify_desk", "ask_authority"]),
        observed_at="2026-07-26")


def test_every_detection_declares_what_it_does_not_establish():
    """Kärnregeln: en observation är aldrig en juridisk slutsats."""
    for kind, spec in B.DETECTION_KINDS.items():
        assert spec["observation_en"] and spec["never_en"], kind
        assert len(spec["never_en"]) > 30, kind
    # ingen detektionstyp får heta något som redan är en anklagelse
    for kind in B.DETECTION_KINDS:
        assert "illegal" not in kind and "unlawful" not in kind


def test_a_report_carries_the_discrepancy_not_a_verdict():
    r = _rep()
    assert r["observation_en"] and r["does_not_establish_en"]
    assert "No corresponding permit" in r["discrepancy_en"]
    assert r["framing"]["choices"]["not_a_legal_finding"] is True
    blob = (r["observation_en"] + r["does_not_establish_en"]).lower()
    assert "unlawful" in blob or "unpermitted" in blob   # nämns som DET SOM EJ VISAS


def test_confidence_is_a_band_with_its_parts_never_a_fake_percentage():
    c = B.confidence({"source_count": 3, "sources_measured": 3,
                      "corroboration": 1.0, "history_points": 10,
                      "resolution": 1.0})
    assert c["band"] == "high" and c["score_0_1"] <= 1.0
    assert set(c["components"]) == {"sources", "sources_measured",
                                    "corroboration", "history", "resolution"}
    assert "not a calibrated probability" in c["not_a_probability_en"]
    assert "94%" in c["not_a_probability_en"]      # namnger fällan
    thin = B.confidence({"source_count": 1, "sources_measured": 0})
    assert thin["band"] in ("low", "very_low")
    # en källa som inte är ansluten drar ned konfidensen
    assert thin["components"]["sources_measured"] == 0.0


def test_options_are_options_and_never_instructions():
    r = _rep()
    for o in r["options"]:
        assert o["option"] in B.ACTION_OPTIONS
        assert o["resolves_en"]
    assert "does not tell you what to do" in r["no_recommendation_en"]
    assert "none" in B.ACTION_OPTIONS          # att avstå är ett alternativ
    try:
        _rep(options=["send_bulldozer"])
        raise AssertionError("okänt alternativ tilläts")
    except ValueError:
        pass


def test_unknown_detection_kind_and_missing_evidence_are_rejected():
    for bad in ({"kind": "vibes"}, {"evidence": []}):
        try:
            B.report(bad.get("kind", "land_use_change"), title="t",
                     summary_en="s", areas=["se"],
                     evidence=bad.get("evidence", [{"source": "x"}]),
                     confidence_inputs={}, snapshot=_snap())
            raise AssertionError(f"tilläts: {bad}")
        except ValueError:
            pass


def test_brief_is_sorted_by_decision_value_not_by_time():
    low = _rep(title="Minor", snap=_snap(relevance_level="L1",
                                         change_percent=3.0,
                                         is_breaking_pattern=False,
                                         cross_domain_links=0,
                                         consecutive_months=0))
    high = _rep(title="Major", snap=_snap())
    b = B.daily_brief([low, high], areas=["se"], date="2026-07-26")
    assert b["count"] >= 1
    assert b["reports"][0]["title"] == "Major"
    assert "not recency" in b["sorted_by_en"]


def test_a_quiet_day_is_reported_as_a_quiet_day():
    """En brief som alltid har innehåll börjar snart lyfta brus."""
    noise = _rep(snap=_snap(relevance_level="L0"))
    b = B.daily_brief([noise], areas=["se"], date="2026-07-26")
    assert b["count"] == 0 and b["reports"] == []
    assert "Nothing crossed the threshold" in b["headline_en"]
    assert "quiet brief is a real result" in b["quiet_day_en"]
    assert b["considered"] == 1


def test_scope_filters_on_area_and_sector():
    se = _rep(areas=["se", "se-14"])
    us = _rep(areas=["us", "us-CA"], title="US thing")
    assert B.daily_brief([se, us], areas=["us"])["count"] == 1
    assert B.daily_brief([se, us], areas=["se"])["reports"][0]["areas"][0] == "se"
    assert B.daily_brief([se, us], sectors=["energy"])["count"] == 0
    assert B.daily_brief([se, us], sectors=["real_estate"])["count"] == 2
    assert B.daily_brief([se, us])["count"] == 2      # utan filter: allt


def test_suppressed_count_is_reported_not_hidden():
    noise = _rep(title="n", snap=_snap(relevance_level="L1",
                                       change_percent=1.0,
                                       is_breaking_pattern=False,
                                       cross_domain_links=0,
                                       consecutive_months=0))
    b = B.daily_brief([_rep(title="Major"), noise], areas=["se"])
    assert b["below_threshold"] >= 1
    assert "held below the significance floor" in b["suppressed_en"]


def test_catalog_exposes_the_limits_of_each_kind():
    c = B.catalog()
    assert len(c["detection_kinds"]) == len(B.DETECTION_KINDS)
    for k in c["detection_kinds"]:
        assert k["never_en"]
    assert "never reports a legal finding" in c["note_en"]



# ── Briefen anpassad efter abonnemang ───────────────────────────────────
def test_explorer_cannot_scope_and_is_told_so():
    """Att tyst ignorera en begärd avgränsning är samma fel som tyst
    degradering: kunden får ett annat svar än det beställda, utan att veta."""
    reps = [_rep(areas=("se", "se-14")), _rep(areas=("se", "se-01"),
                                              title="Something in Stockholm")]
    res = B.daily_brief(reps, areas=["se-14"], sectors=["construction"],
                        plan="explorer")
    ps = res["plan_scope"]
    assert ps["plan"] == "free" and ps["scope"] == "public"
    asked = {d["asked_for"] for d in ps["not_applied"]}
    assert asked == {"areas", "sectors"}
    assert "was not applied" in ps["not_applied_en"]
    # avgränsningen togs bort — inte tillämpad i tysthet
    assert res["scope_en"] == "everywhere covered"


def test_professional_may_scope_by_region_and_sector_but_not_own_assets():
    reps = [_rep(areas=("se", "se-14")), _rep(areas=("se", "se-01"),
                                              title="Elsewhere")]
    res = B.daily_brief(reps, areas=["se-14"], plan="professional",
                        own_assets=True)
    ps = res["plan_scope"]
    assert ps["plan"] == "pro"
    assert [d["asked_for"] for d in ps["not_applied"]] == ["own_assets"]
    assert res["scope_en"] == "se-14"
    for r in res["reports"]:
        assert any(a.lower().startswith("se-14") for a in r["areas"])


def test_enterprise_keeps_every_scoping_it_asked_for():
    res = B.daily_brief([_rep()], areas=["se-14"], sectors=["construction"],
                        plan="enterprise intelligence", own_assets=True)
    ps = res["plan_scope"]
    assert ps["plan"] == "enterprise" and "not_applied" not in ps
    assert ps["scope"] == "own_assets"


def test_no_plan_means_the_engine_imposes_nothing():
    """Affärslogiken ägs av API-lagret, inte av motorn."""
    res = B.daily_brief([_rep()], areas=["se-14"])
    assert res["plan_scope"] == {}
    assert res["scope_en"] == "se-14"


def test_an_unknown_plan_is_refused_rather_than_defaulted():
    """Att falla tillbaka på den snällaste nivån vid stavfel är hur en
    betalspärr tyst upphör att gälla."""
    try:
        B.daily_brief([_rep()], plan="platinum")
        raise AssertionError("okänd plan tilläts")
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
