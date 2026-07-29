"""Självrevisionen måste själv kunna fällas — annars är den en grön
stämpel med ett API på.

Varje kontroll prövas mot syntetiskt underlag där felet FINNS, och ska
namnge det. Sist körs hela revisionen mot den riktiga kodbasen och ska
vara passed: det är plattformens egen gröna stämpel, och den faller när
nästa regression införs.

Kör: python3 -m tests.test_selfaudit
"""
from __future__ import annotations

import pathlib
import tempfile

from engine import selfaudit as SA


def _repo(filer: dict[str, str]) -> pathlib.Path:
    rot = pathlib.Path(tempfile.mkdtemp())
    for rel, innehall in filer.items():
        p = rot / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(innehall, encoding="utf-8")
    return rot


def test_an_unguarded_except_in_a_synthetic_repo_is_named():
    rot = _repo({"engine/x.py": (
        "try:\n    pass\nexcept Exception:\n    pass\n")})
    fynd = SA.broad_except_sites(rot)
    assert [f["site"] for f in fynd] == ["engine/x.py:3"]
    # och vakten friar
    rot2 = _repo({"engine/x.py": (
        "try:\n    pass\nexcept OUR_BUGS:\n    raise\n"
        "except Exception:\n    pass\n")})
    assert SA.broad_except_sites(rot2) == []


def test_a_layer_violation_outside_the_seams_is_critical():
    rot = _repo({"engine/smyg.py": "from api.licensing import PLANS\n"})
    fynd = SA.layer_violations(rot)
    assert fynd and fynd[0]["severity"] == "critical"
    assert fynd[0]["site"] == "engine/smyg.py:1"
    # sömmarna själva friar i den riktiga kodbasen
    assert SA.layer_violations() == []


def test_a_nonstdlib_top_import_in_the_core_is_critical():
    rot = _repo({"engine/x.py": "import fastapi\n"})
    fynd = SA.nonstdlib_top_imports(rot)
    assert fynd and fynd[0]["imports"] == "fastapi"
    # lazy import inuti en funktion är INTE den här kontrollens sak
    rot2 = _repo({"engine/x.py": "def f():\n    import psycopg\n"})
    assert SA.nonstdlib_top_imports(rot2) == []


def test_a_missing_honesty_marker_is_named():
    rot = _repo({"engine/scoring.py": "def analyze(): pass\n"})
    fynd = SA.missing_honesty_markers(rot)
    platser = [f["site"] for f in fynd]
    assert "engine/scoring.py" in platser          # markören saknas
    assert "engine/mrai.py" in platser             # filen saknas helt


def test_a_module_no_test_mentions_is_reported():
    rot = _repo({"engine/hemlig.py": "X = 1\n",
                 "tests/test_annat.py": "from engine import scoring\n"})
    fynd = SA.modules_without_tests(rot)
    assert [f["site"] for f in fynd] == ["engine/hemlig.py"]


def test_an_ungated_endpoint_in_the_context_is_found():
    ctx = {"pairs": {("GET", "/v1/oppen"), ("GET", "/v1/gated"),
                     ("GET", "/health")},
           "open_paths": set(),
           "required_capability":
               lambda p: "core" if p == "/v1/gated" else None}
    fynd = SA.ungated_endpoints(ctx)
    assert [f["site"] for f in fynd] == ["/v1/oppen"]


def test_without_api_context_the_gate_check_refuses_not_guesses():
    r = SA.run_audit()
    grind = next(c for c in r["checks"] if c["id"] == "ungated_endpoints")
    assert grind["status"] == "refused"
    assert "refuses rather than" in grind["refusal_en"]
    assert r["checks_refused"] == 1


def test_every_check_can_be_opened():
    """Samma regel som MRAI:s komponenter: en kontroll utan cannot_en är
    ett omdöme med en siffra på."""
    for c in SA.CHECKS:
        assert c["what_en"] and len(c["cannot_en"]) > 60, c["id"]
    r = SA.run_audit()
    assert r["what_en"] and r["cannot_en"]
    assert r["audit_id"]


def test_findings_break_the_pass_and_move_the_audit_id():
    """passed är inte en artighet: ett enda fynd ska fälla den, och
    audit_id är innehållsadresserat — samma fynd, samma id."""
    ctx = {"pairs": {("GET", "/v1/oppen")}, "open_paths": set(),
           "required_capability": lambda p: None}
    r1 = SA.run_audit(ctx)
    assert r1["passed"] is False and r1["finding_count"] >= 1
    r2 = SA.run_audit(ctx)
    assert r2["audit_id"] == r1["audit_id"]


def test_the_real_codebase_passes_its_own_audit():
    """Plattformens egen gröna stämpel — allt revisionen fann är åtgärdat,
    och nästa regression fäller det här testet."""
    from api.surface_scan import selfaudit_context

    r = SA.run_audit(selfaudit_context())
    oppna = {c["id"]: [f["site"] for f in c.get("findings", [])]
             for c in r["checks"] if c.get("findings")}
    assert r["passed"] is True, oppna
    assert r["checks_refused"] == 0


def test_the_surface_is_reachable_without_buying_anything():
    from api.licensing import required_capability

    assert required_capability("/v1/integrity/audit") == "core"
    # och säkerhetsloggen är EN ANNAN yta med hårdare krav — orörd
    assert required_capability("/v1/audit") == "platform_ops"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
