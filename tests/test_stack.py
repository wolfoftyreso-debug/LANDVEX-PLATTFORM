"""Tre lager, och den fråga varje storkund ställer.

*Vi kan koppla quiXzoom och AAMOS via API själva — varför Landvex?*

Det är en rimlig fråga, och ett svar som bara påstår värde är sämre än
inget svar. Testerna här håller fast vid att svaret är konkret: varje
lager säger vad det säljer och vad kunden fortfarande får göra själv,
och luckan för den som bygger ihop de två understa är beskriven som
ARBETE med en endpoint bakom varje rad — inte som ett hot.

Kör: python3 -m tests.test_stack
"""
from __future__ import annotations


def test_each_layer_says_what_it_sells_and_what_is_left_to_you():
    """Ett lager som bara säger vad det ger, utan vad som återstår, är en
    broschyr."""
    from engine.stack import LAYERS
    for lg in LAYERS:
        for f in ("company", "sells_en", "delivers_en", "buys_it_en",
                  "you_still_do_en", "in_this_repo"):
            assert lg[f], (lg["id"], f)
    assert [lg["order"] for lg in LAYERS] == [1, 2, 3]
    assert [lg["company"] for lg in LAYERS] == ["quiXzoom", "AAMOS",
                                                "Landvex"]


def test_the_self_serve_path_is_described_as_supported_not_forbidden():
    """Kunder KOMMER att koppla ihop de två understa i sina interna
    system. Att beskriva det som en genväg eller ett missbruk vore både
    osant och dålig affär."""
    from engine.stack import PRINCIPLE_EN, layer
    perception = layer("perception")
    assert "open on purpose" in perception["buys_it_en"]
    assert "supported path" in PRINCIPLE_EN
    assert "not a workaround" in PRINCIPLE_EN


def test_every_gap_names_work_and_where_it_already_exists():
    """Luckan ska gå att kontrollera. En rad utan endpoint är ett
    påstående om värde, och det är precis vad en konkurrent också
    skriver."""
    from engine.stack import SELF_SERVE_GAP
    assert len(SELF_SERVE_GAP) >= 5
    for g in SELF_SERVE_GAP:
        assert g["missing_en"] and g["why_en"], g
        assert "/v1/" in g["here_en"] or "engine/" in g["here_en"], g


def test_the_top_layer_never_claims_to_decide():
    """Plattformen rekommenderar aldrig — den lämnar underlaget och namnger
    ägaren. Ett lager som säger sig besluta bryter doktrinen i sin egen
    beskrivning."""
    from engine.stack import layer
    d = layer("decision")
    assert "never recommends" in d["you_still_do_en"]
    assert "Decide." in d["you_still_do_en"]


def test_calibration_is_admitted_to_take_time_for_us_too():
    """Den enda raden i luckan som inte går att köpa sig förbi — och den
    gäller oss lika mycket som kunden."""
    from engine.stack import SELF_SERVE_GAP
    kal = next(g for g in SELF_SERVE_GAP if "Calibration" in g["why_en"])
    assert "including us" in kal["why_en"]


def test_each_layer_points_at_something_that_exists_in_this_repo():
    """Annars är lagerkartan en ritning över ett annat system."""
    import pathlib
    from engine.stack import LAYERS
    rot = pathlib.Path(__file__).resolve().parent.parent
    for lg in LAYERS:
        for bit in lg["in_this_repo"].split(" · "):
            if bit.startswith(("engine/", "integrations/")):
                assert (rot / bit).exists(), (lg["id"], bit)


def test_the_contradiction_index_is_honest_about_its_observed_side():
    """Kärnfyndet: kontradiktionsindexet väger officiellt planerat mot
    observerat utfört — och den observerade sidan (`development_m2`) har
    ingen riktig källa. AAMOS bär `apollo_contradictions()`, som ingen
    motor anropar. Testet finns för att luckan ska synas tills den
    stängs, inte för att den ska accepteras."""
    import pathlib
    rot = pathlib.Path(__file__).resolve().parent.parent
    from engine.indices import _OBSERVED, _PLANNED
    planerade = {s for s, _ in _PLANNED}
    observerade = {s for s, _ in _OBSERVED}
    assert not (planerade & observerade), (
        f"samma signal på båda sidor av kontradiktionsindexet: "
        f"{sorted(planerade & observerade)} — då jämför indexet en källa "
        f"med sig själv och kan strukturellt inte hitta en motsägelse")

    # Och den observerade sidan får inte matas av bygglovskällan. Den
    # räknade förut ut `development_m2` ur bygglovens area och fyllde
    # alltså den OBSERVERADE sidan med pappersarbete — medan quiXzoom-
    # adaptern uttryckligen vägrade göra samma sak.
    from engine.datasources.permits import SIGNALS as PERMIT_SIGNALS
    assert not (set(PERMIT_SIGNALS) & observerade), (
        f"bygglovskällan matar den observerade sidan: "
        f"{sorted(set(PERMIT_SIGNALS) & observerade)}")
    klient = (rot / "integrations" / "aamos.py").read_text(encoding="utf-8")
    assert "apollo_contradictions" in klient, (
        "AAMOS-klienten ska bära kontradiktionsanropet — det är den väg "
        "den observerade sidan ska komma in genom")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
