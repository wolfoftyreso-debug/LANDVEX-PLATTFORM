"""Tester för programs-registry-adaptern. Kör utan pytest/nätverk:
python3 -m tests.test_programs"""
from __future__ import annotations

from engine.datasources.programs import ProgramsClient, normalize_record
from engine.models import Location
from engine.opportunity_intel import support_programs, opportunity_intel
from engine.scoring import analyze

_LOC = Location(59.33, 18.06, address="Stockholm")

_JSON_FIXTURE = ('{"programs":[{"id":"eu-ev-2027","title":"EV charging call",'
                 '"provider":"EU Funding & Tenders","amount_local":[200000,2500000],'
                 '"currency":"SEK","deadline":"2027-03-15","verticals":["elektriker"],'
                 '"url":"https://ex/eu-ev","summary":"Charging infrastructure."}]}')

_RSS_FIXTURE = ('<rss><channel>'
                '<item><title>Energy retrofit grant</title>'
                '<link>https://ex/retrofit</link>'
                '<description>Retrofit support for buildings.</description>'
                '<pubDate>2027-05-01</pubDate></item>'
                '</channel></rss>')


def _client(fixture: str) -> ProgramsClient:
    return ProgramsClient(base_url="https://registry.example/api",
                          transport=lambda url, t: fixture)


def test_not_connected_returns_empty():
    c = ProgramsClient(base_url="")
    assert not c.connected
    assert c.fetch_programs(59.3, 18.0, "elektriker") == []
    assert c.status()["status"] == "ej_ansluten"


def test_json_feed_normalized_and_filtered():
    c = _client(_JSON_FIXTURE)
    recs = c.fetch_programs(59.33, 18.06, "elektriker")
    assert len(recs) == 1
    r = recs[0]
    assert r["source"] == "registry"
    assert r["amount_local"] == [200000, 2500000]
    assert r["deadline"] == "2027-03-15"
    assert r["url"].startswith("https://")
    # Vertical filter: a record tagged elektriker must not show for vvs.
    assert c.fetch_programs(59.33, 18.06, "vvs") == []


def test_rss_fallback():
    c = _client(_RSS_FIXTURE)
    recs = c.fetch_programs(59.33, 18.06, "elektriker")
    assert len(recs) == 1
    assert recs[0]["label_en"] == "Energy retrofit grant"
    assert recs[0]["url"] == "https://ex/retrofit"


def test_soft_failure_is_empty():
    def boom(url, t):
        raise RuntimeError("network down")
    c = ProgramsClient(base_url="https://x", transport=boom)
    # support_programs must not raise even if the registry errors.
    rep = analyze(_LOC, "elektriker")
    out = support_programs(rep, "elektriker", programs=c)
    assert out["live_count"] == 0                # degraded honestly
    assert out["count"] >= 1                     # archetypes still present


def test_live_programs_merge_first():
    c = _client(_JSON_FIXTURE)
    rep = analyze(_LOC, "elektriker")
    out = support_programs(rep, "elektriker", programs=c)
    assert out["live_count"] == 1
    assert out["programs"][0]["source"] == "registry"   # real listed first
    assert any(p["source"] == "archetype" for p in out["programs"])


def test_archetypes_still_work_without_client():
    rep = analyze(_LOC, "elektriker")
    out = support_programs(rep, "elektriker")
    assert out["live_count"] == 0
    assert all(p["source"] == "archetype" for p in out["programs"])
    assert "set LANDVEX_PROGRAMS_URL" in out["notis_en"]


def test_opportunity_intel_threads_client():
    c = _client(_JSON_FIXTURE)
    r = opportunity_intel(_LOC, "elektriker", market="se", programs_client=c)
    assert r["support_programs"]["live_count"] == 1


def test_normalize_never_fabricates():
    r = normalize_record({"title": "Bare"})
    assert r["amount_local"] is None and r["url"] == "" and r["verticals"] == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
