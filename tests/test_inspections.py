"""Kontroller som förfaller — och en kadens som hellre vägrar än gissar.

En flaggleverantör i Stockholm ska se sina stänger varje vecka; en kommun
ska se livbojarna under badsäsongen. Samma motor, olika data.

Testerna prövar gränsfallen, inte de lyckliga fallen: månadsskiften,
skottdagar, säsongens första och sista dag, och en rutin vars intervall
och veckodag inte går ihop. Det är där en schemaläggare tyst börjar
räkna fel, och ett tyst räknefel i den här modulen betyder att någon tror
att en livboj kontrolleras medan den inte gör det.

Kör: python3 -m tests.test_inspections
"""
from __future__ import annotations

from engine import inspections as I

_FLAGGA = dict(id="veckovis_flagga", label_en="Weekly flag check",
               applies_to="flagpole", every_days=7,
               checks=("present", "intact", "raised"))
_BAD = dict(id="badplats", label_en="Lifebuoy check", applies_to="lifebuoy",
            every_days=14, checks=("present", "intact"),
            season=("05-15", "09-15"))


def _rut(**kw):
    d = {**_FLAGGA, **kw}
    return I.routine(**d)


# ── Kadensen vägrar hellre än gissar ────────────────────────────────────
def test_an_impossible_cadence_is_refused_with_a_reason_you_can_act_on():
    """'Var tredje dag, på tisdagar' går inte att uppfylla. Att välja åt
    någon vilken av de två som vinner vore att hitta på en rutin."""
    try:
        _rut(every_days=3, weekday=1)
    except I.RoutineError as e:
        assert "delbart med 7" in str(e) or "every_days=3" in str(e)
        assert "eller ta bort veckodagen" in str(e), \
            "skälet ska säga vad man GÖR åt det"
        return
    raise AssertionError("en omöjlig kadens accepterades")


def test_a_routine_without_checks_is_refused():
    """Utan `checks` går ingen dom att motivera."""
    try:
        _rut(checks=())
    except I.RoutineError as e:
        assert "godkänt" in str(e)
        return
    raise AssertionError("en rutin utan kriterier accepterades")


def test_the_weekday_survives_the_interval():
    """Veckovis på en torsdag ska förbli torsdagar, vecka efter vecka."""
    r = _rut(every_days=7, weekday=3)
    d = "2026-07-30"                      # en torsdag
    for _ in range(6):
        d = I.next_due(r, d, today="2026-01-01")
        from datetime import date
        assert date.fromisoformat(d).weekday() == 3, d


# ── Gränsfall i tiden ───────────────────────────────────────────────────
def test_month_boundaries_and_leap_day_are_just_arithmetic():
    r = _rut(every_days=7)
    assert I.next_due(r, "2026-01-28", today="2026-01-01") == "2026-02-04"
    assert I.next_due(r, "2024-02-26", today="2024-01-01") == "2024-03-04"
    assert I.next_due(r, "2026-12-30", today="2026-01-01") == "2027-01-06"


def test_a_check_falling_outside_the_season_moves_to_the_season_opening():
    """Livbojar kontrolleras inte i januari. Nästa förfall är säsongens
    första dag, inte 'omedelbart'."""
    r = I.routine(**_BAD)
    assert I.next_due(r, "2026-09-10", today="2026-09-11") == "2027-05-15"


def test_the_first_and_last_day_of_the_season_are_inside_it():
    r = I.routine(**_BAD)
    for d in ("2026-05-15", "2026-09-15"):
        assert I.status(r, [], today=d)["status"] != "out_of_season", d
    assert I.status(r, [], today="2026-05-14")["status"] == "out_of_season"


def test_a_season_that_wraps_the_new_year_works():
    """Vinterbelysning: 1 nov–31 mars är en säsong, inte ett fel."""
    r = _rut(season=("11-01", "03-31"))
    assert I.status(r, [], today="2026-12-24")["status"] != "out_of_season"
    assert I.status(r, [], today="2027-02-01")["status"] != "out_of_season"
    assert I.status(r, [], today="2026-07-01")["status"] == "out_of_season"


