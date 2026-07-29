"""Infrastrukturövervakning: färskheten ÄR produkten.

Kunden köper verifierade observationer, inte en sensorström och inte en
uppskattning. Tre fel skulle förstöra just det, och sviten prövar dem
före allt annat:

  1. En utgången färskvara serverad som aktuell status. En
     parkeringsoperatör som dirigerar bilar efter ett tre timmar gammalt
     platsantal skickar dem fel.
  2. Ett uppskattat värde. Ett skattat tal ser ut precis som ett mätt.
  3. Tillförlitlighet som procentsats. "84 % säker" multipliceras vidare
     in i kalkyler talet inte bär.

Kör: python3 -m tests.test_infrastructure
"""
from __future__ import annotations

import time

from engine import infrastructure as I

NU = 1_800_000_000.0


def _obs(minuter_sedan: float, varden: dict, *, objekt: str = "p-1",
         kind: str = "car_parking", nat: str = "quixzoom",
         mission: str = "m-1") -> dict:
    return I.observe(objekt, kind, varden, mission_id=mission,
                     observer_network=nat, tenant="t1",
                     observed_at=NU - minuter_sedan * 60)


# ── 1. Färskvaran ──────────────────────────────────────────────────────
def test_an_expired_perishable_is_history_never_status():
    """Modulens viktigaste rad: värdet flyttas ur `value` och in i
    `last_known`, så att en integration som läser `value` INTE kan råka
    visa ett tre timmar gammalt platsantal som nuläge."""
    o = _obs(180, {"free_spaces": 14})
    s = I.status("p-1", "car_parking", [o], now=NU)
    rad = next(f for f in s["fields"] if f["observation_id"] == "free_spaces")
    assert rad["freshness"] == "stale"
    assert rad["value"] is None, "en utgången färskvara låg kvar i value"
    assert rad["last_known"] == 14
    assert "not the current state" in rad["why_en"]
    assert "nothing was estimated" in rad["why_en"]


def test_a_fresh_observation_is_current_and_an_ageing_one_says_its_age():
    fars = I.status("p-1", "car_parking", [_obs(5, {"free_spaces": 14})],
                    now=NU)
    r = next(f for f in fars["fields"] if f["observation_id"] == "free_spaces")
    assert r["freshness"] == "current" and r["value"] == 14

    aldrande = I.status("p-1", "car_parking",
                        [_obs(45, {"free_spaces": 14})], now=NU)
    r = next(f for f in aldrande["fields"]
             if f["observation_id"] == "free_spaces")
    assert r["freshness"] == "ageing"
    assert r["value"] == 14, "åldrande värde ska serveras MED sin ålder"
    assert r["age_minutes"] == 45.0
    assert "not as a statement about this minute" in r["why_en"]


def test_slow_and_fast_fields_age_at_different_speeds():
    """Hela affärsidén: beläggning åldras på minuter, skador på veckor.
    Samma observation, samma ålder, olika färskhet."""
    o = _obs(60, {"free_spaces": 3, "signage_correct": "good"})
    s = I.status("p-1", "car_parking", [o], now=NU)
    lager = {f["observation_id"]: f["freshness"] for f in s["fields"]}
    assert lager["free_spaces"] == "ageing"
    assert lager["signage_correct"] == "current"


def test_a_field_never_observed_is_never_estimated():
    s = I.status("p-1", "car_parking", [_obs(5, {"free_spaces": 14})],
                 now=NU)
    rad = next(f for f in s["fields"]
               if f["observation_id"] == "ev_charger_works")
    assert rad["freshness"] == "never"
    assert rad["value"] is None and "last_known" not in rad
    assert "looks exactly like a measured one" in rad["why_en"]


