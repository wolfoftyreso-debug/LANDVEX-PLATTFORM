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



# ── Kundytans språk ──────────────────────────────────────────────────────
# Ord som beskriver hur något är BYGGT, inte vad det gör för någon. De hör
# hemma i koden och i beskrivningarna — inte i det namn en kund läser.
_INTERNAL_WORDS = (
    "engine", "adapter", "selector", "seam", "loop", "graph", "index",
    "registry", "layer", "pipeline", "module", "handler",
    "wrapper", "schema", "lambda", "setpoint", "strim", "kpi",
)
# "service" stod här först och fällde "How much service this place needs".
# Ordet är tvetydigt: mikrotjänst är ett byggord, servicebesök är kundens
# eget ord och hela den motorns ämne. En regel som slår på rätt namn är
# fel regel, så den togs bort i stället för att undantas.
# Namn som är produktnamn eller etablerade fackord kunden själv använder.
_ALLOWED = {"Ask Landvex", "Daily Brief", "Platform", "AAMOS Integration"}


def test_no_engineer_speak_in_the_names_a_customer_reads():
    """"Lambda Index". "STRIM Knowledge Graph". "Significance Selector".
    En kund kan inte vilja ha något hon inte kan namnge, och ingen av dem
    säger vad man får. Beskrivningarna får vara tekniska; namnen inte."""
    offenders = []
    for g in API_CATALOG["engines"]:
        label = g["label_en"]
        if label in _ALLOWED:
            continue
        for w in _INTERNAL_WORDS:
            if w in label.lower():
                offenders.append(f"{g['id']}: {label!r} innehåller {w!r}")
    assert not offenders, (
        "Interna ord på kundytan:\n  " + "\n  ".join(offenders))


def test_the_id_is_the_contract_and_the_label_is_the_surface():
    """Namnen fick bytas. Id:na är det maskiner, löften och kapabiliteter
    hänger på — de får aldrig följa med i en omdöpning."""
    ids = {g["id"] for g in API_CATALOG["engines"]}
    for p in S.PROMISES:
        for e in p["engines"]:
            assert e in ids, f"löftet pekar på motor-id {e!r} som inte finns"
    for g in API_CATALOG["engines"]:
        assert g["id"] == g["id"].lower(), g["id"]
        assert " " not in g["id"], g["id"]


def test_the_tagline_promises_something_rather_than_naming_a_market():
    """"Decision Intelligence for the Physical World" är vad ett analysföretag
    kallar facket. Det är inte vad en kund säger till en kollega."""
    t = API_CATALOG["tagline_en"]
    assert t and len(t) < 70, t
    for jargon in ("intelligence", "platform", "solution", "leverage",
                   "ecosystem", "synerg"):
        assert jargon not in t.lower(), f"taglinen säger {jargon!r}"


def test_every_engine_still_says_what_it_does_somewhere():
    """Ett kortare namn får inte betyda mindre information. Beskrivningen
    bär tekniken; namnet bär nyttan."""
    for g in API_CATALOG["engines"]:
        assert g["label_en"].strip(), g["id"]
        assert len(g["beskrivning_en"]) > 30, \
            f"{g['id']} har namn men ingen förklaring"



def test_the_demo_page_only_calls_endpoints_that_exist():
    """Demosidan är det man visar för en kund. Ett anrop mot en borttagen
    endpoint upptäcks då framför dem, inte i CI."""
    import pathlib
    import re
    html = (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "demo.html").read_text(encoding="utf-8")
    called = set(re.findall(r'call\("(/v1/[^"]+)"', html))
    assert len(called) >= 5, f"demosidan visar bara {len(called)} bevis"
    missing = called - _all_paths()
    assert not missing, f"demo.html anropar endpoints som inte finns: {missing}"


def test_the_demo_page_says_nothing_it_did_not_fetch():
    """Sidans löfte är att varje siffra kommer från ett live-anrop. Då får
    det inte finnas hårdkodade resultat i HTML:en."""
    import pathlib
    import re
    html = (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "demo.html").read_text(encoding="utf-8")
    kropp = html.split("<main", 1)[1].split("</main>", 1)[0] \
        if "<main" in html else ""
    # Bevisen renderas av JS; <main> ska vara tom i källan.
    assert "Stockholm" not in kropp and "Tyresö" not in kropp, \
        "demosidan har inbakade resultat i HTML — då är de inte hämtade"
    # Och den ska säga att den kan misslyckas.
    assert re.search(r"if a call fails|the call failed", html, re.I), \
        "sidan lovar inte vad den gör när ett anrop misslyckas"



def test_the_explore_page_only_offers_questions_the_engine_answers():
    """Sidan är gjord för någon som INTE kan området. En exempelfråga som
    ger noll rader är det värsta första intrycket som finns — den som
    stod här först gav intent `hjalp` och ingenting alls."""
    import pathlib
    import re

    from engine.ask import ask
    html = (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "explore.html").read_text(encoding="utf-8")
    block = html.split("const EXEMPEL = [", 1)[1].split("];", 1)[0]
    fragor = re.findall(r'"([^"]+)"', block)
    assert len(fragor) >= 3, "för få exempelfrågor"
    tomma = [q for q in fragor if not (ask(q).get("rader") or [])]
    assert not tomma, f"exempelfrågor utan svar: {tomma}"


def test_the_explore_page_plots_the_measure_the_engine_ranked_by():
    """Rangordnas raderna på brist men stapeln ritar score säger diagrammet
    emot meningen ovanför sig, och en sorterad lista ser osorterad ut."""
    import pathlib
    html = (pathlib.Path(__file__).resolve().parent.parent
            / "frontend" / "explore.html").read_text(encoding="utf-8")
    assert "matRader" in html
    assert "fallande" in html, "sidan letar inte upp det sorterade måttet"
    assert "svarmatt" in html, "måttet står inte utskrivet vid diagrammet"
    # Och den får aldrig sortera om motorns ordning.
    assert ".sort(" not in html.split("<script>", 1)[1], \
        "sidan sorterar om raderna — det påstår en annan rangordning"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
