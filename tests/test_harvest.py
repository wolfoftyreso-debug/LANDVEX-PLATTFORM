"""Skördad data får aldrig se färskare eller närmare ut än den är.

Hela poängen med att skörda i stället för att fråga i förfrågningsvägen
är att svaret blir snabbt, artigt och reproducerbart. Priset är att
datan är gammal — och ett gammalt tal som serveras tyst som ett aktuellt
är precis det fel plattformen finns för att förhindra.

Sviten prövar därför de tre reglerna hårdare än den lyckliga vägen:
åldern, avståndet, och att förfrågningsvägen INTE kan göra ett nätanrop.

Kör: python3 -m tests.test_harvest
"""
from __future__ import annotations

import json
import time
import urllib.parse

from engine import harvest as H

_REGION = ("us-newyork", "New York", 40.71, -74.01)


def _overpass_svar(antal: dict[str, int]) -> bytes:
    """Overpass svarar med en count-post per out count-sats, i ordning."""
    poster = [{"type": "count", "id": 0, "tags": {"total": str(antal[v])}}
              for v in sorted(H.OSM_TAGS)]
    return json.dumps({"elements": poster}).encode("utf-8")


def _alla(n: int = 3) -> dict[str, int]:
    return {v: n for v in H.OSM_TAGS}


def _transport(svar: bytes):
    def t(*a):
        return svar
    return t


def _pa(monkey_env: dict):
    import os
    for k, v in monkey_env.items():
        os.environ[k] = v


def _av(*namn):
    import os
    for n in namn:
        os.environ.pop(n, None)


# ── Overpass-frågan ─────────────────────────────────────────────────────
def test_one_query_counts_every_industry_not_one_query_each():
    """Ett anrop per region och dygn är artigt mot en gratistjänst.
    Tjugo anrop per region är det inte."""
    q = H._overpass_query(59.31, 18.07, sorted(H.OSM_TAGS), 3000)
    assert q.count("out count;") == len(H.OSM_TAGS)
    assert q.startswith("[out:json]")
    assert "around:3000,59.31,18.07" in q
    # både noder och ytor: en gymhall är ofta en byggnad, inte en punkt
    assert 'node["leisure"="fitness_centre"]' in q
    assert 'way["leisure"="fitness_centre"]' in q


def test_a_mismatched_answer_is_refused_rather_than_guessed():
    """Ett tal på fel bransch är värre än inget tal: frisörernas antal
    som svar på bilverkstäderna ser fullt rimligt ut."""
    kort = json.dumps({"elements": [{"type": "count", "tags": {"total": "4"}}]})
    try:
        H._parse_overpass(kort.encode(), sorted(H.OSM_TAGS))
    except ValueError as e:
        assert "refusing to guess" in str(e)
    else:
        raise AssertionError("felaktigt antal svar accepterades")


def test_the_count_becomes_the_same_scale_the_other_source_uses():
    """places.py använder min(10, n). En andra skala för samma signal
    hade betytt att två källor svarat i olika enheter."""
    _pa({"LANDVEX_OSM_URL": "https://x"})
    try:
        rader = H.harvest_region(
            "osm", _REGION, "us",
            transport=_transport(_overpass_svar({**_alla(3), "gym": 25})))
        per = {r["signal_id"]: r for r in rader}
        assert per["competition_pressure:gym"]["value"] == 10.0
        assert per["competition_pressure:gym"]["observed_count"] == 25
        assert per["competition_pressure:frisor"]["value"] == 3.0
        assert all(r["unit"] == "0–10" for r in rader)
    finally:
        _av("LANDVEX_OSM_URL")


