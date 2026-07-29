"""De fyra avsikterna får krympa. Sanningen får inte.

Samma disciplin som test_surface.py: kategorierna måste faktiskt TÄCKA
alla motorer i katalogen (ingen hemlös, ingen dubbelräknad), och de två
kedjorna får aldrig påstå en förmåga (t.ex. automatisk objektdetektering
från bild) som plattformen inte har.

Kör: python3 -m tests.test_chain
"""
from __future__ import annotations

from api.catalog import API_CATALOG
from engine import chain as CH


def _catalog_ids() -> set[str]:
    return {g["id"] for g in API_CATALOG["engines"]}


def test_every_engine_belongs_to_exactly_one_intent_category():
    claimed: dict[str, list[str]] = {}
    for c in CH.CATEGORIES:
        for e in c["engines"]:
            claimed.setdefault(e, []).append(c["id"])

    twice = {e: cs for e, cs in claimed.items() if len(cs) > 1}
    assert not twice, f"Motorer räknade under flera avsikter: {twice}"

    homeless = _catalog_ids() - set(claimed)
    assert not homeless, (
        f"Motorer som ingen avsiktskategori tar ansvar för: "
        f"{sorted(homeless)}")

    invented = set(claimed) - _catalog_ids()
    assert not invented, \
        f"Kategorier som pekar på motorer som inte finns: {sorted(invented)}"


def test_the_counts_add_up_to_the_catalogue():
    cats = CH.categories()
    assert sum(c["engine_count"] for c in cats) == len(API_CATALOG["engines"])
    assert sum(c["endpoint_count"] for c in cats) == sum(
        len(g["endpoints"]) for g in API_CATALOG["engines"])


def test_four_categories_in_the_users_own_order():
    assert len(CH.CATEGORIES) == 4
    assert [c["order"] for c in CH.categories()] == [1, 2, 3, 4]
    assert [c["id"] for c in CH.categories()] == [
        "decision_intelligence", "control_intelligence",
        "data_collection", "activation"]


def test_each_category_is_a_first_person_intent_not_a_module_name():
    for c in CH.CATEGORIES:
        assert c["intent_en"].startswith("I "), c["id"]
        assert c["result_en"], c["id"]
        for word in ("engine", "endpoint", "API", "module"):
            assert word.lower() not in c["intent_en"].lower(), \
                f"{c['id']}: {word!r} hör hemma i koden, inte kundens mening"


def test_category_of_maps_both_ways():
    assert CH.category_of("inspections")["id"] == "control_intelligence"
    assert CH.category_of("sponsorship")["id"] == "data_collection"
    assert CH.category_of("opportunity")["id"] == "decision_intelligence"
    assert CH.category_of("deliveries")["id"] == "activation"
    assert CH.category_of("den-har-finns-inte") is None


def test_inspections_and_infrastructure_are_control_not_decision():
    """Löftesindelningen (surface.py) och avsiktsindelningen (den här)
    är MEDVETET olika kartor — inspections hör hemma under 'who_carries_it'
    i löftena men under 'control_intelligence' i avsikterna, och båda är
    rätt på sin egen fråga."""
    assert CH.category_of("inspections")["id"] == "control_intelligence"
    assert CH.category_of("infrastructure")["id"] == "control_intelligence"


def test_ground_truth_chain_never_claims_automated_object_detection():
    """Det farligaste vore att skriva 'object detection' eller 'computer
    vision' här — plattformen bygger domar på en mänsklig zoomers
    verdikt, aldrig på bildanalys. Vision-lagret är medvetet outbyggt."""
    text = " ".join(s["does_en"] + s["label_en"] for s in CH.GROUND_TRUTH_CHAIN)
    for claim in ("object detection", "computer vision", "image "
                  "recognition", "automatically detect"):
        assert claim not in text.lower(), \
            f"kedjan påstår en förmåga som inte är byggd: {claim!r}"
    assert "zoomer" in text.lower()
    assert "verdict" in text.lower()


def test_ground_truth_chain_states_the_image_is_never_stored_here():
    first = CH.GROUND_TRUTH_CHAIN[0]
    assert first["id"] == "observation"
    assert "never stored" in first["does_en"]


def test_signal_chain_names_real_normalization_methods():
    text = " ".join(s["does_en"] for s in CH.SIGNAL_CHAIN)
    for method in ("saturating", "linear", "inverse", "banded"):
        assert method in text, f"{method!r} saknas — måste matcha engine/signals.py"


def test_chains_state_what_they_converge_on_not_a_fake_shared_pipeline():
    c = CH.chains()
    assert c["ground_truth"]["stages"] and c["signal"]["stages"]
    assert c["ground_truth"]["stages"] != c["signal"]["stages"], \
        "de två kedjorna fick inte bli en och samma pipeline av misstag"
    assert "not a shared step-by-step pipeline" in c["converge_on_en"]


def test_chain_overview_names_the_deliberate_omission():
    o = CH.chain_overview()
    assert o["tagline_en"] == "From observation to decision."
    assert o["full_catalogue"] == "/v1/catalog"
    assert "vision" in o["principle_en"].lower()
    assert "not built" in o["principle_en"].lower() or \
        "not been built" in o["principle_en"].lower()
    assert o["categories"] and o["chains"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
