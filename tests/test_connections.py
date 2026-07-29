"""Kundens kryp-in: nycklar som aldrig läcker, status som aldrig ljuger.

Tre saker bevakas hårt:

  * hemligheten lämnar ALDRIG systemet omaskerad — varje läsväg går
    genom masked(), och testet letar efter nyckeln i hela svaret,
  * `verified` blir aldrig sant utan att leverantörens riktiga server
    svarat — ett nätfel, ett policyblock eller tystnad är "configured",
    aldrig ett hoppfullt "antagligen ok",
  * modellens ord är märkta som modellens — en tolkning, aldrig ett
    Landvex-mätvärde, och en utebliven berättelse hittas aldrig på.

Kör: python3 -m tests.test_connections
"""
from __future__ import annotations

import io
import json
import urllib.error

from engine import connections as C

NYCKEL = "sk-ant-api03-hemlighemlig-XYZ9"


def _koppla(**kw):
    bas = dict(provider="anthropic", config={"api_key": NYCKEL},
               tenant="t1")
    bas.update(kw)
    return C.connection(bas["provider"], bas["config"],
                        tenant=bas["tenant"])


def test_an_unknown_provider_is_refused_with_the_catalog():
    try:
        C.connection("langchain", {}, tenant="t1")
    except C.ConnectionRefused as e:
        assert "anthropic" in str(e) and "slack_webhook" in str(e)
    else:
        raise AssertionError("okänd leverantör kopplades")


def test_a_connection_without_its_required_field_cannot_exist():
    try:
        C.connection("anthropic", {}, tenant="t1")
    except C.ConnectionRefused as e:
        assert "api_key" in str(e) and "cannot ever work" in str(e)
    else:
        raise AssertionError("nyckellös koppling skapades")
    try:
        C.connection("anthropic", {"api_key": NYCKEL, "org": "x"},
                     tenant="t1")
    except C.ConnectionRefused as e:
        assert "org" in str(e)
    else:
        raise AssertionError("okänt fält accepterades tyst")


def test_a_connection_needs_a_tenant():
    try:
        C.connection("anthropic", {"api_key": NYCKEL}, tenant="")
    except C.ConnectionRefused as e:
        assert "tenant" in str(e)
    else:
        raise AssertionError("nyckeln blev allas")


def test_webhooks_pass_the_same_ssrf_gate_as_pushes():
    for mal in ("http://hooks.slack.com/x",
                "https://127.0.0.1/hook",
                "https://192.168.1.10/hook"):
        try:
            C.connection("slack_webhook", {"webhook_url": mal},
                         tenant="t1")
        except C.ConnectionRefused:
            pass
        else:
            raise AssertionError(f"{mal} accepterades")


def test_the_secret_never_leaves_the_system_unmasked():
    """Hela det maskerade svaret genomsöks — nyckeln får inte finnas
    NÅGONSTANS i det, och de sista fyra tecknen ska kännas igen."""
    rec = _koppla()
    m = C.masked(rec)
    assert NYCKEL not in json.dumps(m), "nyckeln läckte genom masked()"
    assert m["config"]["api_key"].endswith(NYCKEL[-4:])
    assert m["config"]["api_key"].startswith("••••")
    # Kort hemlighet: total maskering — fyra sista av åtta avslöjar halva.
    kort = C.connection("openai", {"api_key": "sk-kort1"}, tenant="t1")
    assert C.masked(kort)["config"]["api_key"] == "••••"
    # Webhook-URL:en är en hemlighet (den som har den kan posta).
    hook = C.connection(
        "slack_webhook",
        {"webhook_url": "https://hooks.slack.com/services/T0/B0/xyz"},
        tenant="t1")
    assert "hooks.slack.com" not in json.dumps(C.masked(hook))


def test_configured_is_not_verified():
    rec = _koppla()
    assert rec["status"] == "configured"
    assert rec["verified_at"] is None


