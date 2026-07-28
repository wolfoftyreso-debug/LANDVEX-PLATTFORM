"""Körningar utan människa — och att de inte kör två gånger.

Två processer som kör samma jobb ger kunden två beställda fältuppdrag för
samma objekt, och det upptäcks först när fakturan kommer. Testerna nedan
prövar claimet både med lager (atomiskt i databasen) och utan (bara den
egna processen, och det ska stå i svaret).

Det andra som prövas är gränsen: en bevakning som vaknar utan historik
har ingenting att titta på, och måste säga det i stället för att
utvärdera en tom serie och rapportera "inga avvikelser" — vilket läses
som lugn.

Kör: python3 -m tests.test_scheduler
"""
from __future__ import annotations

import os
import tempfile

from engine import scheduler as S

_NU = 1_800_000_000.0        # fast tid; ingenting härleds ur klockan


def _jobb(**kw):
    d = {"id": "j1", "kind": "inspections_exceptions", "tenant": "flaggab"}
    d.update(kw)
    return S.job(**d)


def test_a_job_without_a_tenant_is_refused():
    """Ett schemalagt jobb agerar obevakat. Utan kund agerar det på allas
    data, utan att någon tittar på."""
    try:
        S.job("j", "inspections_exceptions", tenant="")
    except S.ScheduleRefused as e:
        assert "tenant" in str(e)
    else:
        raise AssertionError("jobb utan tenant tilläts")


def test_an_unknown_kind_lists_the_ones_that_exist():
    try:
        S.job("j", "gör_allt", tenant="t")
    except S.ScheduleRefused as e:
        assert "scan_refresh" in str(e)
    else:
        raise AssertionError("okänd jobbtyp tilläts")


def test_the_cadence_vocabulary_is_the_one_monitors_already_use():
    """Ett andra cron-språk i samma kodbas glider isär. Samma ord in,
    samma fel ut."""
    from engine.monitors import cadence_minutes

    for kad, minuter in (({"every": "hourly"}, 60),
                         ({"every": "daily"}, 1440),
                         ({"every": "interval", "interval_minutes": 15}, 15)):
        assert cadence_minutes(S.job("j", "monitors", cadence=kad,
                                     tenant="t")["cadence"]) == minuter
    try:
        S.job("j", "monitors", cadence={"every": "fortnightly"}, tenant="t")
    except ValueError as e:
        assert "fortnightly" in str(e)
    else:
        raise AssertionError("okänd kadens tilläts")


def test_a_job_runs_once_and_then_not_again_until_it_is_due():
    S.reset()
    S.save_job(_jobb(cadence={"every": "daily"}))
    r1 = S.run_due("flaggab", _NU)
    assert r1["ran_count"] == 1
    r2 = S.run_due("flaggab", _NU + 60)          # en minut senare
    assert r2["ran_count"] == 0
    assert r2["skipped"][0]["why_en"] == "not due yet"
    r3 = S.run_due("flaggab", _NU + 86_400 + 1)  # ett dygn senare
    assert r3["ran_count"] == 1
    S.reset()


def test_a_disabled_job_is_skipped_with_a_reason_not_silently():
    S.reset()
    S.save_job(_jobb(enabled=False))
    r = S.run_due("flaggab", _NU)
    assert r["ran_count"] == 0
    assert r["skipped"][0]["why_en"] == "disabled"
    S.reset()


def test_one_customers_schedule_never_runs_on_anothers_data():
    S.reset()
    S.save_job(_jobb(id="a", tenant="flaggab"))
    S.save_job(_jobb(id="b", tenant="kommunen"))
    r = S.run_due("flaggab", _NU)
    assert [x["id"] for x in r["ran"]] == ["a"]
    assert [j["id"] for j in S.all_jobs("kommunen")] == ["b"]
    S.reset()


def test_two_runs_at_the_same_moment_only_execute_the_job_once():
    """Utan claim skulle båda se 'inte körd' och båda köra. Med kunden
    som betalar per uppdrag är det två fakturor för ett objekt."""
    S.reset()
    S.save_job(_jobb(cadence={"every": "hourly"}))
    a = S.run_due("flaggab", _NU)
    b = S.run_due("flaggab", _NU)               # exakt samma nu
    assert (a["ran_count"], b["ran_count"]) == (1, 0)
    S.reset()


def test_without_a_store_the_run_says_the_claim_is_process_local():
    """En processlokal spärr som utger sig för att vara ett klusterlås är
    värre än ingen spärr: den lugnar den som skalar ut."""
    S.reset()
    S.save_job(_jobb())
    r = S.run_due("flaggab", _NU)
    assert "THIS process" in r["claim_en"]
    S.reset()


