"""Det andra nätet — och att det faktiskt går att koppla in och proba.

En andra leverantör som ingen kan konfigurera, ingen kan proba och som
inte syns i /v1/sensors är inte ett andra nät. Den är en klass i en fil.
Sviten prövar därför tre saker utöver parsningen:

  * varje leverantör har en miljövariabel som REGISTRET känner
    (engine/deployment.ENVIRONMENT) — annars går den inte att sätta i
    produktion,
  * varje leverantör har en probe — annars kan `verified_live` aldrig
    sättas för den, och ett nät som inte går att bevisa är inget bevis,
  * varje leverantör syns i klientstatusen.

Fixturerna är API:ernas DOKUMENTERADE svarsform. Att de stämmer med
verkligheten kan bara ett anrop avgöra, och nätet är spärrat här — det
är därför `verified_live` står kvar på False överallt.

Kör: python3 -m tests.test_sensor_providers
"""
from __future__ import annotations

import json

from engine.datasources import sensor_apis as S


def _fast(svar: object):
    """Transport som alltid ger samma dokumenterade svar."""
    def transport(*a):
        return json.dumps(svar).encode("utf-8")
    return transport


def _trasig(*a):
    raise OSError("nätet svarade inte")


# ── Luft: Sensor.Community ──────────────────────────────────────────────
_SC_SVAR = [
    {"sensor": {"id": 1, "sensor_type": {"name": "SDS011"}},
     "sensordatavalues": [{"value_type": "P1", "value": "14.2"},
                          {"value_type": "P2", "value": "7.1"}]},
    {"sensor": {"id": 2, "sensor_type": {"name": "SDS011"}},
     "sensordatavalues": [{"value_type": "P1", "value": "16.2"},
                          {"value_type": "P2", "value": "8.9"},
                          {"value_type": "temperature", "value": "3.0"}]},
]


def test_citizen_air_parses_the_documented_shape():
    c = S.SensorCommunityAir(transport=_fast(_SC_SVAR),
                             base_url="https://x")
    r = c.latest(59.31, 18.07)
    assert r["values"] == {"pm10_ug_m3": 15.2, "pm25_ug_m3": 8.0}
    assert r["readings"] == {"pm10_ug_m3": 2, "pm25_ug_m3": 2}
    assert r["sensors"] == 2 and r["measured"] is True


def test_citizen_air_says_that_no2_is_absent_not_zero():
    """Nätet mäter inte NO₂. Att mappa in det på något som råkar likna
    hade gjort en lucka till ett mätvärde."""
    c = S.SensorCommunityAir(transport=_fast(_SC_SVAR), base_url="https://x")
    r = c.latest(59.31, 18.07)
    assert "no2_ug_m3" not in r["values"]
    assert "NO₂ is not" in r["basis_en"] and "not zero" in r["basis_en"]
    # och den säger vad billiga sensorer INTE klarar
    assert "humid" in r["basis_en"].lower()


def test_a_value_that_cannot_be_read_is_not_counted_as_zero():
    trasigt = [{"sensor": {"id": 9},
                "sensordatavalues": [{"value_type": "P1", "value": "n/a"},
                                     {"value_type": "P2", "value": "5.0"}]}]
    c = S.SensorCommunityAir(transport=_fast(trasigt), base_url="https://x")
    r = c.latest(59.31, 18.07)
    assert "pm10_ug_m3" not in r["values"]
    assert r["values"]["pm25_ug_m3"] == 5.0


# ── Vatten: USGS ────────────────────────────────────────────────────────
def _usgs(kod: str, varde: str) -> dict:
    return {"value": {"timeSeries": [{
        "sourceInfo": {"siteName": "MISSISSIPPI RIVER AT ST. LOUIS"},
        "variable": {"variableCode": [{"value": kod}]},
        "values": [{"value": [{"value": varde,
                               "dateTime": "2026-07-28T12:00:00"}]}]}]}}


