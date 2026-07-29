"""Kundens kryp-in: egna kopplingar till språkmodeller och vanliga system.

En betalande kund kopplar sina EGNA konton — en språkmodellsnyckel, en
Slack-webhook — till sin tenant. Katalogen över vad som går att koppla
är DATA (en ny integration är en rad, inte en gren), och tre regler är
själva modulen:

* **Hemligheter ekas aldrig tillbaka.** Nyckeln lagras för att användas,
  och varje läsväg går genom `masked()` — de sista fyra tecknen räcker
  för att kunden ska känna igen sin nyckel, resten är prickar. En nyckel
  som syns i ett API-svar hamnar i loggar, skärmdelningar och
  supportärenden.
* **"Konfigurerad" är inte "verifierad".** En sparad koppling har
  status `configured`. `verified` sätts ENDAST av en riktig probe där
  leverantörens server faktiskt svarade — aldrig av att formuläret var
  korrekt ifyllt. Skillnaden är exakt den mellan att ha en nyckel och
  att ha en nyckel som fungerar.
* **Modellens ord är modellens.** Det en kopplad språkmodell skriver är
  en TOLKNING från kundens egen modell, märkt som sådan — aldrig ett
  Landvex-mätvärde, och det lagras inte som fakta.

Webhook-mål valideras med samma SSRF-grind som pusharna: https, inga
loopback-/privatadresser. Rent stdlib; själva anropen bor i
integrations/llm.py (motorn ringer aldrig ut).
"""
from __future__ import annotations

import time as _time

from .pushes import PushRefused, validate_target


class ConnectionRefused(ValueError):
    """Kopplingen gick inte att skapa eller använda, och varför."""


DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"