# ── De tre reglerna ─────────────────────────────────────────────────────
def test_a_row_past_its_max_age_is_absent_not_a_value():
    """Ett gammalt tal som serveras tyst är värre än inget: mock är
    märkt mock, ett inaktuellt värde ser ut som en mätning."""
    H.reset()
    nu = 1_800_000_000.0
    H.store_rows([{"source": "osm", "region_code": "x",
                   "signal_id": "competition_pressure:gym", "value": 4.0,
                   "lat": 40.71, "lon": -74.01, "observed_at": nu}])
    farsk = H.read("osm", 40.71, -74.01, ["competition_pressure:gym"],
                   now=nu + 86400)
    assert farsk["competition_pressure:gym"]["value"] == 4.0
    gammal = H.read("osm", 40.71, -74.01, ["competition_pressure:gym"],
                    now=nu + 31 * 86400)
    assert gammal == {}, "en rad över max_age_days lästes som ett värde"
    H.reset()


def test_max_age_is_per_source_because_a_shop_and_the_weather_differ():
    H.reset()
    nu = 1_800_000_000.0
    for kalla, sid in (("osm", "competition_pressure:gym"),
                       ("open_meteo", "air_temperature_c")):
        H.store_rows([{"source": kalla, "region_code": "x",
                       "signal_id": sid, "value": 1.0, "lat": 0.0,
                       "lon": 0.0, "observed_at": nu}])
    tva_dygn = nu + 2 * 86400
    assert H.read("osm", 0.0, 0.0, ["competition_pressure:gym"],
                  now=tva_dygn), "OSM ska tåla två dygn"
    assert H.read("open_meteo", 0.0, 0.0, ["air_temperature_c"],
                  now=tva_dygn) == {}, "väder ska inte tåla två dygn"
    H.reset()


def test_a_reading_from_too_far_away_is_not_a_reading_here():
    H.reset()
    nu = time.time()
    H.store_rows([{"source": "osm", "region_code": "nyc",
                   "signal_id": "competition_pressure:gym", "value": 7.0,
                   "lat": 40.71, "lon": -74.01, "observed_at": nu}])
    nara = H.read("osm", 40.75, -73.98, ["competition_pressure:gym"])
    assert nara and nara["competition_pressure:gym"]["distance_km"] < 6
    langt = H.read("osm", 42.36, -71.06, ["competition_pressure:gym"])
    assert langt == {}, "ett värde från Boston svarade för New York"
    H.reset()


def test_the_nearest_row_wins_and_the_distance_travels_with_it():
    """En mätning från grannkommunen är ett svagare underlag än en från
    platsen, och skillnaden får inte försvinna."""
    H.reset()
    nu = time.time()
    H.store_rows([
        {"source": "osm", "region_code": "nara", "lat": 40.72,
         "lon": -74.01, "signal_id": "competition_pressure:gym",
         "value": 2.0, "observed_at": nu},
        {"source": "osm", "region_code": "langre", "lat": 40.85,
         "lon": -74.01, "signal_id": "competition_pressure:gym",
         "value": 9.0, "observed_at": nu}])
    r = H.read("osm", 40.71, -74.01, ["competition_pressure:gym"])
    rad = r["competition_pressure:gym"]
    assert rad["value"] == 2.0 and rad["region_code"] == "nara"
    assert 0 <= rad["distance_km"] < 3
    H.reset()


# ── Förfrågningsvägen ───────────────────────────────────────────────────
def test_the_request_path_cannot_make_a_network_call():
    """Bevisat, inte antaget: en transport som kastar vid anrop visar att
    HarvestedSource bara läser lagret."""
    from engine.datasources.adapters import HarvestedSource
    from engine.models import Location

    H.reset()
    nu = time.time()
    H.store_rows([{"source": "osm", "region_code": "nyc", "lat": 40.71,
                   "lon": -74.01, "signal_id": "competition_pressure:gym",
                   "value": 6.0, "observed_at": nu, "observed_count": 6}])
    import urllib.request
    riktig = urllib.request.urlopen

    def spring(*a, **kw):
        raise AssertionError("förfrågningsvägen gjorde ett nätanrop")

    urllib.request.urlopen = spring
    try:
        sig, extras = HarvestedSource().fetch(
            Location(40.71, -74.01), "gym", ["competition_pressure"])
    finally:
        urllib.request.urlopen = riktig
    assert sig["competition_pressure"].value == 6.0
    assert sig["competition_pressure"].source == "osm"
    assert sig["competition_pressure"].quality < 1.0
    assert "km from the point" in extras["harvested"][
        "competition_pressure"]["basis_en"]
    H.reset()


