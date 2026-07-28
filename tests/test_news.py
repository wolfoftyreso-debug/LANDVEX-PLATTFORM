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
    return [{"region": f"r{i}", "reported": 100,
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
    assert "article(s) per" in topp["means_en"]
    # och en typisk plats kallas typisk, inte bra eller dålig
    assert {x["band"] for x in r["rows"][1:]} == {"typical"}


def test_a_region_without_a_reported_count_is_left_out_not_assumed_zero():
    rader = _rader(6) + [{"region": "utan", "published": 12}]
    r = N.attention_index(rader)
    assert "utan" not in {x["region"] for x in r["rows"]}
    assert r["peers"] == 6


def test_zero_reported_is_not_an_infinite_ratio():
    r = N.attention_index(_rader(6) + [{"region": "noll", "reported": 0,
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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