# ── Katalogen: vad som går att koppla, som data ────────────────────────
CONNECTORS: dict[str, dict] = {
    "anthropic": {
        "label_en": "Anthropic Claude (your own API key)",
        "kind": "llm",
        "fields": (
            {"id": "api_key", "label_en": "API key", "secret": True,
             "required": True, "placeholder_en": "sk-ant-..."},
            {"id": "model", "label_en": "Model", "secret": False,
             "required": False,
             "placeholder_en": DEFAULT_ANTHROPIC_MODEL},
        ),
        "enables_en": ("Narrate any Landvex analysis with your own "
                       "Claude model: the numbers stay ours, the "
                       "interpretation is yours, billed to your key."),
        "cannot_en": ("The model's text is an interpretation from YOUR "
                      "model — it is never a Landvex measurement, and "
                      "it is not stored as fact. Landvex cannot see "
                      "your Anthropic usage or billing."),
    },
    "openai": {
        "label_en": "OpenAI (your own API key)",
        "kind": "llm",
        "fields": (
            {"id": "api_key", "label_en": "API key", "secret": True,
             "required": True, "placeholder_en": "sk-..."},
            {"id": "model", "label_en": "Model", "secret": False,
             "required": False, "placeholder_en": "gpt-4o"},
        ),
        "enables_en": ("Narrate any Landvex analysis with your own "
                       "OpenAI model, billed to your key."),
        "cannot_en": ("Same rule as every connected model: its text is "
                      "an interpretation, never a Landvex measurement, "
                      "and it is not stored as fact."),
    },
    "slack_webhook": {
        "label_en": "Slack (incoming webhook)",
        "kind": "notify",
        "fields": (
            {"id": "webhook_url", "label_en": "Webhook URL",
             "secret": True, "required": True,
             "placeholder_en": "https://hooks.slack.com/services/..."},
        ),
        "enables_en": ("Push deliveries and alerts land in your Slack "
                       "channel instead of a generic webhook."),
        "cannot_en": ("Delivery is at-least-once; Slack's own rate "
                      "limits and retention apply. The webhook URL is a "
                      "secret — anyone holding it can post to your "
                      "channel, which is why it is masked like a key."),
    },
    "feedback_webhook": {
        "label_en": "Your own system (credential feedback loop)",
        "kind": "feedback",
        "fields": (
            {"id": "webhook_url", "label_en": "Endpoint URL",
             "secret": True, "required": True,
             "placeholder_en": "https://api.yourcompany.com/landvex/"
                               "credentials"},
        ),
        "enables_en": ("Every approved mission's signed credential is "
                       "POSTed into your own system the moment it is "
                       "issued — verify it back against "
                       "/v1/credentials/verify and the loop closes."),
        "cannot_en": ("Delivery is at-least-once and the result is "
                      "recorded honestly — a failed POST never looks "
                      "delivered. What your system does with the "
                      "credential is yours; the signature can always "
                      "be re-verified against the platform."),
    },
    "teams_webhook": {
        "label_en": "Microsoft Teams (incoming webhook)",
        "kind": "notify",
        "fields": (
            {"id": "webhook_url", "label_en": "Webhook URL",
             "secret": True, "required": True,
             "placeholder_en": "https://outlook.office.com/webhook/..."},
        ),
        "enables_en": ("Push deliveries and alerts land in your Teams "
                       "channel."),
        "cannot_en": ("Same as Slack: at-least-once delivery, and the "
                      "URL is a secret because holding it means posting "
                      "rights."),
    },
    # ── Affärssystemen: myndigheters och företags standardsystem ──────
    # Landvex talar ren JSON över https mot systemens INBOUND-ytor —
    # integrationsplattformen kunden redan har (CPI, Power Automate,
    # scripted REST) äger mappningen till interna format. Det är ärligt:
    # ett löfte om att skriva IDocs vore ett löfte om någon annans
    # system. En ny integration är en rad, inte en gren.
    "sap": {
        "label_en": "SAP (Integration Suite / OData inbound)",
        "kind": "enterprise",
        "fields": (
            {"id": "endpoint_url",
             "label_en": "Inbound https endpoint (CPI iFlow or OData "
                         "service accepting POST)",
             "secret": True, "required": True,
             "placeholder_en": "https://your-tenant.it-cpi.cfapps.eu10."
                               "hana.ondemand.com/http/landvex"},
            {"id": "auth_value",
             "label_en": "Authorization header value",
             "secret": True, "required": False,
             "placeholder_en": "Basic ... or Bearer ..."},
            {"id": "auth_header", "label_en": "Auth header name",
             "secret": False, "required": False,
             "placeholder_en": "Authorization"},
        ),
        "enables_en": ("Scheduled deliveries and approved-mission "
                       "credentials land in your SAP landscape through "
                       "the Integration Suite endpoint your team "
                       "already operates."),
        "cannot_en": ("Landvex POSTs plain JSON/CSV over https to the "
                      "inbound endpoint. Mapping into IDocs, BAPIs or "
                      "CDS views happens in YOUR integration layer, "
                      "where it belongs — a platform that promised to "
                      "write SAP internals would be promising someone "
                      "else's system."),
    },
    "servicenow": {
        "label_en": "ServiceNow (Table API / scripted REST)",
        "kind": "enterprise",
        "fields": (
            {"id": "endpoint_url",
             "label_en": "Instance endpoint (Table API or scripted "
                         "REST)",
             "secret": True, "required": True,
             "placeholder_en": "https://yourco.service-now.com/api/now/"
                               "table/incident"},
            {"id": "auth_value",
             "label_en": "Authorization header value",
             "secret": True, "required": False,
             "placeholder_en": "Basic ..."},
            {"id": "auth_header", "label_en": "Auth header name",
             "secret": False, "required": False,
             "placeholder_en": "Authorization"},
        ),
        "enables_en": ("Deliveries and credentials POST straight into "
                       "your instance — an exception feed pointed at "
                       "the incident table becomes tickets your "
                       "operators already triage."),
        "cannot_en": ("Landvex sends the rows; assignment rules, SLAs "
                      "and workflows run in your instance. A failed "
                      "POST is recorded as failed — it never becomes a "
                      "ticket that looks filed."),
    },
    "dynamics365": {
        "label_en": "Microsoft Dynamics 365 (Power Automate inbound)",
        "kind": "enterprise",
        "fields": (
            {"id": "endpoint_url",
             "label_en": "HTTP-trigger flow URL (Power Automate)",
             "secret": True, "required": True,
             "placeholder_en": "https://prod-xx.westeurope.logic.azure."
                               "com/workflows/..."},
            {"id": "auth_value",
             "label_en": "Authorization header value (if the flow "
                         "checks one)",
             "secret": True, "required": False,
             "placeholder_en": "Bearer ..."},
            {"id": "auth_header", "label_en": "Auth header name",
             "secret": False, "required": False,
             "placeholder_en": "Authorization"},
        ),
        "enables_en": ("Deliveries and credentials trigger your Power "
                       "Automate flow, which writes into Dataverse/"
                       "Dynamics exactly the way your admins decided."),
        "cannot_en": ("The flow URL carries a signature and is treated "
                      "as a secret. What the flow does downstream is "
                      "yours; Landvex only knows whether the trigger "
                      "answered."),
    },
    "visma": {
        "label_en": "Visma (inbound integration endpoint)",
        "kind": "enterprise",
        "fields": (
            {"id": "endpoint_url",
             "label_en": "Inbound https endpoint (Visma.net "
                         "integration or your Visma middleware)",
             "secret": True, "required": True,
             "placeholder_en": "https://integration.yourco.se/visma/"
                               "landvex"},
            {"id": "auth_value",
             "label_en": "Authorization header value",
             "secret": True, "required": False,
             "placeholder_en": "Bearer ..."},
            {"id": "auth_header", "label_en": "Auth header name",
             "secret": False, "required": False,
             "placeholder_en": "Authorization"},
        ),
        "enables_en": ("Deliveries and credentials land in the Visma "
                       "landscape common across Swedish public sector "
                       "and SMEs, through the inbound endpoint your "
                       "integration team operates."),
        "cannot_en": ("Visma is a family of products with different "
                      "APIs — Landvex POSTs plain JSON/CSV to ONE "
                      "https endpoint you choose, and the mapping into "
                      "your specific Visma product lives in your "
                      "integration layer. OAuth flows against Visma "
                      "Connect are your middleware's to run."),
    },
    "unit4": {
        "label_en": "Unit4 ERP / Agresso (inbound endpoint)",
        "kind": "enterprise",
        "fields": (
            {"id": "endpoint_url",
             "label_en": "Inbound https endpoint (Unit4 ERP web "
                         "services gateway or your middleware)",
             "secret": True, "required": True,
             "placeholder_en": "https://erp.yourco.se/unit4/landvex"},
            {"id": "auth_value",
             "label_en": "Authorization header value",
             "secret": True, "required": False,
             "placeholder_en": "Basic ... or Bearer ..."},
            {"id": "auth_header", "label_en": "Auth header name",
             "secret": False, "required": False,
             "placeholder_en": "Authorization"},
        ),
        "enables_en": ("Deliveries and credentials reach the Unit4/"
                       "Agresso environment that runs much of Swedish "
                       "government administration."),
        "cannot_en": ("Landvex speaks plain https to the endpoint you "
                      "expose; ABW web services, workflow steps and "
                      "posting rules stay in your Unit4 configuration "
                      "— a receipt landing there is an inbox item, "
                      "not a booked transaction."),
    },
    "salesforce": {
        "label_en": "Salesforce (Flow / Apex REST inbound)",
        "kind": "enterprise",
        "fields": (
            {"id": "endpoint_url",
             "label_en": "Inbound endpoint (Flow HTTP or Apex REST)",
             "secret": True, "required": True,
             "placeholder_en": "https://yourco.my.salesforce.com/"
                               "services/apexrest/landvex"},
            {"id": "auth_value",
             "label_en": "Authorization header value",
             "secret": True, "required": False,
             "placeholder_en": "Bearer ..."},
            {"id": "auth_header", "label_en": "Auth header name",
             "secret": False, "required": False,
             "placeholder_en": "Authorization"},
        ),
        "enables_en": ("Deliveries and credentials land in your org "
                       "through the REST surface your Salesforce team "
                       "exposes."),
        "cannot_en": ("Token refresh and OAuth flows live in your "
                      "middleware or a long-lived integration user — "
                      "Landvex sends the request with the header you "
                      "configured and records the answer, nothing "
                      "more."),
    },
}


