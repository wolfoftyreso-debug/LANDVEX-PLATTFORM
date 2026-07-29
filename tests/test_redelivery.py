"""Omkörning och larm: kön är levande, historiken skrivs aldrig om.

Kör: python3 -m tests.test_redelivery
"""
from __future__ import annotations

import json

from engine import connections as CN
from engine import deliveries as DL
from engine import scheduler as S


def _fix(status=200, kropp=b"ok", *, fel=None):
    anrop = []

    def transport(*args):
        anrop.append(args)
        if fel is not None:
            raise fel
        return status, kropp
    transport.anrop = anrop
    return transport


# ── Omkörning ────────────────────────────────────────────────────────
def test_retry_of_a_push_rebuilds_from_the_job_with_a_new_id():
    from integrations.redelivery import retry

    DL.reset()
    S.reset()
    try:
        S.save_job(S.job(
            "dagligt", "push", cadence={"every": "daily"},
            params={"dataset": "hotspots", "format": "csv",
                   "target_url": "https://nere.example/x",
                   "dataset_params": {"vertical": "gym",
                                      "market": "us", "top_n": 2}},
            tenant="t1"))
        # Ett misslyckat försök i loggen, kopplat till jobbets id.
        DL.record(tenant="t1", kind="push.hotspots", provider="webhook",
                  body=b"gammal", delivery_id="lvx-del-gammal",
                  delivered=False, status="OSError",
                  source="dagligt")
        ut = retry("lvx-del-gammal", tenant="t1",
                   transport=_fix(200, b"mottaget"))
        assert ut["retried"] is True
        assert ut["result"]["delivered"] is True
        assert ut["result"]["delivery_id"] != "lvx-del-gammal", \
            "omkörningen ska få ett NYTT id"
        # Den gamla raden står orörd som misslyckad.
        gammal = next(r for r in DL.all_deliveries("t1")
                     if r["id"] == "lvx-del-gammal")
        assert gammal["delivered"] is False
    finally:
        DL.reset()
        S.reset()


def test_retry_refuses_a_delivered_row_and_an_unknown_id():
    from integrations.redelivery import retry

    DL.reset()
    try:
        DL.record(tenant="t1", kind="push.hotspots", provider="webhook",
                  body=b"x", delivery_id="lvx-del-ok", delivered=True,
                  status=200, source="j1")
        r1 = retry("lvx-del-ok", tenant="t1")
        assert r1["retried"] is False and "succeeded" in r1["why_en"]
        r2 = retry("lvx-del-saknas", tenant="t1")
        assert r2["retried"] is False and "no such delivery" in r2["why_en"]
    finally:
        DL.reset()


def test_retry_of_a_credential_is_refused_never_replayed():
    from integrations.redelivery import retry

    DL.reset()
    try:
        DL.record(tenant="t1", kind="credential", provider="sap",
                  body=b"x", delivery_id="lvx-del-cred",
                  delivered=False, status=500, source="lvx-cred-abc")
        ut = retry("lvx-del-cred", tenant="t1")
        assert ut["retried"] is False
        assert "issued ONCE" in ut["why_en"]
        assert "still verifiable" in ut["why_en"]
    finally:
        DL.reset()


def test_retry_of_a_healed_exception_is_refused_as_noise():
    """Avvikelsen läkt sedan felet (en godkänd kontroll registrerad
    efter det) ⇒ ärendet vore ett ärende om ett problem som inte finns
    — omkörningen vägrar det."""
    from integrations.redelivery import retry
    from engine import inspections as I

    DL.reset()
    CN.reset()
    I.reset()
    try:
        I.save_routine(I.routine("v", "Weekly", "flagpole", 7,
                                 checks=["present"], tenant="t1"))
        I.save_asset(I.asset("fp1", "flagpole", tenant="t1"))
        I.save_check(I.record("fp1", "v", "pass", mission_id="qz-m1",
                              tenant="t1"))
        CN.save_connection(CN.connection(
            "servicenow",
            {"endpoint_url": "https://co.service-now.com/api/x"},
            tenant="t1"))
        DL.record(tenant="t1", kind="inspection_exception",
                  provider="servicenow", body=b"x",
                  delivery_id="lvx-del-arende", delivered=False,
                  status=500, source="fp1")
        ut = retry("lvx-del-arende", tenant="t1")
        assert ut["retried"] is False
        assert "healed" in ut["why_en"]
    finally:
        DL.reset()
        CN.reset()
        I.reset()


def test_retry_of_a_standing_exception_rebuilds_with_a_new_id():
    from integrations.redelivery import retry
    from engine import inspections as I

    DL.reset()
    CN.reset()
    I.reset()
    try:
        I.save_routine(I.routine("v", "Weekly", "flagpole", 7,
                                 checks=["present"], tenant="t1"))
        I.save_asset(I.asset("fp1", "flagpole", tenant="t1"))
        # Ingen kontroll registrerad ⇒ objektet är fortfarande i
        # avvikelseflödet (never_checked) — felet står kvar.
        CN.save_connection(CN.connection(
            "servicenow",
            {"endpoint_url": "https://co.service-now.com/api/x"},
            tenant="t1"))
        DL.record(tenant="t1", kind="inspection_exception",
                  provider="servicenow", body=b"x",
                  delivery_id="lvx-del-arende2", delivered=False,
                  status=500, source="fp1")
        ut = retry("lvx-del-arende2", tenant="t1",
                   transport=_fix(201, b"{}"))
        assert ut["retried"] is True
        assert ut["result"]["sent"] == 1
        rader = [r for r in DL.all_deliveries("t1")
                if r["kind"] == "inspection_exception"]
        assert len(rader) == 2, "ny rad ska läggas till, inte skriva över"
    finally:
        DL.reset()
        CN.reset()
        I.reset()