def test_with_a_store_the_claim_is_atomic_and_survives_a_restart():
    from engine.storage.sqlite import SqliteStore

    path = os.path.join(tempfile.mkdtemp(), "sched.db")
    store = SqliteStore(path)
    S.reset()
    S.set_store(store)
    try:
        S.save_job(_jobb(cadence={"every": "hourly"}))
        # Villkoret sitter i UPDATE-satsen: andra anropet får noll rader.
        assert store.claim_job("j1", "flaggab", _NU, 3600) is True
        assert store.claim_job("j1", "flaggab", _NU, 3600) is False
        assert store.claim_job("j1", "flaggab", _NU + 3601, 3600) is True
        # Fel kund kan inte ta jobbet ifrån rätt kund.
        assert store.claim_job("j1", "kommunen", _NU + 99_999, 3600) is False
        store.close()

        igen = SqliteStore(path)                 # omstart
        S.set_store(igen)
        jobb = S.all_jobs("flaggab")
        assert [j["id"] for j in jobb] == ["j1"]
        assert jobb[0]["last_run"] > 0           # last_run läses ur kolumnen
        r = S.run_due("flaggab", _NU)
        assert "store" in r["claim_en"].lower()
        igen.close()
    finally:
        S.set_store(None)
        S.reset()


def test_a_woken_watch_with_no_history_skips_instead_of_reporting_calm():
    """Att utvärdera en tom serie ger 'inget triggat'. Det läses som lugn,
    men betyder blind — och det är skillnaden hela produkten säljs på."""
    S.reset()
    S.save_job(_jobb(id="watch", kind="monitors"))
    r = S.run_due("flaggab", _NU)
    rad = r["ran"][0]
    assert rad["skipped"] is True
    assert "empty series" in rad["detail_en"]
    assert "scan_refresh" in rad["detail_en"]    # vägen framåt står med
    S.reset()


def test_a_failing_job_does_not_take_the_run_down_with_it():
    """Nästa jobb gäller en annan kund. Ett fel skrivs in i jobbet så det
    syns i registret i stället för i en logg ingen läser."""
    S.reset()
    trasig = dict(S.JOB_KINDS["inspections_exceptions"])

    def _sprick(job, now):
        raise RuntimeError("källan svarade inte")

    S.JOB_KINDS["_trasig"] = {**trasig, "run": _sprick}
    try:
        S.save_job(_jobb(id="fel", kind="_trasig"))
        S.save_job(_jobb(id="ok", kind="inspections_exceptions"))
        r = S.run_due("flaggab", _NU)
        assert r["ran_count"] == 2
        lagen = {x["id"]: x["status"] for x in r["ran"]}
        assert lagen == {"fel": "error", "ok": "ok"}
        assert r["errors"][0]["id"] == "fel"
        assert "källan svarade inte" in r["errors"][0]["why_en"]
        # och felet finns kvar på jobbet, inte bara i svaret
        assert {j["id"]: j["last_status"]
                for j in S.all_jobs("flaggab")}["fel"] == "error"
    finally:
        S.JOB_KINDS.pop("_trasig", None)
        S.reset()


def test_the_dispatch_job_counts_refusals_rather_than_hiding_them():
    """En körning som beställde noll för att endpointen är osatt får inte
    se ut som en körning där ingenting förföll."""
    from engine import inspections as I

    S.reset()
    I.reset()
    I.save_routine(I.routine("v", "Weekly", "flagpole", 7,
                             checks=["present"], tenant="flaggab"))
    I.save_asset(I.asset("fp1", "flagpole", lat=59.3, lon=18.0,
                         tenant="flaggab"))
    S.save_job(_jobb(id="best", kind="inspections_dispatch"))
    r = S.run_due("flaggab", _NU)["ran"][0]
    assert r["ordered"] == 0 and r["refused"] == 1
    assert "LANDVEX_QUIXZOOM_URL" in r["refusals"][0]
    I.reset()
    S.reset()


def test_every_job_kind_names_the_package_it_needs():
    from api.licensing import PLANS

    kanda = set().union(*(set(p["capabilities"]) for p in PLANS.values()))
    for kid, k in S.JOB_KINDS.items():
        assert k["capability"] in kanda, kid
        assert k["label_en"] and k["note_en"], kid


def test_the_catalog_states_what_a_schedule_cannot_do():
    k = S.catalog()
    assert "does not create" in k["cannot_en"]
    import json
    assert json.dumps(k)          # inga anropbara objekt i svaret


def test_the_ticker_is_off_unless_someone_turned_it_on():
    """En bakgrundstråd som startar för att någon importerat en modul, och
    sedan beställer fältuppdrag åt en kund, är en dyr överraskning."""
    from api import ticker

    gammal = os.environ.pop("LANDVEX_SCHEDULER", None)
    try:
        assert ticker.enabled() is False
        assert ticker.start() is False
        st = ticker.status()["scheduler"]
        assert st["running"] is False
        assert "/v1/schedules/run" in st["how_en"]
        os.environ["LANDVEX_SCHEDULER"] = "on"
        assert ticker.enabled() is True
    finally:
        os.environ.pop("LANDVEX_SCHEDULER", None)
        if gammal is not None:
            os.environ["LANDVEX_SCHEDULER"] = gammal


def test_the_tick_interval_has_a_floor():
    from api import ticker

    gammal = os.environ.get("LANDVEX_SCHEDULER_INTERVAL_S")
    try:
        os.environ["LANDVEX_SCHEDULER_INTERVAL_S"] = "0"
        assert ticker.interval_s() == 5.0
        os.environ["LANDVEX_SCHEDULER_INTERVAL_S"] = "inte ett tal"
        assert ticker.interval_s() == 60.0
    finally:
        os.environ.pop("LANDVEX_SCHEDULER_INTERVAL_S", None)
        if gammal is not None:
            os.environ["LANDVEX_SCHEDULER_INTERVAL_S"] = gammal


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
