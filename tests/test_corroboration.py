"""Vad ett andra oberoende nät faktiskt tillför.

Fler sensorer gör inte ett underlag robustare av sig självt. Tio
mätpunkter på samma väg, från samma myndighet, genom samma
insamlingskedja, faller tillsammans när kedjan gör det — och tio
samstämmiga tal från ett trasigt system ser precis ut som tio
samstämmiga tal från ett fungerande.

Kör: python3 -m tests.test_corroboration
"""
from __future__ import annotations

from engine import corroboration as C


def _k(klass, **kw):
    return {"sensor_class": klass, **kw}


def test_one_network_can_never_corroborate_itself():
    """Kärnregeln. Hur perfekt en källa än stämmer med sina egna
    avläsningar är det fortfarande en källa."""
    r = C.assess([_k("road_flow", value=820), _k("road_flow", value=820),
                  _k("road_flow", value=820)])
    assert r["independent_sources"] == 1
    assert r["strength"] in ("weak", "none")
    assert r["strength"] != "strong"


def test_two_networks_of_different_kinds_that_agree_is_the_strongest_case():
    r = C.assess([_k("road_flow", value=820), _k("air_quality", value=812)])
    assert r["independent_sources"] == 2
    assert len(r["modalities"]) == 2
    assert r["strength"] == "strong"


def test_two_networks_measuring_the_same_quantity_corroborate_less():
    """Samma fysiska storhet betyder att de kan dela systematiskt fel."""
    r = C.assess([_k("road_flow", value=820),
                  _k("parking_occupancy", value=800)])
    assert r["modalities"] == ["vehicle_count"]
    assert r["strength"] == "moderate", r["strength"]


def test_disagreement_is_a_finding_not_weak_support():
    """Det här var ett riktigt logikfel i första versionen: två OENSE nät
    fick 'strong', eftersom oberoende och olik modalitet räknades in medan
    oenigheten bara lät bli att lägga till. Två nät som pekar åt olika
    håll är sämre underlag än ett ensamt — minst ett har fel, och det går
    inte att veta vilket."""
    r = C.assess([_k("road_flow", value=820), _k("air_quality", value=180)])
    assert r["conflicting"] is True
    assert r["strength"] == "conflicting"
    assert r["score"] <= 0.25
    assert "disagree" in r["why_en"]


def test_no_comparable_numbers_is_not_the_same_as_disagreement():
    """Två nät kan bekräfta ATT något hände utan att mäta samma storhet.
    Att kalla det oenighet vore att hitta på en konflikt som inte finns."""
    r = C.assess([_k("earth_observation"), _k("field_observation")])
    assert r["agreement"] is None
    assert r["conflicting"] is False
    assert C.assess([_k("road_flow", value=1)])["agreement"] is None


def test_unmeasured_sources_do_not_count_toward_corroboration():
    r = C.assess([_k("road_flow", value=820),
                  _k("air_quality", value=812, measured=False)])
    assert r["independent_sources"] == 1
    assert r["unmeasured_ignored"] == 1
    assert r["strength"] != "strong"


def test_three_independent_networks_beat_two():
    tva = C.assess([_k("road_flow", value=820), _k("air_quality", value=815)])
    tre = C.assess([_k("road_flow", value=820), _k("air_quality", value=815),
                    _k("mobility_flow", value=818)])
    assert tre["score"] > tva["score"]


def test_the_strength_is_a_band_and_says_why_it_is_not_a_percentage():
    r = C.assess([_k("road_flow", value=820), _k("air_quality", value=812)])
    assert isinstance(r["strength"], str)
    assert "84%" in r["not_a_probability_en"]
    assert "multiplied onward" in r["not_a_probability_en"]


def test_independence_names_the_three_cases_distinctly():
    samma = C.independence("road_flow", "road_flow")
    delad = C.independence("road_flow", "parking_occupancy")
    olik = C.independence("road_flow", "air_quality")
    assert samma["independent"] is False
    assert delad["independent"] and not delad["different_modality"]
    assert olik["independent"] and olik["different_modality"]
    assert len({samma["why_en"], delad["why_en"], olik["why_en"]}) == 3
    assert "systematic error" in delad["why_en"]


def test_every_sensor_class_has_a_modality():
    """En klass utan modalitet faller tillbaka på sitt eget namn och
    ser då ut som sin egen modalitet — vilket överdriver oberoendet."""
    from engine.sensors import SENSORS
    utan = sorted(set(SENSORS) - set(C.MODALITY))
    assert not utan, f"sensorklasser utan modalitet: {utan}"


