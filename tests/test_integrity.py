"""Tester för integritetslagret (neutralitet/citat/grounding/självrevision).
Kör utan pytest och utan nätverk: python3 -m tests.test_integrity"""
from __future__ import annotations

from engine.integrity import (
    DISCLAIMER, UNABLE, audit, canonical_hash, classify_query, derive_trend,
    derive_uncertainty, evidence_link, integrity_score, neutralize,
    validate_provenance, validate_text, verify_citations,
)


# --- 1. Frågegrind -------------------------------------------------------
def test_query_gate_blocks_prediction():
    b = classify_query("What will happen to prices next year?")
    assert b and b["reason"] == "prediction"


def test_query_gate_blocks_normative_and_value():
    assert classify_query("What should I do?")["reason"] == "normative"
    assert classify_query("Which is the best location?")["reason"] == "value_judgment"


def test_query_gate_passes_neutral():
    assert classify_query("What is the observed population change in Malmö?") is None


# --- 2. Utfalls-sanering -------------------------------------------------
def test_neutralize_strips_causal_words_and_adds_disclaimer():
    clean, viol = neutralize("The rise was caused by policy, therefore prices rose.")
    assert "caused by" in viol and "therefore" in viol
    assert "[BLOCKED]" in clean
    assert DISCLAIMER in clean


def test_neutralize_neutral_text_only_gets_disclaimer():
    clean, viol = neutralize("An observed deviation occurred in employment during 2025.")
    assert viol == []
    assert "[BLOCKED]" not in clean
    assert clean.endswith(DISCLAIMER)


def test_neutralize_all_blocked_falls_back():
    clean, _ = neutralize("should must better worse")
    assert clean == UNABLE


def test_validate_text_reports_validity():
    assert validate_text("neutral observation")["valid"] is True
    assert validate_text("this proves it")["valid"] is False


# --- 3. Citat / grounding ------------------------------------------------
def test_provenance_requires_all_nine_fields():
    ok, missing = validate_provenance({"source_id": "scb"})
    assert not ok and "license" in missing and len(missing) == 8
    full = {f: "x" for f in (
        "source_id", "source_type", "update_frequency", "temporal_coverage",
        "geographic_coverage", "method", "uncertainty", "license", "last_verified")}
    assert validate_provenance(full) == (True, [])


def test_derive_trend():
    assert derive_trend(101, 100)[0] == "stable"      # 1% < 2%
    assert derive_trend(110, 100)[0] == "up"
    assert derive_trend(90, 100)[0] == "down"
    assert derive_trend(5, None)[0] == "stable"


def test_derive_uncertainty():
    assert derive_uncertainty(12, [85, 90, 88]) == "low"
    assert derive_uncertainty(3, [90]) == "high"
    assert derive_uncertainty(8, [55]) == "high"
    assert derive_uncertainty(8, [70, 75]) == "medium"


def test_verify_citations_blocks_unsourced_and_mismatch():
    retrieved = {"IDX_POP": {"value": 100.0}}
    r = verify_citations(
        [{"index_id": "IDX_POP", "value": 100.0},   # ok
         {"index_id": "IDX_GHOST", "value": 5},      # inte i kontext
         {"index_id": "IDX_POP", "value": 999}],     # värde-mismatch
        retrieved)
    assert r["all_valid"] is False
    assert len(r["valid"]) == 1 and len(r["invalid"]) == 2
    problems = {x["problem"] for x in r["invalid"]}
    assert problems == {"index_not_in_context", "value_mismatch"}


def test_verify_citations_all_valid():
    r = verify_citations([{"index_id": "A"}], {"A": {"value": 1}})
    assert r["all_valid"] is True


def test_evidence_link_deterministic_and_tamper_evident():
    p = {"data": [1, 2], "sources": ["scb"]}
    assert evidence_link(p) == evidence_link(dict(reversed(list(p.items()))))
    assert evidence_link(p) != evidence_link({"data": [1, 3], "sources": ["scb"]})
    assert evidence_link(p).startswith("EL-")


def test_canonical_hash_order_independent():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


# --- 4. Självrevision ----------------------------------------------------
def test_audit_flags_missing_uncertainty():
    f = audit([{"value": 1, "method": "observed", "source": "scb"}])
    assert any(x["category"] == "missing_uncertainty" and x["severity"] == "critical"
               for x in f)


def test_audit_flags_estimate_as_observation():
    f = audit([{"value": 1, "uncertainty": "low", "method": "estimated"}])
    assert any(x["category"] == "estimate_as_observation" for x in f)


def test_audit_flags_suspicious_stability():
    f = audit([{"value": 5, "uncertainty": "low", "method": "observed",
                "source": "scb", "series": [5, 5, 5, 5, 5]}])
    assert any(x["category"] == "suspicious_stability" for x in f)


def test_audit_clean_record_passes():
    f = audit([{"value": 5, "uncertainty": "low", "method": "observed",
                "source": "scb", "series": [1, 2, 3, 4, 5]}])
    assert f == []
    assert integrity_score(f) == {"integrity_score": 100, "passed": True,
                                  "critical_count": 0, "finding_count": 0}


def test_integrity_score_fails_on_critical():
    f = audit([{"value": 1, "method": "observed"}])   # saknar uncertainty
    s = integrity_score(f)
    assert s["passed"] is False and s["integrity_score"] < 100


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
