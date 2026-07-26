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
        {"id": "opportunity_intel", "label_en": "Opportunity Intelligence",
         "beskrivning_en": "Business Navigation: support-program fit, hidden "
                           "opportunities, 'you're missing money', legal "
                           "categories, lifecycle and expansion advice for a "
                           "location + business profile.",
         "endpoints": [{"method": "POST", "path": "/v1/opportunities"}]},
        {"id": "risk_intelligence", "label_en": "Risk Intelligence",
         "beskrivning_en": "Business radar: a Risk Score beside the "
                           "Opportunity Score, ten risk categories, the "
                           "Business Signals framework and a cautious "
                           "counterparty-health model. Computed categories "
                           "score from local signals; the rest are honest "
                           "monitoring categories awaiting live feeds.",
         "endpoints": [{"method": "POST", "path": "/v1/risk-intelligence"}]},
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
        {"id": "kpi", "label_en": "KPI Engine",
         "beskrivning_en": "Societal KPI registry (7 categories) with "
                           "invert-aware status/trend and threshold + "
                           "velocity alerts. Deterministic, no ML.",
         "endpoints": [{"method": "GET", "path": "/v1/kpi"},
                       {"method": "POST", "path": "/v1/kpi/evaluate"}]},
        {"id": "lambda", "label_en": "Lambda Index",
         "beskrivning_en": "Geometric-mean balance index across 8 societal "
                           "axes (~1.0 balanced); penalises extremes so a "
                           "strong axis cannot mask a weak one.",
         "endpoints": [{"method": "POST", "path": "/v1/lambda"}]},
        {"id": "setpoints", "label_en": "Setpoint & Tolerance",
         "beskrivning_en": "Calibrated reference thresholds per indicator "
                           "(Maastricht 60%, Gini 0.30, TFR 2.1 …) with four "
                           "nested zones and sourced derivation.",
         "endpoints": [{"method": "GET", "path": "/v1/setpoints"},
                       {"method": "POST", "path": "/v1/setpoints/assess"}]},
        {"id": "claims", "label_en": "Claims & Citation",
         "beskrivning_en": "Turns a figure into a verifiable, content-hashed, "
                           "versioned claim with 3-owner governance and "
                           "text/APA/BibTeX citations.",
         "endpoints": [{"method": "POST", "path": "/v1/cite"}]},
        {"id": "feeds", "label_en": "Intelligence Feeds",
         "beskrivning_en": "Change detection: turns KPI movements into "
                           "deduplicated why-now events (top changes, "
                           "structural decline, priority alerts, anomalies).",
         "endpoints": [{"method": "GET", "path": "/v1/feeds"},
                       {"method": "POST", "path": "/v1/feeds/events"}]},
        {"id": "worthiness", "label_en": "Significance Selector",
         "beskrivning_en": "Scores which changes are worth surfacing and "
                           "ranks them hero/primary/secondary/mention.",
         "endpoints": [{"method": "POST", "path": "/v1/worthiness"}]},
        {"id": "decision", "label_en": "Decision Graph",
         "beskrivning_en": "Structured decision basis (coverage, gaps, "
                           "assumptions) — never a recommendation. Crisis "
                           "queries are met with support resources.",
         "endpoints": [{"method": "GET", "path": "/v1/decision"},
                       {"method": "POST", "path": "/v1/decision"}]},
        {"id": "strim", "label_en": "STRIM Knowledge Graph",
         "beskrivning_en": "Citable, versioned, neutral entity graph "
                           "(schema.org / JSON-LD) with immutable slugs and "
                           "an editorial neutral-language gate.",
         "endpoints": [{"method": "GET", "path": "/v1/strim"},
                       {"method": "POST", "path": "/v1/strim/entity"}]},
        {"id": "data_sources", "label_en": "Data-source Adapters",
         "beskrivning_en": "Connection status for the Kolada and SVK/ENTSO-E "
                           "adapters — honestly not-connected until their "
                           "URL is set.",
         "endpoints": [{"method": "GET", "path": "/v1/sources"},
                       {"method": "GET", "path": "/v1/kolada"},
                       {"method": "GET", "path": "/v1/svk"}]},
        {"id": "outcomes", "label_en": "Outcome Calibration",
         "beskrivning_en": "Logs establishments and real outcomes, calibrates "
                           "the model (Brier, reliability), and unlocks a "
                           "survival-based expected_roi once data exists.",
         "endpoints": [{"method": "POST", "path": "/v1/outcomes"},
                       {"method": "GET", "path": "/v1/outcomes/calibration"},
                       {"method": "POST", "path": "/v1/outcomes/roi"}]},
        {"id": "correlate", "label_en": "Cross-domain Correlation",
         "beskrivning_en": "Surfaces associations across domains (e.g. diet x "
                           "pharma x living) as hypotheses — never causation: "
                           "spurious flag, confounder control (partial "
                           "correlation), and replication across markets.",
         "endpoints": [{"method": "POST", "path": "/v1/correlate"},
                       {"method": "POST", "path": "/v1/correlate/cross-market"}]},
        {"id": "scenario", "label_en": "Credible Scenarios",
         "beskrivning_en": "Credibility-gated societal scenarios: only speaks "
                           "when there are enough credible sources AND a "
                           "systematic historical tendency; shows the basis, a "
                           "widening band and explicit assumptions. Never a "
                           "bare prediction.",
         "endpoints": [{"method": "POST", "path": "/v1/scenario"}]},
        {"id": "event_study", "label_en": "Event Study",
         "beskrivning_en": "Before/after an intervention and difference-in-"
                           "differences vs controls (e.g. legalisation -> "
                           "accidents). Observational, parallel-trends stated.",
         "endpoints": [{"method": "POST", "path": "/v1/event-study"}]},
        {"id": "benchmark", "label_en": "Peer Benchmark",
         "beskrivning_en": "Places a value in the distribution of comparable "
                           "units (percentile, z-score, outlier band) — is a "
                           "claimed shortage/excess actually unusual, or normal?",
         "endpoints": [{"method": "POST", "path": "/v1/benchmark"}]},
        {"id": "wages", "label_en": "Wage Registry",
         "beskrivning_en": "Standard wage per standard occupation across "
                           "markets. Swedish anchor (wage-statistics level) x "
                           "documented FX — schablon, not PPP-adjusted; real "
                           "local wages arrive via SCB/BLS/Eurostat/ILOSTAT.",
         "endpoints": [{"method": "GET", "path": "/v1/wages"},
                       {"method": "POST", "path": "/v1/wages/lookup"},
                       {"method": "POST", "path": "/v1/wages/compare"},
                       {"method": "POST", "path": "/v1/wages/context"}]},
        {"id": "corrections", "label_en": "Community Corrections",
         "beskrivning_en": "Wikipedia-style sourced corrections from regional "
                           "users; when enough independent, converging, sourced "
                           "corrections arrive the system adapts the value "
                           "(labelled community, reversible, traceable).",
         "endpoints": [{"method": "POST", "path": "/v1/corrections/submit"},
                       {"method": "POST", "path": "/v1/corrections/consensus"},
                       {"method": "POST", "path": "/v1/corrections/adapt"}]},
        {"id": "entrypoints", "label_en": "Entry points (decision journeys)",
         "beskrivning_en": "Role-based doors into the engine — citizen, "
                           "business, investor, municipality, journalist, "
                           "researcher. Each ends in a decision answer "
                           "(answered_by), tools as the evidence layer, event "
                           "feeds as the live overlay.",
         "endpoints": [{"method": "GET", "path": "/v1/entrypoints"}]},
        {"id": "admin", "label_en": "Administrative Register",
         "beskrivning_en": "Complete level-1 units for 18 countries (US "
                           "states, Canadian provinces, Swiss cantons, German "
                           "Länder, Swedish counties, French/Spanish/Italian/"
                           "Danish/Dutch/Norwegian/Finnish/Austrian/Belgian/"
                           "Irish/Portuguese/Polish/Czech regions), a level-2 "
                           "municipal tier (counties/kommuner/communes) that "
                           "loads live from official registers, and a level-3 "
                           "postal tier (ZIP/postcode/PLZ) documented per "
                           "country — a partial seed is never presented as "
                           "complete.",
         "endpoints": [{"method": "GET", "path": "/v1/admin"}]},
        {"id": "flows", "label_en": "Cost/Benefit Flows",
         "beskrivning_en": "Expected value beyond the feelings: certain costs "
                           "against probability-weighted gains — net value, "
                           "benefit/cost ratio, break-even probability and "
                           "sensitivity (where the conclusion is fragile). "
                           "Gated on credible sources; a framing, never advice.",
         "endpoints": [{"method": "POST", "path": "/v1/flows/expected-value"}]},
        {"id": "customer", "label_en": "Customer Journey (KYC → active)",
         "beskrivning_en": "Where a customer stands across KYC, onboarding, "
                           "platform setup and active operation — each stage "
                           "naming its owner. KYC and onboarding are owned "
                           "outside this platform and it says so instead of "
                           "pretending to progress them. KYC is never "
                           "performed or self-attested here: absent a "
                           "provider verdict the answer is not_verified, and "
                           "billing, live layers, partner API and sensitive "
                           "analysis stay gated.",
         "endpoints": [{"method": "GET", "path": "/v1/customer/journey"},
                       {"method": "POST", "path": "/v1/customer/stage"}]},
        {"id": "visitor", "label_en": "Visitor Seam (onboarding intake)",
         "beskrivning_en": "The documented seam a customer onboarding "
                           "delivers into. Accepts a customer record via "
                           "field names or aliases, reports what is missing "
                           "rather than inferring it, and grades how well the "
                           "platform knows this visitor (unknown → partial → "
                           "known → routed) with the single next question "
                           "that lifts it a step.",
         "endpoints": [{"method": "GET", "path": "/v1/visitor/contract"},
                       {"method": "POST", "path": "/v1/visitor"}]},
        {"id": "merit", "label_en": "Merit Engine (measurable performance)",
         "beskrivning_en": "Which places perform measurably well across six "
                           "dimensions of business capability — enterprise "
                           "base, labour engagement, economic breadth, "
                           "investment conversion, attraction and resilience "
                           "— with how (which dimensions they lead) and why "
                           "(which sourced drivers differ). Credit is awarded "
                           "on exactly the standard used to challenge a "
                           "place: same normalisation, same peer percentiles, "
                           "same refusal when coverage is thin, and no "
                           "causal claim.",
         "endpoints": [{"method": "POST", "path": "/v1/merit"}]},
        {"id": "saturation", "label_en": "Market Saturation",
         "beskrivning_en": "How saturated a trade's market is in a place: "
                           "establishments per 10,000 residents, ranked "
                           "against comparable regions, with the band, the "
                           "peer median and how many more or fewer it would "
                           "take to reach it. Every count states whether it "
                           "came from an official business register or is an "
                           "estimate. Density is never presented as "
                           "opportunity.",
         "endpoints": [{"method": "GET", "path": "/v1/registers"},
                       {"method": "POST", "path": "/v1/saturation"}]},
        {"id": "inbox", "label_en": "Event Routing (who it is for)",
         "beskrivning_en": "Turns broadcast feeds into 'your decision may have "
                           "changed'. A visitor registers what they have at "
                           "stake (a place, a trade, an occupation, a decision "
                           "they own, a watch they set); movements are routed "
                           "by that stake, ranked so accountability outranks "
                           "curiosity, and everything held back is listed with "
                           "its reason.",
         "endpoints": [{"method": "GET", "path": "/v1/inbox"},
                       {"method": "POST", "path": "/v1/inbox/subscribe"},
                       {"method": "POST", "path": "/v1/inbox/route"}]},
        {"id": "monitors", "label_en": "Control Monitors (cron)",
         "beskrivning_en": "Register a watch on a metric — threshold breach, "
                           "structural change-point, anomaly or sustained "
                           "decline — run it on a schedule (cron), and escalate "
                           "a triggered finding into an owned decision. "
                           "Control-infrastructure intelligence: find errors "
                           "and deviations, closed against accountability.",
         "endpoints": [{"method": "GET", "path": "/v1/monitors"},
                       {"method": "POST", "path": "/v1/monitors"},
                       {"method": "POST", "path": "/v1/monitors/evaluate"},
                       {"method": "POST", "path": "/v1/monitors/run"},
                       {"method": "POST", "path": "/v1/monitors/escalate"}]},
        {"id": "sensitive", "label_en": "Sensitive-category Guard",
         "beskrivning_en": "Surfaces associations on protected categories "
                           "(origin, victim status, health…) ONLY with "
                           "k-anonymity, mandatory confounder control (raw vs "
                           "controlled), official sources, and ecological-"
                           "fallacy warnings. Truth, never ammunition.",
         "endpoints": [{"method": "POST", "path": "/v1/sensitive-association"}]},
        {"id": "accountability", "label_en": "Accountability Loop",
         "beskrivning_en": "Commits a decision to a responsible owner + an "
                           "expected outcome, resolves it against the actual, "
                           "and keeps a per-owner ledger. Every result carries "
                           "its framing (a result is always an answer).",
         "endpoints": [{"method": "POST", "path": "/v1/decisions/commit"},
                       {"method": "POST", "path": "/v1/decisions/resolve"},
                       {"method": "GET", "path": "/v1/decisions/ledger"}]},
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
