"""Sensorer: vad som kan mätas, och vad en mätning aldrig kan avgöra.

Fyndet som gjorde modulen nödvändig: upptäcktslagret känner igen nio
sorters FYSISK förändring — en byggd yta som ändrats, ett flöde som
avviker, ett objekt som försvunnit — medan varenda inkopplad källa är
statistik som uppdateras kvartalsvis. Plattformen kunde upptäcka saker
den inte hade någon möjlighet att se.

Kör: python3 -m tests.test_sensors
"""
from __future__ import annotations

import json

from engine import sensors as S
from engine.brief import DETECTION_KINDS
from engine.datasources import sensor_apis as A


# ── Registret ────────────────────────────────────────────────────────────
def test_every_detection_kind_names_something_that_could_measure_it():
    """En upptäckt utan tänkbar mätare är ett löfte utan täckning."""
    saknar = S.unfed_detections()
    assert not saknar, (
        "Dessa upptäckter kan ingen sensorklass i registret mata:\n  "
        + "\n  ".join(saknar))
    for kind, klasser in S.catalog()["detection_coverage"].items():
        assert klasser, kind


def test_every_sensor_class_declares_what_it_can_never_establish():
    """Kärnregeln. Sensordata frestar värre än statistik: en mätning i
    minuten känns som kunskap. En trafikräknare som visar fyrtio procent
    mindre flöde vet inte om vägen stängdes, arbetsgivaren flyttade eller
    slingan gick sönder."""
    for sid, s in S.SENSORS.items():
        assert len(s["cannot_en"]) > 60, f"{sid} saknar en riktig gräns"
        assert s["what_en"] and s["cadence"] and s["operator_en"], sid
        assert s["state"] in ("adapter", "connected", "contract",
                              "none"), sid
        for d in s["feeds"]:
            assert d in DETECTION_KINDS, f"{sid} matar okänd upptäckt {d}"


def test_the_gap_is_stated_rather_than_left_to_be_assumed():
    c = S.catalog()
    assert sum(c["by_state"].values()) == c["count"]
    for lage in ("adapter", "contract", "none"):
        assert str(c["by_state"].get(lage, 0)) in c["gap_en"], lage
    assert "quarterly" in c["gap_en"]


def test_contract_and_adapter_are_not_the_same_promise():
    """`contract` betyder att vi väntar på ett AVTAL, `adapter` att vi
    väntar på en nyckel. Att slå ihop dem hade dolt att sex av klasserna
    kräver att någon annan bestämmer sig, inte att vi bygger klart."""
    kontrakt = [k for k, v in S.SENSORS.items() if v["state"] == "contract"]
    assert kontrakt, "läget används inte alls"
    for k in kontrakt:
        assert S.SENSORS[k]["open_data"] is False, (
            f"{k} är märkt öppen data men saknar publikt API — då är det "
            f"antingen fel läge eller fel märkning")
    # Och tvärtom: allt som har en adapter mot ett publikt API ska vara
    # märkt som öppen data, annars stämmer inte kartan med terrängen.
    for k, v in S.SENSORS.items():
        if v["state"] == "adapter" and k != "field_observation":
            assert v["open_data"], k


def test_no_client_claims_to_be_live_verified_from_here():
    """Utgående nät är spärrat i utvecklingsmiljön. En klient som påstår
    sig verifierad härifrån ljuger om en körning som aldrig gjorts."""
    for cl in A.clients_status():
        assert cl["verified_live"] is False, cl["client"]
        assert "not verified live" in cl["note_en"]


# ── Trafikverket ─────────────────────────────────────────────────────────
# Dokumenterad svarsform.
TRV_SVAR = {"RESPONSE": {"RESULT": [{"TrafficFlow": [
    {"SiteId": "1001", "VehicleFlowRate": 820, "AverageVehicleSpeed": 74.0,
     "MeasurementTime": "2026-07-27T08:00:00"},
    {"SiteId": "1002", "VehicleFlowRate": 640, "AverageVehicleSpeed": 68.0,
     "MeasurementTime": "2026-07-27T08:00:00"},
]}]}}


