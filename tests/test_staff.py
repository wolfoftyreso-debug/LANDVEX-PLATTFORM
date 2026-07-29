"""Egna anställda som zoomers: referenser in, aldrig personer.

Kör: python3 -m tests.test_staff
"""
from __future__ import annotations

import json

from engine import staff as ST


def test_a_reference_is_linked_and_a_person_is_refused():
    rad = ST.member("qz-staff-007", tenant="t1",
                    role_label_en="Rental fleet, Arlanda")
    assert rad["kind"] == "member" and rad["zoomer_ref"] == "qz-staff-007"
    for fel in ("anna.svensson@bolag.se", "Anna Svensson", "staff-007"):
        try:
            ST.member(fel, tenant="t1")
        except ST.StaffRefused as e:
            assert "quiXzoom" in str(e)
        else:
            raise AssertionError(f"{fel!r} accepterades som referens")


def test_an_invite_carries_a_role_never_an_identity():
    inv = ST.invite(tenant="t1", role_label_en="Store staff, Gamla stan")
    assert inv["id"].startswith("lvx-inv-")
    assert inv["status"] == "pending"
    assert "identity and consent" in inv["hand_to_employee_en"]
    try:
        ST.invite(tenant="t1", role_label_en="")
    except ST.StaffRefused as e:
        assert "role label" in str(e)
    else:
        raise AssertionError("rollös inbjudan skapades")


def test_an_invite_is_claimed_once_and_becomes_a_member():
    ST.reset()
    try:
        inv = ST.invite(tenant="t1", role_label_en="Butik Nord")
        ST.save_staff(inv)
        ny = ST.claim_invite(inv["id"], "qz-staff-042", tenant="t1")
        assert ny["kind"] == "member"
        assert ny["role_label_en"] == "Butik Nord"
        assert "qz-staff-042" in ST.refs("t1")
        # Koden är förbrukad — en återanvändbar kod släpper in vem som
        # helst som sett den.
        try:
            ST.claim_invite(inv["id"], "qz-staff-043", tenant="t1")
        except ST.StaffRefused as e:
            assert "once" in str(e)
        else:
            raise AssertionError("koden gick att använda två gånger")
        # Fel tenant kan inte lösa in någon annans kod.
        inv2 = ST.invite(tenant="t1", role_label_en="X")
        ST.save_staff(inv2)
        try:
            ST.claim_invite(inv2["id"], "qz-staff-044", tenant="t2")
        except ST.StaffRefused as e:
            assert "tenant-bound" in str(e)
        else:
            raise AssertionError("t2 löste in t1:s kod")
    finally:
        ST.reset()


def test_the_roster_feeds_a_named_audience():
    """Registret är det rutinernas riktade publik pekar på."""
    from engine import inspections as I

    ST.reset()
    try:
        ST.save_staff(ST.member("qz-staff-001", tenant="t1",
                                role_label_en="Hyrbilar"))
        ST.save_staff(ST.member("qz-staff-002", tenant="t1",
                                role_label_en="Hyrbilar"))
        pub = I.audience(pool="named",
                         zoomer_ids=tuple(ST.refs("t1")),
                         label_en="Own staff")
        assert pub["zoomer_ids"] == ("qz-staff-001", "qz-staff-002")
    finally:
        ST.reset()


def test_removal_stops_targeting_and_isolation_holds():
    ST.reset()
    try:
        ST.save_staff(ST.member("qz-a-1", tenant="t1"))
        ST.save_staff(ST.member("qz-b-1", tenant="t2"))
        assert ST.refs("t1") == ["qz-a-1"]
        assert ST.remove_staff("qz-a-1", tenant="t1") is True
        assert ST.refs("t1") == []
        assert ST.refs("t2") == ["qz-b-1"], "t2:s rad rördes"
        assert ST.remove_staff("qz-b-1", tenant="t1") is False, \
            "t1 raderade t2:s rad"
    finally:
        ST.reset()


def test_staff_survive_a_restart():
    from engine.storage.sqlite import SqliteStore

    ST.reset()
    ST.set_store(SqliteStore(":memory:"))
    try:
        ST.save_staff(ST.member("qz-staff-001", tenant="t1"))
        assert ST.refs("t1") == ["qz-staff-001"]
        assert ST.remove_staff("qz-staff-001", tenant="t1") is True
    finally:
        ST.set_store(None)
        ST.reset()


def test_the_catalog_states_the_boundary():
    k = ST.catalog()
    assert "never names" in k["cannot_en"]
    assert "quiXzoom" in k["cannot_en"]
    assert json.dumps(k)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
