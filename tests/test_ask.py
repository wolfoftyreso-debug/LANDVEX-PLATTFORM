"""Tests for Ask Landvex (NL parser + answers). Runs without pytest:
python3 -m tests.test_ask"""
from __future__ import annotations

import json

from engine.ask import ask, parse

# The platform's canonical example questions – all must parse to a
# real intent (never "hjalp"), with the entities asserted below.
CANONICAL = [
    ("What are the five biggest business opportunities in Örebro "
     "right now?", "mojligheter_kommun"),
    ("What are the three biggest business opportunities in Gothenburg?",
     "mojligheter_kommun"),
    ("Where in Europe is the shortage of electricians greatest?",
     "global_brist"),
    ("Where in the world is the shortage of carpenters greatest?",
     "global_brist"),
    ("Where is the best place to start a plumbing company in Germany?",
     "basta_lage_vertikal"),
    ("Which country is best for a Swedish carpenter to move to?",
     "land_ranking"),
    ("Which occupations will be missing most in Umeå over the next "
     "five years?", "bristyrken_kommun"),
    ("Which occupations are missing most in Berlin?",
     "bristyrken_kommun"),
    ("Which US state will need the most nurses over the next ten "
     "years?", "nationell_brist"),
    ("Where in Sweden is the need for nurses greatest?",
     "nationell_brist"),
    ("Where should I open a café?", "basta_lage_vertikal"),
    ("How risky is it to start a gym in Solna?", "riskprofil"),
    ("Where is the imbalance greatest for car repair shops?",
     "gap_analys"),
    ("Create an establishment plan for a car repair shop in "
     "Skellefteå.", "etableringsplan"),
    ("Where in Sweden are there the most pet owners?", "segment_karta"),
    ("What do the target groups look like in Umeå?",
     "malgrupper_kommun"),
    ("Which region has the most heat pumps approaching replacement "
     "age?", "service_karta"),
    ("Where is the best place to start a company servicing EV "
     "chargers?", "service_karta"),
    ("What does the service demand look like in Umeå?",
     "servicebehov_kommun"),
    ("Where will the need for refrigeration technicians increase "
     "over the next five years?", "nationell_brist"),
]


# ── Parsing ──────────────────────────────────────────────────────────

def test_parse_opportunities():
    q = parse("What are the five biggest business opportunities in "
              "Örebro right now?")
    assert q.intent == "mojligheter_kommun"
    assert q.kommun[1] == "Örebro"
    assert q.top_n == 5


def test_parse_shortage_with_horizon():
    q = parse("Which occupations will be missing most in Umeå over "
              "the next five years?")
    assert q.intent == "bristyrken_kommun"
    assert q.kommun[1] == "Umeå"
    assert q.target_year == 2031            # BASE_YEAR 2026 + 5
    assert parse("Which occupations are missing most in Umeå by "
                 "2035?").target_year == 2035
    assert parse("What are the top 3 business opportunities in "
                 "Örebro?").top_n == 3


def test_parse_national_shortage():
    q = parse("Where in Sweden is the need for nurses greatest?")
    assert q.intent == "nationell_brist"
    assert q.occupation_id == "sjukskoterska"
    assert q.market == "se"
    q2 = parse("Which US state will need the most nurses over the "
               "next ten years?")
    assert q2.intent == "nationell_brist"
    assert q2.market == "us" and q2.target_year == 2036


def test_parse_synonyms_exonyms_and_genitive():
    q = parse("Where should I open a coffee shop?")
    assert q.intent == "basta_lage_vertikal" and q.vertical_id == "cafe"
    q2 = parse("Biggest business opportunities in Kalmar's city centre?")
    assert q2.kommun[1] == "Kalmar"
    q3 = parse("Where are plumbers needed most?")
    assert q3.occupation_id == "vvs_montor"
    q4 = parse("What are the three biggest business opportunities in "
               "Gothenburg?")
    assert q4.kommun[1] == "Göteborg" and q4.top_n == 3


