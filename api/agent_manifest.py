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
    return {"name": name, "beskrivning_en": desc,
            "method": method, "path": path,
            "input_schema": {"type": "object", "properties": props,
                             "required": required}}


AGENT_MANIFEST: dict = {
    "platform": "LANDVEX Opportunity Engine",
    "engine_version": ENGINE_VERSION,
    "instruktioner_en": (
        "Every response includes confidence, assumptions and caveats – "
        "relay them in final results, never strip them. Municipality "
        "codes and valid ids come from the catalog tools (markets/"
        "occupations/segments/products/profile-options). Use ask for free "
        "text, the typed tools for chained workflows."),
    "tools": [
        _tool("ask_landvex",
              "Free-text question – routed to the right engine.",
              "POST", "/v1/ask",
              {"question": {"type": "string"}}, ["question"]),
        _tool("analyze_location",
              "Opportunity report for a location and vertical.",
              "POST", "/v1/analyze",
              {"lat": {"type": "number"}, "lon": {"type": "number"},
               "vertical": {"type": "string"},
               "radius_minutes": {"type": "integer"}},
              ["lat", "lon", "vertical"]),
        _tool("scan_market",
              "Profile-driven market sweep → hotspots with decision cards.",
              "POST", "/v1/scan",
              {"profile": {"type": "object"}, "market": {"type": "string"},
               "top_n": {"type": "integer"}, "level": {"type": "string"}},
              ["profile"]),
        _tool("decision_report",
              "Full decision report for one region and vertical: "
              "opportunity analysis, risk, establishment plan, segments, "
              "service demand and all city indices in one response.",
              "POST", "/v1/report",
              {"kommun_kod": {"type": "string"},
               "vertical": {"type": "string"},
               "market": {"type": "string"}},
              ["kommun_kod", "vertical"]),
        _tool("workforce_forecast",
              "Skills forecast per region with intervals and milestones.",
              "POST", "/v1/workforce/forecast",
              {"kommun_kod": {"type": "string"},
               "target_year": {"type": "integer"},
               "occupation_ids": {"type": "array", "items": {"type": "string"}},
               "market": {"type": "string"}},
              ["kommun_kod"]),
        _tool("workforce_simulate",
              "Education simulation: extra places/year → new gap path.",
              "POST", "/v1/workforce/simulate",
              {"kommun_kod": {"type": "string"},
               "occupation_id": {"type": "string"},
               "extra_places_per_year": {"type": "number"},
               "target_year": {"type": "integer"},
               "market": {"type": "string"}},
              ["kommun_kod", "occupation_id", "extra_places_per_year"]),
        _tool("risk_profile",
              "Multi-dimensional risk profile with suggested mitigations.",
              "POST", "/v1/risk",
              {"lat": {"type": "number"}, "lon": {"type": "number"},
               "vertical": {"type": "string"}}, ["lat", "lon", "vertical"]),
        _tool("compare_locations",
              "Compare 2–4 locations for the same vertical.",
              "POST", "/v1/compare",
              {"vertical": {"type": "string"},
               "locations": {"type": "array", "items": _LOC,
                             "minItems": 2, "maxItems": 4}},
              ["vertical", "locations"]),
        _tool("gap_analysis",
              "Imbalances: high demand × low supply × development.",
              "POST", "/v1/gaps",
              {"vertical": {"type": "string"}, "market": {"type": "string"},
               "top_n": {"type": "integer"}}, ["vertical"]),
        _tool("establishment_plan",
              "Establishment plan: premises, investment, staff, economy, "
              "risk.",
              "POST", "/v1/plan",
              {"kommun_kod": {"type": "string"}, "vertical": {"type": "string"},
               "market": {"type": "string"}, "team_size": {"type": "string"},
               "budget_band": {"type": "string"}},
              ["kommun_kod", "vertical"]),
        _tool("segment_analysis",
              "Segment profile for a region (pet owners, families etc.).",
              "POST", "/v1/segments/analyze",
              {"kommun_kod": {"type": "string"}, "market": {"type": "string"}},
              ["kommun_kod"]),
        _tool("city_indices",
              "All city indices (infrastructure risk, safety, climate, "
              "growth, contradiction) for a region – traceable.",
              "POST", "/v1/indices/assess",
              {"kommun_kod": {"type": "string"}, "market": {"type": "string"}},
              ["kommun_kod"]),
        _tool("service_analysis",
              "Service demand from the installed base for a region.",
              "POST", "/v1/service/analyze",
              {"kommun_kod": {"type": "string"}, "market": {"type": "string"},
               "target_year": {"type": "integer"}}, ["kommun_kod"]),
    ],
    "kataloger": [{"method": "GET", "path": p} for p in
                  ("/v1/catalog", "/v1/markets", "/v1/workforce/occupations",
                   "/v1/segments", "/v1/products", "/v1/profile-options")],
}
