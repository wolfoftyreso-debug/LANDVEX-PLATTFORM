"""Tester för kundresan KYC → onboarding → uppsättning → aktiv.
Kör: python3 -m tests.test_customer"""
from __future__ import annotations

from engine import customer as C


def test_journey_names_an_owner_for_every_stage():
    j = C.journey()
    ids = [s["id"] for s in j["stages"]]
    assert ids == ["kyc", "onboarding", "setup", "active"]
    for s in j["stages"]:
        assert s["owner"] and s["produces_en"]
    # de två första ägs INTE av plattformen
    by = {s["id"]: s["owned_by_platform"] for s in j["stages"]}
    assert by["kyc"] is False and by["onboarding"] is False
    assert by["setup"] is True and by["active"] is True


def test_missing_kyc_is_never_assumed_to_be_fine():
    """Säker default: utan besked är kunden INTE verifierad."""
    for rec in ({}, {"kyc_status": ""}, {"kyc_status": "probably ok"}):
        k = C.kyc_status(rec)
        assert k["state"] == "not_verified" and k["verified"] is False
        assert k["blocked_en"]                     # allt känsligt spärrat
        assert "never assumes" in k["source_en"] or "not verified" in k["source_en"]


def test_verified_kyc_unlocks_the_gated_capabilities():
    k = C.kyc_status({"kyc_status": "verified", "kyc_provider": "acme-kyc",
                      "kyc_verified_at": "2026-02-01"})
    assert k["verified"] and k["provider"] == "acme-kyc"
    assert k["unlocks_en"] and not k["blocked_en"]
    assert "billing & commission payouts" in k["unlocks_en"]


def test_rejected_and_expired_are_not_verified():
    for state in ("rejected", "expired", "pending"):
        k = C.kyc_status({"kyc_status": state})
        assert k["state"] == state and not k["verified"]
        assert k["blocked_en"]


def test_journey_blocks_at_kyc_before_anything_else():
    s = C.stage({"visitor_id": "u1", "role": "business", "place": "se-1880"})
    assert s["stage"] == "kyc" and not s["complete"]
    assert s["blocked_by"]["stage"] == "kyc"
    assert s["blocked_by"]["owner"] == "external KYC/AML provider"
    assert "cannot do this step" in s["blocked_by"]["action_en"]


def test_journey_then_blocks_on_onboarding_fields():
    s = C.stage({"kyc_status": "verified"})
    assert s["stage"] == "onboarding" and not s["complete"]
    assert s["blocked_by"]["stage"] == "onboarding"
    assert s["blocked_by"]["owner"] == "Landvex customer onboarding"


def test_journey_reaches_setup_then_active():
    part = C.stage({"kyc_status": "verified", "visitor_id": "u1",
                    "role": "business"})
    assert part["stage"] == "setup" and not part["complete"]
    assert part["blocked_by"]["missing"] == "place"
    assert part["blocked_by"]["owner"] == "this platform"   # vår att lösa

    full = C.stage({"kyc_status": "verified", "visitor_id": "u1",
                    "role": "business", "place": "se-1880",
                    "trade": "elektriker"})
    assert full["stage"] == "active" and full["complete"]
    assert full["blocked_by"] is None
    assert full["guide"]["status"] == "answer"


def test_stage_carries_the_guide_so_the_ui_never_guesses():
    s = C.stage({"kyc_status": "verified", "visitor_id": "u1"})
    assert s["guide"]["status"] == "identify"        # vet inte vem du är
    assert len(s["guide"]["options"]) == 6


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