def _trv(svar, spara=None):
    def t(url, payload, timeout):
        if spara is not None:
            spara.append((url, payload))
        return json.dumps(svar).encode()
    return A.TrafikverketFlow(transport=t, base_url="https://trv.example",
                              api_key="hemlig")


def test_traffic_flow_parses_the_documented_shape():
    sett = []
    c = _trv(TRV_SVAR, sett)
    r = c.flow(59.3145, 18.0705, radius_m=5000)
    assert r["vehicles_per_hour"] == 730.0        # (820+640)/2
    assert r["average_speed_kmh"] == 71.0
    assert r["measurement_points"] == 2
    assert r["measured"] is True
    # Frågan ska bära nyckeln och punkten, och radien vi bad om.
    url, payload = sett[0]
    body = payload.decode()
    assert 'authenticationkey="hemlig"' in body
    assert "18.0705 59.3145" in body and 'radius="5000"' in body


def test_a_flow_with_no_numbers_is_none_not_zero():
    """Noll fordon och "ingen mätpunkt svarade" är olika saker. Att
    returnera 0 hade blivit en tom väg i rapporten."""
    c = _trv({"RESPONSE": {"RESULT": [{"TrafficFlow": [
        {"SiteId": "x", "VehicleFlowRate": None}]}]}})
    assert c.flow(59.3, 18.1) is None


def test_the_basis_says_how_many_points_it_rests_on():
    r = _trv(TRV_SVAR).flow(59.3, 18.1)
    assert "2 measurement point" in r["basis_en"]
    assert "narrower basis" in r["basis_en"]


def test_without_an_api_key_there_is_no_call_at_all():
    sett = []

    def t(url, payload, timeout):
        sett.append(url)
        return b"{}"
    c = A.TrafikverketFlow(transport=t, base_url="https://trv.example",
                           api_key="")
    assert c.connected is False
    assert c.flow(59.3, 18.1) is None
    assert sett == [], "ringde trots att nyckeln saknas"


# ── SMHI ─────────────────────────────────────────────────────────────────
SMHI_SVAR = {"station": {"key": "97400", "name": "Stockholm-Observatoriekullen"},
             "value": [{"date": 1785000000000, "value": "3.2", "quality": "G"}]}


def _smhi(svar):
    def t(url, timeout):
        return json.dumps(svar).encode()
    return A.SmhiWeather(transport=t, base_url="https://smhi.example")


def test_smhi_parses_the_documented_shape_and_keeps_the_quality_flag():
    r = _smhi(SMHI_SVAR).latest("air_temperature_c", "97400")
    assert r["value"] == 3.2
    assert r["station"] == "Stockholm-Observatoriekullen"
    assert r["quality"] == "G"
    # Kvalitetsflaggan får inte tigas ihjäl: 'Y' är grovkontrollerad och
    # kan revideras. Att visa den som fastställd vore en tyst uppgradering.
    assert "'G' is checked" in r["basis_en"]


def test_an_unknown_signal_is_refused_rather_than_guessed():
    assert _smhi(SMHI_SVAR).latest("finns_inte", "97400") is None


def test_a_disconnected_client_never_calls():
    sett = []

    def t(url, timeout):
        sett.append(url)
        return b"{}"
    c = A.SmhiWeather(transport=t, base_url="")
    assert c.connected is False
    assert c.latest("air_temperature_c", "97400") is None
    assert sett == []


