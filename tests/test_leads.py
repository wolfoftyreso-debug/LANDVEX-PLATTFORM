"""Områdesspaning: en spårbar rad per adress, aldrig en anonymiserad
aggregering — och aldrig bilden.

Bevakar: okänt villkor och adresser utan koordinater vägras med namn;
en severity utom "none" kräver bevis, exakt som inspections.record();
leads() filtrerar på tröskeln och sorterar allvarligast först; en
okänd spanings-id ger en tom, förklarad lista i stället för ett
serverfel; dispatchen återanvänder MissionDispatcher rakt av och
vägrar likadant när quiXzoom inte är anslutet.

Kör: python3 -m tests.test_leads
"""
from __future__ import annotations

from engine import leads as LD


def _adress(id_="a1", address="12 Main St", lat=59.3, lon=18.0):
    return {"id": id_, "address": address, "lat": lat, "lon": lon}


class _StubDispatcher:
    """Fångar beställningen utan nät — samma yta som MissionDispatcher."""
    connected = True

    def __init__(self, *a, **kw):
        self.calls = []

    def dispatch(self, asset, rut, due_at, **kw):
        self.calls.append({"asset": asset, "rut": rut})
        return {"mission_id": f"m-{len(self.calls)}", "asset_id": asset["id"],
               "routine_id": rut["id"], "due_at": due_at, "source": "quixzoom"}


def test_an_unknown_condition_is_refused_by_name():
    try:
        LD.survey("s1", "x", "not_a_real_condition", [_adress()], tenant="t1")
    except LD.SurveyRefused as e:
        assert "not_a_real_condition" in str(e)
    else:
        raise AssertionError("okänt villkor accepterades")


def test_a_survey_needs_at_least_one_address():
    try:
        LD.survey("s1", "x", "window_cleanliness", [], tenant="t1")
    except LD.SurveyRefused as e:
        assert "at least one address" in str(e)
    else:
        raise AssertionError("tom adresslista accepterades")


def test_an_address_without_coordinates_is_refused():
    try:
        LD.survey("s1", "x", "window_cleanliness",
                 [{"id": "a1", "address": "12 Main St"}], tenant="t1")
    except LD.SurveyRefused as e:
        assert "coordinates" in str(e)
    else:
        raise AssertionError("adress utan koordinater accepterades")


def test_a_survey_needs_a_tenant():
    try:
        LD.survey("s1", "x", "window_cleanliness", [_adress()], tenant="")
    except LD.SurveyRefused as e:
        assert "tenant" in str(e)
    else:
        raise AssertionError("spaning utan tenant accepterades")


def test_a_severity_other_than_none_requires_evidence():
    LD.reset()
    try:
        LD.verdict("s1", "a1", "severe", tenant="t1")
    except LD.SurveyRefused as e:
        assert "evidence" in str(e)
    else:
        raise AssertionError("severe utan bevis accepterades")
    # "none" behöver inget bevis — det är en observation av frånvaro.
    v = LD.verdict("s1", "a1", "none", tenant="t1")
    assert v["severity"] == "none"


def test_the_image_itself_is_never_carried_by_the_verdict():
    v = LD.verdict("s1", "a1", "moderate", mission_id="m1", tenant="t1")
    for forbjudet in ("photo", "image", "media_url", "jpg", "png"):
        assert forbjudet not in v, v


def test_leads_filters_by_threshold_and_ranks_severest_first():
    LD.reset()
    surv = LD.survey(
        "s1", "Window survey", "window_cleanliness",
        [_adress("a1", "12 Main St"), _adress("a2", "14 Main St"),
        _adress("a3", "16 Main St")], tenant="t1")
    LD.save_survey(surv)
    LD.save_verdict(LD.verdict("s1", "a1", "light", mission_id="m1", tenant="t1"))
    LD.save_verdict(LD.verdict("s1", "a2", "severe", mission_id="m2", tenant="t1"))
    LD.save_verdict(LD.verdict("s1", "a3", "none", tenant="t1"))

    resultat = LD.leads("s1", min_severity="light", tenant="t1")
    assert resultat["count"] == 2
    assert [r["address_id"] for r in resultat["leads"]] == ["a2", "a1"], \
        "severe ska stå före light"

    bara_severe = LD.leads("s1", min_severity="severe", tenant="t1")
    assert bara_severe["count"] == 1
    assert bara_severe["leads"][0]["address_id"] == "a2"


def test_leads_never_carries_the_photo_only_the_reference():
    LD.reset()
    surv = LD.survey("s1", "x", "facade_condition", [_adress()], tenant="t1")
    LD.save_survey(surv)
    LD.save_verdict(LD.verdict("s1", "a1", "severe", evidence_ref="ref-1",
                              tenant="t1"))
    resultat = LD.leads("s1", tenant="t1")
    rad = resultat["leads"][0]
    assert "mission_id" in rad
    for forbjudet in ("photo", "image_url", "evidence_ref"):
        assert forbjudet not in rad, rad


def test_an_unknown_survey_id_gives_an_empty_explained_list():
    LD.reset()
    resultat = LD.leads("finns-inte", tenant="t1")
    assert resultat["count"] == 0 and resultat["leads"] == []
    assert "no such survey" in resultat["why_en"]


def test_tenants_never_see_each_others_surveys_or_leads():
    LD.reset()
    surv = LD.survey("s1", "x", "window_cleanliness", [_adress()], tenant="t1")
    LD.save_survey(surv)
    LD.save_verdict(LD.verdict("s1", "a1", "severe", mission_id="m1",
                              tenant="t1"))
    assert LD.all_surveys("t2") == []
    annan = LD.leads("s1", tenant="t2")
    assert annan["count"] == 0, "t2 kunde läsa t1:s spaning"


def test_dispatch_reuses_missiondispatcher_one_mission_per_address():
    LD.reset()
    surv = LD.survey("s1", "Window survey", "window_cleanliness",
                     [_adress("a1"), _adress("a2", "14 Main St")], tenant="t1")
    stub = _StubDispatcher()
    ut = LD.dispatch_survey(surv, dispatcher=stub)
    assert ut["ordered_count"] == 2 and ut["refused_count"] == 0
    assert len(stub.calls) == 2
    # rutinens checks-lista bär villkoret, precis som en inspections-rutin.
    assert stub.calls[0]["rut"]["checks"] == ["window_cleanliness"]


def test_dispatch_refuses_honestly_when_quixzoom_is_not_connected():
    """Ingen LANDVEX_QUIXZOOM_URL i testmiljön ⇒ MissionDispatcher()
    vägrar precis som för fotokontroller — samma väg, samma vägran."""
    LD.reset()
    surv = LD.survey("s1", "x", "window_cleanliness", [_adress()], tenant="t1")
    ut = LD.dispatch_survey(surv)
    assert ut["connected"] is False
    assert ut["ordered_count"] == 0 and ut["refused_count"] == 1
    assert "LANDVEX_QUIXZOOM_URL" in ut["refused"][0]["why_en"]


def test_it_belongs_to_its_own_addon_not_asset_inspections():
    from api.licensing import required_capability
    assert required_capability("/v1/leads") == "lead_surveys"
    assert required_capability("/v1/leads/survey") == "lead_surveys"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
