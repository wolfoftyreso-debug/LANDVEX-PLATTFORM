"""Ytan får krympa. Sanningen får inte.

En sammanfattning som utelämnar något är inte en sammanfattning, det är
en reklamsida ovanpå en oförändrad röra. Testerna nedan låser fast att de
fyra löftena faktiskt TÄCKER de 45 motorerna: ingen hemlös, ingen räknad
två gånger, och ingen ingång som pekar på en endpoint som inte finns.

Kör: python3 -m tests.test_surface
"""
from __future__ import annotations

from api.catalog import API_CATALOG
from engine import surface as S


def _catalog_ids() -> set[str]:
    return {g["id"] for g in API_CATALOG["engines"]}


def _all_paths() -> set[str]:
    return {e["path"] for g in API_CATALOG["engines"] for e in g["endpoints"]}


def test_every_engine_belongs_to_exactly_one_promise():
    """Kärntestet. Utan det är ytan bara en trevligare framsida."""
    claimed: dict[str, list[str]] = {}
    for p in S.PROMISES:
        for e in p["engines"]:
            claimed.setdefault(e, []).append(p["id"])

    twice = {e: ps for e, ps in claimed.items() if len(ps) > 1}
    assert not twice, f"Motorer räknade under flera löften: {twice}"

    homeless = _catalog_ids() - set(claimed)
    assert not homeless, (
        f"Motorer som inget löfte tar ansvar för: {sorted(homeless)}. "
        f"Antingen hör de hemma under ett löfte, eller så ska de inte "
        f"stå i katalogen.")

    invented = set(claimed) - _catalog_ids()
    assert not invented, \
        f"Löften som pekar på motorer som inte finns: {sorted(invented)}"


def test_the_counts_add_up_to_the_catalogue():
    s = S.surface()
    assert s["engine_count"] == len(API_CATALOG["engines"])
    assert sum(p["engine_count"] for p in s["promises"]) == s["engine_count"]
    assert sum(p["endpoint_count"] for p in s["promises"]) \
        == s["endpoint_count"]


def test_four_promises_and_no_more():
    """Fyra är valet. Växer listan tillbaka mot fyrtiofem är snittet
    ogjort — och då ska testet säga ifrån, inte tyst följa med."""
    assert len(S.PROMISES) == 4
    assert [p["order"] for p in S.promises()] == [1, 2, 3, 4]


def test_each_entry_point_actually_exists():
    paths = _all_paths()
    for p in S.PROMISES:
        assert p["entry"] in paths, \
            f"{p['id']} lovar {p['entry']} som inte finns i katalogen"


def test_each_promise_is_a_question_a_human_would_ask():
    for p in S.PROMISES:
        assert p["question_en"].endswith("?"), p["id"]
        assert p["question_sv"].endswith("?"), p["id"]
        # Inga ingenjörsord på kundytan.
        for word in ("engine", "index", "API", "endpoint", "graph",
                     "selector", "adapter"):
            assert word.lower() not in p["question_en"].lower(), \
                f"{p['id']}: '{word}' hör hemma i katalogen, inte i frågan"


def test_each_promise_states_what_it_refuses():
    """Vägran är produkten. Ett löfte som bara lovar är ett säljargument."""
    for p in S.PROMISES:
        assert p["refusal_en"], p["id"]
        assert p["for_en"] and p["settles_en"], p["id"]


def test_promise_of_maps_both_ways():
    assert S.promise_of("saturation")["id"] == "is_there_room"
    assert S.promise_of("brief")["id"] == "what_changed"
    assert S.promise_of("accountability")["id"] == "who_carries_it"
    assert S.promise_of("den-har-finns-inte") is None


def test_detail_lists_the_engines_underneath():
    s = S.surface(detail=True)
    total = sum(len(p["engines"]) for p in s["promises"])
    assert total == len(API_CATALOG["engines"])
    for p in s["promises"]:
        for e in p["engines"]:
            assert e["id"] and e["label_en"] and e["endpoints"]


def test_the_full_catalogue_is_still_offered_not_hidden():
    """Att krympa ytan får inte betyda att dölja plattformen."""
    s = S.surface()
    assert s["full_catalogue"] == "/v1/catalog"
    assert s["endpoint_count"] > 50        # sanningen står kvar i klartext



# ── Demon ────────────────────────────────────────────────────────────────
def test_the_demo_only_calls_endpoints_that_exist():
    """En demo som anropar en borttagen endpoint upptäcks framför kunden."""
    import pathlib
    import re
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "scripts" / "demo90.py").read_text(encoding="utf-8")
    called = set(re.findall(r'_call\(base,\s*"([^"]+)"', src))
    called.discard("/health")
    missing = called - _all_paths()
    assert not missing, f"demo90 anropar endpoints som inte finns: {missing}"
    assert len(called) >= 5, "demon visar färre steg än den utger sig för"


def test_the_demo_can_fail_itself():
    """En demo som alltid avslutar med 0 är en inspelning, inte ett bevis."""
    import inspect

    from scripts import demo90
    src = inspect.getsource(demo90.run)
    assert src.count("d.holds(") == 5, \
        "varje steg måste kontrollera sitt eget påstående"
    assert "return (0 if report[\"ok\"] else 1)" in src


def test_the_demo_does_not_invent_its_own_timings():
    """Den första versionen skrev 0:00, 0:15, 0:35 som om det vore
    förfluten tid. Den körde på tjugo sekunder. En demo för en plattform
    om att inte överdriva får inte överdriva om sig själv."""
    import inspect
    import re

    from scripts import demo90
    src = inspect.getsource(demo90)
    assert not re.search(r'"\d:\d\d"', src), \
        "hårdkodade tidsstämplar tillbaka i demon"
    assert "time.perf_counter()" in src
    assert "self.elapsed" in inspect.getsource(demo90.Demo.beat)


def test_ninety_seconds_is_enforced_not_just_asserted():
    """Namnet är ett påstående. Ett påstående utan grind är en slogan."""
    from scripts import demo90
    assert demo90.BUDGET_S == 90.0
    import inspect
    src = inspect.getsource(demo90.run)
    assert "within = total <= BUDGET_S" in src
    assert '"within_budget": within' in src


def test_the_demo_shows_a_refusal():
    """Steg 4 ÄR produkten. Försvinner vägran ur demon säljer den något
    annat än det som byggts."""
    import inspect

    from scripts import demo90
    src = inspect.getsource(demo90.run)
    assert "/v1/saturation" in src
    assert 'sup.get("measured") is False' in src
    assert 'sup.get("establishments") is None' in src


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
