"""Nyheter får mata analysen — men grinden sitter före, inte efter.

Ett system som låter en rubrik röra ett tal är en ryktesförstärkare med
API. Sviten prövar därför främst spärrarna: att syndikering inte blir
bekräftelse, att en ensam ägare inte får påverka något, och att
ingenting härifrån någonsin blir ett numeriskt signalvärde.

Kör: python3 -m tests.test_news
"""
from __future__ import annotations

import json

from engine import news as N

_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Flode</title>
<item><title>Fabriken laggs ned</title>
<description>200 jobb forsvinner enligt bolaget</description>
<pubDate>Tue, 28 Jul 2026 08:00:00 GMT</pubDate>
<link>https://x/1</link></item>
<item><title>Ny detaljplan antagen</title>
<description>Kommunen beslutade pa tisdagen</description>
<link>https://x/2</link></item>
</channel></rss>"""


def _post(outlet: str, titel: str, sammanfattning: str = "") -> dict:
    return {"outlet": outlet,
            "owner": N.OUTLETS.get(outlet, {}).get("owner", outlet),
            "title": titel, "summary": sammanfattning}


# ── Flödet in ───────────────────────────────────────────────────────────
def test_rss_parses_into_items():
    poster = N.parse_feed(_RSS, "svt")
    assert len(poster) == 2
    assert poster[0]["title"] == "Fabriken laggs ned"
    assert poster[0]["owner"] == "svt"
    assert poster[0]["link"] == "https://x/1"


def test_atom_parses_too_because_a_feed_is_a_feed():
    atom = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
    <entry><title>Rubrik</title><summary>Text</summary>
    <updated>2026-07-28T08:00:00Z</updated></entry></feed>"""
    poster = N.parse_feed(atom, "sr")
    assert len(poster) == 1 and poster[0]["title"] == "Rubrik"


def test_a_feed_that_declares_entities_is_refused_unparsed():
    ond = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY lol "lol">]>'
           b'<rss><channel><item><title>&lol;</title></item></channel></rss>')
    try:
        N.parse_feed(ond, "svt")
    except ValueError as e:
        assert "declares entities" in str(e)
    else:
        raise AssertionError("entitetsdeklaration accepterades")


# ── Syndikering: det som gör "flera medier" värdelöst ───────────────────
def test_the_same_wire_copy_in_five_papers_is_not_five_confirmations():
    poster = [_post(o, "Fabriken i Tyreso laggs ned",
                    "200 jobb forsvinner enligt bolaget")
              for o in ("dn", "di", "svd", "aftonbladet")]
    k = N.cluster(poster)
    assert len(k) == 1, "samma uppgift hamnade i flera kluster"
    # dn+di = Bonnier, svd+aftonbladet = Schibsted → TVÅ röster, inte fyra
    assert k[0]["independent_networks"] == 2
    assert len(k[0]["outlets"]) == 4


def test_two_titles_with_one_owner_are_one_voice():
    k = N.cluster([_post("dn", "Beskedet kom pa tisdagen om fabriken"),
                   _post("di", "Beskedet kom pa tisdagen om fabriken")])
    assert k[0]["independent_networks"] == 1
    assert k[0]["may_inform_analysis"] is False
    assert "cannot corroborate itself" in k[0]["why_en"]
    ind = N.outlets_are_independent("dn", "di")
    assert ind["independent"] is False and "Same owner" in ind["why_en"]


def test_wire_agencies_are_marked_so_the_reader_can_discount_them():
    k = N.cluster([_post("tt", "Regeringen presenterade forslaget idag"),
                   _post("svt", "Regeringen presenterade forslaget idag")])
    assert k[0]["agencies"] == ["tt"]
    assert "wire agency" in k[0]["why_en"]


def test_different_stories_do_not_collapse_into_one_cluster():
    k = N.cluster([_post("svt", "Fabriken i Tyreso laggs ned helt"),
                   _post("sr", "Ny simhall invigs i Nacka pa lordag")])
    assert len(k) == 2


