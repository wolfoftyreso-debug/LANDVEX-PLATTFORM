"""Tester för ansvarsloopen (beslut → ägare → förväntat → faktiskt utfall).
Kör: python3 -m tests.test_accountability"""
from __future__ import annotations

from engine import accountability as A

_OWNERS = {"formellt": "Kommunstyrelsen", "operativt": "Stadskontoret",
           "uppfoljning": "Revisionen"}
_EXP = {"metric": "employment_rate", "direction": "increase", "target": 96.0}


def _fresh():
    A.set_store(None)
    A.reset()


def test_commit_requires_all_three_owners():
    _fresh()
    try:
        A.commit("Bygg", {"formellt": "X"}, _EXP)
        raise AssertionError()
    except ValueError as e:
        assert "operativt" in str(e) or "no owner" in str(e)


def test_commit_requires_expected_fields():
    _fresh()
    try:
        A.commit("Bygg", _OWNERS, {"metric": "x"})   # saknar direction/target
        raise AssertionError()
    except ValueError:
        pass


def test_commit_is_content_hashed():
    _fresh()
    a = A.commit("Bygg cykelbana", _OWNERS, _EXP, committed_at="2026-01-01")
    assert a["id"] and a["status"] == "open" and a["owners"] == _OWNERS


def test_resolve_increase_met_and_framing():
    _fresh()
    c = A.commit("Höj sysselsättning", _OWNERS, _EXP)
    r = A.resolve(c, 97.0)
    assert r["met"] is True and r["deviation_pct"] > 0
    # "Statistik ljuger alltid": resultatet bär sin inramning.
    assert "framing" in r and "one framing" in r["framing"]["note"]
    assert r["framing"]["choices"]["target"] == 96.0


def test_resolve_decrease_direction():
    _fresh()
    c = A.commit("Sänk arbetslöshet", _OWNERS,
                 {"metric": "unemployment", "direction": "decrease", "target": 5.0})
    assert A.resolve(c, 4.2)["met"] is True
    assert A.resolve(c, 6.0)["met"] is False


def test_resolve_effectiveness_from_baseline():
    _fresh()
    c = A.commit("Nå 96", _OWNERS, _EXP)
    r = A.resolve(c, 94.0, baseline=90.0)   # 90→96 mål, nådde 94 → 66.7%
    assert 60 <= r["effectiveness"] <= 70


def test_ledger_scores_owner():
    _fresh()
    c1 = A.commit("A", _OWNERS, _EXP, committed_at="1")
    c2 = A.commit("B", _OWNERS, _EXP, committed_at="2")
    A.resolve(c1, 97.0)          # met
    A.resolve(c2, 94.0)          # ej met
    led = A.ledger()
    row = led["ledger"][0]
    assert row["owner"] == "Kommunstyrelsen"
    assert row["decisions"] == 2 and row["resolved"] == 2 and row["met"] == 1
    assert row["met_rate"] == 0.5
    assert "framing" in led


def test_ledger_counts_open():
    _fresh()
    A.commit("Öppet beslut", _OWNERS, _EXP, committed_at="9")
    led = A.ledger()
    assert led["ledger"][0]["open"] == 1 and led["total_resolved"] == 0


def test_store_backed_survives_restart():
    import os
    import tempfile
    from engine.storage.sqlite import SqliteStore
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _fresh()
        s1 = SqliteStore(path)
        A.set_store(s1)
        c = A.commit("Persist", _OWNERS, _EXP, committed_at="p")
        A.resolve(c, 97.0)
        s1.close()
        s2 = SqliteStore(path)          # "omstart"
        A.set_store(s2)
        led = A.ledger()
        assert led["total_decisions"] == 1 and led["total_resolved"] == 1
        assert led["ledger"][0]["met"] == 1
        s2.close()
    finally:
        A.set_store(None); A.reset()
        os.unlink(path)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    A.set_store(None); A.reset()
    print(f"\n{len(fns)} tester gröna.")