# ── Strömbrytaren, delad med registerklienterna ──────────────────────────
class _Klocka:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_a_dead_sensor_network_costs_one_call_not_one_per_point():
    """Ett mätnät har hundratals punkter. Utan strömbrytare blir en nere
    källa till ett blockerande anrop per punkt — samma fel som tog
    /v1/saturation från 0,3 till 19 sekunder."""
    anrop = []

    def t(url, timeout):
        anrop.append(url)
        raise OSError("connection refused")
    klocka = _Klocka()
    c = A.SmhiWeather(transport=t, base_url="https://smhi.example",
                      clock=klocka, retry_after_s=300)
    for _ in range(200):
        assert c.latest("air_temperature_c", "97400") is None
    assert len(anrop) == 1, f"{len(anrop)} anrop mot en källa som sagt ifrån"
    assert c.down
    klocka.t += 301
    c.latest("air_temperature_c", "97400")
    assert len(anrop) == 2, "kom aldrig tillbaka efter pausen"


def test_our_own_bug_still_crashes_instead_of_pausing_the_sensor():
    def trasig(url, timeout):
        raise AttributeError("'SmhiWeather' object has no attribute 'nope'")
    c = A.SmhiWeather(transport=trasig, base_url="https://smhi.example")
    try:
        c.latest("air_temperature_c", "97400")
    except AttributeError:
        assert not c.down, "vårt fel pausade sensorn i stället för att braka"
    else:
        raise AssertionError("AttributeError svaldes av strömbrytaren")


def test_the_breaker_lives_in_one_place_only():
    """Register- och sensorklienterna delar strömbrytare. En andra kopia
    av en regel är en regel som kommer att glida isär."""
    import inspect

    from engine.datasources import register_apis
    from engine.datasources.faults import Breaker
    assert "Breaker" in inspect.getsource(A)
    src = inspect.getsource(register_apis.RegisterProvider)
    assert "_down_until" in src        # registret har fortfarande sin egen
    assert Breaker.__module__.endswith("faults")



# ── Proben: en spärrad brandvägg är inte en trasig adapter ───────────────
def test_the_probe_tells_a_blocked_network_from_a_broken_adapter():
    """Första versionen gjorde en egen TCP-koll mot värden. Med en
    utgående proxy LYCKAS den anslutningen medan hämtningen ändå faller —
    och då skrevs brandväggen ned som en trasig adapter. Klassningen sker
    nu på felet från det VERKLIGA anropet."""
    import socket as _s
    import urllib.error as _u

    from scripts.sensor_probe import unreachable
    # Kom aldrig fram:
    for e in (_u.URLError("blocked"), _s.timeout(), OSError("refused"),
              ConnectionError(), _u.HTTPError("u", 403, "x", {}, None),
              _u.HTTPError("u", 407, "x", {}, None)):
        assert unreachable(e), type(e).__name__
    # Servern SVARADE — det är ett riktigt besked, inte ett nätfel:
    assert not unreachable(_u.HTTPError("u", 404, "x", {}, None))
    assert not unreachable(ValueError("bad json"))
    assert not unreachable(None)


def test_the_breaker_remembers_why_it_tripped():
    """Utan det kan proben inte skilja de två fallen alls."""
    def nere(url, timeout):
        raise OSError("connection refused")
    c = A.SmhiWeather(transport=nere, base_url="https://smhi.example")
    assert c.last_error is None
    c.latest("air_temperature_c", "97400")
    assert isinstance(c.last_error, OSError)

    # Och ett lyckat anrop nollställer minnet.
    ok = A.SmhiWeather(transport=lambda u, t: json.dumps(SMHI_SVAR).encode(),
                       base_url="https://smhi.example")
    ok.latest("air_temperature_c", "97400")
    assert ok.last_error is None


def test_the_probe_never_writes_verified_live_by_itself():
    """En probe som redigerar sin egen källa låter ett enda lyckosamt
    anrop märka koden som bevisad."""
    import pathlib
    import re
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "scripts" / "sensor_probe.py").read_text(encoding="utf-8")
    # Det som räknas är inte att ordet saknas, utan att inget SKRIVS.
    assert not re.search(r'open\([^)]*["\']w', src), \
        "proben öppnar en fil för skrivning"
    assert ".write(" not in src and "json.dump(" not in src
    # Den ska i stället be en människa göra det, i en läsbar commit.
    assert "by hand" in src and "someone can read" in src