# ── Skapa och maskera ──────────────────────────────────────────────────
def connection(provider: str, config: dict, *, tenant: str) -> dict:
    """Skapa en koppling — eller vägra med ett skäl som går att åtgärda.

    Allt prövas när kopplingen SKAPAS: en nyckel som är fel upptäcks
    annars i en obevakad nattkörning månader senare.
    """
    if not tenant:
        raise ConnectionRefused(
            "a connection needs a tenant: the key is one customer's "
            "own, and without a tenant it would be everyone's")
    spec = CONNECTORS.get(provider)
    if spec is None:
        raise ConnectionRefused(
            f"unknown provider {provider!r}; choose "
            f"{', '.join(sorted(CONNECTORS))}")
    config = dict(config or {})
    for f in spec["fields"]:
        varde = str(config.get(f["id"], "") or "").strip()
        if f["required"] and not varde:
            raise ConnectionRefused(
                f"{provider} needs {f['id']!r} ({f['label_en']}). "
                f"Without it the connection cannot ever work, and a "
                f"connection that cannot work should not exist.")
        config[f["id"]] = varde
    okanda = set(config) - {f["id"] for f in spec["fields"]}
    if okanda:
        raise ConnectionRefused(
            f"unknown field(s) {sorted(okanda)} for {provider}; it "
            f"takes {', '.join(f['id'] for f in spec['fields'])}")
    # Alla mål-URL:er genom samma SSRF-grind som pusharna — en kunds
    # endpoint får inte bli vår väg in i vårt eget nät.
    for urlfalt in ("webhook_url", "endpoint_url"):
        if config.get(urlfalt):
            try:
                validate_target(config[urlfalt])
            except PushRefused as e:
                raise ConnectionRefused(str(e)) from e
    return {
        "provider": provider, "tenant": tenant,
        "kind": spec["kind"], "config": config,
        "status": "configured",
        # verified_at sätts ENDAST av en riktig probe (integrations-
        # lagret) — aldrig här. Ett korrekt ifyllt formulär bevisar
        # ingenting om nyckeln.
        "verified_at": None,
        "created_at": _time.time(),
    }