def test_the_industry_decides_which_count_answers():
    """Utan branschen i nyckeln hade frisörernas antal svarat för
    bilverkstäderna."""
    from engine.datasources.adapters import HarvestedSource
    from engine.models import Location

    H.reset()
    nu = time.time()
    H.store_rows([
        {"source": "osm", "region_code": "nyc", "lat": 40.71, "lon": -74.01,
         "signal_id": "competition_pressure:frisor", "value": 9.0,
         "observed_at": nu},
        {"source": "osm", "region_code": "nyc", "lat": 40.71, "lon": -74.01,
         "signal_id": "competition_pressure:bilverkstad", "value": 1.0,
         "observed_at": nu}])
    k = HarvestedSource()
    loc = Location(40.71, -74.01)
    assert k.fetch(loc, "frisor", ["competition_pressure"])[0][
        "competition_pressure"].value == 9.0
    assert k.fetch(loc, "bilverkstad", ["competition_pressure"])[0][
        "competition_pressure"].value == 1.0
    # en bransch utan OSM-tagg får inget svar alls, inte ett lånat
    assert k.fetch(loc, "raketfabrik", ["competition_pressure"])[0] == {}
    H.reset()


# ── Doktrinen ───────────────────────────────────────────────────────────
def test_a_mapped_place_is_never_an_establishment_count():
    """OSM får fylla observerat utbud men aldrig etableringsräkningen.
    Att blanda ihop dem vore att uppgradera ett svagare underlag tyst."""
    for s in H.SOURCES.values():
        for sid in s["signals"]:
            assert "establish" not in sid, sid
    assert "register" in H.SOURCES["osm"]["cannot_en"]
    assert "saturation" in H.SOURCES["osm"]["cannot_en"]


def test_osm_says_that_absence_is_not_absence():
    t = H.SOURCES["osm"]["cannot_en"]
    assert "Crowd-mapped" in t and "not absence on the ground" in t
    assert H.SOURCES["osm"]["quality"] < 1.0


def test_nothing_is_switched_on_by_accident():
    """Ingen källa får svara förrän någon bett om det — samma doktrin som
    resten: osatt är inte trasigt."""
    _av("LANDVEX_OPEN_DATA", "LANDVEX_OSM_URL", "LANDVEX_METEO_URL")
    assert H.open_data_on() is False
    for sid in H.SOURCES:
        assert H.url_for(sid) == "", sid
        assert H.harvest_region(sid, _REGION, "us") == []


def test_the_switch_only_turns_on_what_needs_no_key():
    _pa({"LANDVEX_OPEN_DATA": "on"})
    try:
        for sid, s in H.SOURCES.items():
            if s["keyless"]:
                assert H.url_for(sid) == s["default_url"].rstrip("/"), sid
            else:
                assert H.url_for(sid) == "", f"{sid} slogs på utan nyckel"
    finally:
        _av("LANDVEX_OPEN_DATA")


def test_every_source_declares_what_it_needs_and_what_it_cannot_do():
    from engine.deployment import ENVIRONMENT

    for sid, s in H.SOURCES.items():
        assert s["env"] in ENVIRONMENT, (
            f"{sid} läser {s['env']} som inte står i registret")
        assert s["max_age_days"] > 0, sid
        assert 0 < s["quality"] <= 1.0, sid
        assert len(s["cannot_en"]) > 60, sid
        assert s["default_url"].startswith(("https://", "feeds://")), sid
        # En källa som fyller EN signal ska säga vilken. En som inte
        # fyller någon (nyheter) ska säga varför den ändå finns — annars
        # ser den ut som en glömd rad.
        if not s["signals"]:
            assert "never a signal" in s["fills_en"].lower() or \
                "never becomes a signal" in s["cannot_en"].lower(), sid