def test_parse_electrician_context():
    # "Electrician" is both occupation and industry – context decides.
    assert parse("Where is the shortage of electricians greatest?"
                 ).intent == "nationell_brist"
    assert parse("Should I start an electrical firm in Borås?"
                 ).vertical_id == "elektriker"


def test_parse_risk():
    q = parse("How risky is it to start a gym in Solna?")
    assert q.intent == "riskprofil"
    assert q.vertical_id == "gym" and q.kommun[1] == "Solna"


def test_parse_unknown_municipality_and_help():
    q = parse("Which occupations are missing in Hylte municipality?")
    assert q.intent == "okand_kommun" and q.unmatched_kommun == "Hylte"
    assert parse("What is the weather like?").intent == "hjalp"


def test_parse_global_and_move():
    q = parse("Where in Europe is the shortage of electricians "
              "greatest?")
    assert q.intent == "global_brist"
    assert q.occupation_id == "elektriker" and q.group == "eu"
    q2 = parse("Where in the world is the shortage of carpenters "
               "greatest?")
    assert q2.intent == "global_brist"
    assert q2.occupation_id == "snickare" and q2.group == "varlden"
    q3 = parse("Which country is best for a Swedish carpenter to "
               "move to?")
    assert q3.intent == "land_ranking" and q3.occupation_id == "snickare"


def test_parse_plan_gap_service():
    q = parse("Create an establishment plan for a car repair shop in "
              "Skellefteå.")
    assert q.intent == "etableringsplan"
    assert q.vertical_id == "bilverkstad" and q.kommun[1] == "Skellefteå"
    q2 = parse("Where is the imbalance greatest for car repair shops?")
    assert q2.intent == "gap_analys" and q2.vertical_id == "bilverkstad"
    q3 = parse("Which region has the most heat pumps approaching "
               "replacement age?")
    assert q3.intent == "service_karta"
    assert q3.product_id == "varmepump_luft"
    q4 = parse("Where is the best place to start a company servicing "
               "EV chargers?")
    assert q4.intent == "service_karta" and q4.product_id == "laddbox"
    q5 = parse("What does the service demand look like in Umeå?")
    assert q5.intent == "servicebehov_kommun" and q5.kommun[1] == "Umeå"


def test_parse_segments_and_disambiguation():
    q = parse("Where in Sweden are there the most pet owners?")
    assert q.intent == "segment_karta"
    assert q.segment_id == "djuragare" and q.market == "se"
    q2 = parse("What do the target groups look like in Umeå?")
    assert q2.intent == "malgrupper_kommun" and q2.kommun[1] == "Umeå"
    # Industry wins over segment in an establishment context.
    q3 = parse("Where should I start an elderly care business?")
    assert q3.intent == "basta_lage_vertikal"
    assert q3.vertical_id == "aldreomsorg" and q3.segment_id is None


def test_parse_market_routing():
    q = parse("Where is the best place to start a plumbing company in "
              "Germany?")
    assert q.intent == "basta_lage_vertikal"
    assert q.vertical_id == "vvs" and q.market == "de"
    q2 = parse("Which occupations are missing most in Berlin?")
    assert q2.intent == "bristyrken_kommun"
    assert q2.region_market == "de" and q2.kommun[1] == "Berlin"


def test_parse_canonical_questions():
    for fraga, intent in CANONICAL:
        q = parse(fraga)
        assert q.intent == intent, (fraga, q.intent, intent)
        assert q.intent not in ("hjalp", "okand_kommun"), fraga


# ── Answers ──────────────────────────────────────────────────────────

