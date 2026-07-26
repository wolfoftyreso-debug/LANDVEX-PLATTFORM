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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