def test_the_scheduler_can_run_a_harvest_and_says_when_it_is_off():
    from engine import scheduler as S

    _av("LANDVEX_OPEN_DATA", "LANDVEX_OSM_URL")
    S.reset()
    S.save_job(S.job("skord", "harvest", tenant="t",
                     params={"source": "osm", "market": "us"}))
    r = S.run_due("t", 1_800_000_000.0)["ran"][0]
    assert r["skipped"] is True and r["harvested"] == 0
    assert "LANDVEX_OPEN_DATA=on" in r["detail_en"]
    S.reset()


def test_an_unknown_harvest_source_is_an_error_not_a_quiet_zero():
    from engine import scheduler as S

    S.reset()
    S.save_job(S.job("fel", "harvest", tenant="t",
                     params={"source": "gissning"}))
    r = S.run_due("t", 1_800_000_000.0)
    assert r["ran"][0]["status"] == "error"
    assert "unknown harvest source" in r["errors"][0]["why_en"]
    S.reset()


def test_the_catalog_states_why_it_is_harvested_at_all():
    k = H.catalog()
    assert "700 ms" in k["principle_en"]
    assert "ABSENT" in k["cannot_en"]
    assert k["industries_mapped"] == len(H.OSM_TAGS)
    assert json.dumps(k)          # inga anropbara objekt i svaret


def test_open_meteo_parses_the_documented_shape():
    _pa({"LANDVEX_METEO_URL": "https://x"})
    try:
        svar = json.dumps({"current": {"temperature_2m": 3.4,
                                       "precipitation": 0.2}}).encode()
        rader = H.harvest_region("open_meteo", _REGION, "us",
                                 transport=_transport(svar))
        per = {r["signal_id"]: r["value"] for r in rader}
        assert per == {"air_temperature_c": 3.4, "precipitation_mm": 0.2}
        assert "model reanalysis" in H.SOURCES["open_meteo"]["cannot_en"]
    finally:
        _av("LANDVEX_METEO_URL")


def test_a_source_that_answers_with_nonsense_stores_nothing():
    """En trasig skörd får inte lämna halva rader efter sig."""
    _pa({"LANDVEX_OSM_URL": "https://x"})
    try:
        assert H.harvest_region("osm", _REGION, "us",
                                transport=_transport(b"inte json")) == []
    finally:
        _av("LANDVEX_OSM_URL")


def test_the_harvest_url_is_form_encoded_the_way_overpass_wants_it():
    _pa({"LANDVEX_OSM_URL": "https://x"})
    sedda = {}

    def t(url, payload, timeout):
        sedda["url"], sedda["payload"] = url, payload
        return _overpass_svar(_alla(1))

    try:
        H.harvest_region("osm", _REGION, "us", transport=t)
        assert sedda["url"] == "https://x"
        krop = urllib.parse.parse_qs(sedda["payload"].decode())
        assert krop["data"][0].startswith("[out:json]")
    finally:
        _av("LANDVEX_OSM_URL")


def test_coverage_only_counts_what_has_actually_been_harvested():
    """En källa som är påslagen men aldrig körd kan inte svara.
    Täckningsytan får inte påstå något annat — det vore att räkna en
    avsikt som en mätning."""
    from engine.coverage import coverage
    from engine.datasources.adapters import HarvestedSource

    H.reset()
    _pa({"LANDVEX_OPEN_DATA": "on"})       # påslagen, men inget skördat
    try:
        assert HarvestedSource().connected is False
        assert coverage("us")["real_weight"] == 0.0
        H.store_rows([{"source": "osm", "region_code": "nyc", "market": "us",
                       "signal_id": "competition_pressure:gym", "value": 4.0,
                       "lat": 40.71, "lon": -74.01,
                       "observed_at": time.time()}])
        k = HarvestedSource()
        assert k.connected is True and k.markets == ("us",)
        assert coverage("us")["real_weight"] > 0.0
        # och en marknad som inte skördats rör sig inte
        assert "de" not in k.markets
    finally:
        _av("LANDVEX_OPEN_DATA")
        H.reset()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
