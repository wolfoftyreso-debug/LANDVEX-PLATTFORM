"""Täckningsytan får inte vara vänligare än verkligheten.

(Namnet skiljer sig från `tests/test_coverage.py`, som handlar om något
annat: att en bransch är inlagd i SAMTLIGA tabeller. Den här sviten
gäller `engine/coverage.py` — vad plattformen kan svara på VAR.)

Poängen med att publicera sin egen täckning är att den är obekväm. Ett
tal som räknar en oansluten adapter som ansluten, eller som låter
SCB-adaptern gälla för Texas, är värre än inget tal alls: det ser ut som
en mätning och är en förhoppning.

Kör: python3 -m tests.test_coverage_surface
"""
from __future__ import annotations

from engine.coverage import compare_markets, coverage


class _Fejk:
    """En källa med känt läge — testet ska inte bero på miljövariabler."""

    def __init__(self, name, signals, markets=(), connected=True):
        self.name = name
        self.SIGNALS = tuple(signals)
        self.markets = tuple(markets)
        self.connected = connected

    def fetch(self, *a, **kw):
        return {}, {}


def test_a_source_that_cannot_reach_the_market_is_not_counted_as_cover():
    """SCB-adaptern är kopplad och /health säger 'ok' — men den kan inte
    svara för en punkt i Texas. Räknas den ändå blir mock till verklig
    data i statistiken."""
    k = [_Fejk("scb", ("pop_growth_pct", "income_index"), markets=("se",))]
    se = coverage("se", sources=k)
    us = coverage("us", sources=k)
    assert se["signals"]["live"] == 2
    assert us["signals"]["live"] == 0
    assert us["signals"]["out_of_scope"] == 2
    assert us["real_weight"] == 0.0
    assert se["real_weight"] > 0.0


def test_an_unconnected_adapter_is_ready_not_live():
    """Skillnaden mellan 'skriven' och 'ansluten' är hela skillnaden
    mellan en demo och en produkt."""
    k = [_Fejk("permits", ("building_permits",), connected=False)]
    c = coverage("se", sources=k)
    rad = {r["signal_id"]: r for r in c["signal_rows"]}["building_permits"]
    assert rad["state"] == "adapter_ready"
    assert rad["source"] == "mock"      # det är fortfarande mock som svarar
    assert c["real_weight"] == 0.0


def test_out_of_scope_and_ready_are_not_the_same_problem():
    """Det ena är ett avtal, det andra en ny integration. Slår man ihop
    dem ser den dyra luckan billig ut."""
    k = [_Fejk("scb", ("pop_growth_pct",), markets=("se",)),
         _Fejk("permits", ("building_permits",), connected=False)]
    c = coverage("us", sources=k)
    per = {r["source"]: r for r in c["what_would_change_it"]}
    assert per["scb"]["in_scope"] is False
    assert "does not reach this market" in per["scb"]["what_en"].lower()
    assert per["permits"]["in_scope"] is True
    assert "connect it" in per["permits"]["what_en"].lower()


def test_the_headline_number_is_weighted_not_a_signal_count():
    """Signalerna finns överallt och betyder ingenting i sig. Det som
    avgör svaret är vikterna."""
    tung = coverage("se", sources=[
        _Fejk("x", ("detached_homes", "avg_building_age"))])
    latt = coverage("se", sources=[_Fejk("x", ("parking_score",))])
    el_tung = {v["vertical_id"]: v for v in tung["by_vertical"]}["elektriker"]
    el_latt = {v["vertical_id"]: v for v in latt["by_vertical"]}["elektriker"]
    assert el_tung["real_weight"] > el_latt["real_weight"]


def test_no_source_at_all_says_none_rather_than_a_small_number():
    c = coverage("us", sources=[])
    assert c["real_weight"] == 0.0 and c["band"] == "none"
    assert "deterministic mock" in c["band_en"]
    assert all(v["real_weight"] == 0.0 for v in c["by_vertical"])


def test_the_bands_do_not_promise_more_than_they_measure():
    """Bandet gäller VÅRT underlag, aldrig hur säkert ett enskilt svar
    är — det omdömet vägrar corroboration.py uttrycka i procent."""
    c = coverage("se")
    assert "corroborated" in c["cannot_en"]
    assert "never as a percentage" in c["cannot_en"]
    for ord_ in ("certain", "accurate", "guarantee"):
        assert ord_ not in c["band_en"].lower()


def test_every_market_can_be_asked_and_an_unknown_one_is_refused():
    from engine.markets import MARKETS

    for mid in list(MARKETS)[:5]:
        c = coverage(mid)
        assert c["market"] == mid and 0.0 <= c["real_weight"] <= 1.0
    try:
        coverage("atlantis")
    except ValueError as e:
        assert "atlantis" in str(e)
    else:
        raise AssertionError("okänd marknad tilläts")


def test_the_market_comparison_counts_markets_with_real_data_honestly():
    k = [_Fejk("scb", ("pop_growth_pct",), markets=("se",))]
    j = compare_markets(["se", "us", "de"], sources=k)
    assert j["count"] == 3 and j["with_real_data"] == 1
    assert j["markets"][0]["market"] == "se"      # sorterat på verklig vikt
    assert "labelled as such" in j["summary_en"]
    assert "not a covered market" in j["cannot_en"]


def test_the_connected_rule_lives_in_one_place():
    """Regeln låg bara i api/health och var därför oåtkomlig för motorn.
    Två kopior av samma regel glider isär."""
    import inspect

    import api.health as health
    from engine.datasources.base import DataSource
    assert "def connected" in inspect.getsource(DataSource)
    kalla = inspect.getsource(health.source_status)
    assert "connected" in kalla, "health räknar inte längre samma sak"
    assert 'getattr(inner, "base_url"' not in kalla, \
        "regeln är kopierad igen"


def test_the_real_adapters_declare_where_they_can_answer():
    """Räckvidden ska vara data, inte något man vet om man läst koden."""
    from engine.datasources.adapters import production_sources

    per = {s.name: tuple(getattr(s, "markets", ()))
           for s in production_sources()}
    assert per["scb"] == ("se",), per["scb"]
    assert per["livability"] == ("se",), per["livability"]
    # De generiska HTTP-källorna har ingen inbyggd gräns — de svarar för
    # det som ligger bakom URL:en, och att påstå en gräns vore påhitt.
    assert per["permits"] == () and per["places"] == ()


def test_the_surface_is_free_and_public_on_purpose():
    """En kund som måste köpa för att få veta vad talen vilar på har
    redan fått fel produkt."""
    from api.licensing import required_capability
    from engine.offering import DECISIONS

    assert required_capability("/v1/coverage") == "core"
    d = {x["id"]: x for x in DECISIONS}["coverage_here"]
    assert d["plan"] == "free" and d["status"] == "built"
    assert d["answered_by"] == "/v1/coverage"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
