"""Tester för wiki-rättelser + consensus-adaptation.
Kör: python3 -m tests.test_corrections"""
from __future__ import annotations

from engine import corrections as C


def _fresh():
    C.set_store(None); C.reset()


def _submit_n(n, base=44.0, spread=0.0, one_submitter=False, sourced=True):
    for i in range(n):
        C.submit("se-1880", "parking_per_100_jobs",
                 base + (spread * (i - n / 2)),
                 source=("SCB" if sourced else ""),
                 submitter_id=("u0" if one_submitter else f"u{i}"))


def test_submit_requires_source():
    _fresh()
    try:
        C.submit("r", "k", 1.0, source="", submitter_id="u1")
        raise AssertionError()
    except ValueError:
        pass


def test_consensus_not_met_below_threshold():
    _fresh(); _submit_n(3)
    c = C.consensus("parking_per_100_jobs", "se-1880")
    assert c["threshold_met"] is False
    assert any("distinct submitters" in x for x in c["needed"])


def test_brigading_blocked_same_submitter():
    _fresh(); _submit_n(6, one_submitter=True)
    c = C.consensus("parking_per_100_jobs", "se-1880")
    # 6 inlämningar men 1 distinkt inlämnare (idempotent id → 1 rad ändå)
    assert c["distinct_submitters"] == 1 and c["threshold_met"] is False


def test_divergence_blocks_adapt():
    _fresh(); _submit_n(6, base=44, spread=20)   # spridda värden → hög CV
    c = C.consensus("parking_per_100_jobs", "se-1880")
    assert c["converged"] is False and c["threshold_met"] is False


def test_consensus_met_adapts():
    _fresh(); _submit_n(6, base=44, spread=0.3)   # 6 distinkta, samstämmiga, källbelagda
    c = C.consensus("parking_per_100_jobs", "se-1880")
    assert c["threshold_met"] is True
    a = C.adapt("parking_per_100_jobs", "se-1880")
    assert a["status"] == "adapted" and a["source"] == "community"
    assert a["reversible"] is True
    assert a["provenance"]["distinct_submitters"] >= 5


def test_adapt_not_yet_when_thin():
    _fresh(); _submit_n(2)
    assert C.adapt("parking_per_100_jobs", "se-1880")["status"] == "not_yet"


def test_store_backed_survives_restart():
    import os
    import tempfile
    from engine.storage.sqlite import SqliteStore
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    try:
        _fresh()
        s1 = SqliteStore(path); C.set_store(s1)
        _submit_n(6, base=44, spread=0.3)
        assert C.consensus("parking_per_100_jobs", "se-1880")["threshold_met"]
        s1.close()
        s2 = SqliteStore(path); C.set_store(s2)   # "omstart"
        assert C.adapt("parking_per_100_jobs", "se-1880")["status"] == "adapted"
        s2.close()
    finally:
        C.set_store(None); C.reset(); os.unlink(path)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    C.set_store(None); C.reset()
    print(f"\n{len(fns)} tester gröna.")