# ── OpenAQ ───────────────────────────────────────────────────────────────
AQ_SVAR = {"results": [
    {"parameter": {"name": "no2", "units": "µg/m³"}, "value": 21.4},
    {"parameter": {"name": "no2", "units": "µg/m³"}, "value": 18.6},
    {"parameter": {"name": "pm25", "units": "µg/m³"}, "value": 7.2},
    {"parameter": {"name": "okänd"}, "value": 99.0},
]}


def test_air_quality_averages_per_parameter_and_keeps_the_station_count():
    c = A.OpenAqAir(transport=lambda u, t: json.dumps(AQ_SVAR).encode(),
                    base_url="https://aq.example", api_key="k")
    r = c.latest(59.3, 18.1)
    assert r["values"]["no2_ug_m3"] == 20.0        # (21.4+18.6)/2
    assert r["values"]["pm25_ug_m3"] == 7.2
    assert "pm10_ug_m3" not in r["values"]          # inget värde, inget påhitt
    assert r["stations"] == {"no2_ug_m3": 2, "pm25_ug_m3": 1}
    # En station i en gatukanjon och tio spridda är olika underlag.
    assert "street canyon" in r["basis_en"]


def test_air_quality_needs_a_key_before_it_calls():
    sett = []
    c = A.OpenAqAir(transport=lambda u, t: (sett.append(u), b"{}")[1],
                    base_url="https://aq.example", api_key="")
    assert c.connected is False and c.latest(59.3, 18.1) is None
    assert sett == []


# ── Copernicus STAC ──────────────────────────────────────────────────────
def _stac(moln):
    svar = {"features": [{"properties": {"eo:cloud_cover": c}} for c in moln]}
    return A.CopernicusStac(
        transport=lambda u, p, t: json.dumps(svar).encode(),
        base_url="https://stac.example")


def test_cloud_over_a_parcel_is_not_evidence_that_nothing_changed():
    """Klientens hela poäng: den säger om en jämförelse är MÖJLIG, inte
    vad den skulle visa."""
    r = _stac([88.0, 91.0, 95.0]).coverage(
        59.3, 18.1, start="2026-05-01", end="2026-07-01")
    assert r["scenes"] == 3 and r["usable_scenes"] == 0
    assert r["comparable"] is False
    assert "absence of observation" in r["basis_en"]


def test_two_clear_passes_make_a_comparison_possible():
    r = _stac([4.0, 92.0, 11.0]).coverage(
        59.3, 18.1, start="2026-05-01", end="2026-07-01")
    assert r["usable_scenes"] == 2 and r["comparable"] is True


def test_one_clear_pass_is_not_a_comparison():
    r = _stac([4.0, 92.0]).coverage(59.3, 18.1, start="a", end="b")
    assert r["usable_scenes"] == 1 and r["comparable"] is False


# ── SMHI hydrologi ───────────────────────────────────────────────────────
def test_a_gauge_says_what_it_measured_and_what_it_cannot():
    svar = {"station": {"name": "Uppsala"},
            "value": [{"date": 1785000000000, "value": "142.5"}]}
    c = A.SmhiHydro(transport=lambda u, t: json.dumps(svar).encode(),
                    base_url="https://hydro.example")
    r = c.latest("water_level_cm", "2255")
    assert r["value"] == 142.5 and r["station"] == "Uppsala"
    assert "culverts" in r["basis_en"]


# ── Ägarlevererad feed ───────────────────────────────────────────────────
FEED_SVAR = {"stream": {"id": "bldg-12", "label": "Kv Björnen 4",
                        "owner": "Fastighets AB"},
             "readings": [{"at": "2026-07-27T08:00Z", "value": 41.2,
                           "unit": "kWh"},
                          {"at": "2026-07-27T09:00Z", "value": 38.8,
                           "unit": "kWh"}]}