def test_a_tenant_only_sees_its_own_connections():
    C.reset()
    try:
        C.save_connection(_koppla(tenant="t1"))
        C.save_connection(_koppla(provider="openai",
                                  config={"api_key": "sk-annan-XYZ"},
                                  tenant="t2"))
        assert [r["provider"] for r in C.all_connections("t1")] == \
            ["anthropic"]
        try:
            C.get_connection("anthropic", tenant="t2")
        except C.ConnectionRefused as e:
            assert "no 'anthropic' connection" in str(e)
        else:
            raise AssertionError("t2 läste t1:s nyckel")
    finally:
        C.reset()


def test_connections_survive_a_restart_and_delete_deletes():
    from engine.storage.sqlite import SqliteStore

    C.reset()
    C.set_store(SqliteStore(":memory:"))
    try:
        C.save_connection(_koppla())
        rad = C.get_connection("anthropic", tenant="t1")
        assert rad["config"]["api_key"] == NYCKEL, \
            "lagret ska bevara nyckeln för ANVÄNDNING"
        assert C.delete_connection("anthropic", tenant="t1") is True
        assert C.all_connections("t1") == []
        assert C.delete_connection("anthropic", tenant="t1") is False
    finally:
        C.set_store(None)
        C.reset()


def test_both_stores_offer_the_connection_contract():
    from engine.storage.postgres import PostgresStore
    from engine.storage.sqlite import SqliteStore

    for st in (SqliteStore, PostgresStore):
        for metod in ("save_connection", "all_connections",
                      "delete_connection"):
            assert callable(getattr(st, metod, None)), f"{st.__name__}.{metod}"


# ── Proben: bara ett riktigt svar räknas ───────────────────────────────
def _fix(status=200, kropp=b"{}", *, fel=None):
    anrop = []

    def transport(url, headers, body, timeout):
        anrop.append({"url": url, "headers": dict(headers), "body": body})
        if fel is not None:
            raise fel
        return status, kropp
    transport.anrop = anrop
    return transport


def test_a_probe_verifies_only_when_the_real_server_answers():
    from integrations import llm

    rec = _koppla()
    ok = llm.probe(rec, transport=_fix(200))
    assert ok["verified"] is True and "says nothing about tomorrow" \
        in ok["why_en"]

    nej = llm.probe(rec, transport=_fix(fel=urllib.error.HTTPError(
        "https://api.anthropic.com/v1/models", 401, "unauthorized",
        {}, io.BytesIO(b""))))
    assert nej["verified"] is False and nej["status"] == 401
    assert "not accepted" in nej["why_en"]

    tyst = llm.probe(rec, transport=_fix(fel=OSError("egress blocked")))
    assert tyst["verified"] is False and tyst["status"] == 0
    assert "nothing was verified" in tyst["why_en"]
    assert NYCKEL not in tyst["why_en"], "nyckeln i ett felmeddelande"


def test_the_probe_sends_the_key_where_the_provider_expects_it():
    from integrations import llm

    t = _fix(200)
    llm.probe(_koppla(), transport=t)
    assert t.anrop[0]["headers"]["x-api-key"] == NYCKEL
    assert t.anrop[0]["body"] is None, "proben ska inte generera tokens"

    t2 = _fix(200)
    llm.probe(C.connection("openai", {"api_key": "sk-open-XYZW"},
                           tenant="t1"), transport=t2)
    assert t2.anrop[0]["headers"]["Authorization"] == "Bearer sk-open-XYZW"


def test_a_webhook_probe_is_a_visible_labelled_test_message():
    from integrations import llm

    hook = C.connection(
        "slack_webhook",
        {"webhook_url": "https://hooks.slack.com/services/T0/B0/xyz"},
        tenant="t1")
    t = _fix(200)
    assert llm.probe(hook, transport=t)["verified"] is True
    kropp = json.loads(t.anrop[0]["body"])
    assert "connection test" in kropp["text"]
    assert "Nothing else follows" in kropp["text"]


