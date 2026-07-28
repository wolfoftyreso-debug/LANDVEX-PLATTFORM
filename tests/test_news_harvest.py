"""Nyhetsskörden hela vägen, mot en RIKTIG server.

`tests/test_news.py` bevisar parsningen med bytesträngar i minnet. Det
räcker inte för att våga säga att skörden fungerar: mellan en bytesträng
och en skördad rad ligger urllib, Breaker, tidsgränsen, checksumman och
lagret — och det var precis där förra buggen satt (Breaker.fetch lägger
på sin egen timeout, så skördaren skickade fyra argument till en
tretaligs transport och lagrade tyst noll rader).

Den här sviten startar därför en lokal HTTP-server som serverar fyra
RSS-flöden och kör `harvest.harvest_region("news", ...)` mot dem utan
någon fejkad transport alls.

Vad den INTE bevisar: att svt.se svarar. Nätet är policyspärrat här.
Fixtur bevisar parsning och lagring, aldrig att adressen finns — och
därför sätts inget `verified_live` någonstans av det här testet.

Kör: python3 -m tests.test_news_harvest
"""
from __future__ import annotations

import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import harvest as H
from engine import mrai as M
from engine import news as N

# Samma telegram hos tre titlar i TVÅ ägargrupper (svt / bonnier×2), och
# en ensam uppgift hos en fjärde. Det är hela poängen med modulen: fyra
# tidningar är inte fyra bekräftelser.
_TELEGRAM = ("Fabriken i Nacka läggs ned efter trettio år",
             "Beskedet kom på måndagen. Omkring tvåhundra anställda "
             "berörs av nedläggningen i Nacka.")
_ENSAM = ("Ny cykelbana invigd i Solna",
          "Kommunen invigde på tisdagen en cykelbana i Solna centrum.")

_SIDOR: dict[str, tuple[str, tuple[str, str]]] = {
    "/svt.xml": ("svt", _TELEGRAM),
    "/dn.xml": ("dn", _TELEGRAM),
    "/di.xml": ("di", _TELEGRAM),
    "/aftonbladet.xml": ("aftonbladet", _ENSAM),
}


def _rss(titel: str, ingress: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>fixtur</title>'
        f"<item><title>{titel}</title><description>{ingress}</description>"
        "<pubDate>Mon, 27 Jul 2026 08:00:00 GMT</pubDate>"
        f"<link>https://exempel.invalid/{abs(hash(titel))}</link></item>"
        "</channel></rss>").encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):                                    # noqa: N802
        rad = _SIDOR.get(self.path)
        if rad is None:
            self.send_error(404)
            return
        kropp = _rss(*rad[1])
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.send_header("Content-Length", str(len(kropp)))
        self.end_headers()
        self.wfile.write(kropp)

    def log_message(self, *a):                           # tyst fixtur
        return


_SRV: ThreadingHTTPServer | None = None
_BAS = ""
_FEEDS_ORIG = N.FEEDS


def _start() -> None:
    global _SRV, _BAS
    _SRV = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    _BAS = f"http://127.0.0.1:{_SRV.server_address[1]}"
    threading.Thread(target=_SRV.serve_forever, daemon=True).start()
    N.FEEDS = tuple(
        {"outlet": utgivare, "market": "se", "section": "fixtur",
         "url": f"{_BAS}{sokvag}"}
        for sokvag, (utgivare, _) in _SIDOR.items())
    os.environ["LANDVEX_NEWS_ON"] = "1"


def _stop() -> None:
    N.FEEDS = _FEEDS_ORIG
    os.environ.pop("LANDVEX_NEWS_ON", None)
    if _SRV is not None:
        _SRV.shutdown()
        _SRV.server_close()


def _skorda() -> list[dict]:
    """Kör skörden som schemaläggaren gör det — utan fejkad transport."""
    from engine.markets import MARKETS

    region = MARKETS["se"].regions[0]
    return H.harvest_region("news", region, "se", timeout=10.0)


# ── Testerna ────────────────────────────────────────────────────────────
def test_a_real_fetch_lands_one_row_per_item_in_its_own_table():
    """Skörden går via news_items, aldrig via `harvested`."""
    N.reset()
    H.reset()
    rader = _skorda()
    assert rader == [], "nyhetsposter får inte också läggas i harvested"
    poster = N.all_items(market="se")
    assert len(poster) == len(_SIDOR), \
        f"{len(poster)} poster, väntade {len(_SIDOR)}"
    assert {p["outlet"] for p in poster} == {u for u, _ in _SIDOR.values()}
    # ägaren följer med ur OUTLETS — utan den blir syndikering bekräftelse
    assert {p["owner"] for p in poster} == {"svt", "bonnier", "schibsted"}
    assert N.last_harvest()["items"] == len(_SIDOR)
    assert N.last_harvest()["unparsed"] == []


def test_the_second_run_stores_the_same_rows_not_twice_as_many():
    """Skörden körs varje dygn. Utan idempotens växer lagret linjärt och
    varje titel räknas som en ny röst."""
    N.reset()
    _skorda()
    forsta = len(N.all_items(market="se"))
    _skorda()
    assert len(N.all_items(market="se")) == forsta


