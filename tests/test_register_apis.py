"""Tester för de riktiga registerklienterna.

Fixturerna är i respektive API:s FAKTISKA svarsformat (JSON-stat2 från
PxWeb, matrisformatet från api.census.gov, JSON-stat från Eurostat), så
det som testas är den parsning som kommer att möta skarp data.

Kör: python3 -m tests.test_register_apis
"""
from __future__ import annotations

import json

from engine.datasources import register_apis as RA

# ── Fixturer i verkligt format ──────────────────────────────────────────
# PxWeb / JSON-stat2 (SCB, SSB, DST, StatFin svarar så här).
PXWEB_JSONSTAT2 = {
    "version": "2.0", "class": "dataset",
    "label": "Establishments by region, industry and year",
    "id": ["Region", "SNI2007", "Tid"], "size": [1, 1, 1],
    "dimension": {
        "Region": {"label": "region",
                   "category": {"index": {"0138": 0},
                                "label": {"0138": "Tyresö"}}},
        "SNI2007": {"label": "industry",
                    "category": {"index": {"4321": 0},
                                 "label": {"4321": "Electrical installation"}}},
        "Tid": {"label": "year",
                "category": {"index": {"2023": 0, "2024": 1},
                             "label": {"2023": "2023", "2024": "2024"}}},
    },
    "value": [41],
}

# api.census.gov/data/2022/cbp – matris, rad 0 = rubriker.
CENSUS_CBP = [["ESTAB", "state", "county", "NAICS2017"],
              ["1287", "06", "037", "238210"]]

# Eurostat dissemination API – JSON-stat med glest value-objekt.
EUROSTAT_JSONSTAT = {
    "class": "dataset", "label": "Local units by NUTS region and NACE",
    "id": ["geo", "nace_r2", "time"], "size": [1, 1, 1],
    "dimension": {
        "geo": {"category": {"index": {"DE300": 0},
                             "label": {"DE300": "Berlin"}}},
        "nace_r2": {"category": {"index": {"4321": 0}}},
        "time": {"category": {"index": {"2022": 0}, "label": {"2022": "2022"}}},
    },
    "value": {"0": 3894},
}


def _tp(payload):
    """Transport som returnerar en fast nyttolast (ingen nätverkstrafik)."""
    def t(url, body, timeout):
        t.last_url, t.last_body = url, body
        return json.dumps(payload).encode()
    t.last_url = t.last_body = None
    return t


def test_pxweb_parses_real_jsonstat2_and_posts_a_query():
    tp = _tp(PXWEB_JSONSTAT2)
    p = RA.PxWebRegister(transport=tp)
    got = p.count("se", "0138", "43.21")
    assert got["count"] == 41 and got["measured"] is True
    assert got["provider"] == "pxweb"
    assert "Statistics Sweden" in got["source"]
    assert got["year"] == "2024"                    # senaste perioden
    # frågan ska POSTas med region + näringsgren, NACE utan punkt
    body = json.loads(tp.last_body.decode())
    codes = {q["code"]: q["selection"]["values"] for q in body["query"]}
    assert codes["Region"] == ["0138"]
    assert codes["SNI2007"] == ["4321"]
    assert body["response"]["format"] == "json-stat2"


def test_pxweb_serves_all_four_nordic_agencies():
    assert set(RA.PXWEB_TABLES) == {"se", "no", "dk", "fi"}
    for c in RA.PXWEB_TABLES:
        assert RA.PROVIDER_FOR[c] == "pxweb"
        p = RA.PxWebRegister(transport=_tp(PXWEB_JSONSTAT2))
        assert p.count(c, "0001", "43.21")["count"] == 41
    assert RA.PxWebRegister(transport=_tp(PXWEB_JSONSTAT2)
                            ).count("zz", "1", "43.21") is None


def test_census_parses_the_matrix_and_builds_a_fips_query():
    tp = _tp(CENSUS_CBP)
    p = RA.CensusCbpRegister(transport=tp)
    got = p.count("us", "06037", "238210")
    assert got["count"] == 1287 and got["measured"] is True
    assert "Census" in got["source"]
    # colon is percent-encoded by urlencode; compare the decoded URL
    from urllib.parse import unquote
    url = unquote(tp.last_url)
    assert "for=county:037" in url and "in=state:06" in url
    assert "NAICS2017=238210" in url
    # fel land eller ofullständig FIPS ⇒ inget anrop, inget påhittat tal
    assert p.count("se", "0138", "238210") is None
    assert p.count("us", "06", "238210") is None


def test_eurostat_parses_sparse_jsonstat():
    tp = _tp(EUROSTAT_JSONSTAT)
    p = RA.EurostatRegister(transport=tp)
    got = p.count("de", "DE300", "43.21")
    assert got["count"] == 3894 and got["source"] == "Eurostat"
    assert "geo=DE300" in tp.last_url and "nace_r2=4321" in tp.last_url


def test_a_broken_or_empty_response_yields_none_never_a_number():
    for payload in ({}, {"value": []}, {"value": {}}, [], [["ESTAB"]],
                    {"count": None}):
        assert RA.PxWebRegister(transport=_tp(payload)
                                ).count("se", "0138", "43.21") is None
        assert RA.CensusCbpRegister(transport=_tp(payload)
                                    ).count("us", "06037", "238210") is None

    def boom(url, body, timeout):
        raise OSError("network unreachable")
    assert RA.PxWebRegister(transport=boom).count("se", "0138", "43.21") is None
    assert RA.CensusCbpRegister(transport=boom).count("us", "06037",
                                                      "238210") is None


