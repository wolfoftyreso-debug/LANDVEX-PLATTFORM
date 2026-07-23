"""Tester för AAMOS-integrationslagret. Körs utan pytest:
python3 -m tests.test_aamos"""
from __future__ import annotations

from api.licensing import required_capability
from integrations.aamos import (AamosClient, AamosUnavailable,
                                agent_chat_safe, agents,
                                cognition_brief_safe, platform_status,
                                watch)


def _klient(svar: dict | None = None, fel: bool = False,
            logg: list | None = None) -> AamosClient:
    def transport(method, url, body):
        if logg is not None:
            logg.append((method, url, body))
        if fel:
            raise OSError("connection refused")
        return svar if svar is not None else {}
    return AamosClient(base_url="http://localhost:3100",
                       transport=transport)


def test_client_builds_urls_and_routes_methods():
    logg = []
    c = _klient({"ok": True}, logg=logg)
    c.graph_stats()
    c.identity_agents()
    c.alerts()
    c.health_summary()
    c.cognition_brief("EV charging in Texas")
    c.agent_chat("status?", agent_id="bernt")
    metoder = [(m, u.split("http://localhost:3100")[1]) for m, u, _ in logg]
    assert ("GET", "/api/aamos/graph/stats") in metoder
    assert ("GET", "/api/aamos/identity/agents") in metoder
    assert ("GET", "/api/aamos/alerts") in metoder
    assert ("GET", "/api/aamos/control-plane/health-summary") in metoder
    assert ("POST", "/api/aamos/cognition/strategic-brief") in metoder
    assert ("POST", "/api/aamos/agent-loop/chat") in metoder
    # POST-kroppar skickas med.
    body = [b for m, _, b in logg if m == "POST"][0]
    assert body and "topic" in body


def test_client_not_connected_and_errors():
    tom = AamosClient(base_url="")
    assert not tom.connected
    assert tom.status()["status"] == "ej_ansluten"
    try:
        tom.graph_stats()
    except AamosUnavailable:
        pass
    else:
        raise AssertionError("Ej ansluten skulle ha kastat")
    trasig = _klient(fel=True)
    try:
        trasig.alerts()
    except AamosUnavailable:
        pass
    else:
        raise AssertionError("Transportfel skulle ha kastat")


def test_endpoint_helpers_degrade_honestly():
    """Hjälparna får aldrig fälla en endpoint – ärlig degradering."""
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource
    from api.health import build_health, source_status
    res = Resolver([MockSource()])

    tom = AamosClient(base_url="")
    ps = platform_status(tom, res, None, build_health, source_status)
    assert ps["opportunity_engine"]["status"] == "ok"
    assert ps["aamos"]["status"] == "ej_ansluten"
    assert "aamos_health" not in ps

    w = watch(tom, res, source_status)
    assert w["alerts"] == [] and "not connected" in w["notis_en"]
    a = agents(tom)
    assert a["agents"] == []
    chat = agent_chat_safe(tom, "hello")
    assert "not connected" in chat["svar_en"]
    brief = cognition_brief_safe(tom, "topic")
    assert "not connected" in brief["svar_en"]

    # Ansluten men svarar med fel → degraderad, aldrig exception.
    trasig = _klient(fel=True)
    ps2 = platform_status(trasig, res, None, build_health, source_status)
    assert ps2["aamos"]["status"] == "ej_ansluten"
    w2 = watch(trasig, res, source_status)
    assert w2["alerts"] == []


def test_endpoint_helpers_pass_through_when_connected():
    from engine.datasources.base import Resolver
    from engine.datasources.mock import MockSource
    from api.health import build_health, source_status
    res = Resolver([MockSource()])
    c = _klient({"agents": [{"id": "bernt", "status": "active"}],
                 "alerts": [{"level": "warning", "text": "disk 80%"}],
                 "services": 82, "ok": True})
    assert agents(c)["agents"][0]["id"] == "bernt"
    assert watch(c, res, source_status)["alerts"][0]["level"] == "warning"
    ps = platform_status(c, res, None, build_health, source_status)
    assert "aamos_health" in ps and "aamos_services" in ps


def test_new_endpoints_are_capability_gated():
    assert required_capability("/v1/platform/status") == "core"
    assert required_capability("/v1/watch") == "platform_ops"
    assert required_capability("/v1/agents") == "partner_api"
    assert required_capability("/v1/agents/chat") == "partner_api"
    assert required_capability("/v1/cognition/brief") == "partner_api"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
