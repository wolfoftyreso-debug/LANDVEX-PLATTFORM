"""Tester för SCB-adaptern. Körs utan pytest:  python3 -m tests.test_scb

Helt utan nätverk: PxWeb-svar simuleras med fixturer i samma format
som SCB:s API (metadata + JSON-stat2). Live-verifiering av riktiga
tabellsökvägar görs separat med  python3 -m engine.datasources.scb
"""
from __future__ import annotations

from engine.datasources import scb
from engine.datasources.adapters import ScbSource
from engine.datasources.base import Resolver
from engine.datasources.mock import MockSource
from engine.models import Location
from engine.scoring import analyze

STHLM = Location(59.3145, 18.0705, "Hornsgatan 52")

# ── Fixturer (formatet PxWeb v1 levererar) ───────────────────────────

POP_META = {"title": "Folkmängd efter region, ålder och år", "variables": [
    {"code": "Region", "text": "region",
     "values": ["0180"], "valueTexts": ["Stockholm"]},
    {"code": "Civilstand", "text": "civilstånd",
     "values": ["OG", "G"], "valueTexts": ["ogifta", "gifta"], "elimination": True},
    {"code": "Alder", "text": "ålder",
     "values": ["10", "30", "70", "tot"],
     "valueTexts": ["10 år", "30 år", "70 år", "totalt ålder"]},
    {"code": "Kon", "text": "kön",
     "values": ["1", "2"], "valueTexts": ["män", "kvinnor"], "elimination": True},
    {"code": "ContentsCode", "text": "tabellinnehåll",
     "values": ["BE0101N1"], "valueTexts": ["Folkmängd"]},
    {"code": "Tid", "text": "år",
     "values": ["2024", "2025"], "valueTexts": ["2024", "2025"], "time": True},
]}

# id-ordning Region×Alder×ContentsCode×Tid, radmajor:
# ålder 10: 2024=1000, 2025=1100 · 30: 2000/2100 · 70: 1000/1000 · tot: 4000/4200
POP_DATA = {
    "class": "dataset",
    "id": ["Region", "Alder", "ContentsCode", "Tid"],
    "size": [1, 4, 1, 2],
    "dimension": {
        "Region": {"category": {"index": {"0180": 0}, "label": {"0180": "Stockholm"}}},
        "Alder": {"category": {"index": {"10": 0, "30": 1, "70": 2, "tot": 3},
                               "label": {"10": "10 år", "30": "30 år",
                                         "70": "70 år", "tot": "totalt ålder"}}},
        "ContentsCode": {"category": {"index": {"BE0101N1": 0},
                                      "label": {"BE0101N1": "Folkmängd"}}},
        "Tid": {"category": {"index": {"2024": 0, "2025": 1},
                             "label": {"2024": "2024", "2025": "2025"}}},
    },
    "value": [1000, 1100, 2000, 2100, 1000, 1000, 4000, 4200],
}

INCOME_META = {"title": "Sammanräknad förvärvsinkomst", "variables": [
    {"code": "Region", "text": "region",
     "values": ["0180", "00"], "valueTexts": ["Stockholm", "Riket"]},
    {"code": "Kon", "text": "kön",
     "values": ["1", "2", "1+2"], "valueTexts": ["män", "kvinnor", "totalt"]},
    {"code": "ContentsCode", "text": "tabellinnehåll",
     "values": ["HE0110J7", "HE0110J8"],
     "valueTexts": ["Medianinkomst, tkr", "Medelinkomst, tkr"]},
    {"code": "Tid", "text": "år", "values": ["2024"], "valueTexts": ["2024"],
     "time": True},
]}

INCOME_DATA = {
    "class": "dataset",
    "id": ["Region", "Kon", "ContentsCode", "Tid"],
    "size": [2, 1, 1, 1],
    "dimension": {
        "Region": {"category": {"index": {"0180": 0, "00": 1},
                                "label": {"0180": "Stockholm", "00": "Riket"}}},
        "Kon": {"category": {"index": {"1+2": 0}, "label": {"1+2": "totalt"}}},
        "ContentsCode": {"category": {"index": {"HE0110J8": 0},
                                      "label": {"HE0110J8": "Medelinkomst, tkr"}}},
        "Tid": {"category": {"index": {"2024": 0}, "label": {"2024": "2024"}}},
    },
    "value": [420.0, 330.0],   # Sthlm 420 tkr, riket 330 tkr → index 127.3
}