def masked(rec: dict) -> dict:
    """Kopplingen som den får LÄMNA systemet: hemligheter är prickar.

    Sista fyra tecknen behålls så kunden känner igen sin nyckel; en
    nyckel i ett API-svar hamnar annars i loggar och skärmdelningar.
    """
    spec = CONNECTORS.get(rec.get("provider"), {"fields": ()})
    hemliga = {f["id"] for f in spec["fields"] if f.get("secret")}
    cfg = {}
    for k, v in (rec.get("config") or {}).items():
        if k in hemliga and v:
            cfg[k] = ("••••" + v[-4:]) if len(v) > 8 else "••••"
        else:
            cfg[k] = v
    ut = {k: v for k, v in rec.items() if k != "config"}
    ut["config"] = cfg
    return ut


def target_url_of(rec: dict) -> str:
    """Kopplingens leveransadress — webhook eller enterprise-endpoint."""
    cfg = rec.get("config") or {}
    url = cfg.get("webhook_url") or cfg.get("endpoint_url") or ""
    if not url:
        raise ConnectionRefused(
            f"{rec.get('provider')!r} carries no delivery URL — it is "
            f"not a system deliveries can land in")
    return url


def headers_for(rec: dict) -> dict:
    """HTTP-huvudena en leverans till kopplingen ska bära.

    Autentiseringsvärdet är en hemlighet: det läses HÄR för att sättas
    på anropet — aldrig för att loggas eller ekas.
    """
    cfg = rec.get("config") or {}
    huvud = {"content-type": "application/json"}
    if cfg.get("auth_value"):
        huvud[cfg.get("auth_header") or "Authorization"] = \
            cfg["auth_value"]
    return huvud


def feedback_target(tenant: str) -> dict | None:
    """Vart kvittona ska: feedback-webhooken om den finns, annars
    första affärssystemet. EN regel, delad av båda API-lagren —
    två egna urval hade varit två sanningar om samma leverans."""
    rader = all_connections(tenant)
    for r in rader:
        if r.get("provider") == "feedback_webhook":
            return r
    for r in rader:
        if r.get("kind") == "enterprise":
            return r
    return None


def catalog() -> dict:
    return {
        "what_en": ("Your own connections: bring your own language-"
                    "model key or team webhook, and Landvex uses YOUR "
                    "account for narration and delivery. Keys are "
                    "stored to be used and never echoed back — every "
                    "read path masks them."),
        "connectors": [{"id": cid, **{k: v for k, v in c.items()
                                      if k != "fields"},
                        "fields": [dict(f) for f in c["fields"]]}
                       for cid, c in CONNECTORS.items()],
        "verification_en": ("'Configured' means the form was filled "
                            "in. 'Verified' is set only when the "
                            "provider's real server answered a probe — "
                            "a correctly shaped key proves nothing "
                            "about whether it works."),
        "cannot_en": ("Landvex never proxies your key to anyone else "
                      "and never uses it for anything but the feature "
                      "you connected it for. What Landvex cannot do: "
                      "see your provider bill, revoke your key, or "
                      "guarantee the provider is up."),
    }


# ── Lagret (samma mönster som inspections/sponsorship) ─────────────────
_STORE = None
_KOPPLINGAR: dict[tuple[str, str], dict] = {}


def set_store(store: object) -> None:
    global _STORE
    _STORE = store


def save_connection(rec: dict) -> str:
    if _STORE is not None and getattr(_STORE, "save_connection", None):
        return _STORE.save_connection(rec)
    _KOPPLINGAR[(rec["tenant"], rec["provider"])] = dict(rec)
    return rec["provider"]


def all_connections(tenant: str | None = None) -> list[dict]:
    if _STORE is not None and getattr(_STORE, "all_connections", None):
        rader = _STORE.all_connections()
    else:
        rader = list(_KOPPLINGAR.values())
    if tenant is not None:
        rader = [r for r in rader if r.get("tenant") == tenant]
    return rader


def delete_connection(provider: str, *, tenant: str) -> bool:
    if _STORE is not None and getattr(_STORE, "delete_connection", None):
        return _STORE.delete_connection(provider, tenant)
    return _KOPPLINGAR.pop((tenant, provider), None) is not None


def get_connection(provider: str, *, tenant: str) -> dict:
    """Kopplingen med hemligheterna intakta — för ANVÄNDNING, aldrig
    för att lämna systemet. Läsvägar utåt går genom masked()."""
    rec = next((r for r in all_connections(tenant)
                if r.get("provider") == provider), None)
    if rec is None:
        raise ConnectionRefused(
            f"no {provider!r} connection for this tenant — create one "
            f"first (POST /v1/connections); the catalog lists what it "
            f"needs")
    return rec


def reset() -> None:
    """Endast för tester."""
    _KOPPLINGAR.clear()
