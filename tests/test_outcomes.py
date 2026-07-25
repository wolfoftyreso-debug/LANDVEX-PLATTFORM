"""Tester för utfalls-/kalibreringslagret.
Kör: python3 -m tests.test_outcomes"""
from __future__ import annotations

from engine import outcomes as O


def _seed(n_per_bucket=40):
    """Fyll registret: höga scores överlever oftare (välkalibrerat-ish)."""
    O.reset()
    for i in range(n_per_bucket):
        # prime-hink (score 90): 90% överlevnad. Unik established_at → ingen dedup.
        O.record(O.log_outcome({"market": "us"}, "cafe", 90,
                               survived=(i % 10 != 0), months_active=24,
                               established_at=f"p{i}"))
        # weak-hink (score 40): 30% överlevnad
        O.record(O.log_outcome({"market": "us"}, "cafe", 40,
                               survived=(i % 10 < 3), months_active=6,
                               established_at=f"w{i}"))


def test_log_outcome_hashed_id():
    r = O.log_outcome({"market": "us"}, "gym", 72, survived=True)
    assert r["id"] and r["predicted_score"] == 72.0


def test_append_only_idempotent():
    O.reset()
    r = O.log_outcome({"market": "us"}, "gym", 72, survived=True)
    O.record(r); O.record(r)
    assert len(O.all_records()) == 1


def test_insufficient_before_min_sample():
    O.reset()
    O.record(O.log_outcome({"market": "us"}, "gym", 80, survived=True))
    cal = O.calibration()
    assert cal["status"] == "insufficient" and cal["n"] == 1
    assert O.expected_roi(80)["status"] == "ej_tillgangligt"


def test_brier_bounds():
    O.reset()
    O.record(O.log_outcome({}, "x", 100, survived=True))    # perfekt
    O.record(O.log_outcome({}, "x", 0, survived=False, established_at="b"))
    assert O.brier_score(O.all_records()) == 0.0


def test_calibration_unlocks_and_reports_gap():
    _seed()
    cal = O.calibration()
    assert cal["status"] == "calibrated" and cal["n"] >= O.MIN_SAMPLE
    assert 0.0 <= cal["brier_score"] <= 1.0
    names = {b["bucket"] for b in cal["reliability"]}
    assert "prime" in names and "weak" in names
    assert isinstance(cal["overall_gap"], float)


def test_calibrated_survival_and_roi_unlock():
    _seed()
    s = O.calibrated_survival(90)
    assert s["status"] == "calibrated" and 0.8 <= s["survival_probability"] <= 1.0
    roi = O.expected_roi(90)
    assert roi["status"] == "indikation" and "not a guarantee" in roi["caveat"]


def test_low_bucket_survival_lower():
    _seed()
    assert (O.calibrated_survival(90)["survival_probability"]
            > O.calibrated_survival(40)["survival_probability"])


def test_store_backed_survives_restart():
    """Med ett Store överlever utfallen en 'omstart' (nytt store-objekt,
    samma fil) och process-minnet är irrelevant."""
    import os
    import tempfile
    from engine.storage.sqlite import SqliteStore
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        O.reset()
        s1 = SqliteStore(path)
        O.set_store(s1)
        for i in range(3):
            O.record(O.log_outcome({"market": "us"}, "cafe", 80,
                                   survived=True, established_at=f"s{i}"))
        assert len(O.all_records()) == 3
        # idempotent på id
        O.record(O.log_outcome({"market": "us"}, "cafe", 80,
                               survived=True, established_at="s0"))
        assert len(O.all_records()) == 3
        s1.close()
        # "omstart": nytt store mot samma fil
        s2 = SqliteStore(path)
        O.set_store(s2)
        assert len(O.all_records()) == 3      # överlevde
        s2.close()
    finally:
        O.set_store(None)
        O.reset()
        os.unlink(path)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  ✓ {fn.__name__}")
    O.set_store(None); O.reset()
    print(f"\n{len(fns)} tester gröna.")
