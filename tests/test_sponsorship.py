"""Sponsrade uppdrag: pengarna, transparensen — och gränsen mot personen.

Tre saker kan gå riktigt illa här, och sviten prövar dem först:

  1. Ett uppdrag vars finansiär är dold. Zoomern ska veta vad hen
     deltar i INNAN accept.
  2. En budget som tyst överskrids. Ett tak som inte håller är ingen
     budget, det är en prognos med fel namn.
  3. Persondata som sipprar in i sponsorstatistiken. En "aggregerad"
     cell med fyra personer i är en individ med ett medelvärde på.

Kör: python3 -m tests.test_sponsorship
"""
from __future__ import annotations

import time

from engine import sponsorship as SP


def _kampanj(**kw) -> dict:
    bas = dict(id="garmin-trail", sponsor_visible_en="Garmin Nordic AB",
               mission_class="content",
               brief_en="Photograph a Garmin watch on a trail run outdoors",
               budget=1000.0,
               rewards=({"kind": "cash", "amount": 75.0},
                        {"kind": "voucher",
                         "label_en": "Starbucks voucher"}),
               rights_agreement_ref="qz-agr-2026-0142",
               tenant="t1")
    bas.update(kw)
    return SP.campaign(**bas)


# ── 1. Transparensen är fält, inte policy ──────────────────────────────
def test_a_mission_whose_funder_is_hidden_is_refused_at_creation():
    for tom in ("", "   "):
        try:
            _kampanj(sponsor_visible_en=tom)
        except SP.SponsorshipRefused as e:
            assert "ZOOMER sees" in str(e)
        else:
            raise AssertionError("dold finansiär skulle ha vägrats")


def test_the_mission_body_tells_the_zoomer_what_they_are_joining():
    k = _kampanj()
    kropp = SP.mission_body(k, region_code="0180")
    assert kropp["sponsor_visible_en"] == "Garmin Nordic AB"
    assert "funded by Garmin Nordic AB" in kropp["what_this_means_en"]
    # och var personen, betalningen och samtycket faktiskt bor
    assert "quiXzoom, not with the sponsor" in kropp["what_this_means_en"]
    assert kropp["rewards_offered"][0]["amount"] == 75.0


def test_content_missions_need_a_rights_reference_before_anything_exists():
    """Ett uppdrag vars material ingen får använda är ett löfte som inte
    kan hållas — och det ska fällas INNAN någon fotograferar."""
    try:
        _kampanj(rights_agreement_ref="")
    except SP.SponsorshipRefused as e:
        assert "rights_agreement_ref" in str(e)
    else:
        raise AssertionError("content utan rättighetsavtal skulle vägrats")
    # verification-klassen kräver det INTE: den samlar lägesbild, inte
    # material som sponsorn ska publicera
    k = _kampanj(id="gata", mission_class="verification",
                 brief_en="Photograph the pedestrian crossing",
                 rights_agreement_ref="")
    assert k["mission_class"] == "verification"


# ── 2. Budgeten är ett tak ─────────────────────────────────────────────
def test_the_budget_cap_stops_the_next_mission_and_says_why():
    k = _kampanj(budget=200.0)                 # 75 kr/uppdrag → 2 ryms
    for _ in range(2):
        grind = SP.can_order(k)
        assert grind["allowed"], grind
        k["spent"] += grind["cost"]
        k["ordered"] += 1
    grind = SP.can_order(k)
    assert grind["allowed"] is False
    assert "budget cap" in grind["why_en"]
    assert "150.00 of 200.00" in grind["why_en"]


def test_pacing_holds_for_a_day_and_resets_the_next():
    k = _kampanj(max_per_day=3)
    assert SP.can_order(k, today_count=2)["allowed"] is True
    stopp = SP.can_order(k, today_count=3)
    assert stopp["allowed"] is False and "pacing" in stopp["why_en"]
    assert "Tomorrow counts from zero" in stopp["why_en"]


def test_co_sponsor_shares_must_account_for_the_whole_bill():
    try:
        _kampanj(co_sponsors=({"name_en": "Garmin", "share": 0.5},
                              {"name_en": "Kommunen", "share": 0.3}))
    except SP.SponsorshipRefused as e:
        assert "not 1.0" in str(e)
    else:
        raise AssertionError("oallokerad andel skulle ha vägrats")
    k = _kampanj(co_sponsors=({"name_en": "Garmin", "share": 0.6},
                              {"name_en": "Kommunen", "share": 0.4}))
    assert len(k["co_sponsors"]) == 2


def test_an_unpaid_campaign_is_not_a_campaign():
    for fel in ({"rewards": ()}, {"budget": 0},
                {"rewards": ({"kind": "bitcoin", "amount": 1},)},
                {"rewards": ({"kind": "cash"},)},   # kontant utan belopp
                {"brief_en": "  "}, {"mission_class": "spionage"},
                {"tenant": ""}):
        try:
            _kampanj(**fel)
        except SP.SponsorshipRefused:
            continue
        raise AssertionError(f"{fel} skulle ha vägrats")


