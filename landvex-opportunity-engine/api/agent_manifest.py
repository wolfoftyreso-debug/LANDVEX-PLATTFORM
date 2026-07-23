"""Agent-manifest – motorerna som verktyg för AI-agenter.

GET /v1/agent-manifest returnerar plattformens kapabiliteter i
verktygsform (namn, beskrivning, endpoint, JSON Schema för indata) så
att en agentrutine – i AWS-fasen eller via extern API-yta – kan
upptäcka och anropa motorerna utan handskriven integration. Samma
kontrakt som /v1/catalog men på verktygsnivå.

Principer för agentkonsumtion (ingår i manifestet):
- Alla svar bär konfidens/antaganden/caveats – agenten ska återge dem,
  aldrig strippa dem.
- /v1/ask är den breda ingången (naturligt språk); de typade verktygen
  ger deterministiska kontrakt för kedjade arbetsflöden.
"""
from __future__ import annotations

from engine.version import ENGINE_VERSION

_LOC = {"type": "object",
        "properties": {"lat": {"type": "number"}, "lon": {"type": "number"},
                       "address": {"type": "string"}},
        "required": ["lat", "lon"]}


def _tool(name, desc, method, path, props, required):
    return {"name": name, "beskrivning_sv": desc,
            "method": method, "path": path,
            "input_schema": {"type": "object", "properties": props,
                             "required": required}}


AGENT_MANIFEST: dict = {
    "platform": "LANDVEX Opportunity Engine",
    "engine_version": ENGINE_VERSION,
    "instruktioner_sv": (
        "Varje svar innehåller konfidens, antaganden och caveats – återge "
        "dem i slutresultat, strippa dem aldrig. Kommunkoder och giltiga "
        "id:n hämtas från katalogverktygen (markets/occupations/segments/"
        "products/profile-options). Använd ask för fritext, de typade "
        "verktygen för kedjade flöden."),
    "tools": [
        _tool("ask_landvex",
              "Fritextfråga på svenska – routas till rätt motor.",
              "POST", "/v1/ask",
              {"question": {"type": "string"}}, ["question"]),
        _tool("analyze_location",
              "Opportunity-rapport för en plats och bransch.",
              "POST", "/v1/analyze",
              {"lat": {"type": "number"}, "lon": {"type": "number"},
               "vertical": {"type": "string"},
               "radius_minutes": {"type": "integer"}},
              ["lat", "lon", "vertical"]),
        _tool("scan_market",
              "Profilstyrt marknadssvep → hotspots med beslutskort.",
              "POST", "/v1/scan",
              {"profile": {"type": "object"}, "market": {"type": "string"},
               "top_n": {"type": "integer"}, "level": {"type": "string"}},
              ["profile"]),
        _tool("workforce_forecast",
              "Kompetensprognos per region med intervall och milstolpar.",
              "POST", "/v1/workforce/forecast",
              {"kommun_kod": {"type": "string"},
               "target_year": {"type": "integer"},
               "occupation_ids": {"type": "array", "items": {"type": "string"}},
               "market": {"type": "string"}},
              ["kommun_kod"]),
        _tool("workforce_simulate",
              "Utbildningssimulering: extra platser/år → ny bristbana.",
              "POST", "/v1/workforce/simulate",
              {"kommun_kod": {"type": "string"},
               "occupation_id": {"type": "string"},
               "extra_places_per_year": {"type": "number"},
               "target_year": {"type": "integer"},
               "market": {"type": "string"}},
              ["kommun_kod", "occupation_id", "extra_places_per_year"]),
        _tool("risk_profile",
              "Flerdimensionell riskprofil med åtgärdsförslag.",
              "POST", "/v1/risk",
              {"lat": {"type": "number"}, "lon": {"type": "number"},
               "vertical": {"type": "string"}}, ["lat", "lon", "vertical"]),
        _tool("compare_locations",
              "Jämför 2–4 platser för samma bransch.",
              "POST", "/v1/compare",
              {"vertical": {"type": "string"},
               "locations": {"type": "array", "items": _LOC,
                             "minItems": 2, "maxItems": 4}},
              ["vertical", "locations"]),
        _tool("gap_analysis",
              "Obalanser: hög efterfrågan × lågt utbud × utveckling.",
              "POST", "/v1/gaps",
              {"vertical": {"type": "string"}, "market": {"type": "string"},
               "top_n": {"type": "integer"}}, ["vertical"]),
        _tool("establishment_plan",
              "Etableringsplan: lokal, investering, personal, ekonomi, risk.",
              "POST", "/v1/plan",
              {"kommun_kod": {"type": "string"}, "vertical": {"type": "string"},
               "market": {"type": "string"}, "team_size": {"type": "string"},
               "budget_band": {"type": "string"}},
              ["kommun_kod", "vertical"]),
        _tool("segment_analysis",
              "Målgruppsprofil för en region (djurägare, barnfamiljer m.fl.).",
              "POST", "/v1/segments/analyze",
              {"kommun_kod": {"type": "string"}, "market": {"type": "string"}},
              ["kommun_kod"]),
        _tool("city_indices",
              "Alla stadsindex (infrastrukturrisk, trygghet, klimat, "
              "tillväxt, kontradiktion) för en region – spårbara.",
              "POST", "/v1/indices/assess",
              {"kommun_kod": {"type": "string"}, "market": {"type": "string"}},
              ["kommun_kod"]),
        _tool("service_analysis",
              "Servicebehov från installerad bas för en region.",
              "POST", "/v1/service/analyze",
              {"kommun_kod": {"type": "string"}, "market": {"type": "string"},
               "target_year": {"type": "integer"}}, ["kommun_kod"]),
    ],
    "kataloger": [{"method": "GET", "path": p} for p in
                  ("/v1/catalog", "/v1/markets", "/v1/workforce/occupations",
                   "/v1/segments", "/v1/products", "/v1/profile-options")],
}
