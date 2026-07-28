"""Fem sätt att betala, och ett av dem går inte att leverera.

Bakgrunden: koden sa "ingen månadsavgift, provision per levererad lead"
medan landvex.com sa "enterprise-prissättning, tre månaders pilot följt
av årlig prenumeration". Det såg ut som en motsägelse. Det var två
paketeringar av flera, var och en riktig för sin kund, beskrivna på var
sitt ställe som om den var den enda.

Testerna håller fast vid det som gör skillnaden användbar i stället för
förvirrande: varje paketering ska säga vad kunden får, NÄR betalningen
utlöses — den rad en inköpsavdelning avgör saken på — och om den går att
leverera i dag.

Kör: python3 -m tests.test_commercial
"""
from __future__ import annotations


def test_every_packaging_says_what_it_buys_and_when_you_pay():
    """'När' är den rad som avgör om en kommun kan handla alls. En
    paketering utan den är en prislista, inte en affärsmodell."""
    from engine.commercial import PACKAGINGS
    for p in PACKAGINGS:
        for f in ("name_en", "buys_en", "pays_when_en", "fits_en",
                  "unit_en"):
            assert p[f], (p["id"], f)
        assert isinstance(p["built"], bool), p["id"]


def test_a_packaging_that_cannot_be_delivered_says_so():
    """Att sälja en paketering vars leveranskedja inte är sluten är inte
    optimism, det är en skuld som förfaller vid första fakturan."""
    from engine.commercial import PACKAGINGS
    ej = [p for p in PACKAGINGS if not p["built"]]
    assert ej, ("minst en paketering väntar på uppdragsflödet — om den "
                "listan blir tom ska någon ha BYGGT det, inte tagit bort "
                "raden")
    for p in ej:
        assert "NOT DELIVERABLE" in p["depends_on_en"], p["id"]
        assert len(p["depends_on_en"]) > 60, (
            f"{p['id']}: säg vad som saknas, inte bara att något gör det")


def test_a_deliverable_packaging_names_what_delivers_it():
    """Annars är 'levererbar' ett påstående utan täckning."""
    from engine.commercial import PACKAGINGS
    for p in PACKAGINGS:
        if not p["built"] or p["id"] == "open":
            continue
        assert p["depends_on_en"], p["id"]
        assert ("/v1/" in p["depends_on_en"]
                or "engine/" in p["depends_on_en"]
                or "commercial wrapper" in p["depends_on_en"]), p["id"]


def test_every_plan_points_at_packagings_that_exist():
    """En plan som pekar på en paketering som inte finns säljer luft."""
    from engine.commercial import PACKAGINGS
    from engine.offering import PLAN_SURFACE
    kanda = {p["id"] for p in PACKAGINGS}
    for plan, v in PLAN_SURFACE.items():
        pkg = set(v.get("packagings", ()))
        assert pkg, f"{plan} saknar paketering"
        assert pkg <= kanda, (plan, sorted(pkg - kanda))


def test_every_packaging_is_reachable_from_some_plan():
    """Och tvärtom: en paketering ingen plan erbjuder är en affärsmodell
    ingen kan köpa."""
    from engine.commercial import PACKAGINGS
    from engine.offering import PLAN_SURFACE
    erbjudna = {x for v in PLAN_SURFACE.values()
                for x in v.get("packagings", ())}
    for p in PACKAGINGS:
        assert p["id"] in erbjudna, f"{p['id']} går inte att köpa någonstans"
        assert set(p["plans"]) <= set(PLAN_SURFACE), p["id"]


def test_the_free_tier_can_never_be_billed():
    """Explorer är gratis. En betald paketering på den nivån vore ett
    löftesbrott i registret självt."""
    from engine.commercial import for_plan
    for p in for_plan("free"):
        assert p["unit_en"] == "nothing", p["id"]
        assert "Never" in p["pays_when_en"]


def test_the_municipal_route_does_not_require_a_purchase_order_per_lead():
    """Kärnan i varför flera modeller behövs: en kommun KAN inte köpa
    leads styckvis, och en franchise vill inte köpa en pilot."""
    from engine.commercial import PACKAGINGS
    pilot = next(p for p in PACKAGINGS if p["id"] == "pilot_then_subscription")
    lead = next(p for p in PACKAGINGS if p["id"] == "per_lead")
    assert "budget cycle" in pilot["fits_en"]
    assert "up front" in pilot["pays_when_en"] or "annually" in pilot["pays_when_en"]
    assert "delivery" in lead["pays_when_en"]
    assert "enterprise" in pilot["plans"] and "enterprise" not in lead["plans"]


def test_the_principle_explains_why_there_is_more_than_one():
    """Utan skälet läser fem modeller som obeslutsamhet."""
    from engine.commercial import catalog
    c = catalog()
    assert "cannot buy at all" in c["principle_en"]
    assert "not deliverable" in c["honesty_en"]
    assert c["deliverable_count"] < c["count"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