def test_the_catalog_states_the_principle_rather_than_implying_it():
    c = C.catalog()
    assert "not more robust" in c["principle_en"]
    assert c["single_source_ceiling"] == "weak"
    assert {b["band"] for b in c["bands"]} == {"strong", "moderate",
                                               "weak", "none"}
    # Varje modalitet ska bära minst en klass, annars är kartan bara text.
    for m, klasser in c["modalities"].items():
        assert klasser, m


def test_two_networks_in_the_same_class_are_two_sources():
    """Modulens EGET exempel på oberoende — Trafikverket och Digitraffic —
    räknades som en enda källa, eftersom oberoende mättes på klass och
    båda är road_flow. Taket 'a single network cannot corroborate itself'
    slog alltså till på just det par docstringen valt som förebild."""
    r = C.assess([
        {"sensor_class": "road_flow", "network": "trafikverket",
         "value": 820},
        {"sensor_class": "road_flow", "network": "digitraffic_road",
         "value": 800}])
    assert r["independent_sources"] == 2
    assert r["capped_by_single_source"] is False
    assert r["strength"] == "moderate"
    assert r["networks"] == ["digitraffic_road", "trafikverket"]
    assert r["sensor_classes"] == ["road_flow"]


def test_two_networks_in_the_same_class_still_never_reach_strong():
    """De delar modalitet och kan bära samma systematiska fel. Bättre än
    ett nät, sämre än ett nät plus ett satellitbevis."""
    samma = C.assess([
        {"sensor_class": "road_flow", "network": "trafikverket", "value": 800},
        {"sensor_class": "road_flow", "network": "digitraffic_road",
         "value": 800}])
    olika = C.assess([
        {"sensor_class": "road_flow", "network": "trafikverket", "value": 800},
        {"sensor_class": "earth_observation", "network": "copernicus_stac",
         "value": 800}])
    assert samma["strength"] == "moderate"
    assert olika["strength"] == "strong"
    assert samma["score"] < olika["score"]


def test_two_networks_that_disagree_are_still_a_finding():
    r = C.assess([
        {"sensor_class": "seismic", "network": "usgs", "value": 4.4},
        {"sensor_class": "seismic", "network": "emsc", "value": 1.2}])
    assert r["conflicting"] is True and r["strength"] == "conflicting"


def test_the_same_network_twice_is_not_a_second_opinion():
    r = C.assess([
        {"sensor_class": "road_flow", "network": "trafikverket", "value": 820},
        {"sensor_class": "road_flow", "network": "trafikverket", "value": 818}])
    assert r["independent_sources"] == 1
    assert r["strength"] not in ("moderate", "strong")


def test_no_single_network_can_ever_reach_moderate_whatever_it_says():
    """Uttömmande, inte exemplifierande.

    Taket SINGLE_SOURCE_CEILING är en andra spärr på en dörr poängen
    redan bommar: med ett enda nät kan summan aldrig överstiga 0,45
    (0,25 för olika modalitet + 0,20 för perfekt samstämmighet), och
    +0,45 för oberoende kräver två nät. Testet visar det genom att pröva
    varje kombination som går att bygga med ett nät i stället för att
    lita på att en flagga sätts.
    """
    klasser = sorted(C.MODALITY)
    for a in klasser:
        for b in klasser:
            for varden in ((800, 800), (800, 799), (0, 0), (5, 5000)):
                r = C.assess([
                    {"sensor_class": a, "network": "ett_nat",
                     "value": varden[0]},
                    {"sensor_class": b, "network": "ett_nat",
                     "value": varden[1]}])
                assert r["independent_sources"] == 1, (a, b)
                assert r["score"] <= 0.45, (a, b, varden, r["score"])
                assert r["strength"] in ("none", "weak", "conflicting"), (
                    a, b, varden, r["strength"])


def test_leaving_the_network_out_changes_nothing():
    """Bakåtkompatibilitet, mätt: ett anrop som inte känner till fältet
    ska få exakt samma tal som före ändringen."""
    utan = C.assess([{"sensor_class": "road_flow", "value": 820},
                     {"sensor_class": "weather", "value": 800}])
    med = C.assess([
        {"sensor_class": "road_flow", "network": "road_flow", "value": 820},
        {"sensor_class": "weather", "network": "weather", "value": 800}])
    assert utan["score"] == med["score"]
    assert utan["strength"] == med["strength"]
    assert utan["independent_sources"] == med["independent_sources"] == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