def test_provider_routing_picks_the_right_client_per_country():
    assert isinstance(RA.provider_for("se"), RA.PxWebRegister)
    assert isinstance(RA.provider_for("us"), RA.CensusCbpRegister)
    assert isinstance(RA.provider_for("de"), RA.EurostatRegister)
    assert isinstance(RA.provider_for("zz"), RA.GenericRegister)


def test_status_does_not_claim_live_verification():
    st = RA.providers_status()
    ids = {p["id"] for p in st["providers"]}
    assert {"pxweb", "census_cbp", "eurostat", "generic"} == ids
    # Ingen provider får påstå sig live-verifierad förrän proben körts.
    assert all(p["verified_live"] is False for p in st["providers"])
    assert "NOT live-verified" in st["note_en"]
    assert "register_probe" in st["probe"]


def test_generic_mirror_still_works():
    p = RA.GenericRegister(base_url="http://mirror.example",
                           transport=_tp({"count": 12, "year": 2025,
                                          "source": "mirror"}))
    got = p.count("se", "0138", "43.21")
    assert got["count"] == 12 and got["provider"] == "generic"
    assert RA.GenericRegister(base_url="").count("se", "0138", "43.21") is None



# ── Strömbrytaren ────────────────────────────────────────────────────────
class _Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def tick(self, s): self.t += s


def _counting_transport(fail=True):
    calls = []
    def t(url, payload, timeout):
        calls.append(url)
        if fail:
            raise OSError("connection refused")
        return b'{"count": 7, "year": 2024, "source": "test"}'
    return t, calls


def test_one_dead_authority_costs_one_call_not_one_per_region():
    """Kärnfyndet. En mättnadsjämförelse över 60 kommuner gjorde 60
    blockerande HTTPS-anrop à ~0,3 s och tog 19 sekunder att svara
    "vet inte" — 94 % av demons körtid, för noll information."""
    tr, calls = _counting_transport(fail=True)
    clock = _Clock()
    p = RA.PxWebRegister(transport=tr, clock=clock, retry_after_s=300.0)
    for _ in range(60):
        assert p.count("se", "0138", "43.21") is None
    assert len(calls) == 1, (
        f"{len(calls)} anrop mot en källa som redan sagt ifrån en gång")
    assert p.down


def test_the_pause_expires_so_a_source_can_come_back():
    """En källa som är nere för alltid vore lika fel som ingen paus."""
    tr, calls = _counting_transport(fail=True)
    clock = _Clock()
    p = RA.PxWebRegister(transport=tr, clock=clock, retry_after_s=300.0)
    p.count("se", "0138", "43.21")
    assert len(calls) == 1
    clock.tick(299)
    p.count("se", "0138", "43.21")
    assert len(calls) == 1, "försökte igen innan pausen gått ut"
    clock.tick(2)
    p.count("se", "0138", "43.21")
    assert len(calls) == 2, "kom aldrig tillbaka efter pausen"


def test_a_working_source_is_never_paused():
    tr, calls = _counting_transport(fail=False)
    p = RA.GenericRegister(transport=tr, clock=_Clock(),
                           base_url="https://register.example")
    for _ in range(5):
        p.count("se", "0138", "43.21")
    assert len(calls) == 5 and not p.down


def test_a_success_clears_an_earlier_pause():
    state = {"fail": True}
    calls = []
    def tr(url, payload, timeout):
        calls.append(url)
        if state["fail"]:
            raise OSError("down")
        return b'{"count": 7, "year": 2024, "source": "test"}'
    clock = _Clock()
    p = RA.GenericRegister(transport=tr, clock=clock, retry_after_s=10.0,
                           base_url="https://register.example")
    p.count("se", "0138", "43.21")
    assert p.down
    clock.tick(11); state["fail"] = False
    p.count("se", "0138", "43.21")
    assert not p.down, "en lyckad hämtning nollställde inte pausen"


def test_the_breaker_never_turns_into_an_invented_number():
    """Snabbhet får aldrig köpas med ett påhittat antal."""
    tr, _ = _counting_transport(fail=True)
    p = RA.PxWebRegister(transport=tr, clock=_Clock())
    for _ in range(10):
        assert p.count("se", "0138", "43.21") is None


def test_providers_are_shared_so_the_breaker_survives_between_regions():
    """En brytare som återskapas vid varje anrop är ingen brytare."""
    RA.reset_breakers()
    a = RA.provider_for("se")
    b = RA.provider_for("se")
    assert a is b, "varje anrop fick en egen instans — brytaren glöms bort"
    # Egen transport/klocka ⇒ egen instans, så tester inte stör varandra.
    own = RA.provider_for("se", transport=_counting_transport()[0])
    assert own is not a


def test_an_our_bug_still_crashes_instead_of_tripping_the_breaker():
    """Strömbrytaren får inte bli ett nytt ställe där våra buggar göms."""
    def broken(url, payload, timeout):
        raise AttributeError("'PxWebRegister' object has no attribute 'nope'")
    p = RA.PxWebRegister(transport=broken, clock=_Clock())
    try:
        p.count("se", "0138", "43.21")
    except AttributeError:
        assert not p.down, "vårt fel pausade källan i stället för att braka"
    else:
        raise AssertionError("AttributeError svaldes av strömbrytaren")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
