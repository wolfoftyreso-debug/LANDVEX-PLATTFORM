"""Tester för händelseroutning (intresse → leverans → beslut att ompröva).
Kör: python3 -m tests.test_inbox"""
from __future__ import annotations

from engine import accountability
from engine import inbox as I
from engine import monitors as M


def setup():
    I.reset()
    M.reset()
    accountability.reset()


def _ev(sev="high", scope="se-1880", metrics=None, summary="x moved"):
    return {"origin": "feed", "source_id": "daily_top_changes", "severity": sev,
            "scope": scope, "scope_type": "regional", "summary": summary,
            "why": ["moved"], "metrics": metrics or ["parking"], "owner": "",
            "checksum": "c" + sev + scope}


def test_subscription_requires_a_stake():
    setup()
    for bad in [("", "citizen", [I.stake("place", "se-1880")]),
                ("anna", "citizen", [])]:
        try:
            I.subscribe(*bad)
            raise AssertionError("tom prenumeration tilläts: " + str(bad))
        except ValueError:
            pass
    try:
        I.stake("vibes", "x")
        raise AssertionError("okänd intressetyp tilläts")
    except ValueError:
        pass


def test_only_events_touching_a_stake_are_delivered():
    setup()
    I.subscribe("anna", "citizen", [I.stake("place", "se-1880")])
    r = I.route([_ev(scope="se-1880"), _ev(scope="se-0180")])
    row = r["routed"][0]
    assert row["delivered_count"] == 1
    assert row["delivered"][0]["scope"] == "se-1880"
    # och det som hölls tillbaka redovisas med skäl — aldrig tyst
    assert row["suppressed_count"] == 1
    assert "no stake" in row["suppressed"][0]["reason"]


def test_severity_floor_and_threshold_suppress_with_reasons():
    setup()
    I.subscribe("anna", "citizen", [I.stake("place", "se-1880")],
                min_severity="high")
    r = I.route([_ev(sev="low", scope="se-1880")])
    row = r["routed"][0]
    assert row["delivered_count"] == 0
    assert "severity floor" in row["suppressed"][0]["reason"]


def test_accountability_outranks_curiosity():
    """Ett beslut du bär väger tyngre än en plats du följer."""
    setup()
    owners = {"formellt": "ks", "operativt": "kontoret", "uppfoljning": "rev"}
    d = accountability.commit("Raise employment", owners,
                              {"metric": "employment_rate",
                               "direction": "increase", "target": 96},
                              kpi_ids=["employment_rate"], committed_at="2026-01")
    I.subscribe("bo", "municipality",
                [I.stake("place", "se-1880"),
                 I.stake("decision", d["id"])])
    ev_place = _ev(scope="se-1880", metrics=["parking"], summary="parking moved")
    ev_dec = _ev(scope="se-9999", metrics=["employment_rate"],
                 summary="employment moved")
    r = I.route([ev_place, ev_dec], decisions=[d])
    items = r["routed"][0]["delivered"]
    assert len(items) == 2
    assert items[0]["summary"] == "employment moved"      # ansvar först
    assert items[0]["relevance"] > items[1]["relevance"]
    rv = items[0]["revisit_decision"]
    assert rv["owner"] == "ks" and rv["id"] == d["id"]
    assert items[0]["why_it_matters_to_you"]


def test_monitor_finding_routes_to_its_owner():
    setup()
    m = M.define("debt_gdp", "SE", "threshold", "finance-unit",
                 params={"level": 60})
    f = M.evaluate(m, [55, 58, 62])
    I.subscribe("finance-unit", "municipality", [I.stake("monitor", m["id"])])
    r = I.route([I.from_finding(f)])
    got = r["routed"][0]["delivered"][0]
    assert got["origin"] == "monitor"
    assert "watch you set up" in got["why_it_matters_to_you"]
    assert got["reanswer_with"].startswith("/v1/")


def test_feed_event_normalises():
    ev = I.from_feed_event({"feed": "priority_alerts", "severity": "critical",
                            "scope_code": "se-0180", "scope_type": "regional",
                            "summary": "s", "why_now": ["w"],
                            "kpi_ids": ["k"], "checksum": "abc"})
    assert ev["origin"] == "feed" and ev["metrics"] == ["k"]
    assert ev["severity"] == "critical"


def test_brief_delivers_an_event_once_with_its_strongest_link():
    """Två prenumerationer som båda matchar ska inte ge dubbla larm."""
    setup()
    owners = {"formellt": "ks", "operativt": "k", "uppfoljning": "r"}
    d = accountability.commit("Fund places", owners,
                              {"metric": "shortage", "direction": "decrease",
                               "target": 40},
                              kpi_ids=["shortage"], committed_at="2026-01")
    I.subscribe("bo", "municipality", [I.stake("place", "se-1880")])
    I.subscribe("bo", "municipality", [I.stake("place", "se-1880"),
                                       I.stake("decision", d["id"])])
    ev = _ev(scope="se-1880", metrics=["shortage"], summary="shortage widened")
    b = I.brief("bo", [ev], decisions=[d])
    assert b["count"] == 1                       # en gång, inte två
    assert b["items"][0]["matched_stake"]["kind"] == "decision"   # starkast


def test_brief_is_honest_when_nothing_is_yours():
    setup()
    I.subscribe("anna", "citizen", [I.stake("place", "se-1880")])
    b = I.brief("anna", [_ev(scope="se-0180")])
    assert b["count"] == 0 and b["held_back"] == 1
    assert "Nothing you have a stake in" in b["headline_en"]
    none = I.brief("okand", [_ev()])
    assert none["status"] == "no_subscription"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
