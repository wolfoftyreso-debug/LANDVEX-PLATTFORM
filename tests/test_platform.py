"""Tester för plattformslagret (hälsa, metrics, audit, manifest).
Körs utan pytest:  python3 -m tests.test_platform"""
from __future__ import annotations

import json
import os
import tempfile

from api.agent_manifest import AGENT_MANIFEST
from api.catalog import API_CATALOG
from api.health import build_health
from api.security import AuditLog, Metrics
from engine.datasources.adapters import ScbSource, production_sources
from engine.datasources.base import Resolver
from engine.datasources.cache import CachedSource
from engine.datasources.mock import MockSource
from engine.storage.sqlite import SqliteStore


def test_health_reports_sources_and_persistence():
    resolver = Resolver(production_sources() + [MockSource()])
    h = build_health(resolver, SqliteStore(":memory:"))
    assert h["status"] == "ok" and h["engine_version"]
    assert h["persistens"] == "sqlite"
    namn = {k["source"]: k["status"] for k in h["kallor"]}
    assert namn["scb"] == "ok"
    assert namn["permits"] == "ej_ansluten"          # stub redovisas ärligt
    assert namn["mock"] == "ok"
    assert build_health(resolver, None)["persistens"] == "av"


def test_health_detects_paused_source_through_cache():
    now = [1000.0]
    src = ScbSource(clock=lambda: now[0])
    src._down_until = 2000.0                          # simulerad felpaus
    resolver = Resolver([CachedSource(src, SqliteStore(":memory:")),
                         MockSource()])
    h = build_health(resolver, None)
    assert h["status"] == "degraderad"
    assert any(k["status"] == "pausad" for k in h["kallor"])
    now[0] = 3000.0                                   # pausen har löpt ut
    assert build_health(resolver, None)["status"] == "ok"


def test_prometheus_export():
    m = Metrics()
    m.observe("/v1/analyze", 200, 12.0)
    m.observe("/v1/scan", 500, 40.0)
    text = m.to_prometheus([{"source": "scb", "status": "pausad"}])
    assert "landvex_requests_total 2" in text
    assert "landvex_errors_5xx_total 1" in text
    assert 'landvex_requests_by_path_total{path="/v1/analyze"} 1' in text
    assert 'landvex_source_up{source="scb"} 0' in text


def test_audit_tail():
    path = os.path.join(tempfile.mkdtemp(), "audit.log")
    log = AuditLog(path=path)
    for i in range(5):
        log.write({"i": i})
    assert [e["i"] for e in log.tail(3)] == [2, 3, 4]
    assert AuditLog(path=os.path.join(tempfile.mkdtemp(), "x.log")).tail() == []


def test_agent_manifest_matches_catalog():
    names = [t["name"] for t in AGENT_MANIFEST["tools"]]
    assert len(names) == len(set(names))              # unika verktygsnamn
    katalog_paths = {ep["path"] for e in API_CATALOG["engines"]
                     for ep in e["endpoints"]}
    for t in AGENT_MANIFEST["tools"]:
        assert t["path"] in katalog_paths, t["path"]  # spårbart till katalogen
        schema = t["input_schema"]
        assert schema["type"] == "object"
        for req in schema["required"]:
            assert req in schema["properties"], (t["name"], req)
    assert "caveats" in AGENT_MANIFEST["instruktioner_en"]
    assert json.dumps(AGENT_MANIFEST)                 # serialiserbart


def test_catalog_lists_all_engines():
    ids = {e["id"] for e in API_CATALOG["engines"]}
    assert {"ask", "opportunity", "workforce", "risk", "compare",
            "gaps", "plan", "segments", "installed_base"} <= ids


def test_commission_model_per_lead():
    """quiXzoom-kommission per lead, score-graderad; Growth utan månadsavgift."""
    from engine.commission import commission_qz, commission_for_lead
    from engine.scan import scan
    from engine.profile import profile_from_dict
    from api.licensing import PLANS
    assert commission_qz(0.95) == 0.15 and commission_qz(90) == 0.15
    assert commission_qz(0.65) == 0.10 and commission_qz(66) == 0.10
    assert commission_qz(0.30) == 0.05 and commission_qz(0.0) == 0.05
    assert commission_for_lead(82) == commission_for_lead(82)   # determinism
    assert PLANS["pro"]["pris_manad"] is None                   # ingen mån.avg
    assert PLANS["pro"]["kommission"]["modell"] == "per_lead"
    r = scan(profile_from_dict({"vertical_id": "gym"}), top_n=3, market="us")
    for h in r["hotspots"]:
        assert h["commission"]["qz_token"] == \
            commission_qz(h["opportunity_score"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