def test_usgs_water_converts_into_the_units_the_other_network_uses():
    """Två nät jämförda i olika enheter blir 'conflicting' av ren
    aritmetik. Konverteringen sker i klienten och står i svaret."""
    c = S.UsgsWater(transport=_fast(_usgs("00060", "1000")),
                    base_url="https://x")
    r = c.latest("discharge_m3s", "07010000")
    assert r["raw_value"] == 1000.0 and r["raw_unit"] == "ft³/s"
    assert r["unit"] == "m³/s"
    assert r["value"] == round(1000 * 0.0283168, 3) == 28.317
    assert "Converted from ft³/s to m³/s" in r["basis_en"]

    c2 = S.UsgsWater(transport=_fast(_usgs("00065", "10")),
                     base_url="https://x")
    r2 = c2.latest("water_level_cm", "07010000")
    assert r2["value"] == 304.8 and r2["unit"] == "cm"


def test_usgs_no_reading_sentinel_is_not_a_measurement():
    """NWIS skriver -999999 när mätaren inte gav något. Ett sentinelvärde
    som slinker igenom blir ett vattenstånd på minus tre kilometer."""
    c = S.UsgsWater(transport=_fast(_usgs("00065", "-999999")),
                    base_url="https://x")
    assert c.latest("water_level_cm", "07010000") is None


def test_usgs_ignores_a_series_for_another_parameter():
    c = S.UsgsWater(transport=_fast(_usgs("00060", "1000")),
                    base_url="https://x")
    assert c.latest("water_level_cm", "07010000") is None


# ── Satellit: NASA CMR ──────────────────────────────────────────────────
_CMR = {"feed": {"entry": [
    {"id": "G1", "time_start": "2026-05-02T10:00:00Z", "cloud_cover": "8.0"},
    {"id": "G2", "time_start": "2026-05-18T10:00:00Z", "cloud_cover": "12.5"},
    {"id": "G3", "time_start": "2026-06-03T10:00:00Z", "cloud_cover": "88.0"},
    {"id": "G4", "time_start": "2026-06-19T10:00:00Z"},
]}}


def test_cmr_cloud_cover_arrives_as_a_string_and_is_still_compared():
    """CMR skriver molntäcket som sträng. En jämförelse mot ett tal ger
    TypeError, scenen räknas som oanvändbar, och en tom karta ser ut som
    'ingen passage' i stället för som en bugg."""
    c = S.NasaCmrScenes(transport=_fast(_CMR), base_url="https://x")
    r = c.coverage(59.31, 18.07, start="2026-05-01", end="2026-07-01")
    assert r["scenes"] == 4
    assert r["usable_scenes"] == 2          # 8.0 och 12.5 under 30 %
    assert r["comparable"] is True
    assert r["collection"] == "LANDSAT_OT_C2_L2"


def test_one_usable_scene_is_no_comparison_at_all():
    en = {"feed": {"entry": [{"id": "G1", "cloud_cover": "5.0"},
                             {"id": "G2", "cloud_cover": "95.0"}]}}
    c = S.NasaCmrScenes(transport=_fast(en), base_url="https://x")
    r = c.coverage(59.31, 18.07, start="2026-05-01", end="2026-07-01")
    assert r["usable_scenes"] == 1 and r["comparable"] is False
    assert "absence of observation" in r["basis_en"]


# ── Seismik: EMSC ───────────────────────────────────────────────────────
_FDSN = {"features": [{"properties": {"mag": 3.1}},
                      {"properties": {"mag": 4.4}},
                      {"properties": {"mag": None}}]}


def test_emsc_and_usgs_are_summarised_by_the_same_code():
    """Skiljer sig två kataloger åt ska skillnaden komma från näten, inte
    från två olika parsningar."""
    e = S.EmscSeismic(transport=_fast(_FDSN), base_url="https://x")
    u = S.UsgsSeismic(transport=_fast(_FDSN), base_url="https://x")
    re_ = e.events(59.31, 18.07, radius_km=500.0, min_magnitude=1.0)
    ru = u.events(59.31, 18.07, radius_km=500.0, min_magnitude=1.0)
    for r in (re_, ru):
        assert r["events"] == 3 and r["with_magnitude"] == 2
        assert r["max_magnitude"] == 4.4
    assert re_["source"] != ru["source"]        # men de säger vilka de är
    assert "magnitude for the same event" in re_["basis_en"]