# ── 2. Inga uppskattningar, inga procentsatser ─────────────────────────
def test_nothing_in_the_answer_claims_to_be_an_estimate():
    """Fältsvep: ingen nyckel får antyda en modell mellan observationer."""
    s = I.status("p-1", "car_parking",
                 [_obs(5, {"free_spaces": 14}), _obs(400, {"occupancy": 0.9})],
                 now=NU)
    FORBJUDNA = ("estimate", "predicted", "forecast", "interpolat",
                 "modelled", "modeled", "projected")

    def svep(x, vag=""):
        if isinstance(x, dict):
            for k, v in x.items():
                assert not any(f in str(k).lower() for f in FORBJUDNA), \
                    f"{vag}.{k} antyder en uppskattning"
                svep(v, f"{vag}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                svep(v, f"{vag}[{i}]")

    svep(s)
    assert "estimated, interpolated or modelled" in s["cannot_en"]


def test_confidence_is_a_band_never_a_score():
    """Specen bad om en Confidence Score. Doktrinen förbjuder
    procentsatser — ett tal som 84 % multipliceras vidare in i kalkyler
    det inte bär."""
    s = I.status("p-1", "car_parking", [_obs(5, {"free_spaces": 14})],
                 now=NU)
    rad = next(f for f in s["fields"] if f["observation_id"] == "free_spaces")
    k = rad["confidence"]
    assert isinstance(k["band"], str)
    assert k["band"] in ("strong", "moderate", "weak", "none",
                         "conflicting")
    assert not isinstance(k["band"], (int, float))
    assert "never a score" in s["cannot_en"]


def test_one_observer_network_can_never_exceed_weak():
    """En ensam observatör kan inte bekräfta sig själv, hur många gånger
    hen än tittat — samma tak som resten av plattformen."""
    manga = [_obs(m, {"free_spaces": 10}) for m in (1, 2, 3, 4, 5)]
    s = I.status("p-1", "car_parking", manga, now=NU)
    rad = next(f for f in s["fields"] if f["observation_id"] == "free_spaces")
    assert rad["confidence"]["observations"] == 5
    assert rad["confidence"]["band"] in ("weak", "none")

    tva_nat = [_obs(1, {"free_spaces": 10}, nat="quixzoom"),
               _obs(2, {"free_spaces": 10}, nat="operator_sensors")]
    s2 = I.status("p-1", "car_parking", tva_nat, now=NU)
    rad2 = next(f for f in s2["fields"]
                if f["observation_id"] == "free_spaces")
    assert rad2["confidence"]["band"] != "none"


# ── 3. Registrering vägrar det som inte går att lita på ────────────────
def test_an_observation_without_evidence_is_refused():
    try:
        I.observe("p-1", "car_parking", {"free_spaces": 4}, mission_id="")
    except I.ObservationRefused as e:
        assert "assertion" in str(e)
    else:
        raise AssertionError("observation utan mission_id skulle vägrats")


def test_values_must_match_their_declared_kind():
    for varden in ({"free_spaces": -2}, {"free_spaces": "många"},
                   {"occupancy": 1.4}, {"ev_charger_works": "kanske"},
                   {"signage_correct": "utmärkt"},
                   {"finns_inte": 1}):
        try:
            I.observe("p-1", "car_parking", varden, mission_id="m-1")
        except I.ObservationRefused:
            continue
        raise AssertionError(f"{varden} skulle ha vägrats")


def test_an_empty_visit_is_not_an_observation():
    try:
        I.observe("p-1", "car_parking", {}, mission_id="m-1")
    except I.ObservationRefused as e:
        assert "a visit is not an observation" in str(e)
    else:
        raise AssertionError("tom observation skulle vägrats")


def test_no_object_type_or_observation_carries_media():
    """Bilden bor hos quiXzoom. Att kolumnen inte finns är spärren som
    inte kan glömmas."""
    o = _obs(5, {"free_spaces": 14})
    for f in ("photo", "image", "media", "thumbnail", "url", "blob"):
        assert f not in o, f
    assert o["mission_id"] == "m-1"


# ── Reality Freshness och förfall ──────────────────────────────────────
def test_the_next_check_is_driven_by_the_fastest_perishing_field():
    """Ett objekt vars beläggning går ut om 20 minuter behöver ses igen
    om 20 minuter, hur färsk skyltavläsningen än är."""
    o = _obs(5, {"free_spaces": 14, "signage_correct": "good"})
    fr = I.freshness_record("p-1", "car_parking", [o], now=NU)
    assert fr["next_check_driven_by"] in ("free_spaces", "occupancy",
                                          "accessible_spaces_free")
    assert fr["next_check_due_in_minutes"] <= 20.0
    assert "FASTEST-perishing" in fr["why_en"]
    assert "Frequency is not accuracy" in fr["cannot_en"]


def test_due_separates_never_verified_from_overdue():
    objekt = [{"id": "p-1", "kind": "car_parking", "label_en": "P1"},
              {"id": "p-2", "kind": "bike_parking", "label_en": "P2"}]
    d = I.due(objekt, [_obs(500, {"free_spaces": 2})], now=NU)
    assert [r["object_id"] for r in d["due"]] == ["p-1"]
    assert [r["object_id"] for r in d["never_verified"]] == ["p-2"]
    assert "OUR silence" in d["cannot_en"]


def test_a_quiet_answer_says_it_is_a_result():
    objekt = [{"id": "p-1", "kind": "car_parking"}]
    d = I.due(objekt, [_obs(1, {"free_spaces": 14, "occupancy": 0.5,
                                "accessible_spaces_free": 2})], now=NU)
    if not d["due"] and not d["never_verified"]:
        assert "That is a result, not an empty answer" in d["quiet_en"]


def test_an_unknown_trigger_is_an_error_not_a_quiet_skip():
    try:
        I.due([], [], triggers=[{"kind": "efter_fullmåne"}])
    except I.ObservationRefused as e:
        assert "unknown trigger" in str(e)
    else:
        raise AssertionError("okänd trigger skulle ha vägrats")


# ── SLA: räknad ur historiken ──────────────────────────────────────────
def test_the_sla_is_measured_from_history_not_read_from_the_contract():
    objekt = [{"id": "p-1", "kind": "car_parking"}]
    tata = [_obs(m, {"free_spaces": 5}) for m in (10, 40, 70, 100)]
    r = I.sla_report(objekt, tata, promised_minutes=60,
                     window_hours=3, now=NU)
    assert r["rows"][0]["verifications"] == 4
    assert "from the actual observation history" in r["measured_en"]

    glesa = [_obs(m, {"free_spaces": 5}) for m in (10, 170)]
    brutet = I.sla_report(objekt, glesa, promised_minutes=60,
                          window_hours=3, now=NU)
    assert brutet["met"] is False and brutet["breaches"] == 1
    assert brutet["rows"][0]["worst_gap_minutes"] > 60
    assert "never whether what they saw was right" in brutet["cannot_en"]


# ── Katalogen och data-doktrinen ───────────────────────────────────────
def test_every_observation_declares_how_fast_it_ages_and_what_it_cannot():
    for tid, typ in I.OBJECT_TYPES.items():
        assert typ["observations"], tid
        for o in typ["observations"]:
            assert o["kind"] in I.OBS_KINDS, (tid, o["id"])
            assert 0 < o["fresh_minutes"] <= o["stale_minutes"], (tid, o["id"])
            assert len(o["cannot_en"]) > 40, (tid, o["id"])


def test_the_catalogue_says_what_the_customer_is_actually_buying():
    kat = I.catalog()
    assert "VERIFIED observation" in kat["pricing_note_en"]
    assert "not a live sensor feed" in kat["pricing_note_en"]
    assert "estimates nothing between visits" in kat["cannot_en"]
    assert set(kat["triggers"]) == set(I.TRIGGERS)
    for t in kat["triggers"].values():
        assert t["cannot_en"]


def test_observations_are_per_tenant_and_survive_a_restart():
    import os
    import tempfile

    from engine import inspections as INS
    from engine.storage.sqlite import SqliteStore

    with tempfile.TemporaryDirectory() as d:
        sokvag = os.path.join(d, "o.db")
        s1 = SqliteStore(sokvag)
        INS.set_store(s1)
        try:
            INS.save_observation(_obs(5, {"free_spaces": 4}))
            annan = I.observe("p-9", "car_parking", {"free_spaces": 1},
                              mission_id="m-9", tenant="t2")
            INS.save_observation(annan)
            s1.close()
            INS.set_store(SqliteStore(sokvag))        # "omstart"
            assert len(INS.all_observations("t1")) == 1
            assert len(INS.all_observations("t2")) == 1
        finally:
            INS.set_store(None)
            INS.reset()


def test_it_is_sold_with_the_inspections_package():
    from api.licensing import required_capability

    assert required_capability("/v1/infrastructure") == "asset_inspections"
    assert required_capability(
        "/v1/infrastructure/status") == "asset_inspections"


def test_freshness_uses_wall_clock_when_no_time_is_given():
    """Standardvärdet får inte vara noll — då hade allt sett urgammalt
    ut i produktion."""
    o = I.observe("p-1", "car_parking", {"free_spaces": 3},
                  mission_id="m-1", tenant="t1")
    assert abs(o["observed_at"] - time.time()) < 5
    s = I.status("p-1", "car_parking", [o])
    rad = next(f for f in s["fields"]
               if f["observation_id"] == "free_spaces")
    assert rad["freshness"] == "current"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