# ── Status ──────────────────────────────────────────────────────────────
def test_an_object_never_seen_is_unknown_not_current():
    """Det farligaste läget att kalla 'ok'."""
    s = I.status(_rut(), [], today="2026-07-28")
    assert s["status"] == "never_checked"
    assert "unknown" in s["why_en"]


def test_overdue_counts_days_and_says_what_the_number_means():
    r = _rut()
    c = [I.record("a1", r["id"], "pass", performed_at="2026-07-01",
                  mission_id="m1")]
    s = I.status(r, c, today="2026-07-28")
    assert s["status"] == "overdue"
    assert s["days_overdue"] == 20        # förföll 2026-07-08
    assert "past due" in s["why_en"]


def test_a_failed_check_outranks_the_schedule():
    """Ett underkänt objekt blir inte aktuellt av att kontrolleras i
    tid — det blir aktuellt av att åtgärdas."""
    r = _rut()
    c = [I.record("a1", r["id"], "missing", performed_at="2026-07-27",
                  mission_id="m9")]
    s = I.status(r, c, today="2026-07-28")
    assert s["status"] == "failed"
    assert "outranks the schedule" in s["why_en"]


def test_due_soon_is_a_planning_horizon_not_a_deadline():
    r = _rut()
    c = [I.record("a1", r["id"], "pass", performed_at="2026-07-25",
                  mission_id="m1")]
    assert I.status(r, c, today="2026-07-28")["status"] == "due_soon"


# ── Domen ───────────────────────────────────────────────────────────────
def test_a_verdict_without_evidence_is_refused():
    """En godkänd kontroll utan bevis är ett påstående. Det är i
    efterhand posten behövs, och då går den inte att försvara."""
    for v in ("pass", "fail", "missing"):
        try:
            I.record("a1", "r1", v)
        except ValueError as e:
            assert "bevis" in str(e)
            continue
        raise AssertionError(f"{v} utan bevis accepterades")
    # `unclear` ÄR ett giltigt utfall utan bevis: bidragsgivaren kom fram
    # men kunde inte avgöra. Att kräva bevis för osäkerhet vore att
    # tvinga fram en gissning.
    assert I.record("a1", "r1", "unclear")["verdict"] == "unclear"


def test_the_media_itself_is_never_stored():
    """En fältbild innehåller människor. Domen och pekaren lagras här;
    bilden stannar hos quiXzoom, som har samtycket."""
    c = I.record("a1", "r1", "pass", mission_id="m1",
                 evidence_ref="qz://m1/frame/3")
    forbjudna = ("image", "photo", "media", "bild", "base64", "blob",
                 "bytes", "data_url")
    for f in c:
        assert not any(x in f.lower() for x in forbjudna), (
            f"fältet {f!r} ser ut att bära media — bilden får inte lagras "
            f"i kontrollposten")


def test_the_verdict_states_what_one_observation_cannot_settle():
    c = I.record("a1", "r1", "missing", mission_id="m1")
    assert "cannot say for how long" in c["basis_en"].replace("it ", "")


# ── Leveranserna ────────────────────────────────────────────────────────
def _demo():
    r = _rut()
    stanger = [{"id": f"fp{i}", "kind": "flagpole",
                "label_en": f"Flagpole {i}"} for i in range(1, 6)]
    checks = [
        I.record("fp1", r["id"], "pass", performed_at="2026-07-27", mission_id="m1"),
        I.record("fp2", r["id"], "pass", performed_at="2026-07-26", mission_id="m2"),
        I.record("fp3", r["id"], "pass", performed_at="2026-07-25", mission_id="m3"),
        I.record("fp4", r["id"], "pass", performed_at="2026-06-01", mission_id="m4"),
        I.record("fp5", r["id"], "missing", performed_at="2026-07-20", mission_id="m5"),
    ]
    return stanger, [r], checks


def test_the_compliance_register_is_what_you_show_afterwards():
    a, r, c = _demo()
    rap = I.compliance(a, r, c, today="2026-07-28")
    assert rap["count"] == 5
    assert rap["by_status"]["overdue"] == 1          # fp4
    assert rap["by_status"]["failed"] == 1           # fp5
    assert rap["current"] == 3
    assert rap["share_current"] == 0.6
    assert "not a guarantee of" in rap["cannot_en"]