def test_emsc_asks_in_degrees_because_that_is_what_it_takes():
    """EMSC tar radien i grader. Skickas kilometer blir sökradien hundra
    gånger för stor — och svaret ser fullt rimligt ut."""
    sedda = {}

    def transport(url, timeout):
        sedda["url"] = url
        return json.dumps(_FDSN).encode("utf-8")

    c = S.EmscSeismic(transport=transport, base_url="https://x")
    c.events(59.31, 18.07, radius_km=222.0, min_magnitude=2.0)
    assert "maxradius=2.0" in sedda["url"]
    assert "maxradiuskm" not in sedda["url"]


# ── AIS: BarentsWatch ───────────────────────────────────────────────────
_AIS = [{"mmsi": 1, "speedOverGround": 12.0},
        {"mmsi": 2, "speedOverGround": 0.1},
        {"mmsi": 3, "speedOverGround": None}]


def _token_transport(*a):
    return json.dumps({"access_token": "T", "expires_in": 3600}).encode()


def test_barentswatch_exchanges_credentials_before_it_reads():
    burna = {}

    def transport(url, token, timeout):
        burna["token"] = token
        return json.dumps(_AIS).encode("utf-8")

    c = S.BarentsWatchAis(transport=transport, base_url="https://x",
                          client_id="i", client_secret="s",
                          token_transport=_token_transport)
    r = c.vessels()
    assert burna["token"] == "T"
    assert r["vessels"] == 3 and r["under_way"] == 1


def test_barentswatch_without_credentials_refuses_rather_than_returning_none_vessels():
    """En tom lista läses som 'inga fartyg i farvattnet'. Det är inte
    samma sak som 'vi har inte ansökt om åtkomst än'."""
    c = S.BarentsWatchAis(base_url="https://x", client_id="",
                          client_secret="")
    assert c.connected is False
    assert c.vessels() is None
    c2 = S.BarentsWatchAis(base_url="", client_id="i", client_secret="s")
    assert c2.connected is False


def test_a_failed_token_exchange_is_recorded_where_the_probe_looks():
    def trasig_token(*a):
        raise OSError("proxy nekade CONNECT")

    c = S.BarentsWatchAis(base_url="https://x", client_id="i",
                          client_secret="s", token_transport=trasig_token)
    assert c.vessels() is None
    assert isinstance(c.last_error, OSError)


# ── Gemensamt för ALLA leverantörer ─────────────────────────────────────
def test_no_provider_invents_an_answer_when_it_is_not_configured():
    for cls in S.all_clients():
        c = cls(base_url="")
        assert c.connected is False, cls.__name__
        assert c.describe()["connected"] is False


def test_no_provider_claims_to_be_verified_live():
    """Nätet är policyspärrat i byggmiljön. En flagga satt utan ett svar
    från riktig värd är precis vad proben finns för att förhindra."""
    for cls in S.all_clients():
        assert cls.verified_live is False, cls.__name__


def test_every_provider_can_be_switched_on_from_the_environment_registry():
    from engine.deployment import ENVIRONMENT

    for cls in S.all_clients():
        assert cls.ENV, f"{cls.__name__} saknar ENV"
        assert cls.ENV in ENVIRONMENT, (
            f"{cls.__name__} läser {cls.ENV} som inte står i "
            f"engine/deployment.ENVIRONMENT — den går inte att koppla in "
            f"i produktion, och .env.example nämner den inte")