# ── Grinden ─────────────────────────────────────────────────────────────
def test_a_single_owner_may_never_move_an_assessment():
    """Registreras, syns, går att läsa — men rör ingenting."""
    k = N.cluster([_post("svt", "Enda kallan pastar nagot om orten")])
    c = N.claims_for(k)
    assert c["count"] == 0 and c["held_back_count"] == 1
    assert "cannot corroborate itself" in c["held_back"][0]["why_en"]


def test_two_independent_owners_pass_the_gate():
    k = N.cluster([_post("svt", "Fabriken i Tyreso laggs ned helt"),
                   _post("dn", "Fabriken i Tyreso laggs ned helt")])
    c = N.claims_for(k, market="se")
    assert c["count"] == 1 and c["held_back_count"] == 0
    assert c["may_inform"][0]["networks"] == 2


def test_what_passes_the_gate_moves_a_band_and_never_a_number():
    """Ett band går att argumentera emot. Ett tal ser ut som en mätning."""
    k = N.cluster([_post("svt", "Fabriken i Tyreso laggs ned helt"),
                   _post("dn", "Fabriken i Tyreso laggs ned helt")])
    c = N.claims_for(k)
    bidrag = c["may_inform"][0]["contributes_en"]
    assert "RISK BAND" in bidrag and "never set a numeric signal" in bidrag
    assert "rumour amplifier" in c["cannot_en"]
    # och inget fält i svaret bär ett signalvärde
    assert not any(k_ in c["may_inform"][0] for k_ in ("value", "signal_id"))


def test_outlets_agreeing_is_agreement_about_a_report():
    """Tio redaktioner kan upprepa en enda felaktig källa, och måttet kan
    inte se det — bara att de är olika bolag."""
    k = N.cluster([_post("svt", "Samma uppgift fran alla haller nu"),
                   _post("dn", "Samma uppgift fran alla haller nu"),
                   _post("sr", "Samma uppgift fran alla haller nu")])
    assert "about the world" in k[0]["cannot_en"]
    # tidningar mäter samma sak → aldrig högsta bandet, hur många de än är
    assert k[0]["strength"] != "strong"


# ── Uppmärksamhetsindexet ───────────────────────────────────────────────
def _rader(n: int, publicerat=None):
    return [{"region": f"r{i}", "reported_per_100k": 800,
             "population": 100_000,
             "published": (publicerat[i] if publicerat else 10)}
            for i in range(n)]


def test_an_attention_ratio_without_peers_is_refused():
    """Ett tal är varken högt eller lågt i sig självt."""
    r = N.attention_index(_rader(N.PEER_MIN - 1))
    assert r["count"] == 0 and "needs peers" in r["refusal_en"]


def test_the_ratio_is_published_against_reported_never_against_occurred():
    r = N.attention_index(_rader(6))
    for text in (r["cannot_en"], N.catalog()["attention_index"]["cannot_en"]):
        assert "never published against occurred" in text
        assert "dark figure" in text
        assert "accusation" in text


def test_a_place_written_about_far_more_than_its_peers_is_flagged_as_such():
    r = N.attention_index(_rader(6, publicerat=[10, 10, 10, 10, 10, 40]))
    topp = r["rows"][0]
    assert topp["region"] == "r5" and topp["band"] == "far_above"
    assert topp["vs_peer_median"] == 4.0
    assert "article(s) per 100k" in topp["means_en"]
    # och en typisk plats kallas typisk, inte bra eller dålig
    assert {x["band"] for x in r["rows"][1:]} == {"typical"}


def test_a_region_without_a_reported_count_is_left_out_not_assumed_zero():
    rader = _rader(6) + [{"region": "utan", "published": 12,
                          "population": 50_000}]
    r = N.attention_index(rader)
    assert "utan" not in {x["region"] for x in r["rows"]}
    assert r["peers"] == 6


