"""Tester för påståendelagret (UIO + governance + citat).
Kör: python3 -m tests.test_claims"""
from __future__ import annotations

from engine import claims as C


def _c(**kw):
    base = dict(
        statement="Population of Malmö grew 1.2% in 2025",
        value=1.2, unit="%",
        source={"authority": "SCB", "origin": "PxWeb"},
        jurisdiction={"scope": "municipality", "country": "SE", "region": "Malmö"},
        time={"observed_at": "2025-12-31"},
        owners={"formellt": "Kommunstyrelsen", "operativt": "Stadskontoret",
                "uppfoljning": "Revisionen"})
    base.update(kw)
    return C.build_claim(**base)


def test_content_addressed_id_is_deterministic():
    a, b = _c(), _c()
    assert a["id"] == b["id"] and a["checksum"] == a["id"]
    assert C.verify(a)


def test_different_content_different_id():
    assert _c(value=1.2)["id"] != _c(value=9.9)["id"]


def test_revise_increments_and_links_without_mutating():
    v1 = _c()
    v2 = C.revise(v1, value=1.5)
    assert v2["version"] == 2
    assert v2["previous_version"] == v1["id"]
    assert v2["id"] != v1["id"]
    assert v1["version"] == 1 and v1["value"] == 1.2   # oförändrat original
    assert C.verify(v2)


def test_tamper_is_detected():
    a = _c()
    a["value"] = 999   # manipulera utan att uppdatera checksum
    assert C.verify(a) is False


def test_governance_requires_three_owners():
    ok, missing = C.validate_governance(_c())
    assert ok and missing == []
    bad = _c(owners={"formellt": "X"})
    ok2, missing2 = C.validate_governance(bad)
    assert not ok2 and set(missing2) == {"operativt", "uppfoljning"}


def test_relation_typed_and_bounded():
    a = _c()
    C.add_relation(a, "supersedes", "abc123", strength=2.0)   # klipps till 1.0
    assert a["relations"][0]["type"] == "supersedes"
    assert a["relations"][0]["strength"] == 1.0
    try:
        C.add_relation(a, "nonsense", "x")
        raise AssertionError()
    except ValueError:
        pass


def test_k_anonymity_gate():
    assert C.k_anonymity_ok(5) is True
    assert C.k_anonymity_ok(4) is False


def test_cite_formats():
    a = _c()
    assert "SCB" in C.cite(a, "text") and "does not originate" in C.cite(a, "text")
    assert C.cite(a, "apa").startswith("SCB (2025)")
    assert C.cite(a, "bibtex").startswith("@misc{landvex_")


def test_claimlog_append_only_and_latest():
    log = C.ClaimLog()
    v1 = _c(); log.append(v1)
    v2 = C.revise(v1, value=1.5); log.append(v2)
    assert len(log) == 2
    assert log.append(v1) == v1["id"]   # idempotent
    assert len(log) == 2
    assert log.latest(v1["id"])["id"] == v2["id"]   # följer lineage framåt


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