DENSITY_META = {"title": "Befolkningstäthet", "variables": [
    {"code": "Region", "text": "region",
     "values": ["0180"], "valueTexts": ["Stockholm"]},
    {"code": "Kon", "text": "kön",
     "values": ["1", "2"], "valueTexts": ["män", "kvinnor"], "elimination": True},
    {"code": "ContentsCode", "text": "tabellinnehåll",
     "values": ["BE0101U1"],
     "valueTexts": ["Invånare per kvadratkilometer (befolkningstäthet)"]},
    {"code": "Tid", "text": "år", "values": ["2024"], "valueTexts": ["2024"],
     "time": True},
]}

DENSITY_DATA = {
    "class": "dataset",
    "id": ["Region", "ContentsCode", "Tid"],
    "size": [1, 1, 1],
    "dimension": {
        "Region": {"category": {"index": {"0180": 0}, "label": {"0180": "Stockholm"}}},
        "ContentsCode": {"category": {"index": {"BE0101U1": 0},
                                      "label": {"BE0101U1": "Invånare per km²"}}},
        "Tid": {"category": {"index": {"2024": 0}, "label": {"2024": "2024"}}},
    },
    "value": [5200.0],
}

_FIXTURES = {scb.POP_TABLE: (POP_META, POP_DATA),
             scb.INCOME_TABLE: (INCOME_META, INCOME_DATA),
             scb.DENSITY_TABLE: (DENSITY_META, DENSITY_DATA)}


def fake_transport(url: str, payload: bytes | None, timeout: float) -> bytes:
    import json
    for table, (meta, data) in _FIXTURES.items():
        if url.endswith(table):
            return json.dumps(meta if payload is None else data).encode()
    raise AssertionError(f"Oväntad URL i test: {url}")


def failing_transport(url: str, payload: bytes | None, timeout: float) -> bytes:
    raise OSError("nätverk nere (simulerat)")


def _client() -> scb.ScbClient:
    return scb.ScbClient(transport=fake_transport)


# ── Tester ───────────────────────────────────────────────────────────

def test_build_query_eliminates_and_picks_contents():
    q = scb.build_query(POP_META, region=["0180"], time_top=2,
                        contents_like=("folkmängd",), take_all=("Alder",))
    by_code = {sel["code"]: sel["selection"] for sel in q}
    assert by_code["Region"] == {"filter": "item", "values": ["0180"]}
    assert by_code["Tid"] == {"filter": "top", "values": ["2"]}
    assert by_code["ContentsCode"]["values"] == ["BE0101N1"]
    assert by_code["Alder"]["values"] == ["10", "30", "70", "tot"]
    assert "Civilstand" not in by_code and "Kon" not in by_code  # eliminerade


def test_build_query_prefers_total_category():
    q = scb.build_query(INCOME_META, region=["0180", "00"], time_top=1,
                        contents_like=("medelinkomst",))
    by_code = {sel["code"]: sel["selection"] for sel in q}
    assert by_code["Kon"]["values"] == ["1+2"]           # "totalt" vald
    assert by_code["ContentsCode"]["values"] == ["HE0110J8"]  # medel, inte median


def test_population_signals():
    sig, extra = scb.population_signals(_client(), "0180")
    # "tot"-kategorin får inte dubbelräknas: total 2025 = 1100+2100+1000 = 4200
    assert sig["pop_growth_pct"] == 5.0
    assert sig["age_20_45_share"] == 50.0                # 2100/4200
    assert sig["share_65plus"] == 23.8                   # 1000/4200
    assert extra == {"ar": "2025", "folkmangd_kommun": 4200}


def test_income_index():
    assert scb.income_index_signal(_client(), "0180") == 127.3


def test_density_to_households():
    assert scb.density_signal(_client(), "0180") == round(5200 / 2.2, 0)


def test_locator():
    loc = scb.KommunLocator()
    assert loc.locate(59.3145, 18.0705) == ("0180", "Stockholm")
    assert loc.locate(57.7005, 12.9405) == ("1490", "Borås")
    assert loc.locate(0.0, 0.0) is None                  # utanför tröskeln


