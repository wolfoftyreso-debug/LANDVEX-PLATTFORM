"""Varumärket på uppdraget och kvittot som sluter loopen.

Bevakar: profilen valideras vid dörren, varumärkesblocket rider på
BÅDA uppdragsslagen (fotokontroll och sponsrat), bara godkänt
certifieras, en ändrad byte fäller signaturen, person vägras i
kvittot, och en misslyckad leverans ser aldrig levererad ut.

Kör: python3 -m tests.test_company
"""
from __future__ import annotations

import json

from engine import company as CO
from engine import credentials as CR


def _profil(**kw):
    bas = dict(name="Flaggservice AB",
               about_en="Flags and flagpoles across Stockholm.",
               logo_url="https://cdn.flaggservice.se/logo.png",
               website="https://flaggservice.se",
               brand_color="#0A84FF")
    bas.update(kw)
    return CO.profile("flaggab", **bas)


def test_a_profile_without_a_name_is_refused():
    try:
        CO.profile("t1", name="   ")
    except CO.ProfileRefused as e:
        assert "unnamed" in str(e)
    else:
        raise AssertionError("namnlös profil sparades")


def test_profile_urls_must_be_public_https():
    for falt, varde in (("logo_url", "http://cdn.x.se/l.png"),
                        ("logo_url", "https://192.168.0.5/l.png"),
                        ("website", "https://localhost/x")):
        try:
            CO.profile("t1", name="X", **{falt: varde})
        except CO.ProfileRefused as e:
            assert falt in str(e)
        else:
            raise AssertionError(f"{falt}={varde} accepterades")
    try:
        CO.profile("t1", name="X", brand_color="blå")
    except CO.ProfileRefused as e:
        assert "#hex" in str(e)
    else:
        raise AssertionError("ordet 'blå' blev en färg")


def test_the_brand_rides_on_the_photo_check_mission():
    """Dispatchkroppen till quiXzoom bär loggan och tap-infon —
    och utan profil finns inget block alls (ärlig frånvaro)."""
    from engine import inspections as I
    from integrations.quixzoom_dispatch import MissionDispatcher

    CO.reset()
    try:
        d = MissionDispatcher(base_url="https://qz.example",
                              transport=lambda *a, **k: b'{"id":"m1"}')
        asset = I.asset("fp1", "flagpole", label_en="Stången",
                        lat=59.3, lon=18.0, tenant="flaggab")
        rut = I.routine("v", "Weekly", "flagpole", 7,
                        checks=["present"], tenant="flaggab")
        utan = d._kropp(asset, rut, "2026-08-01", 50)
        assert "brand" not in utan, "block utan profil hittades på"
        CO.save_profile(_profil())
        med = d._kropp(asset, rut, "2026-08-01", 50)
        assert med["brand"]["company_en"] == "Flaggservice AB"
        assert med["brand"]["logo_url"].startswith("https://cdn.")
        assert "Tap-through" in med["brand"]["tap_info_en"]
    finally:
        CO.reset()


def test_the_brand_rides_on_the_sponsored_mission_too():
    from engine import sponsorship as SP

    CO.reset()
    try:
        CO.save_profile(CO.profile(
            "t1", name="Garmin Nordic",
            logo_url="https://cdn.garmin.com/nordic.png"))
        kamp = SP.campaign(
            "k1", "Garmin Nordic", "verification",
            "Photograph the trailhead sign", budget=1000.0,
            rewards=({"kind": "cash", "amount": 50.0},), tenant="t1")
        kropp = SP.mission_body(kamp, region_code="0180")
        assert kropp["brand"]["company_en"] == "Garmin Nordic"
        assert kropp["sponsor_visible_en"] == "Garmin Nordic"
    finally:
        CO.reset()


def test_only_a_pass_is_certified():
    CR.reset()
    try:
        for dom in ("fail", "unclear", ""):
            try:
                CR.issue("check_passed", {"verdict": dom},
                         tenant="t1", mission_id="m1")
            except CR.CredentialRefused as e:
                assert "only a PASS" in str(e)
            else:
                raise AssertionError(f"{dom!r} certifierades")
        utan_uppdrag = None
        try:
            CR.issue("check_passed", {"verdict": "pass"},
                     tenant="t1", mission_id="")
        except CR.CredentialRefused as e:
            utan_uppdrag = str(e)
        assert utan_uppdrag and "mission reference" in utan_uppdrag
    finally:
        CR.reset()