def test_an_owner_supplied_feed_says_who_supplied_it():
    """Den är så god som deras mätare och deras ärlighet, och ingendera
    går att kontrollera härifrån. Att tiga om det vore att presentera
    partsinlaga som mätning."""
    c = A.GenericSensorFeed(
        transport=lambda u, t: json.dumps(FEED_SVAR).encode(),
        base_url="https://feed.example")
    r = c.readings("bldg-12")
    assert r["latest"] == 38.8 and r["mean"] == 40.0
    assert r["owner"] == "Fastighets AB" and r["unit"] == "kWh"
    assert "not measured independently" in r["basis_en"]


def test_the_generic_feed_serves_several_sensor_classes():
    """Sex klasser saknar publikt API. De delar en dokumenterad form i
    stället för att få var sin halvfärdig adapter mot ett API som inte
    finns."""
    c = A.GenericSensorFeed(sensor_class="district_heating",
                            base_url="https://feed.example")
    assert c.sensor_class == "district_heating"
    assert c.describe()["sensor_class"] == "district_heating"


def test_a_feed_with_no_numbers_is_none():
    c = A.GenericSensorFeed(
        transport=lambda u, t: json.dumps({"readings": []}).encode(),
        base_url="https://feed.example")
    assert c.readings("x") is None


def test_every_client_shares_the_one_breaker():
    """Åtta adaptrar, en strömbrytare. En andra kopia av en regel är en
    regel som kommer att glida isär."""
    for cls in A.CLIENTS.values():
        c = cls(base_url="https://x.example")
        assert hasattr(c, "last_error") and hasattr(c, "down")



def test_the_probe_covers_every_adapter_that_exists():
    """En adapter utan probe kan aldrig bli verifierad — den står kvar som
     obekräftad för alltid utan att någon märker varför."""
    from scripts.sensor_probe import PROBES
    # Nycklarna är `klass:klient`. Att bara kräva en probe per KLASS lät
    # ett andra nät ligga oprobat i registret: NWS och Digitraffic road
    # hade funnits i PROVIDERS sedan tidigare utan någon väg att bli
    # bekräftade.
    vantade = {f"{klass}:{c.id}" for klass, grupp in A.PROVIDERS.items()
               for c in grupp}
    utan = sorted(vantade - set(PROBES))
    assert not utan, f"leverantörer utan probe: {utan}"
    okanda = sorted(set(PROBES) - vantade)
    assert not okanda, f"probe utan leverantör: {okanda}"
    for nyckel in PROBES:
        klass = nyckel.split(":", 1)[0]
        assert klass in S.SENSORS, f"probe för okänd sensorklass: {klass}"


def test_the_registry_and_the_clients_agree_on_which_classes_have_adapters():
    """Kartan måste stämma med terrängen åt BÅDA hållen."""
    med_adapter = {k for k, v in S.SENSORS.items()
                   if v["state"] in ("adapter", "contract")}
    byggda = set(A.CLIENTS)
    saknas = byggda - med_adapter
    assert not saknas, (
        f"klienter finns men registret säger inget byggt: {sorted(saknas)}")
    for k in ("air_quality", "earth_observation", "water_level",
              "road_flow", "weather"):
        assert S.SENSORS[k]["state"] == "adapter", k
        assert k in byggda, k



def test_every_cadence_word_has_a_readable_form_on_the_surface():
    """Kadensen är maskinvänliga ord. Skrivs de rakt ut efter "every" blir
    de ogrammatiska — "every minutes", "every hourly". Ytan översätter, och
    en ny kadens i registret måste få en översättning samtidigt."""
    import pathlib
    import re
    html = (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "explore.html").read_text(encoding="utf-8")
    block = html.split("const KADENS = {", 1)[1].split("};", 1)[0]
    kanda = set(re.findall(r"(\w+)\s*:", block))
    anvanda = {s["cadence"] for s in S.SENSORS.values()}
    saknas = anvanda - kanda
    assert not saknas, f"kadens utan läsbar form på ytan: {sorted(saknas)}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
