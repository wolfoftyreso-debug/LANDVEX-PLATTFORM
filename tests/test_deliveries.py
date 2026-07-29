"""Utgången som enterprises kräver den: signerad, spårbar, ärlig.

Kör: python3 -m tests.test_deliveries
"""
from __future__ import annotations

import hashlib
import json

from engine import credentials as CR
from engine import deliveries as DL


def test_every_outbound_post_carries_the_three_headers():
    CR.reset()
    DL.reset()
    try:
        kropp = b'{"x": 1}'
        h = DL.outbound_headers("t1", kropp, "credential")
        assert h["X-Landvex-Delivery-Id"].startswith("lvx-del-")
        assert h["X-Landvex-Schema"] == "credential.v1"
        # Signaturen är HMAC med tenantens hemlighet — mottagaren kan
        # räkna om den, och en annan tenant får en annan signatur.
        assert h["X-Landvex-Signature"] != DL.outbound_headers(
            "t2", kropp, "credential")["X-Landvex-Signature"]
        # Idempotens: två leveranser = två id:n, aldrig återbruk.
        assert h["X-Landvex-Delivery-Id"] != DL.outbound_headers(
            "t1", kropp, "credential")["X-Landvex-Delivery-Id"]
    finally:
        CR.reset()
        DL.reset()


def test_the_log_stores_the_hash_never_the_body():
    """Kroppen kan bära det som redan lämnat huset — loggen får aldrig
    bli en andra kopia av den."""
    DL.reset()
    try:
        kropp = json.dumps({"secret_value": "sk-super-hemlig-123",
                            "score": 61}).encode()
        rad = DL.record(tenant="t1", kind="push.hotspots",
                        provider="sap", body=kropp,
                        delivery_id="lvx-del-abc", delivered=True,
                        status=200)
        dump = json.dumps(DL.all_deliveries("t1"))
        assert "sk-super-hemlig-123" not in dump, "kroppen i loggen"
        assert rad["body_sha256"] == hashlib.sha256(kropp).hexdigest()
        assert rad["bytes"] == len(kropp)
    finally:
        DL.reset()


def test_verification_answers_from_the_log_not_from_claims():
    DL.reset()
    try:
        kropp = b'{"riktig": true}'
        DL.record(tenant="t1", kind="credential", provider="sap",
                  body=kropp, delivery_id="lvx-del-riktig",
                  delivered=True, status=201)
        ok = DL.verify_delivery(
            "lvx-del-riktig", hashlib.sha256(kropp).hexdigest(),
            tenant="t1")
        assert ok["known"] is True and ok["match"] is True

        fel = DL.verify_delivery(
            "lvx-del-riktig", hashlib.sha256(b'{"fejk": 1}').hexdigest(),
            tenant="t1")
        assert fel["known"] is True and fel["match"] is False
        assert "altered in transit" in fel["why_en"]

        okand = DL.verify_delivery("lvx-del-finns-ej", "00", tenant="t1")
        assert okand["known"] is False
        # Fel tenant ser inte raden alls — loggen är kundens egen.
        annan = DL.verify_delivery(
            "lvx-del-riktig", hashlib.sha256(kropp).hexdigest(),
            tenant="t2")
        assert annan["known"] is False
    finally:
        DL.reset()


def test_a_failed_attempt_is_a_row_that_says_failed():
    DL.reset()
    try:
        DL.record(tenant="t1", kind="inspection_exception",
                  provider="servicenow", body=b"{}",
                  delivery_id="lvx-del-nere", delivered=False,
                  status="OSError", why_en="never got there")
        rad = DL.all_deliveries("t1")[0]
        assert rad["delivered"] is False and rad["status"] == "OSError"
    finally:
        DL.reset()


def test_the_credential_forward_logs_and_signs():
    """Kvittoleveransen bär de tre huvudena och bokförs — även när
    mottagaren säger nej."""
    from engine import connections as CN
    from integrations import feedback

    CR.reset()
    DL.reset()
    CN.reset()
    try:
        kopp = CN.connection(
            "feedback_webhook",
            {"webhook_url": "https://api.kund.se/lvx"}, tenant="t1")
        cred = CR.issue("check_passed", {"verdict": "pass"},
                        tenant="t1", mission_id="m1")
        fangat = {}

        def transport(url, headers, body, timeout):
            fangat.update(headers)
            return 503, b"nere"
        ut = feedback.forward(cred, kopp, transport=transport)
        assert ut["delivered"] is False
        assert ut["delivery_id"].startswith("lvx-del-")
        assert fangat["X-Landvex-Schema"] == "credential.v1"
        assert fangat["X-Landvex-Signature"], "osignerad utgång"
        rad = DL.all_deliveries("t1")[0]
        assert rad["id"] == ut["delivery_id"]
        assert rad["delivered"] is False and rad["status"] == 503
    finally:
        CR.reset()
        DL.reset()
        CN.reset()


def test_the_push_delivery_logs_with_its_dataset_schema():
    from engine import pushes as P

    DL.reset()
    try:
        fangat = {}

        def transport(url, body, headers, timeout):
            fangat.update(headers)
            return 200, b"ok"
        ut = P.deliver({"tenant": "t1",
                        "params": {"dataset": "hotspots", "format": "csv",
                                   "target_url": "https://mottagare.se/h",
                                   "dataset_params": {"vertical": "gym",
                                                      "market": "us",
                                                      "top_n": 2}}},
                       transport=transport)
        assert ut["delivered"] is True
        assert fangat["X-Landvex-Schema"] == "push.hotspots.v1"
        rad = DL.all_deliveries("t1")[0]
        assert rad["kind"] == "push.hotspots"
        assert rad["id"] == ut["delivery_id"]
    finally:
        DL.reset()


def test_the_scheduled_exception_report_is_a_job_kind():
    """Nattlig arkivering: jobbtypen finns med rätt kapabilitet, en
    namngiven koppling prövas när jobbet SKAPAS, och utan koppling är
    körningen en redovisad vägran — aldrig en tyst natt."""
    from engine import connections as CN
    from engine import scheduler as S

    CN.reset()
    try:
        rad = S.JOB_KINDS["exception_report"]
        assert rad["capability"] == "asset_inspections"
        assert "never a quiet night" in rad["note_en"]
        try:
            S.job("natt", "exception_report",
                  cadence={"every": "daily"},
                  params={"connection": "servicenow"}, tenant="t1")
        except S.ScheduleRefused as e:
            assert "servicenow" in str(e)
        else:
            raise AssertionError("okopplat system accepterades vid "
                                 "skapandet")
        ut = S.JOB_KINDS["exception_report"]["run"](
            {"tenant": "t1", "params": {}}, 0.0)
        assert ut["sent"] == 0
        assert "no system connected" in ut["why_en"]
    finally:
        CN.reset()


def test_the_catalog_states_what_the_log_cannot_say():
    k = DL.catalog()
    assert "never the payload body" in k["cannot_en"]
    assert "receiver's word" in k["cannot_en"]
    assert json.dumps(k)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