def test_a_credential_verifies_and_a_changed_byte_fails_it():
    CR.reset()
    try:
        cred = CR.issue("check_passed",
                        {"verdict": "pass", "asset_id": "fp1"},
                        tenant="t1", mission_id="qz-m1")
        assert cred["id"].startswith("lvx-cred-")
        assert CR.verify(cred, tenant="t1")["valid"] is True
        fusk = json.loads(json.dumps(cred))
        fusk["subject"]["asset_id"] = "fp2"
        svar = CR.verify(fusk, tenant="t1")
        assert svar["valid"] is False and "altered" in svar["why_en"]
        # Fel tenant kan aldrig gå i god för kvittot.
        assert CR.verify(cred, tenant="t2")["valid"] is False
    finally:
        CR.reset()


def test_a_credential_never_carries_a_person():
    CR.reset()
    try:
        CR.issue("sponsored_completion",
                 {"campaign_id": "k1", "zoomer_id": "qz-1"},
                 tenant="t1", mission_id="m1")
    except CR.CredentialRefused as e:
        assert "never" in str(e).lower() and "quiXzoom" in str(e)
    else:
        raise AssertionError("personen följde med kvittot")
    finally:
        CR.reset()


def test_forwarding_is_honest_with_and_without_a_connection():
    from engine import connections as CN
    from integrations import feedback

    CR.reset()
    cred = CR.issue("check_passed", {"verdict": "pass"},
                    tenant="t1", mission_id="m1")
    utan = feedback.forward(cred, None)
    assert utan["delivered"] is False
    assert "loop closes" in utan["why_en"]

    koppling = CN.connection(
        "feedback_webhook",
        {"webhook_url": "https://api.kund.se/landvex"}, tenant="t1")
    anrop = []

    def transport(url, headers, body, timeout):
        anrop.append(json.loads(body))
        return 200, b"ok"
    ok = feedback.forward(cred, koppling, transport=transport)
    assert ok["delivered"] is True
    assert anrop[0]["id"] == cred["id"], "kvittot ska skickas ordagrant"

    def nere(url, headers, body, timeout):
        raise OSError("connection refused")
    fel = feedback.forward(cred, koppling, transport=nere)
    assert fel["delivered"] is False
    assert "Nothing is reported as delivered" in fel["why_en"]
    assert "api.kund.se" not in fel["why_en"], "webhooken i felet"
    CR.reset()


def test_the_secret_has_no_read_path_and_survives_a_restart():
    """Hemligheten lämnar aldrig systemet — inte ens maskerad — och
    ett kvitto verifierar efter omstart (hemligheten bor i lagret)."""
    from engine.storage.sqlite import SqliteStore

    CR.reset()
    st = SqliteStore(":memory:")
    CR.set_store(st)
    try:
        cred = CR.issue("check_passed", {"verdict": "pass"},
                        tenant="t1", mission_id="m1")
        assert st.credential_secret("t1").hex() not in json.dumps(cred)
        # "Omstart": minnescachen töms, lagret består.
        CR.reset()
        assert CR.verify(cred, tenant="t1")["valid"] is True
    finally:
        CR.set_store(None)
        CR.reset()


def test_both_stores_offer_the_company_contract():
    from engine.storage.postgres import PostgresStore
    from engine.storage.sqlite import SqliteStore

    for st in (SqliteStore, PostgresStore):
        for metod in ("save_company_profile", "get_company_profile",
                      "credential_secret"):
            assert callable(getattr(st, metod, None)), f"{st.__name__}.{metod}"


def test_the_catalogs_state_what_they_cannot_do():
    for kat in (CO.catalog(), CR.catalog()):
        assert len(kat["cannot_en"]) > 60
        assert json.dumps(kat)
    assert "quiXzoom's" in CO.catalog()["cannot_en"]
    assert "never WHO" in CR.catalog()["cannot_en"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