def test_scb_source_wins_over_mock():
    resolver = Resolver([ScbSource(client=_client()), MockSource()])
    report = analyze(STHLM, "frisor", resolver=resolver)
    assert report.data_coverage > 0.0
    # Determinism gäller även med fixtur-SCB i kedjan.
    again = analyze(STHLM, "frisor", resolver=resolver)
    assert report.to_dict() == again.to_dict()


def test_scb_source_signal_values_and_extras():
    src = ScbSource(client=_client())
    signals, extras = src.fetch(STHLM, "frisor",
                                ["income_index", "pop_growth_pct", "foot_traffic"])
    assert signals["income_index"].value == 127.3
    assert signals["income_index"].source == "scb"
    assert signals["pop_growth_pct"].value == 5.0
    assert "foot_traffic" not in signals                 # inte SCB:s signal
    assert extras["scb"]["kommun_namn"] == "Stockholm"
    assert extras["scb"]["ar"] == "2025"


def test_scb_source_network_failure_falls_back_to_mock():
    src = ScbSource(client=scb.ScbClient(transport=failing_transport))
    resolver = Resolver([src, MockSource()])
    report = analyze(STHLM, "frisor", resolver=resolver)
    assert report.data_coverage == 0.0                   # ärlig täckning
    assert 0 <= report.opportunity_score <= 100
    # Källan pausar sig efter totalfel – inga nya anrop direkt efter.
    assert src._down_until > 0


def test_scb_source_outside_sweden_returns_empty():
    src = ScbSource(client=_client())
    signals, extras = src.fetch(Location(52.52, 13.40, "Berlin"), "cafe",
                                ["income_index"])
    assert signals == {} and extras == {}


def test_quixzoom_adapter_via_aamos_core():
    """quiXzoom är mission-baserat och nås via AAMOS Core. Densiteten
    (antal missions) blir signalen field_observation_density."""
    from engine.datasources.adapters import QuixzoomSource
    from engine.models import Location
    from integrations.aamos import AamosClient
    loc = Location(29.76, -95.37)
    SIG = ["field_observation_density"]
    # Ej ansluten (ingen AAMOS_CORE_URL) → tomt, ärligt.
    assert QuixzoomSource(client=AamosClient(base_url="")).fetch(
        loc, "gym", SIG) == ({}, {})
    urls = []

    def transport(method, url, body):
        urls.append(url)
        return {"missions": [
            {"id": "m1", "location": {"lat": 29.76, "lng": -95.37}},
            {"id": "m2", "location": {"lat": 29.77, "lng": -95.38}},
            {"id": "m3", "location": {"lat": 29.75, "lng": -95.36}}]}
    src = QuixzoomSource(client=AamosClient(
        base_url="http://localhost:3100", transport=transport))
    vals, extras = src.fetch(loc, "gym", SIG + ["development_m2"])
    assert "/api/aamos/quixzoom/missions" in urls[0] and "lat=29.76" in urls[0]
    assert vals["field_observation_density"].value == 3.0
    assert vals["field_observation_density"].source == "quixzoom"
    # development_m2 hittas ALDRIG på – kräver Vision (ärlighet).
    assert "development_m2" not in vals
    assert extras["quixzoom"]["via"] == "aamos_core"


def test_quixzoom_adapter_pauses_on_error():
    from engine.datasources.adapters import QuixzoomSource
    from engine.models import Location
    from integrations.aamos import AamosClient
    t = [0.0]

    def boom(method, url, body):
        raise OSError("connection refused")
    src = QuixzoomSource(
        client=AamosClient(base_url="http://x", transport=boom),
        retry_after_s=300.0, clock=lambda: t[0])
    loc = Location(29.76, -95.37)
    SIG = ["field_observation_density"]
    assert src.fetch(loc, "gym", SIG) == ({}, {})
    kallad = []
    src._client._transport = lambda m, u, b: kallad.append(u) or {}
    assert src.fetch(loc, "gym", SIG) == ({}, {})
    assert not kallad                            # pausad – inget anrop
    t[0] = 301.0
    src.fetch(loc, "gym", SIG)
    assert kallad                                # provar igen efter paus


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