def test_four_titles_become_one_story_carried_by_two_owners():
    N.reset()
    _skorda()
    kluster = N.cluster(N.all_items(market="se"))
    stora = [k for k in kluster if len(k["items"]) > 1]
    assert len(stora) == 1, f"väntade ETT syndikerat kluster, fick {stora}"
    k = stora[0]
    assert len(k["items"]) == 3 and k["independent_networks"] == 2
    assert sorted(k["owners"]) == ["bonnier", "svt"]
    assert k["may_inform_analysis"] is True
    # tre titlar, två ägare — bandet får ALDRIG bli starkt av fler
    # tidningar i samma koncern
    assert k["strength"] != "strong"
    ensamma = [x for x in kluster if len(x["items"]) == 1]
    assert len(ensamma) == 1 and ensamma[0]["may_inform_analysis"] is False


def test_the_verification_component_computes_once_something_is_harvested():
    """Blockeraren: före skörden var komponenten alltid `refused` med
    'absence of INPUT'. Nu ska den räkna — och tala om vad den räknat."""
    N.reset()
    varde, _b, vagran = M._independent_verification("se")
    assert varde is None and "absence of INPUT" in vagran
    _skorda()
    varde, basis, vagran = M._independent_verification("se")
    assert vagran == ""
    assert varde == 0.5, f"ett bekräftat av två kluster, fick {varde}"
    assert basis["clusters"] == 2 and basis["corroborated"] == 1
    assert basis["owners_seen"] == ["bonnier", "schibsted", "svt"]


def test_swedish_newspapers_do_not_verify_the_german_press():
    """Felet som fanns: komponenten läste HELA lagret oavsett marknad, så
    två svenska tidningar gav Tyskland och Japan 100 %. Ett tal om ETT
    lands press räknat på ett ANNATS är precis vad modulen säger sig
    undvika."""
    N.reset()
    _skorda()
    assert M._independent_verification("se")[0] is not None
    for annat in ("de", "jp", "us"):
        varde, _b, vagran = M._independent_verification(annat)
        assert varde is None, f"{annat} fick {varde} ur svensk press"
        assert "absence of INPUT" in vagran


def test_a_wire_item_alone_is_not_a_countrys_own_journalism():
    """Globala telegram får bekräfta en inhemsk uppgift — men ett kluster
    som BARA består av telegram är ingen tysk press."""
    import time

    N.reset()
    N.store_items([
        {"checksum": "w1", "outlet": "reuters", "owner": "reuters",
         "market": "", "title": "Global chip shortage eases",
         "summary": "Supply improved in June, analysts said.",
         "harvested_at": time.time()},
        {"checksum": "w2", "outlet": "ap", "owner": "ap", "market": "",
         "title": "Global chip shortage eases",
         "summary": "Supply improved in June, analysts said.",
         "harvested_at": time.time()}])
    varde, basis, vagran = M._independent_verification("de")
    assert varde is None and basis["items"] == 2 and basis["clusters"] == 0
    assert "only global wire copy" in vagran


def test_the_rows_survive_a_restart_of_the_process():
    """Minnesfallbacken duger för ett test och inte för ett dygn. Samma
    poster ska ligga kvar när lagret öppnas på nytt — och checksumman ska
    hålla dem unika över omstarten."""
    from engine.storage.sqlite import SqliteStore

    with tempfile.TemporaryDirectory() as d:
        sokvag = os.path.join(d, "news.db")
        s1 = SqliteStore(sokvag)
        N.set_store(s1)
        try:
            N.reset()
            _skorda()
            innan = len(N.all_items(market="se"))
            assert innan == len(_SIDOR)
            s1.close() if hasattr(s1, "close") else None
            s2 = SqliteStore(sokvag)                     # "omstart"
            N.set_store(s2)
            assert len(N.all_items(market="se")) == innan
            _skorda()                                    # skörd efter start
            assert len(N.all_items(market="se")) == innan
        finally:
            N.set_store(None)
            N.reset()


def test_a_feed_that_does_not_answer_is_named_not_silently_dropped():
    """Sju flöden som svarar ska gå att skilja från åtta."""
    N.reset()
    original = N.FEEDS
    N.FEEDS = original + ({"outlet": "svd", "market": "se",
                           "section": "fixtur",
                           "url": f"{_BAS}/finns-inte.xml"},)
    try:
        _skorda()
        info = N.last_harvest()
        assert info["feeds"] == len(original) + 1
        assert info["items"] == len(_SIDOR)
    finally:
        N.FEEDS = original


def test_the_index_moves_toward_its_floor_but_is_not_forced_over_it():
    """Skörden ska lyfta den beräknade vikten. Den ska INTE trolla fram
    ett indexvärde — de två återstående komponenterna saknar fortfarande
    underlag, och 50-procentsgolvet ska hålla."""
    N.reset()
    fore = M.mrai("se", limit=4)["of_weight"]
    _skorda()
    efter = M.mrai("se", limit=4)
    assert efter["of_weight"] > fore
    assert "independent_verification" not in efter["refused_components"]
    if efter["of_weight"] < M.MIN_WEIGHT_COMPUTED:
        assert efter["index"] is None
    N.reset()


def test_nothing_here_marks_any_client_as_verified_live():
    """En fixtur bevisar parsning, aldrig att adressen svarar."""
    from engine.datasources import sensor_apis as S

    N.reset()
    _skorda()
    for namn in dir(S):
        kl = getattr(S, namn)
        if isinstance(kl, type) and hasattr(kl, "verified_live"):
            assert kl.verified_live is False, namn


if __name__ == "__main__":
    _start()
    try:
        fns = [v for k, v in sorted(globals().items())
               if k.startswith("test_")]
        for fn in fns:
            fn()
            print(f"  ✓ {fn.__name__}")
        print(f"\n{len(fns)} tester gröna.")
    finally:
        _stop()