def test_the_exception_feed_shows_only_what_needs_someone():
    a, r, c = _demo()
    av = I.exceptions(a, r, c, today="2026-07-28")
    assert av["count"] == 2 and av["of_total"] == 5
    assert av["exceptions"][0]["status"] == "failed", "trasigt före försenat"


def test_a_quiet_feed_is_a_result_not_an_empty_screen():
    r = _rut()
    a = [{"id": "fp1", "kind": "flagpole"}]
    c = [I.record("fp1", r["id"], "pass", performed_at="2026-07-27",
                  mission_id="m1")]
    av = I.exceptions(a, [r], c, today="2026-07-28")
    assert av["count"] == 0
    assert "quiet exception feed is a real result" in av["quiet_en"]


def test_an_object_no_routine_covers_is_named_not_hidden():
    """Ett objekt i registret som ingen sagt hur ofta det ska ses är en
    lucka, och den ska synas i registret i stället för att räknas bort."""
    rap = I.compliance([{"id": "x1", "kind": "bench"}], [_rut()], [],
                       today="2026-07-28")
    assert rap["rows"][0]["status"] == "no_routine"
    assert "nobody has said how often" in rap["rows"][0]["why_en"]


# ── Beställningen ───────────────────────────────────────────────────────
def test_dispatch_refuses_instead_of_inventing_a_mission_id():
    """Ett låtsat uppdrags-id ser ut som en beställd kontroll ända fram
    till dagen någon frågar varför ingen varit på plats."""
    from integrations.quixzoom_dispatch import DispatchRefused, MissionDispatcher
    d = MissionDispatcher(base_url="")
    assert not d.connected
    try:
        d.dispatch({"id": "fp1", "lat": 59.3, "lon": 18.1}, _rut(),
                   "2026-08-04")
    except DispatchRefused as e:
        assert "no mission id exists" in str(e)
        assert "Nothing was invented" in str(e)
        return
    raise AssertionError("beställde utan att vara konfigurerad")


def test_dispatch_refuses_an_object_without_a_place():
    from integrations.quixzoom_dispatch import DispatchRefused, MissionDispatcher
    d = MissionDispatcher(base_url="https://qz.example")
    try:
        d.dispatch({"id": "fp1"}, _rut(), "2026-08-04")
    except DispatchRefused as e:
        assert "no coordinates" in str(e)
        return
    raise AssertionError("skickade någon till en plats som saknas")


def test_dispatch_returns_the_real_id_when_quixzoom_answers():
    import json
    from integrations.quixzoom_dispatch import MissionDispatcher

    def svarar(url, payload, headers, timeout):
        kropp = json.loads(payload)
        assert kropp["reference"]["asset_id"] == "fp1"
        assert kropp["checklist"] == ["present", "intact", "raised"]
        return b'{"id": "QZ-4711", "status": "open"}'

    d = MissionDispatcher(base_url="https://qz.example", transport=svarar)
    r = d.dispatch({"id": "fp1", "lat": 59.3, "lon": 18.1,
                    "label_en": "Flagpole 1"}, _rut(), "2026-08-04")
    assert r["mission_id"] == "QZ-4711"
    assert r["asset_id"] == "fp1"


def test_an_answer_without_a_mission_id_is_refused():
    """Utan id går kontrollen inte att knyta till sitt bevis."""
    from integrations.quixzoom_dispatch import DispatchRefused, MissionDispatcher
    d = MissionDispatcher(base_url="https://qz.example",
                          transport=lambda *a: b'{"ok": true}')
    try:
        d.dispatch({"id": "fp1", "lat": 1.0, "lon": 2.0}, _rut(), "2026-08-04")
    except DispatchRefused as e:
        assert "without a mission id" in str(e)
        return
    raise AssertionError("accepterade ett svar utan uppdrags-id")