def test_zero_reported_is_not_an_infinite_ratio():
    r = N.attention_index(_rader(6) + [{"region": "noll",
                                        "reported_per_100k": 0,
                                        "population": 10_000,
                                        "published": 5}])
    assert all(x["region"] != "noll" for x in r["rows"])


# ── Katalogen ───────────────────────────────────────────────────────────
def test_the_catalog_names_the_owners_behind_the_titles():
    k = N.catalog()
    assert k["owners"]["bonnier"] == ["di", "dn"]
    assert k["owners"]["schibsted"] == ["aftonbladet", "svd"]
    assert "Syndication" in k["principle_en"]
    assert k["min_networks_to_inform"] == N.MIN_NETWORKS_TO_INFORM == 2
    assert json.dumps(k)


def test_every_outlet_declares_an_owner_because_guessing_one_is_the_bug():
    for oid, o in N.OUTLETS.items():
        assert o["owner"], oid
        assert isinstance(o["agency"], bool), oid
        assert o["label_en"], oid


# ── Vägen in i bedömningen ──────────────────────────────────────────────
def _lagg_in(titel: str, utgivare, region="0180"):
    import time
    poster = []
    for o in utgivare:
        p = _post(o, titel, "Beskedet kom pa tisdagen enligt bolaget")
        p.update({"region_code": region, "market": "se",
                  "harvested_at": time.time(), "link": f"https://{o}/1"})
        p["checksum"] = N.item_checksum(p)
        poster.append(p)
    N.store_items(poster)


def test_a_confirmed_news_item_never_moves_the_risk_score():
    """Den viktigaste raden i hela kopplingen. risk_score väger ihop
    ENDAST kategorier som går att räkna ur signaler — ett tal som kunde
    flyttas av en rubrik vore inte längre härlett."""
    from engine.models import Location
    from engine.risk_intel import risk_intelligence

    N.reset()
    plats = Location(59.33, 18.06)
    innan = risk_intelligence(plats, "gym", market="se")
    _lagg_in("Kommunen varslar 200 anstallda i Stockholm",
             ("svt", "dn"), region=innan and "0180")
    efter = risk_intelligence(plats, "gym", market="se")
    assert efter["risk_score"] == innan["risk_score"]
    assert efter["computed_coverage"] == innan["computed_coverage"]
    assert efter["data_coverage"] == innan["data_coverage"]
    N.reset()


def test_two_independent_owners_move_a_category_from_monitoring_to_observed():
    from engine.models import Location
    from engine.risk_intel import risk_intelligence

    N.reset()
    _lagg_in("Nya krav pa upphandling infors i Stockholm", ("svt", "dn"))
    r = risk_intelligence(Location(59.33, 18.06), "gym", market="se")
    kat = {c["id"]: c for c in r["risk_categories"]}["regulatory"]
    assert kat["status"] == "observed"
    assert kat["band_en"] == "Elevated"
    assert set(kat["sources_en"]) == {"svt", "bonnier"}
    assert "not part of risk_score" in kat["notis_en"]
    N.reset()


def test_a_single_owner_leaves_the_category_on_monitoring():
    from engine.models import Location
    from engine.risk_intel import risk_intelligence

    N.reset()
    _lagg_in("Nya krav pa upphandling infors i Stockholm", ("svt",))
    r = risk_intelligence(Location(59.33, 18.06), "gym", market="se")
    kat = {c["id"]: c for c in r["risk_categories"]}["regulatory"]
    assert kat["status"] == "monitoring"
    assert "observed" not in r["observed_categories"]
    N.reset()


