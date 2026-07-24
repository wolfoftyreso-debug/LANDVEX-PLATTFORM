"""API-katalogen – plattformen beskriver sig själv.

Byggd för partner-/gateway-integration (t.ex. en extern API-yta som
aamos.ai): en klient ska kunna fråga GET /v1/catalog och maskinellt
upptäcka samtliga motorer, endpoints och deras syfte – utan att läsa
dokumentation. FastAPI-lagret exponerar dessutom OpenAPI-schemat på
/openapi.json och interaktiv dokumentation på /docs.

Katalogen är data och uppdateras ihop med API:t; testerna låser att
varje listad endpoint faktiskt existerar i båda API-lagren.
"""
from __future__ import annotations

from engine.version import ENGINE_VERSION

API_CATALOG: dict = {
    "platform": "Landvex Opportunity Engine",
    "plattformsfamilj": "RIOS – Reality Intelligence Operating System",
    "tagline_en": "Decision Intelligence for the Physical World",
    "engine_version": ENGINE_VERSION,
    "api_version": "v1",
    "beskrivning_en": "Decision engines for future workforce and "
                      "business needs. API-first: the web portal is one "
                      "client of many. Every response carries confidence, "
                      "assumptions and data coverage.",
    "auth": {"typ": "API key (header X-API-Key), roles "
                    "admin/analyst/partner",
             "notis_en": "OIDC replaces the key store in the production "
                         "phase. Open mode without LANDVEX_API_KEYS "
                         "(development)."},
    "engines": [
        {"id": "ask", "label_en": "Ask Landvex",
         "beskrivning_en": "Natural language in, engine data out.",
         "endpoints": [{"method": "POST", "path": "/v1/ask"}]},
        {"id": "opportunity", "label_en": "Opportunity Engine",
         "beskrivning_en": "Location analysis and profile-driven market "
                           "sweeps with decision cards.",
         "endpoints": [{"method": "POST", "path": "/v1/analyze"},
                       {"method": "POST", "path": "/v1/scan"},
                       {"method": "POST", "path": "/v1/report"},
                       {"method": "GET", "path": "/v1/profile-options"},
                       {"method": "POST", "path": "/v1/profiles"},
                       {"method": "GET", "path": "/v1/profiles"}]},
        {"id": "workforce", "label_en": "Workforce Intelligence",
         "beskrivning_en": "Skills forecasts 1–20 years, simulation, "
                           "national and global shortage maps.",
         "endpoints": [{"method": "GET", "path": "/v1/workforce/occupations"},
                       {"method": "POST", "path": "/v1/workforce/forecast"},
                       {"method": "POST", "path": "/v1/workforce/simulate"},
                       {"method": "GET", "path": "/v1/workforce/map"},
                       {"method": "GET", "path": "/v1/workforce/global-map"}]},
        {"id": "risk", "label_en": "Risk Engine",
         "beskrivning_en": "Multi-dimensional risk profile with suggested "
                           "mitigations.",
         "endpoints": [{"method": "POST", "path": "/v1/risk"}]},
        {"id": "compare", "label_en": "Comparison",
         "beskrivning_en": "2–4 locations head-to-head with a factor "
                           "matrix.",
         "endpoints": [{"method": "POST", "path": "/v1/compare"}]},
        {"id": "gaps", "label_en": "Gap Analysis",
         "beskrivning_en": "Imbalances: high demand × low supply × "
                           "positive development.",
         "endpoints": [{"method": "POST", "path": "/v1/gaps"}]},
        {"id": "plan", "label_en": "Establishment Plan",
         "beskrivning_en": "From analysis to decision basis: premises, "
                           "investment, staffing, economics, risks.",
         "endpoints": [{"method": "POST", "path": "/v1/plan"}]},
        {"id": "segments", "label_en": "Segment Engine",
         "beskrivning_en": "Segment analysis (pet owners, families with "
                           "children, etc.) per region and as a map.",
         "endpoints": [{"method": "GET", "path": "/v1/segments"},
                       {"method": "POST", "path": "/v1/segments/analyze"},
                       {"method": "GET", "path": "/v1/segments/map"}]},
        {"id": "installed_base", "label_en": "Installed Base Engine",
         "beskrivning_en": "Installed base → future service needs, "
                           "technician demand and mismatch opportunities.",
         "endpoints": [{"method": "GET", "path": "/v1/products"},
                       {"method": "POST", "path": "/v1/service/analyze"},
                       {"method": "GET", "path": "/v1/service/map"}]},
        {"id": "indices", "label_en": "Intelligence Map Indices",
         "beskrivning_en": "City indices (infrastructure risk, commercial "
                           "activity, safety, climate risk, urban growth) "
                           "+ the contradiction index – sourced & traceable.",
         "endpoints": [{"method": "GET", "path": "/v1/indices"},
                       {"method": "GET", "path": "/v1/indices/map"},
                       {"method": "POST", "path": "/v1/indices/assess"}]},
        {"id": "platform", "label_en": "Platform",
         "beskrivning_en": "Markets, reports, health and metrics.",
         "endpoints": [{"method": "GET", "path": "/v1/markets"},
                       {"method": "GET", "path": "/v1/reports"},
                       {"method": "GET", "path": "/health"},
                       {"method": "GET", "path": "/metrics"}]},
        {"id": "aamos_integration", "label_en": "AAMOS Integration",
         "beskrivning_en": "Live integration with the AAMOS Capability "
                           "Platform (12+ engines). Reports not-connected "
                           "honestly until AAMOS_CORE_URL is set.",
         "endpoints": [
             {"method": "GET", "path": "/v1/platform/status"},
             {"method": "GET", "path": "/v1/watch"},
             {"method": "GET", "path": "/v1/agents"},
             {"method": "POST", "path": "/v1/agents/chat"},
             {"method": "POST", "path": "/v1/cognition/brief"}]},
    ],
}


def openapi_spec() -> dict:
    """Minimal OpenAPI 3.0-dokument härlett ur API_CATALOG. Ger den
    beroendefria dev-servern samma /openapi.json som FastAPI-lagret så
    att de två servrarna är utbytbara (låst av tests/test_contract)."""
    paths: dict = {}
    for eng in API_CATALOG["engines"]:
        for ep in eng["endpoints"]:
            verb = ep["method"].lower()
            paths.setdefault(ep["path"], {})[verb] = {
                "summary": eng.get("beskrivning_en", eng["label_en"]),
                "tags": [eng["id"]],
                "responses": {"200": {"description": "OK"}},
            }
    return {
        "openapi": "3.0.3",
        "info": {"title": API_CATALOG["platform"],
                 "version": API_CATALOG["engine_version"],
                 "description": API_CATALOG.get("tagline_en", "")},
        "paths": paths,
    }
