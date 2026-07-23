"""Tester för Risk Engine + jämförelsemodulen. Körs utan pytest:
python3 -m tests.test_risk_compare"""
from __future__ import annotations

from engine.compare import compare
from engine.models import Location
from engine.risk import DIMENSIONS, assess, required_signals
from engine.signals import CATALOG

STHLM = Location(59.3145, 18.0705, "Hornsgatan 52")
BORAS = {"lat": 57.7005, "lon": 12.9405, "address": "Borås"}
UMEA = {"lat": 63.8258, "lon": 20.2630, "address": "Umeå"}


# ── Risk Engine ──────────────────────────────────────────────────────

def test_risk_dimensions_are_valid_data():
    for d in DIMENSIONS:
        assert d.mitigation_sv
        assert abs(sum(w for _, w in d.signals) - 1.0) < 1e-6, d.id
        for sid, _ in d.signals:
            assert sid in CATALOG, (d.id, sid)
    assert all(s in CATALOG for s in required_signals())


def test_risk_profile_contract():
    rp = assess(STHLM, "frisor")
    assert 0 <= rp["total_risk"] <= 100
    assert rp["band"] in ("Låg", "Medel", "Hög", "Mycket hög")
    ids = [d["id"] for d in rp["dimensioner"]]
    assert ids == [d.id for d in DIMENSIONS] + ["dataosakerhet"]
    for d in rp["dimensioner"]:
        assert 0 <= d["risk"] <= 100
        assert d["narrativ_sv"]
        if d["risk"] >= 60:
            assert d["atgard_sv"]          # förhöjd risk ⇒ åtgärdsförslag
        if d["id"] != "dataosakerhet":
            assert d["signaler"] and all(
                "riskbidrag" in s and "kalla" in s for s in d["signaler"])
    assert rp["caveats_sv"]
    assert assess(STHLM, "frisor") == rp   # determinism


def test_risk_data_uncertainty_reflects_mock():
    rp = assess(STHLM, "cafe")
    data = next(d for d in rp["dimensioner"] if d["id"] == "dataosakerhet")
    assert data["risk"] >= 60               # allt mockat ⇒ hög dataosäkerhet
    assert data["atgard_sv"]


def test_risk_unknown_vertical():
    try:
        assess(STHLM, "rymdturism")
    except ValueError:
        return
    raise AssertionError("Okänd vertikal ska ge ValueError")


# ── Jämförelse ───────────────────────────────────────────────────────

def test_compare_contract():
    res = compare([BORAS, UMEA,
                   {"lat": 59.3145, "lon": 18.0705, "address": "Hornsgatan"}],
                  "frisor")
    assert len(res["platser"]) == 3
    assert len(res["faktormatris"]) == 6           # frisörens sex faktorer
    for rad in res["faktormatris"]:
        assert len(rad["scores"]) == 3
        best = rad["vinnare_index"]
        assert rad["scores"][best] == max(rad["scores"])
    win = res["vinnare_index"]
    assert res["platser"][win]["opportunity_score"] == max(
        p["opportunity_score"] for p in res["platser"])
    assert res["rekommendation_sv"] and res["caveats_sv"]
    assert all(p["risk_band"] for p in res["platser"])


def test_compare_validates_input():
    for bad_locs, vert in [([BORAS], "frisor"),
                           ([BORAS] * 5, "frisor"),
                           ([BORAS, {"lat": "x", "lon": 1}], "frisor"),
                           ([BORAS, UMEA], "rymdturism")]:
        try:
            compare(bad_locs, vert)
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {vert}, {bad_locs}")


def test_compare_deterministic():
    assert compare([BORAS, UMEA], "cafe") == compare([BORAS, UMEA], "cafe")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