def test_a_blocked_network_is_not_reported_as_quixzoom_refusing():
    """Samma skillnad som proberna lärde oss: spärrat nät säger ingenting
    om motparten."""
    import urllib.error
    from integrations.quixzoom_dispatch import DispatchRefused, MissionDispatcher

    def spärrad(*a):
        raise urllib.error.URLError("Tunnel connection failed: 403")

    d = MissionDispatcher(base_url="https://qz.example", transport=spärrad)
    try:
        d.dispatch({"id": "fp1", "lat": 1.0, "lon": 2.0}, _rut(), "2026-08-04")
    except DispatchRefused as e:
        assert "never got there" in str(e)
        assert "says nothing about" in str(e)
        return
    raise AssertionError("kallade ett spärrat nät för en vägran från quiXzoom")


def test_our_own_bugs_still_propagate():
    from integrations.quixzoom_dispatch import MissionDispatcher

    def buggig(*a):
        raise AttributeError("stavfel")

    d = MissionDispatcher(base_url="https://qz.example", transport=buggig)
    try:
        d.dispatch({"id": "fp1", "lat": 1.0, "lon": 2.0}, _rut(), "2026-08-04")
    except AttributeError:
        return
    raise AssertionError("vår egen bugg svaldes")


def test_a_routine_without_owners_gets_no_accountability_card():
    """Ett intervall är ett beslut någon fattade. Utan namn blir en missad
    kontroll ingen mans sak — och just då är den som farligast."""
    try:
        I.accountability_card(_rut())
    except I.RoutineError as e:
        assert "formellt" in str(e) and "operativt" in str(e)
    else:
        raise AssertionError("kort utan ägare skapades")


def test_a_routine_without_a_measurable_expectation_is_refused_too():
    ag = {"formellt": "A", "operativt": "B", "uppfoljning": "C"}
    try:
        I.accountability_card(_rut(owners=ag, expected={"metric": "x"}))
    except I.RoutineError as e:
        assert "direction" in str(e) or "target" in str(e)
    else:
        raise AssertionError("kort utan mätbart utfall skapades")


def test_the_card_lands_in_the_same_ledger_as_every_other_decision():
    from engine import accountability as A

    ag = {"formellt": "Contract manager", "operativt": "Contributor",
          "uppfoljning": "Ops manager"}
    kort = I.accountability_card(
        _rut(owners=ag, expected={"metric": "share_current",
                                  "direction": "reach", "target": 1.0},
             tenant="flaggab"))
    assert kort["id"] and kort["tenant"] == "flaggab"
    assert kort["status"] == "open"
    assert any(d["id"] == kort["id"] for d in A.all_decisions("flaggab"))
    # och INTE i någon annans register
    assert not any(d["id"] == kort["id"] for d in A.all_decisions("kommunen"))


def test_exceptions_are_not_routed_to_everyone_by_default():
    """Prenumerationerna bär ingen tenant. Faller routningen tillbaka på
    'alla prenumeranter' får en kund en annans adresser i sin inkorg."""
    I.reset()
    I.save_asset(I.asset("fp1", "flagpole", address="Hantverkargatan 1",
                         tenant="flaggab"))
    I.save_routine(_rut(tenant="flaggab"))
    ut = I.route_exceptions("flaggab")
    assert ut["routed_count"] == 0 and ut["routed"] == []
    assert "no tenant" in ut["refusal_en"].lower()
    assert ut["exceptions_count"] >= 1        # det FANNS något att skicka
    I.reset()


def test_a_failed_object_outranks_one_that_merely_falls_due():
    from engine.inbox import from_inspection_exception as norm

    fel = norm({"status": "failed", "days_overdue": 0,
                "asset": {"id": "fp3", "label_en": "Flagpole 3"}})
    snart = norm({"status": "due_soon", "days_overdue": 0,
                  "asset": {"id": "fp1", "label_en": "Flagpole 1"}})
    assert fel["severity"] == "high" and snart["severity"] == "low"
    assert "share_current" in fel["metrics"]   # träffar rutinens ansvarskort