# ── Berättaren: modellens ord är modellens ─────────────────────────────
def test_narration_uses_the_customers_model_and_marks_the_text():
    from integrations import llm

    svar = {"model": "claude-opus-5", "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "The gap is real."}]}
    t = _fix(200, json.dumps(svar).encode())
    ut = llm.narrate(_koppla(), {"score": 61, "caveats_en": ["mock"]},
                     question="Is the gap real?", transport=t)
    assert ut["text"] == "The gap is real."
    assert "never a Landvex measurement" in ut["what_this_is_en"]
    begaran = json.loads(t.anrop[0]["body"])
    assert begaran["model"] == "claude-opus-5"
    assert "caveats" in begaran["messages"][0]["content"]
    assert "treat them as binding" in begaran["messages"][0]["content"]
    assert t.anrop[0]["headers"]["x-api-key"] == NYCKEL


def test_a_model_refusal_is_relayed_never_papered_over():
    from integrations import llm

    svar = {"model": "claude-opus-5", "stop_reason": "refusal",
            "content": []}
    ut = llm.narrate(_koppla(), {"x": 1},
                     transport=_fix(200, json.dumps(svar).encode()))
    assert "declined" in ut["text"] and "relayed as-is" in ut["text"]


def test_a_failed_narration_is_refused_never_invented():
    from integrations import llm

    try:
        llm.narrate(_koppla(), {"x": 1},
                    transport=_fix(fel=OSError("egress blocked")))
    except C.ConnectionRefused as e:
        assert "Nothing was invented" in str(e)
        assert NYCKEL not in str(e)
    else:
        raise AssertionError("utebliven berättelse blev en tom lyckad")


def test_only_llm_connections_can_narrate():
    from integrations import llm

    hook = C.connection(
        "slack_webhook",
        {"webhook_url": "https://hooks.slack.com/services/T0/B0/xyz"},
        tenant="t1")
    try:
        llm.narrate(hook, {"x": 1}, transport=_fix(200))
    except C.ConnectionRefused as e:
        assert "not a language model" in str(e)
    else:
        raise AssertionError("en webhook berättade")


def test_enterprise_systems_are_rows_with_the_same_gates():
    """SAP, ServiceNow, Dynamics, Salesforce: samma SSRF-grind, samma
    maskering — endpointen och auth-värdet är hemligheter."""
    for prov in ("sap", "servicenow", "dynamics365", "salesforce"):
        assert C.CONNECTORS[prov]["kind"] == "enterprise"
        try:
            C.connection(prov, {"endpoint_url": "https://10.0.0.5/api"},
                         tenant="t1")
        except C.ConnectionRefused:
            pass
        else:
            raise AssertionError(f"{prov}: privat endpoint accepterades")
    rec = C.connection("sap", {
        "endpoint_url": "https://cpi.example.hana.ondemand.com/http/lvx",
        "auth_value": "Basic aGVtbGlndDpsb3Nlbg==",
        "auth_header": "Authorization"}, tenant="t1")
    m = json.dumps(C.masked(rec))
    assert "aGVtbGlndDpsb3Nlbg" not in m, "auth-värdet läckte"
    assert "hana.ondemand.com" not in m, "endpointen läckte"


def test_delivery_headers_carry_the_auth_and_nothing_logs_it():
    rec = C.connection("servicenow", {
        "endpoint_url": "https://co.service-now.com/api/now/table/x",
        "auth_value": "Basic c2VydmljZTpub3c="}, tenant="t1")
    huvud = C.headers_for(rec)
    assert huvud["Authorization"] == "Basic c2VydmljZTpub3c="
    assert C.target_url_of(rec).startswith("https://co.service-now")
    # Eget huvudnamn respekteras (t.ex. x-sn-apikey).
    rec2 = C.connection("servicenow", {
        "endpoint_url": "https://co.service-now.com/api/x",
        "auth_value": "nyckel123", "auth_header": "x-sn-apikey"},
        tenant="t1")
    assert C.headers_for(rec2)["x-sn-apikey"] == "nyckel123"
    # En LLM-koppling är inget leveransmål.
    try:
        C.target_url_of(_koppla())
    except C.ConnectionRefused as e:
        assert "no delivery URL" in str(e)
    else:
        raise AssertionError("nyckeln blev en adress")


def test_credentials_can_land_in_the_enterprise_system():
    """feedback_webhook vinner om den finns; annars första
    affärssystemet — och leveransen bär kundens auth-huvud."""
    from integrations import feedback

    C.reset()
    try:
        C.save_connection(C.connection("sap", {
            "endpoint_url": "https://cpi.example.com/http/lvx",
            "auth_value": "Bearer sap-token-77"}, tenant="t1"))
        mal = C.feedback_target("t1")
        assert mal["provider"] == "sap"
        anrop = []

        def transport(url, headers, body, timeout):
            anrop.append({"url": url, "headers": headers})
            return 201, b"{}"
        ut = feedback.forward({"id": "lvx-cred-x", "tenant": "t1"},
                              mal, transport=transport)
        assert ut["delivered"] is True
        assert anrop[0]["url"] == "https://cpi.example.com/http/lvx"
        assert anrop[0]["headers"]["Authorization"] == "Bearer sap-token-77"
        # Webhooken vinner när båda finns — EN regel, inte en gissning.
        C.save_connection(C.connection(
            "feedback_webhook",
            {"webhook_url": "https://api.kund.se/lvx"}, tenant="t1"))
        assert C.feedback_target("t1")["provider"] == "feedback_webhook"
    finally:
        C.reset()


def test_a_push_can_target_a_connection_instead_of_a_raw_url():
    """Prenumerationen pekar på kopplingen; adress och auth hämtas ur
    kryp-in vid varje leverans — hemligheten bor kvar där den maskeras."""
    from engine import pushes as P

    C.reset()
    try:
        C.save_connection(C.connection("sap", {
            "endpoint_url": "https://cpi.example.com/http/lvx",
            "auth_value": "Bearer natt-77"}, tenant="t1"))
        P.validate_subscription({"dataset": "hotspots", "format": "csv",
                                 "connection": "sap"}, tenant="t1")
        for fel in ({"connection": "sap",
                     "target_url": "https://x.se/h",
                     "dataset": "hotspots", "format": "csv"},
                    {"connection": "servicenow",
                     "dataset": "hotspots", "format": "csv"}):
            try:
                P.validate_subscription(fel, tenant="t1")
            except P.PushRefused:
                pass
            else:
                raise AssertionError(f"{fel} accepterades")
        anrop = []

        def transport(url, body, headers, timeout):
            anrop.append({"url": url, "headers": headers})
            return 200, b"ok"
        ut = P.deliver({"tenant": "t1",
                        "params": {"dataset": "hotspots", "format": "csv",
                                   "connection": "sap",
                                   "dataset_params": {"vertical": "gym",
                                                      "market": "us",
                                                      "top_n": 2}}},
                       transport=transport)
        assert ut["delivered"] is True
        assert anrop[0]["url"] == "https://cpi.example.com/http/lvx"
        assert anrop[0]["headers"]["Authorization"] == "Bearer natt-77"
        # Raderad koppling ⇒ redovisad icke-leverans, aldrig ett kvitto.
        C.reset()
        ut2 = P.deliver({"tenant": "t1",
                         "params": {"dataset": "hotspots", "format": "csv",
                                    "connection": "sap"}},
                        transport=transport)
        assert ut2["delivered"] is False
        assert "nothing is reported as sent" in ut2["why_en"]
    finally:
        C.reset()


def test_the_catalog_states_what_it_cannot_do():
    k = C.catalog()
    assert {c["id"] for c in k["connectors"]} == set(C.CONNECTORS)
    for c in k["connectors"]:
        assert len(c["cannot_en"]) > 40, c["id"]
        assert c["fields"], c["id"]
    assert "masks" in k["what_en"]
    assert json.dumps(k)   # serialiserbar — inga funktioner i katalogen


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)} tester gröna.")
