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
    "platform": "LANDVEX Opportunity Engine",
    "engine_version": ENGINE_VERSION,
    "api_version": "v1",
    "beskrivning_sv": "Beslutsmotorer för framtida arbetskrafts- och "
                      "affärsbehov. API-first: webbportalen är en klient "
                      "av flera. Alla svar bär konfidens, antaganden och "
                      "datatäckning.",
    "auth": {"typ": "API-nyckel (header X-API-Key), roller "
                    "admin/analyst/partner",
             "notis_sv": "OIDC ersätter nyckellagret i produktionsfasen. "
                         "Öppet läge utan LANDVEX_API_KEYS (utveckling)."},
    "engines": [
        {"id": "ask", "label_sv": "Fråga Landvex",
         "beskrivning_sv": "Naturligt språk in, motordata ut.",
         "endpoints": [{"method": "POST", "path": "/v1/ask"}]},
        {"id": "opportunity", "label_sv": "Opportunity Engine",
         "beskrivning_sv": "Platsanalys och profilstyrt marknadssvep "
                           "med beslutskort.",
         "endpoints": [{"method": "POST", "path": "/v1/analyze"},
                       {"method": "POST", "path": "/v1/scan"},
                       {"method": "GET", "path": "/v1/profile-options"},
                       {"method": "POST", "path": "/v1/profiles"},
                       {"method": "GET", "path": "/v1/profiles"}]},
        {"id": "workforce", "label_sv": "Workforce Intelligence",
         "beskrivning_sv": "Kompetensprognoser 1–20 år, simulering, "
                           "nationella och globala bristkartor.",
         "endpoints": [{"method": "GET", "path": "/v1/workforce/occupations"},
                       {"method": "POST", "path": "/v1/workforce/forecast"},
                       {"method": "POST", "path": "/v1/workforce/simulate"},
                       {"method": "GET", "path": "/v1/workforce/map"},
                       {"method": "GET", "path": "/v1/workforce/global-map"}]},
        {"id": "risk", "label_sv": "Risk Engine",
         "beskrivning_sv": "Flerdimensionell riskprofil med åtgärdsförslag.",
         "endpoints": [{"method": "POST", "path": "/v1/risk"}]},
        {"id": "compare", "label_sv": "Jämförelse",
         "beskrivning_sv": "2–4 platser mot varandra med faktormatris.",
         "endpoints": [{"method": "POST", "path": "/v1/compare"}]},
        {"id": "gaps", "label_sv": "Gap Analysis",
         "beskrivning_sv": "Obalanser: hög efterfrågan × lågt utbud × "
                           "positiv utveckling.",
         "endpoints": [{"method": "POST", "path": "/v1/gaps"}]},
        {"id": "plan", "label_sv": "Etableringsplan",
         "beskrivning_sv": "Från analys till beslutsunderlag: lokal, "
                           "investering, personal, ekonomi, risker.",
         "endpoints": [{"method": "POST", "path": "/v1/plan"}]},
        {"id": "segments", "label_sv": "Målgruppsmotorn",
         "beskrivning_sv": "Segmentanalys (djurägare, barnfamiljer m.fl.) "
                           "per region och som karta.",
         "endpoints": [{"method": "GET", "path": "/v1/segments"},
                       {"method": "POST", "path": "/v1/segments/analyze"},
                       {"method": "GET", "path": "/v1/segments/map"}]},
        {"id": "installed_base", "label_sv": "Installed Base Engine",
         "beskrivning_sv": "Installerad bas → framtida servicebehov, "
                           "teknikerbehov och mismatch-möjligheter.",
         "endpoints": [{"method": "GET", "path": "/v1/products"},
                       {"method": "POST", "path": "/v1/service/analyze"},
                       {"method": "GET", "path": "/v1/service/map"}]},
        {"id": "indices", "label_sv": "Intelligence Map-index",
         "beskrivning_sv": "Stadsindex (infrastrukturrisk, kommersiell "
                           "aktivitet, trygghet, klimatrisk, urban tillväxt) "
                           "+ kontradiktionsindexet – sourced & traceable.",
         "endpoints": [{"method": "GET", "path": "/v1/indices"},
                       {"method": "GET", "path": "/v1/indices/map"},
                       {"method": "POST", "path": "/v1/indices/assess"}]},
        {"id": "platform", "label_sv": "Plattform",
         "beskrivning_sv": "Marknader, rapporter, hälsa och metrics.",
         "endpoints": [{"method": "GET", "path": "/v1/markets"},
                       {"method": "GET", "path": "/v1/reports"},
                       {"method": "GET", "path": "/health"},
                       {"method": "GET", "path": "/metrics"}]},
    ],
}