def test_every_provider_has_a_probe():
    """Utan probe kan verified_live aldrig sättas för nätet, och ett nät
    som inte går att bevisa är inget bevis."""
    from scripts.sensor_probe import PROBES

    for sensor_class, grupp in S.PROVIDERS.items():
        for cls in grupp:
            nyckel = f"{sensor_class}:{cls.id}"
            assert nyckel in PROBES, f"ingen probe för {nyckel}"


def test_every_provider_shows_up_in_the_client_status():
    ids = {r["client"] for r in S.clients_status()}
    for cls in S.all_clients():
        assert cls.id in ids, cls.__name__


def test_the_networks_that_already_existed_are_counted_as_one_not_zero():
    """grid_telemetry och field_observation stod som 0 leverantörer fast
    båda HAR ett nät. Nollan gjorde mer skada än att bara se snål ut:
    klasserna föll ur listan över dem som saknar ett ANDRA nät, så luckan
    syntes inte i lägesrapporten alls."""
    assert S.independent_count("field_observation") == 1
    assert S.independent_count("grid_telemetry") == 2      # SVK + ENTSO-E
    from engine.sensors import catalog

    rader = {r["id"]: r for r in catalog()["sensors"]}
    for sid in ("grid_telemetry", "field_observation"):
        assert rader[sid]["state"] == "adapter"
        assert rader[sid]["independent_providers"] >= 1, sid


def test_the_wrapper_and_the_client_underneath_never_disagree():
    """En wrapper som säger 'ej ansluten' om en klient som är det gör
    statusbilden till en gissning."""
    for cls in (S.SvkGrid, S.QuixzoomField):
        assert cls(base_url="").connected is False
        c = cls(base_url="https://x")
        assert c.connected is True and c._client.connected is True


def test_entsoe_refuses_without_the_token_it_has_to_be_applied_for():
    c = S.EntsoeGrid(base_url="https://x", token="")
    assert c.connected is False
    assert c.load("10Y1001A1001A46L", start="202607280000",
                  end="202607282300") is None


def test_entsoe_reads_xml_and_does_not_pretend_it_is_json():
    xml = ('<?xml version="1.0"?><GL_MarketDocument xmlns="urn:iec:x">'
           '<TimeSeries><Period><Point><quantity>10500</quantity></Point>'
           '<Point><quantity>10700</quantity></Point></Period>'
           '</TimeSeries></GL_MarketDocument>')

    def transport(url, timeout):
        return xml.encode("utf-8")

    c = S.EntsoeGrid(transport=transport, base_url="https://x", token="T")
    r = c.load("10Y1001A1001A46L", start="202607280000", end="202607282300")
    assert r["points"] == 2 and r["latest_mw"] == 10700.0
    assert r["mean_mw"] == 10600.0
    assert "revised for" in r["basis_en"]


def test_an_xml_answer_that_declares_entities_is_refused_unparsed():
    """`xml.etree` expanderar entiteter; `defusedxml` är ett beroende
    kärnan inte får ta. Båda attackerna kräver en DEKLARATION, så ett
    dokument som bär en avvisas innan parsern ser det."""
    ond = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
           b'<!ENTITY lol2 "&lol;&lol;&lol;">]>'
           b'<r><quantity>&lol2;</quantity></r>')

    def transport(url, timeout):
        return ond

    c = S.EntsoeGrid(transport=transport, base_url="https://x", token="T")
    assert c.load("SE3", start="202607280000", end="202607282300") is None
    # och taket gäller även ett i övrigt oskyldigt men enormt svar
    try:
        S._entsoe_kvantiteter(b"<r/>" + b"x" * (S._XML_MAX_BYTES + 1))
    except ValueError as e:
        assert "over the" in str(e)
    else:
        raise AssertionError("storleken hade inget tak")


def test_a_second_provider_is_a_second_network_not_a_second_class():
    for sensor_class, grupp in S.PROVIDERS.items():
        klasser = {c.sensor_class for c in grupp}
        assert klasser == {sensor_class}, sensor_class
        ider = [c.id for c in grupp]
        assert len(ider) == len(set(ider)), sensor_class


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