def test_an_observed_category_carries_no_number_at_all():
    from engine.models import Location
    from engine.risk_intel import risk_intelligence

    N.reset()
    _lagg_in("Nya krav pa upphandling infors i Stockholm", ("svt", "dn"))
    r = risk_intelligence(Location(59.33, 18.06), "gym", market="se")
    for c in r["risk_categories"]:
        if c.get("status") == "observed":
            for forbjudet in ("risk", "value", "signal_id", "drivers"):
                assert forbjudet not in c, forbjudet
    N.reset()


def test_a_computed_category_keeps_its_number_when_news_touches_it():
    """Rapporteringen läggs BREDVID talet, aldrig i det."""
    from engine.models import Location
    from engine.risk_intel import risk_intelligence

    N.reset()
    plats = Location(59.33, 18.06)
    innan = {c["id"]: c for c in
             risk_intelligence(plats, "gym", market="se")["risk_categories"]}
    _lagg_in("Konkurrent etablerar sig och oppnar i Stockholm",
             ("svt", "dn"))
    efter = {c["id"]: c for c in
             risk_intelligence(plats, "gym", market="se")["risk_categories"]}
    m = efter["market"]
    assert m["status"] == "computed"
    assert m["risk"] == innan["market"]["risk"]
    if "reported_alongside" in m:
        assert "did NOT change it" in m["reported_note_en"]
    N.reset()


def test_news_older_than_a_week_is_not_what_has_happened():
    from engine.models import Location
    from engine.risk_intel import risk_intelligence

    N.reset()
    gammal = _post("svt", "Nya krav pa upphandling infors i Stockholm", "x")
    gammal.update({"region_code": "0180", "harvested_at": 0.0,
                   "link": "https://svt/1"})
    gammal["checksum"] = N.item_checksum(gammal)
    tva = dict(gammal, outlet="dn", owner="bonnier")
    tva["checksum"] = N.item_checksum(tva)
    N.store_items([gammal, tva])
    r = risk_intelligence(Location(59.33, 18.06), "gym", market="se")
    assert r["observed_categories"] == []
    N.reset()


# ── Flödena ─────────────────────────────────────────────────────────────
def test_every_feed_points_at_an_outlet_whose_owner_we_know():
    """Ett flöde vars ägare vi inte känner gör syndikering till
    bekräftelse — precis det modulen finns för att förhindra."""
    for f in N.FEEDS:
        assert f["outlet"] in N.OUTLETS, f["outlet"]
        assert N.OUTLETS[f["outlet"]]["owner"], f["outlet"]
        assert f["url"].startswith("https://"), f["outlet"]


def test_a_global_feed_is_offered_for_every_market():
    se = {f["outlet"] for f in N.feeds_for("se")}
    de = {f["outlet"] for f in N.feeds_for("de")}
    assert "svt" in se and "svt" not in de
    assert {"reuters", "ap"} <= se and {"reuters", "ap"} <= de


def test_the_region_is_matched_on_name_and_says_that_it_is_crude():
    from engine.markets import MARKETS

    reg = MARKETS["se"].regions
    assert N.region_of({"title": "Brand i Nacka centrum"}, reg) == "0182"
    assert N.region_of({"title": "Ingen ort namns har"}, reg) == ""
    assert "mention, not a subject" in N.REGION_MATCH_CANNOT_EN


def test_a_keyword_is_a_candidate_not_a_judgement():
    k = N.cluster([_post("svt", "Nya regler for upphandling"),
                   _post("dn", "Nya regler for upphandling")])
    assert "regulatory" in N.categories_of(k[0])
    assert "not a topic model" in N.CATEGORY_MATCH_CANNOT_EN


def test_a_broken_feed_does_not_hide_behind_the_others():
    """Sju flöden som svarar och ett som inte gör det ska gå att skilja
    från åtta som svarar."""
    N.reset()
    assert N.last_harvest()["items"] == 0
    N.set_last_harvest({"items": 12, "feeds": 8,
                        "unparsed": [{"outlet": "di", "why_en": "x"}]})
    assert N.last_harvest()["unparsed"][0]["outlet"] == "di"
    N.reset()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
