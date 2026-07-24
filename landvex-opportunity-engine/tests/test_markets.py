"""Tester för marknadsmodellen + globala flöden. Körs utan pytest:
python3 -m tests.test_markets"""
from __future__ import annotations

from engine.ask import ask, parse
from engine.markets import (MARKET_GROUPS, MARKETS, find_region_by_name,
                            get_market, get_region, market_catalog)
from engine.profile import profile_from_dict
from engine.scan import scan
from engine.workforce import forecast, global_map


def test_markets_are_valid_data():
    # USA-först + full täckning: alla 27 EU-länder och alla 50 delstater.
    base = {"se", "de", "us", "es", "pl", "fr", "it", "nl", "be", "at",
            "pt", "dk", "fi", "no", "ie", "cz",
            "ca", "mx", "co", "ma", "ng", "sn"}
    eu_extra = {"gr", "ro", "hu", "bg", "hr", "sk", "si", "lt", "lv", "ee",
                "lu", "cy", "mt"}
    assert base | eu_extra == set(MARKETS)
    assert len(MARKETS["us"].regions) >= 50           # alla delstater
    assert len(MARKETS["us"].regions) == max(
        len(m.regions) for m in MARKETS.values())   # USA störst
    assert sum(len(m.regions) for m in MARKETS.values()) >= 200
    # Inset-territorier utanför den kontinentala kartvyn (som riktiga
    # USA-kartor ritar Alaska/Hawaii som insatta rutor).
    _INSET = {"us-anchorage", "us-honolulu"}
    codes = set()
    for m in MARKETS.values():
        assert m.regions and m.currency and m.region_label_en
        lat_min, lat_max, lon_min, lon_max = m.bbox
        for kod, namn, lat, lon in m.regions:
            assert kod not in codes, f"dublettkod {kod}"
            codes.add(kod)
            if kod in _INSET:
                continue
            assert lat_min <= lat <= lat_max, (m.id, namn)
            assert lon_min <= lon <= lon_max, (m.id, namn)
    assert MARKETS["se"].calibrated and not MARKETS["de"].calibrated
    assert all(mid in MARKETS for g in MARKET_GROUPS.values() for mid in g)
    assert "us" not in MARKET_GROUPS["eu"]
    assert set(MARKET_GROUPS["varlden"]) == set(MARKETS)
    assert len(market_catalog()) == len(MARKETS)


def test_region_lookup():
    assert get_region("de", "de-berlin")[1] == "Berlin"
    assert find_region_by_name("warszawa") == ("pl", MARKETS["pl"].regions[0])
    for bad in [("xx", "de-berlin"), ("de", "0180")]:
        try:
            get_region(*bad)
        except ValueError:
            continue
        raise AssertionError(f"Skulle ha avvisats: {bad}")


def test_scan_in_germany():
    res = scan(profile_from_dict({"vertical_id": "vvs"}), market="de", top_n=3)
    assert res["market"] == "de"
    assert res["candidates_scanned"] == len(MARKETS["de"].regions)
    assert res["bbox"] == list(MARKETS["de"].bbox)
    card = res["hotspots"][0]
    # Ekonomischabloner är inte kalibrerade utanför Sverige – ärligt fält.
    assert card["economy_scenario"]["status"] == "ej_kalibrerad"
    # Svenska svepet påverkas inte.
    se = scan(profile_from_dict({"vertical_id": "vvs"}), top_n=1, market="se")
    assert se["hotspots"][0]["economy_scenario"].get("status") != "ej_kalibrerad"


def test_forecast_with_milestones_in_us():
    res = forecast("us-austin", 2035, ["sjukskoterska"], market="us")
    f = res["prognoser"][0]
    ms = f["milstolpar"]
    assert [m["horisont_ar"] for m in ms] == [1, 3, 5, 10, 20]
    assert ms[0]["ar"] == 2027 and ms[-1]["ar"] == 2046
    behov = [m["behov"] for m in ms]
    assert behov == sorted(behov) or behov == sorted(behov, reverse=True)
    assert res["market"] == "us"


def test_global_map_and_ranking():
    res = global_map("elektriker", 2035, group="eu")
    marknader = {r["market"] for r in res["regioner"]}
    assert marknader == set(MARKET_GROUPS["eu"])
    assert len(res["landsranking"]) == len(MARKET_GROUPS["eu"])
    pcts = [r["snitt_brist_pct"] for r in res["landsranking"]]
    assert pcts == sorted(pcts, reverse=True)
    assert any("simulated" in c for c in res["caveats_en"])
    try:
        global_map("elektriker", group="mars")
    except ValueError:
        pass
    else:
        raise AssertionError("Okänd grupp ska ge ValueError")


def test_ask_global_intents():
    q = parse("Var i Europa är det störst brist på elektriker?")
    assert q.intent == "global_brist" and q.group == "eu"
    q2 = parse("Var är det bäst att starta ett VVS-företag i Tyskland?")
    assert q2.intent == "basta_lage_vertikal"
    assert q2.vertical_id == "vvs" and q2.market == "de"
    q3 = parse("Vilket land är bäst för en svensk snickare att flytta till?")
    assert q3.intent == "land_ranking" and q3.occupation_id == "snickare"
    q4 = parse("Vilken amerikansk delstat behöver flest sjuksköterskor "
               "de kommande tio åren?")
    assert q4.intent == "nationell_brist"
    assert q4.market == "us" and q4.target_year == 2036
    q5 = parse("Vilka yrkesgrupper saknas mest i Berlin?")
    assert q5.intent == "bristyrken_kommun" and q5.region_market == "de"


def test_ask_global_answers():
    res = ask("Var i Europa är det störst brist på elektriker?")
    assert res["intent"] == "global_brist"
    assert "(" in res["rader"][0]["label_en"]        # "Stad (Land)"
    assert res["karta"]["bbox"] == [34.0, 71.0, -11.0, 35.0]
    res2 = ask("Vilket land är bäst för en svensk snickare att flytta till?")
    assert res2["intent"] == "land_ranking"
    assert len(res2["rader"]) == len(MARKETS)        # alla marknader rankade
    assert "regulations" in res2["svar_en"]            # ärlighetsnot
    res3 = ask("Var är det bäst att starta ett VVS-företag i Tyskland?")
    assert res3["intent"] == "basta_lage_vertikal"
    assert "Germany" in res3["svar_en"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