def test_ask_opportunities_rows():
    res = ask("What are the three biggest business opportunities in "
              "Gothenburg?")
    assert res["intent"] == "mojligheter_kommun"
    assert len(res["rader"]) == 3
    scores = [r["score"] for r in res["rader"]]
    assert scores == sorted(scores, reverse=True)
    d = res["rader"][0]["detalj"]
    assert d["risk_band"] and d["faktorer"] and "ekonomi_schablon" in d
    assert res["caveats_en"] and res["forslag_en"]
    assert res["svar_en"].startswith("Biggest business opportunities")


def test_ask_shortage_rows():
    res = ask("Which occupations will be missing most in Umeå over "
              "the next five years?")
    assert res["intent"] == "bristyrken_kommun"
    assert res["rader"]
    d = res["rader"][0]["detalj"]
    for key in ("behov_nu", "behov_prognos", "intervall", "konfidens",
                "pensionsavgangar", "medellon_tkr_manad",
                "automationsrisk_schablon", "drivare", "antaganden"):
        assert key in d, key
    assert res["rader"][0]["trend"] in ("rising", "stable", "declining")
    assert res["rader"][0]["efterfragan"] in ("mattad", "vaxande", "hog", "extrem")


def test_ask_national_with_map():
    res = ask("Where in Sweden is the need for nurses greatest?")
    assert res["intent"] == "nationell_brist"
    assert res["karta"]["typ"] == "efterfragan"
    assert len(res["karta"]["kommuner"]) == 40
    assert all(k["efterfragan"] in ("mattad", "vaxande", "hog", "extrem")
               for k in res["karta"]["kommuner"])
    assert res["svar_en"].startswith("Largest calculated need")


def test_ask_hotspots_with_map():
    res = ask("Where should I open a café?")
    assert res["intent"] == "basta_lage_vertikal"
    assert res["karta"]["typ"] == "heatmap"
    assert res["rader"][0]["detalj"]["ekonomi_schablon"]


def test_ask_deterministic_and_empty():
    f = "What are the biggest business opportunities in Gävle?"
    assert ask(f) == ask(f)
    res = ask("")
    assert res["intent"] == "hjalp" and res["forslag_en"]
    assert res["svar_en"].startswith("I understand questions")


def test_a_place_we_do_not_cover_is_never_answered_for_somewhere_else():
    """En fråga om Leningrad fick tidigare ett svar om Dallas.

    Faller en okänd ort igenom till standardmarknaden svarar motorn om fel
    världsdel utan att säga det – exakt det plattformen lovar att inte göra.
    """
    q = parse("Is it a good opportunity to open a hair salon "
              "with 3 employees in Leningrad?")
    assert q.intent == "okand_kommun"
    assert q.unmatched_kommun == "Leningrad"
    res = ask("Is it a good opportunity to open a hair salon in Leningrad?")
    assert res["intent"] == "okand_kommun"
    assert not res["rader"]                       # inga resultat om annan ort
    assert "not covered" in res["svar_en"]
    assert "Leningrad" in res["svar_en"]
    # Täckningen ska räknas fram, inte påstås i en åldrande mening.
    from engine.markets import MARKETS
    assert str(len(MARKETS)) in res["svar_en"]


def test_places_written_without_diacritics_still_match():
    """De flesta skriver Orebro och Umea – det ska träffa rätt kommun."""
    for written, expected in (("Orebro", "Örebro"), ("Umea", "Umeå"),
                              ("Malmo", "Malmö"), ("Goteborg", "Göteborg")):
        q = parse(f"What are the biggest opportunities in {written}?")
        assert q.kommun is not None, f"{written} matchade ingen region"
        assert q.kommun[1] == expected, (written, q.kommun[1])
        assert q.unmatched_kommun is None


def test_regions_groups_and_countries_are_not_mistaken_for_unknown_places():
    for qn in ("Where in Europe is it best to open a gym?",
               "Var finns flest djurägare i Sverige?",
               "Best location for a hair salon in Dallas?"):
        q = parse(qn)
        assert q.intent != "okand_kommun", qn


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tests green.")