def test_the_demo_fixture_is_labelled_simulated_and_mixed():
    """Demokunden ska visa BLANDNINGEN — godkänt, underkänt, aldrig sett
    och försenat. En fixtur där allt är grönt visar ingenting."""
    from scripts.seed_inspections import payload

    p = payload("2026-07-28")
    assert p["source"] == "mock" and "not" in p["note_en"].lower()
    lagen = p["compliance"]["by_status"]
    for krav in ("failed", "never_checked", "overdue"):
        assert lagen.get(krav), f"fixturen saknar {krav}"
    assert p["compliance"]["share_current"] < 1.0
    assert p["exceptions"]["exceptions"][0]["status"] == "failed"
    for rad in p["compliance"]["rows"]:          # aldrig media i registret
        assert not any(k in rad for k in ("image", "photo", "media"))


# ── Riktade zoomers: publiken är rutinens data ─────────────────────────
def test_a_routine_without_an_audience_goes_to_the_open_pool():
    """Precis som före fältet fanns — ingen befintlig rutin byter
    beteende av att riktning blev möjlig."""
    rut = I.routine("r-open", "Weekly check", "flagpole", 7,
                    checks=["present"])
    assert rut["audience"] == {"pool": "open", "zoomer_ids": (),
                               "label_en": ""}


def test_a_named_audience_reaches_the_mission_body_verbatim():
    """Hyrbilarna fotas av de egna anställda, skyltningen av
    butikspersonalen: uppdraget ska bära exakt de kontoreferenser
    rutinen riktar till — och en öppen rutin ska INTE bära någon
    lista alls, för en tom lista i öppna poolen läses som en tom
    riktning."""
    import json as _json

    from integrations.quixzoom_dispatch import MissionDispatcher

    sedd = {}

    def t(url, payload, headers, timeout):
        sedd["kropp"] = _json.loads(payload)
        return b'{"id": "m-1", "created_at": "2026-07-29"}'

    d = MissionDispatcher(base_url="https://qz.example", transport=t)
    obj = I.asset("bil-1", "rental_car", label_en="Hyrbil VXZ 123",
                  lat=59.3, lon=18.0, tenant="t1")
    riktad = I.routine(
        "hyrbilsfoto", "Return photo", "rental_car", 1,
        checks=["exterior", "interior"],
        audience_={"pool": "named",
                   "zoomer_ids": ("qz-staff-001", "qz-staff-002")},
        tenant="t1")
    d.dispatch(obj, riktad, "2026-07-30")
    pub = sedd["kropp"]["audience"]
    assert pub == {"pool": "named",
                   "zoomer_ids": ["qz-staff-001", "qz-staff-002"]}

    oppen = I.routine("r-open2", "Weekly check", "rental_car", 7,
                      checks=["present"], tenant="t1")
    d.dispatch(obj, oppen, "2026-07-30")
    assert sedd["kropp"]["audience"] == {"pool": "open"}
    assert "zoomer_ids" not in sedd["kropp"]["audience"]


def test_a_targeted_pool_cannot_be_empty_or_carry_people():
    """Två vägransgrunder, båda vid SKAPANDET: en riktad publik utan
    referenser är en pool ingen kan ta uppdrag ur, och namn/e-post är
    människor — personen och samtycket bor hos quiXzoom, Landvex lagrar
    kontoreferensen."""
    for fel in ({"pool": "named"},
                {"pool": "named", "zoomer_ids": ()},
                {"pool": "open", "zoomer_ids": ("qz-1",)},
                {"pool": "named", "zoomer_ids": ("anna@butiken.se",)},
                {"pool": "named", "zoomer_ids": ("Anna Andersson",)},
                {"pool": "vip"}):
        try:
            I.routine("r-x", "X", "flagpole", 7, checks=["a"],
                      audience_=fel)
        except I.RoutineError:
            continue
        raise AssertionError(f"publiken {fel} borde ha vägrats")


def test_the_seed_carries_one_targeted_routine_as_a_worked_example():
    from scripts.seed_inspections import flag_supplier

    fix = flag_supplier("2026-07-29")
    riktade = [r for r in fix["routines"]
               if r["audience"]["pool"] == "named"]
    assert len(riktade) == 1
    assert riktade[0]["audience"]["zoomer_ids"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