# ── 3. Gränsen mot personen ────────────────────────────────────────────
def test_a_completion_carrying_a_person_is_refused_at_the_door():
    for falt in ("zoomer_id", "email", "name", "device_id", "phone"):
        try:
            SP.completion("garmin-trail", "m-1",
                          verdicts={falt: "någon", "product_in_frame": True},
                          tenant="t1")
        except SP.SponsorshipRefused as e:
            assert "never WHO" in str(e)
        else:
            raise AssertionError(f"{falt} skulle ha vägrats")


def test_a_completion_records_the_verdict_and_the_place():
    r = SP.completion("garmin-trail", "m-1", region_code="0180",
                      quality_band="good",
                      verdicts={"product_in_frame": True, "outdoors": True,
                                "fresh": True},
                      settlement_ref="qz-settle-991", tenant="t1")
    assert r["verdicts"]["product_in_frame"] is True
    assert r["settlement_ref"] == "qz-settle-991"
    assert not any(k in r for k in ("zoomer_id", "name", "email"))


def test_the_k_floor_suppresses_thin_cells_and_counts_them():
    """Fyra fullbordanden i en region är fyra personer. Cellen visas
    inte — och sponsorn ser ATT något undertrycktes, aldrig vad."""
    SP.reset()
    k = _kampanj(id="mcflurry", mission_class="verification",
                 brief_en="Photograph the product outdoors in daylight",
                 rights_agreement_ref="")
    k["ordered"] = 12
    SP.save_campaign(k)
    nu = time.time()
    for i in range(7):                     # Stockholm: över golvet
        SP.save_completion(SP.completion(
            "mcflurry", f"m-s{i}", region_code="0180",
            quality_band="good", tenant="t1", completed_at=nu))
    for i in range(4):                     # Solna: UNDER golvet
        SP.save_completion(SP.completion(
            "mcflurry", f"m-n{i}", region_code="0184",
            quality_band="fair", tenant="t1", completed_at=nu))
    s = SP.stats("mcflurry", tenant="t1")
    assert s["regions"] == {"0180": 7}
    assert "0184" not in s["regions"]
    assert s["regions_suppressed"] == 1
    assert f"fewer than {SP.K_MIN}" in s["suppressed_note_en"]
    assert s["completed"] == 11 and s["completion_rate"] == round(11 / 12, 3)
    SP.reset()