def test_tied_timestamps_still_order_newest_first():
    """time.time() kan ge samma värde för snabba anrop i följd (grov
    klockupplösning, eller bara otur). En stabil sort på bara tiden
    faller då tillbaka till infogningsordning — fel håll för
    "nyast först". Tvinga en RIKTIG tvilling och bevisa att seq-
    tiebreakern ändå ger rätt ordning."""
    DL.reset()
    try:
        ur = DL._time.time
        DL._time.time = lambda: 1000.0
        try:
            DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                      body=b"x", delivery_id="lvx-del-forst",
                      delivered=False, status=500, source="j")
            DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                      body=b"x", delivery_id="lvx-del-sist",
                      delivered=True, status=200, source="j")
        finally:
            DL._time.time = ur
        # Trots identisk created_at ska den SENARE (lyckade) raden
        # räknas som nyast — annars trodde larmet att målet fortfarande
        # var trasigt.
        forsta = DL.all_deliveries("t1")[0]
        assert forsta["id"] == "lvx-del-sist", (
            "tvillingade tidsstämplar sorterades i infogningsordning, "
            "inte nyast-först")
        assert DL.failure_streaks("t1") == []
    finally:
        DL.reset()


# ── Larmet ───────────────────────────────────────────────────────────
def test_failure_streaks_count_since_the_last_success_and_reset_on_it():
    """Fyra äldre misslyckanden ligger FÖRE en lyckad leverans i tiden
    — de är historik, inte svit. De nio SENARE misslyckandena, efter
    framgången, är sviten larmet ska se."""
    DL.reset()
    try:
        for i in range(4):
            DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                      body=b"x", delivery_id=f"lvx-del-old{i}",
                      delivered=False, status=500, source="j")
        DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                  body=b"x", delivery_id="lvx-del-ok",
                  delivered=True, status=200, source="j")
        for i in range(9):
            DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                      body=b"x", delivery_id=f"lvx-del-f{i}",
                      delivered=False, status=500, source="j")
        sviter = DL.failure_streaks("t1")
        rad = next(s for s in sviter if s["provider"] == "sap")
        assert rad["streak"] == 9, rad
        assert rad["kinds"] == ["push.hotspots"]
    finally:
        DL.reset()


def test_alert_job_fires_over_threshold_and_is_quiet_under_it():
    DL.reset()
    CN.reset()
    S.reset()
    try:
        CN.save_connection(CN.connection(
            "slack_webhook",
            {"webhook_url": "https://hooks.slack.com/services/x"},
            tenant="t1"))
        for i in range(2):
            DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                      body=b"x", delivery_id=f"lvx-del-a{i}",
                      delivered=False, status=500, source="j")
        # Under tröskeln (3): tyst, och det är ett RESULTAT.
        tyst = S.JOB_KINDS["delivery_alert"]["run"](
            {"tenant": "t1", "params": {}}, 0.0)
        assert tyst["alerted"] == 0
        assert "no target" in tyst["why_en"]

        DL.record(tenant="t1", kind="push.hotspots", provider="sap",
                  body=b"x", delivery_id="lvx-del-a2",
                  delivered=False, status=500, source="j")
        larmat = {}

        def fake_send(text, kopp, *, tenant, transport=None):
            larmat["text"] = text
            larmat["provider"] = kopp["provider"]
            return {"delivered": True}
        import integrations.redelivery as RD
        gammal = RD.send_alert
        RD.send_alert = fake_send
        try:
            ut = S.JOB_KINDS["delivery_alert"]["run"](
                {"tenant": "t1", "params": {}}, 0.0)
        finally:
            RD.send_alert = gammal
        assert ut["alerted"] == 1
        assert "3 consecutive" in larmat["text"]
        assert larmat["provider"] == "slack_webhook"
    finally:
        DL.reset()
        CN.reset()
        S.reset()


def test_send_alert_logs_itself_and_refuses_without_a_channel():
    from integrations.redelivery import send_alert

    DL.reset()
    try:
        utan = send_alert("test", None, tenant="t1")
        assert utan["delivered"] is False
        assert "nowhere to go" in utan["why_en"]

        kanal = CN.connection(
            "slack_webhook",
            {"webhook_url": "https://hooks.slack.com/services/x"},
            tenant="t1")
        med = send_alert("varning", kanal, tenant="t1",
                         transport=_fix(200, b"ok"))
        assert med["delivered"] is True
        rad = DL.all_deliveries("t1")[0]
        assert rad["kind"] == "alert"
        assert json.dumps(DL.all_deliveries("t1")).count("varning") == 0, \
            "larmtexten (kroppen) ska inte lagras i loggen"
    finally:
        DL.reset()


def test_scheduled_alert_job_kind_validates_at_creation():
    CN.reset()
    S.reset()
    try:
        rad = S.JOB_KINDS["delivery_alert"]
        assert rad["capability"] == "core"
        try:
            S.job("larm", "delivery_alert", cadence={"every": "hourly"},
                  params={"connection": "slack_webhook"}, tenant="t1")
        except S.ScheduleRefused as e:
            assert "slack_webhook" in str(e)
        else:
            raise AssertionError("okopplad kanal accepterades vid "
                                 "skapandet")
    finally:
        CN.reset()
        S.reset()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