def test_no_sponsor_surface_can_name_a_person():
    """Fältsvep över hela statistiksvaret: inget nyckelnamn och inget
    strängvärde får bära en persondatabeteckning."""
    SP.reset()
    k = _kampanj(id="ikea", mission_class="verification",
                 brief_en="Show an IKEA product in a real home",
                 rights_agreement_ref="")
    SP.save_campaign(k)
    for i in range(6):
        SP.save_completion(SP.completion(
            "ikea", f"m-{i}", region_code="0180", tenant="t1"))
    s = SP.stats("ikea", tenant="t1")

    def svep(x, vag=""):
        if isinstance(x, dict):
            for nyckel, v in x.items():
                assert not any(f in str(nyckel).lower() for f in
                               ("zoomer", "user", "email", "phone",
                                "device", "person")), f"{vag}.{nyckel}"
                svep(v, f"{vag}.{nyckel}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                svep(v, f"{vag}[{i}]")

    svep(s)
    assert "cannot say WHO" in s["cannot_en"]
    SP.reset()


def test_the_stats_name_their_own_roi_assumption():
    SP.reset()
    SP.save_campaign(_kampanj(id="nike", mission_class="verification",
                              brief_en="Photograph your running shoes",
                              rights_agreement_ref=""))
    s = SP.stats("nike", tenant="t1")
    assert "equally valuable" in s["roi_basis_en"]
    assert s["completion_rate"] is None      # inget beställt än
    SP.reset()


def test_a_campaign_belongs_to_its_tenant_only():
    SP.reset()
    SP.save_campaign(_kampanj(id="k1", tenant="t1"))
    SP.save_campaign(_kampanj(id="k2", tenant="t2"))
    assert {k["id"] for k in SP.all_campaigns("t1")} == {"k1"}
    try:
        SP.stats("k2", tenant="t1")
    except SP.SponsorshipRefused:
        pass
    else:
        raise AssertionError("annan kunds kampanj skulle inte gå att läsa")
    SP.reset()


def test_the_catalog_states_what_it_cannot_do():
    kat = SP.catalog()
    assert kat["k_floor"] == SP.K_MIN
    assert "cannot pay anyone and cannot see anyone" in kat["cannot_en"]
    assert "refused at creation" in kat["transparency_en"]
    assert set(kat["reward_kinds"]) >= {"cash", "gift_card", "voucher",
                                        "discount_code", "loyalty_points",
                                        "choice"}


def test_the_sponsor_portal_is_its_own_package():
    from api.licensing import ADDONS, required_capability

    assert required_capability("/v1/sponsorship") == "sponsor_portal"
    assert required_capability("/v1/sponsorship/stats") == "sponsor_portal"
    assert "sponsor_portal" in ADDONS


def test_both_stores_offer_the_sponsorship_contract():
    """Samma regel som för kontroller: ett lager som bär kampanjen
    lokalt men inte i produktion ser säkert ut precis där ingen kund
    finns."""
    from engine.storage.postgres import PostgresStore
    from engine.storage.sqlite import SqliteStore

    for klass in (SqliteStore, PostgresStore):
        for namn in ("save_campaign", "all_campaigns",
                     "save_completion", "all_completions"):
            assert callable(getattr(klass, namn, None)), \
                f"{klass.__name__}.{namn} saknas"


def test_completions_survive_a_restart_and_stay_per_tenant():
    import os
    import tempfile

    from engine.storage.sqlite import SqliteStore

    with tempfile.TemporaryDirectory() as d:
        sokvag = os.path.join(d, "s.db")
        s1 = SqliteStore(sokvag)
        SP.set_store(s1)
        try:
            SP.save_campaign(_kampanj(id="k1", tenant="t1"))
            SP.save_completion(SP.completion("k1", "m-1",
                                             region_code="0180",
                                             tenant="t1"))
            SP.save_completion(SP.completion("k1", "m-2",
                                             region_code="0180",
                                             tenant="t2"))
            s1.close()
            SP.set_store(SqliteStore(sokvag))           # "omstart"
            assert len(SP.all_completions("t1")) == 1
            assert len(SP.all_completions("t2")) == 1
        finally:
            SP.set_store(None)
            SP.reset()


def test_ordering_is_the_only_way_the_budget_moves_and_the_cap_bites():
    """Beställ tills taket säger nej: ordered/spent räknas upp GENOM
    grinden, och vägran vid taket är svaret — inte ett fel att retry:a."""
    SP.reset()
    try:
        SP.save_campaign(_kampanj(budget=200.0,
                                  rewards=({"kind": "cash",
                                            "amount": 75.0},)))
        forsta = SP.order_mission("garmin-trail", tenant="t1",
                                  region_code="0180")
        assert forsta["ordered"] == 1
        assert forsta["committed"] == 75.0
        assert forsta["budget"]["committed"] == 75.0
        assert forsta["mission"]["sponsor_visible_en"] == "Garmin Nordic AB"
        SP.order_mission("garmin-trail", tenant="t1")
        try:
            SP.order_mission("garmin-trail", tenant="t1")
        except SP.SponsorshipRefused as e:
            assert "cap" in str(e) and "150.00" in str(e)
        else:
            raise AssertionError("tredje uppdraget gick förbi taket "
                                 "(150 + 75 > 200)")
        kvar = next(k for k in SP.all_campaigns("t1")
                    if k["id"] == "garmin-trail")
        assert kvar["ordered"] == 2 and kvar["spent"] == 150.0
    finally:
        SP.reset()


def test_another_tenants_campaign_cannot_be_ordered_against():
    SP.reset()
    try:
        SP.save_campaign(_kampanj())
        try:
            SP.order_mission("garmin-trail", tenant="t2")
        except SP.SponsorshipRefused as e:
            assert "unknown campaign" in str(e)
        else:
            raise AssertionError("t2 beställde mot t1:s budget")
    finally:
        SP.reset()


def test_paused_campaigns_refuse_orders_and_closed_stays_closed():
    """Övergångarna är data: pausad kampanj beställer inte, återupptagen
    gör det, och en stängd kampanjs siffror är dess facit."""
    SP.reset()
    try:
        SP.save_campaign(_kampanj())
        SP.set_status("garmin-trail", "paused", tenant="t1")
        try:
            SP.order_mission("garmin-trail", tenant="t1")
        except SP.SponsorshipRefused as e:
            assert "paused" in str(e)
        else:
            raise AssertionError("pausad kampanj beställde")
        SP.set_status("garmin-trail", "active", tenant="t1")
        assert SP.order_mission("garmin-trail", tenant="t1")["ordered"] == 1
        SP.set_status("garmin-trail", "closed", tenant="t1")
        for mal in ("active", "paused"):
            try:
                SP.set_status("garmin-trail", mal, tenant="t1")
            except SP.SponsorshipRefused as e:
                assert "record" in str(e)
            else:
                raise AssertionError(f"closed → {mal} tilläts — facit "
                                     f"skrevs om")
        try:
            SP.set_status("garmin-trail", "avslutad", tenant="t1")
        except SP.SponsorshipRefused as e:
            assert "unknown status" in str(e)
        else:
            raise AssertionError("okänd status tilläts")
    finally:
        SP.reset()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
