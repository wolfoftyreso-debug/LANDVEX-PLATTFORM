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
    "tagline_en": "What the data supports — and where it runs out",
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
        {"id": "opportunity", "label_en": "Where to establish",
         "beskrivning_en": "Location analysis and profile-driven market "
                           "sweeps with decision cards.",
         "endpoints": [{"method": "POST", "path": "/v1/analyze"},
                       {"method": "POST", "path": "/v1/scan"},
                       {"method": "POST", "path": "/v1/report"},
                       {"method": "GET", "path": "/v1/profile-options"},
                       {"method": "POST", "path": "/v1/profiles"},
                       {"method": "GET", "path": "/v1/profiles"}]},
        {"id": "workforce", "label_en": "What skills will be needed",
         "beskrivning_en": "Skills forecasts 1–20 years, simulation, "
                           "national and global shortage maps.",
         "endpoints": [{"method": "GET", "path": "/v1/workforce/occupations"},
                       {"method": "POST", "path": "/v1/workforce/forecast"},
                       {"method": "POST", "path": "/v1/workforce/simulate"},
                       {"method": "GET", "path": "/v1/workforce/map"},
                       {"method": "GET", "path": "/v1/workforce/global-map"}]},
        {"id": "risk", "label_en": "What could go wrong",
         "beskrivning_en": "Multi-dimensional risk profile with suggested "
                           "mitigations.",
         "endpoints": [{"method": "POST", "path": "/v1/risk"}]},
        {"id": "compare", "label_en": "Compare places side by side",
         "beskrivning_en": "2–4 locations head-to-head with a factor "
                           "matrix.",
         "endpoints": [{"method": "POST", "path": "/v1/compare"}]},
        {"id": "opportunity_intel", "label_en": "Money and support you are missing",
         "beskrivning_en": "Business Navigation: support-program fit, hidden "
                           "opportunities, 'you're missing money', legal "
                           "categories, lifecycle and expansion advice for a "
                           "location + business profile.",
         "endpoints": [{"method": "POST", "path": "/v1/opportunities"}]},
        {"id": "risk_intelligence", "label_en": "Where the risk is concentrated",
         "beskrivning_en": "Business radar: a Risk Score beside the "
                           "Opportunity Score, ten risk categories, the "
                           "Business Signals framework and a cautious "
                           "counterparty-health model. Computed categories "
                           "score from local signals; the rest are honest "
                           "monitoring categories awaiting live feeds.",
         "endpoints": [{"method": "POST", "path": "/v1/risk-intelligence"}]},
        {"id": "gaps", "label_en": "What this place is short of",
         "beskrivning_en": "Imbalances: high demand × low supply × "
                           "positive development.",
         "endpoints": [{"method": "POST", "path": "/v1/gaps"}]},
        {"id": "plan", "label_en": "How to open here",
         "beskrivning_en": "From analysis to decision basis: premises, "
                           "investment, staffing, economics, risks.",
         "endpoints": [{"method": "POST", "path": "/v1/plan"}]},
        {"id": "segments", "label_en": "Who lives here",
         "beskrivning_en": "Segment analysis (pet owners, families with "
                           "children, etc.) per region and as a map.",
         "endpoints": [{"method": "GET", "path": "/v1/segments"},
                       {"method": "POST", "path": "/v1/segments/analyze"},
                       {"method": "GET", "path": "/v1/segments/map"}]},
        {"id": "installed_base", "label_en": "How much service this place needs",
         "beskrivning_en": "Installed base → future service needs, "
                           "technician demand and mismatch opportunities.",
         "endpoints": [{"method": "GET", "path": "/v1/products"},
                       {"method": "POST", "path": "/v1/service/analyze"},
                       {"method": "GET", "path": "/v1/service/map"}]},
        {"id": "indices", "label_en": "What a place is actually like",
         "beskrivning_en": "City indices (infrastructure risk, commercial "
                           "activity, safety, climate risk, urban growth) "
                           "+ the contradiction index – sourced & traceable.",
         "endpoints": [{"method": "GET", "path": "/v1/indices"},
                       {"method": "GET", "path": "/v1/indices/map"},
                       {"method": "POST", "path": "/v1/indices/assess"}]},
        {"id": "kpi", "label_en": "Societal measures, and where they are heading",
         "beskrivning_en": "Societal KPI registry (7 categories) with "
                           "invert-aware status/trend and threshold + "
                           "velocity alerts. Deterministic, no ML.",
         "endpoints": [{"method": "GET", "path": "/v1/kpi"},
                       {"method": "POST", "path": "/v1/kpi/evaluate"}]},
        {"id": "lambda", "label_en": "Balance across the board",
         "beskrivning_en": "Geometric-mean balance index across 8 societal "
                           "axes (~1.0 balanced); penalises extremes so a "
                           "strong axis cannot mask a weak one.",
         "endpoints": [{"method": "POST", "path": "/v1/lambda"}]},
        {"id": "setpoints", "label_en": "Reference levels: what counts as normal",
         "beskrivning_en": "Calibrated reference thresholds per indicator "
                           "(Maastricht 60%, Gini 0.30, TFR 2.1 …) with four "
                           "nested zones and sourced derivation.",
         "endpoints": [{"method": "GET", "path": "/v1/setpoints"},
                       {"method": "POST", "path": "/v1/setpoints/assess"}]},
        {"id": "claims", "label_en": "Where a figure came from",
         "beskrivning_en": "Turns a figure into a verifiable, content-hashed, "
                           "versioned claim with 3-owner governance and "
                           "text/APA/BibTeX citations.",
         "endpoints": [{"method": "POST", "path": "/v1/cite"}]},
        {"id": "feeds", "label_en": "What changed, and why it matters now",
         "beskrivning_en": "Change detection: turns KPI movements into "
                           "deduplicated why-now events (top changes, "
                           "structural decline, priority alerts, anomalies).",
         "endpoints": [{"method": "GET", "path": "/v1/feeds"},
                       {"method": "POST", "path": "/v1/feeds/events"}]},
        {"id": "worthiness", "label_en": "Is this worth reacting to?",
         "beskrivning_en": "Scores which changes are worth surfacing and "
                           "ranks them hero/primary/secondary/mention.",
         "endpoints": [{"method": "POST", "path": "/v1/worthiness"}]},
        {"id": "decision", "label_en": "What a decision needs before it is made",
         "beskrivning_en": "Structured decision basis (coverage, gaps, "
                           "assumptions) — never a recommendation. Crisis "
                           "queries are met with support resources.",
         "endpoints": [{"method": "GET", "path": "/v1/decision"},
                       {"method": "POST", "path": "/v1/decision"}]},
        {"id": "strim", "label_en": "Citable facts, and how they connect",
         "beskrivning_en": "Citable, versioned, neutral entity graph "
                           "(schema.org / JSON-LD) with immutable slugs and "
                           "an editorial neutral-language gate.",
         "endpoints": [{"method": "GET", "path": "/v1/strim"},
                       {"method": "POST", "path": "/v1/strim/entity"}]},
        {"id": "data_sources", "label_en": "Which sources are connected",
         "beskrivning_en": "Connection status for the Kolada and SVK/ENTSO-E "
                           "adapters — honestly not-connected until their "
                           "URL is set.",
         "endpoints": [{"method": "GET", "path": "/v1/sources"},
                       {"method": "GET", "path": "/v1/kolada"},
                       {"method": "GET", "path": "/v1/svk"}]},
        {"id": "outcomes", "label_en": "Did the forecast hold?",
         "beskrivning_en": "Logs establishments and real outcomes, calibrates "
                           "the model (Brier, reliability), and unlocks a "
                           "survival-based expected_roi once data exists.",
         "endpoints": [{"method": "POST", "path": "/v1/outcomes"},
                       {"method": "GET", "path": "/v1/outcomes/calibration"},
                       {"method": "POST", "path": "/v1/outcomes/roi"}]},
        {"id": "correlate", "label_en": "What moves together",
         "beskrivning_en": "Surfaces associations across domains (e.g. diet x "
                           "pharma x living) as hypotheses — never causation: "
                           "spurious flag, confounder control (partial "
                           "correlation), and replication across markets.",
         "endpoints": [{"method": "POST", "path": "/v1/correlate"},
                       {"method": "POST", "path": "/v1/correlate/cross-market"}]},
        {"id": "scenario", "label_en": "What could happen next",
         "beskrivning_en": "Credibility-gated societal scenarios: only speaks "
                           "when there are enough credible sources AND a "
                           "systematic historical tendency; shows the basis, a "
                           "widening band and explicit assumptions. Never a "
                           "bare prediction.",
         "endpoints": [{"method": "POST", "path": "/v1/scenario"}]},
        {"id": "event_study", "label_en": "Did that change anything?",
         "beskrivning_en": "Before/after an intervention and difference-in-"
                           "differences vs controls (e.g. legalisation -> "
                           "accidents). Observational, parallel-trends stated.",
         "endpoints": [{"method": "POST", "path": "/v1/event-study"}]},
        {"id": "benchmark", "label_en": "How this compares to similar places",
         "beskrivning_en": "Places a value in the distribution of comparable "
                           "units (percentile, z-score, outlier band) — is a "
                           "claimed shortage/excess actually unusual, or normal?",
         "endpoints": [{"method": "POST", "path": "/v1/benchmark"}]},
        {"id": "wages", "label_en": "What the work pays",
         "beskrivning_en": "Standard wage per standard occupation across "
                           "markets. Swedish anchor (wage-statistics level) x "
                           "documented FX — schablon, not PPP-adjusted; real "
                           "local wages arrive via SCB/BLS/Eurostat/ILOSTAT.",
         "endpoints": [{"method": "GET", "path": "/v1/wages"},
                       {"method": "POST", "path": "/v1/wages/lookup"},
                       {"method": "POST", "path": "/v1/wages/compare"},
                       {"method": "POST", "path": "/v1/wages/context"}]},
        {"id": "corrections", "label_en": "Correct something that is wrong",
         "beskrivning_en": "Wikipedia-style sourced corrections from regional "
                           "users; when enough independent, converging, sourced "
                           "corrections arrive the system adapts the value "
                           "(labelled community, reversible, traceable).",
         "endpoints": [{"method": "POST", "path": "/v1/corrections/submit"},
                       {"method": "POST", "path": "/v1/corrections/consensus"},
                       {"method": "POST", "path": "/v1/corrections/adapt"}]},
        {"id": "entrypoints", "label_en": "Where to start",
         "beskrivning_en": "Role-based doors into the engine — citizen, "
                           "business, investor, municipality, journalist, "
                           "researcher. Each ends in a decision answer "
                           "(answered_by), tools as the evidence layer, event "
                           "feeds as the live overlay.",
         "endpoints": [{"method": "GET", "path": "/v1/entrypoints"}]},
        {"id": "admin", "label_en": "Who governs this place",
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
        {"id": "flows", "label_en": "Is it worth the cost?",
         "beskrivning_en": "Expected value beyond the feelings: certain costs "
                           "against probability-weighted gains — net value, "
                           "benefit/cost ratio, break-even probability and "
                           "sensitivity (where the conclusion is fragile). "
                           "Gated on credible sources; a framing, never advice.",
         "endpoints": [{"method": "POST", "path": "/v1/flows/expected-value"}]},
        {"id": "customer", "label_en": "Getting set up",
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
        {"id": "visitor", "label_en": "Onboarding intake",
         "beskrivning_en": "The documented seam a customer onboarding "
                           "delivers into. Accepts a customer record via "
                           "field names or aliases, reports what is missing "
                           "rather than inferring it, and grades how well the "
                           "platform knows this visitor (unknown → partial → "
                           "known → routed) with the single next question "
                           "that lifts it a step.",
         "endpoints": [{"method": "GET", "path": "/v1/visitor/contract"},
                       {"method": "POST", "path": "/v1/visitor"}]},
        {"id": "livability", "label_en": "Where to build a life",
         "beskrivning_en": "Where a specific household can build a good "
                           "life: job demand for the occupation, pay after "
                           "tax converted to one currency, childcare, "
                           "schools, safety, housing, cost of living, "
                           "healthcare, support services, communications and "
                           "social fabric — weighted by household type, "
                           "including a single parent with a child needing "
                           "additional support. For regulated professions "
                           "the right to work and qualification recognition "
                           "are reported BEFORE any ranking, because they "
                           "decide first. Best and worst are both shown.",
         "endpoints": [{"method": "GET", "path": "/v1/households"},
                       {"method": "POST", "path": "/v1/livability"}]},
        {"id": "merit", "label_en": "Which places actually perform",
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
        {"id": "brief", "label_en": "Daily Brief",
         "beskrivning_en": "What the platform found without being asked. "
                           "Each detection kind declares what it observes AND "
                           "what that observation does not establish — a "
                           "changed surface with no matching permit is a "
                           "discrepancy to check, never a finding of "
                           "illegality. Confidence is a band with its "
                           "components shown rather than a fabricated "
                           "percentage, actions are options stating what each "
                           "would resolve rather than instructions, and a "
                           "quiet day is reported as a quiet day. Sorted by "
                           "decision value, never by recency.",
         "endpoints": [{"method": "GET", "path": "/v1/brief"},
                       {"method": "POST", "path": "/v1/brief"},
                       {"method": "POST", "path": "/v1/brief/report"}]},
        {"id": "corroboration", "label_en": "Does anything else say the same?",
         "beskrivning_en": "More sensors is not more robust. Ten points on "
                           "the same road, from the same authority, through "
                           "the same collection chain, fail together when "
                           "the chain does — and ten agreeing numbers from a "
                           "broken system look exactly like ten agreeing "
                           "numbers from a working one. This scores how "
                           "well a claim is supported: how many INDEPENDENT "
                           "networks say it, whether they measure different "
                           "physical quantities, and whether they agree. "
                           "Disagreement is reported as its own outcome, "
                           "not as weak support: two networks pointing "
                           "opposite ways is a worse basis than one, "
                           "because at least one is wrong and which is not "
                           "knowable from here.",
         "endpoints": [{"method": "GET", "path": "/v1/corroboration"},
                       {"method": "POST", "path": "/v1/corroboration"}]},
        {"id": "sensors", "label_en": "What can actually be measured",
         "beskrivning_en": "The detection layer recognises nine kinds of "
                           "physical change — a built surface that differs, "
                           "a flow that departs from its own range, an "
                           "object gone. Almost every connected source is "
                           "statistics that updates quarterly. This names "
                           "which sensor class could feed each detection, "
                           "how often it says something new, and — the part "
                           "that matters — what it can NEVER establish "
                           "however dense it is. A counter showing forty "
                           "percent less flow does not know whether a road "
                           "closed, an employer moved, or the loop broke.",
         "endpoints": [{"method": "GET", "path": "/v1/sensors"}]},
        {"id": "surface", "label_en": "What Landvex offers",
         "beskrivning_en": "What a person is offered, as opposed to what "
                           "was built. Forty-five engines answer four "
                           "questions a human actually asks: is that true, "
                           "is there room for me, what changed, and who "
                           "carries the decision. Each promise names what "
                           "it REFUSES as well as what it settles. The full "
                           "catalogue is unchanged and still served at "
                           "/v1/catalog for machines — a test asserts every "
                           "engine belongs to exactly one promise, so "
                           "nothing was left homeless or counted twice to "
                           "make the surface look wider.",
         "endpoints": [{"method": "GET", "path": "/v1/surface"}]},
        {"id": "offering", "label_en": "Plans, and what each lets you decide",
         "beskrivning_en": "What each tier lets you DECIDE, not how much data "
                           "it lets you download. Every offer names the "
                           "question it settles, who asks it and the endpoint "
                           "that answers. Anything not written yet is listed "
                           "under not_built_yet rather than omitted or "
                           "implied: a test asserts that every offer marked "
                           "'built' points at an endpoint present in this "
                           "catalogue, so a plan cannot be sold on a feature "
                           "that does not exist.",
         "endpoints": [{"method": "GET", "path": "/v1/offering"}]},
        {"id": "provenance", "label_en": "Where our own numbers come from",
         "beskrivning_en": "Where the platform's OWN numbers come from. Every "
                           "tunable constant declares its origin: sourced to a "
                           "named authority, an established convention, "
                           "calibrated from outcome data here, or simply "
                           "assumed. The thresholds that decide whether the "
                           "system may speak at all are held to the same "
                           "standard as the data they let through.",
         "endpoints": [{"method": "GET", "path": "/v1/provenance"}]},
        {"id": "saturation", "label_en": "Is the market full?",
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
        {"id": "inbox", "label_en": "What matters to you",
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
        {"id": "monitors", "label_en": "Watch something and be told",
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
        {"id": "mrai", "label_en": "Does the reporting line up with the record",
         "beskrivning_en": "Media Reality Alignment Index per market, 0-100, "
                           "composed from source diversity, independent "
                           "verification (owners, not titles), public-data "
                           "alignment and event coverage. Every component "
                           "opens: what it rests on and what it cannot "
                           "settle. A market below the reference-coverage "
                           "floor gets NO value rather than a low one, "
                           "because a low score there would measure our own "
                           "blindness and be read as that country's press.",
         "endpoints": [{"method": "GET", "path": "/v1/mrai"},
                       {"method": "GET", "path": "/v1/mrai/compare"}]},
        {"id": "selfaudit", "label_en": "The platform audits itself",
         "beskrivning_en": "Runs the 2026 revision's measurements as a "
                           "standing surface: ungated endpoints, tenant "
                           "contract, fault doctrine, sqlite/postgres "
                           "parity, layer boundaries, the zero-dependency "
                           "promise, honesty fields, test presence. Every "
                           "check carries what it proves and what it "
                           "cannot — a static scan shows structure, never "
                           "behaviour.",
         "endpoints": [{"method": "GET", "path": "/v1/integrity/audit"}]},
        {"id": "analysis", "label_en": "Find what disagrees",
         "beskrivning_en": "Sweeps a market for contradictions (official "
                           "paperwork against observed ground) and for "
                           "relationships between signals across regions, "
                           "and keeps what it found in a register. Never "
                           "reports a pair where both signals are "
                           "simulated, states how many pairs were tested "
                           "on every finding, and never uses a causal "
                           "word.",
         "endpoints": [{"method": "GET", "path": "/v1/analysis"},
                       {"method": "POST", "path": "/v1/analysis/run"}]},
        {"id": "coverage", "label_en": "What we can answer where you are",
         "beskrivning_en": "Publishes the platform's own coverage per "
                           "market: the share of each industry's weighted "
                           "signal picture that a connected source can "
                           "actually answer for, which adapter would open "
                           "which signals, and which adapters do not reach "
                           "that market at all. Computed from the source "
                           "and sensor state, never asserted.",
         "endpoints": [{"method": "GET", "path": "/v1/coverage"},
                       {"method": "GET", "path": "/v1/coverage/markets"}]},
        {"id": "scheduler", "label_en": "Run it without being asked",
         "beskrivning_en": "Registers jobs that run on a cadence — order "
                           "field missions for what falls due, recompute a "
                           "compliance record, re-run a market sweep and "
                           "store it, wake the watches. Same cadence "
                           "vocabulary as monitors. Jobs are claimed in the "
                           "store so two workers cannot run the same job "
                           "twice, and a watch woken with no history to "
                           "compare against says so instead of reporting "
                           "calm.",
         "endpoints": [{"method": "GET", "path": "/v1/schedules"},
                       {"method": "POST", "path": "/v1/schedules"},
                       {"method": "POST", "path": "/v1/schedules/run"}]},
        {"id": "export", "label_en": "Take it into your own tools",
         "beskrivning_en": "Exports a result as CSV, NDJSON or GeoJSON with "
                           "its provenance inside the file — engine "
                           "version, source state and every caveat, as "
                           "comment lines, a leading _landvex object or a "
                           "GeoJSON member. PDF, XLSX and Parquet are "
                           "refused by name rather than approximated. "
                           "Exporting a dataset requires the same package "
                           "as the endpoint it came from.",
         "endpoints": [{"method": "GET", "path": "/v1/export"},
                       {"method": "POST", "path": "/v1/export"}]},
        {"id": "company", "label_en": "Your brand on every mission",
         "beskrivning_en": "The tenant's company profile — name, logo "
                           "URL, about-text, website, brand colour. "
                           "Every quiXzoom mission the customer orders "
                           "carries it: the logo marks the map pin, and "
                           "tapping it opens who ordered the mission and "
                           "why. When a mission completes AND is "
                           "approved, the platform issues a signed "
                           "credential (HMAC per tenant), forwards it to "
                           "the customer's own system via the "
                           "feedback_webhook connection, and answers "
                           "verification calls — the loop closes. A "
                           "failed check is never certified.",
         "endpoints": [{"method": "GET", "path": "/v1/company"},
                       {"method": "POST", "path": "/v1/company"},
                       {"method": "GET", "path": "/v1/credentials"},
                       {"method": "POST",
                        "path": "/v1/credentials/verify"}]},
        {"id": "staff", "label_en": "Your own staff as zoomers",
         "beskrivning_en": "Link employees' existing quiXzoom accounts "
                           "by reference, or create invite codes redeemed "
                           "during quiXzoom onboarding. The roster is "
                           "what named-audience routines target — 'own "
                           "staff photograph the rental cars'. Landvex "
                           "stores account references and role labels "
                           "only; names and emails are refused at the "
                           "door, because identity and consent live "
                           "with quiXzoom.",
         "endpoints": [{"method": "GET", "path": "/v1/staff"},
                       {"method": "POST", "path": "/v1/staff"},
                       {"method": "POST", "path": "/v1/staff/invite"},
                       {"method": "POST", "path": "/v1/staff/claim"},
                       {"method": "POST", "path": "/v1/staff/remove"}]},
        {"id": "deliveries", "label_en": "The outbound audit log",
         "beskrivning_en": "Every outbound delivery attempt — pushes, "
                           "credentials, filed exceptions — logged with "
                           "the receiver's actual answer. Every POST "
                           "carries an idempotency id, an HMAC signature "
                           "over the body (the tenant's server secret) "
                           "and a schema version to build transforms "
                           "against. The receiving system can verify any "
                           "delivery id against the body it received. "
                           "The log never stores the body itself, and "
                           "'delivered' is the receiver's word — a row's "
                           "existence means the attempt happened, not "
                           "that it succeeded.",
         "endpoints": [{"method": "GET", "path": "/v1/deliveries"},
                       {"method": "POST",
                        "path": "/v1/deliveries/verify"},
                       {"method": "GET",
                        "path": "/v1/deliveries/streaks"},
                       {"method": "POST",
                        "path": "/v1/deliveries/retry"}]},
        {"id": "connections", "label_en": "Your own integrations",
         "beskrivning_en": "Bring your own language-model key (Anthropic, "
                           "OpenAI) or team webhook (Slack, Teams). Keys "
                           "are stored to be used and never echoed back — "
                           "every read path masks them. 'Configured' means "
                           "the form was filled in; 'verified' is set only "
                           "when the provider's real server answered a "
                           "probe. A connected model can narrate any "
                           "analysis — its text is an interpretation "
                           "billed to the customer's own key, never a "
                           "Landvex measurement.",
         "endpoints": [{"method": "GET", "path": "/v1/connections"},
                       {"method": "POST", "path": "/v1/connections"},
                       {"method": "POST",
                        "path": "/v1/connections/delete"},
                       {"method": "POST", "path": "/v1/connections/test"},
                       {"method": "POST",
                        "path": "/v1/connections/narrate"}]},
        {"id": "pushes", "label_en": "Generate your own delivery",
         "beskrivning_en": "The push generator: pick a dataset, a media "
                           "format and a webhook target, preview the "
                           "exact payload, then save the subscription as "
                           "a scheduled job (kind 'push'). Delivery "
                           "results are written on the job — a failed "
                           "POST never looks like a delivered one. "
                           "Targets are validated at creation: https "
                           "only, no private or loopback addresses.",
         "endpoints": [{"method": "GET", "path": "/v1/pushes"},
                       {"method": "POST", "path": "/v1/pushes/preview"}]},
        {"id": "infrastructure", "label_en": "Is it actually free right now?",
         "beskrivning_en": "Recurring verification of physical objects — "
                           "bicycle and car parking, stops, playgrounds, "
                           "recycling stations, berths, beaches — by "
                           "field observation. Freshness is a "
                           "first-class property: every value states how "
                           "long that KIND of value stays current, and "
                           "an expired perishable is served as history "
                           "under 'last_known' rather than as status, so "
                           "an integration cannot read a three-hour-old "
                           "space count as now. Nothing is estimated "
                           "between visits, and confidence is a band "
                           "rather than a score. SLA compliance is "
                           "computed from the observation history, "
                           "never read from the contract.",
         "endpoints": [{"method": "GET", "path": "/v1/infrastructure"},
                       {"method": "GET",
                        "path": "/v1/infrastructure/due"},
                       {"method": "POST",
                        "path": "/v1/infrastructure/observe"},
                       {"method": "POST",
                        "path": "/v1/infrastructure/status"},
                       {"method": "POST",
                        "path": "/v1/infrastructure/freshness"},
                       {"method": "POST",
                        "path": "/v1/infrastructure/sla"}]},
        {"id": "land", "label_en": "What the ground here is worth — "
                                   "relative to the ground next to it",
         "beskrivning_en": "Land-value POSITION across five weighted "
                           "families (location & access, development "
                           "pressure, economic base, infrastructure, "
                           "living environment). It carries no currency "
                           "and no price per square metre on purpose: a "
                           "number shaped like a price gets used like "
                           "one. Below 35% real coverage no position is "
                           "computed at all. Counter-indications are "
                           "listed separately — a place that scores high "
                           "DESPITE high crime is a different message "
                           "than one that scores high without "
                           "objections.",
         "endpoints": [{"method": "GET", "path": "/v1/land"},
                       {"method": "POST", "path": "/v1/land/assess"},
                       {"method": "POST", "path": "/v1/land/compare"}]},
        {"id": "sponsorship", "label_en": "Fund missions, see aggregates",
         "beskrivning_en": "Sponsored missions: brands fund verification "
                           "or authentic-content work, zoomers choose "
                           "among offered rewards, and sponsors see "
                           "k-floored aggregates — never an individual. "
                           "The funding sponsor is a required, "
                           "zoomer-visible field: a mission whose funder "
                           "is hidden is refused at creation. Content "
                           "missions additionally require a rights "
                           "agreement reference before a single mission "
                           "is generated. The wallet, the payout, the "
                           "photograph and every per-person record live "
                           "with quiXzoom.",
         "endpoints": [{"method": "GET", "path": "/v1/sponsorship"},
                       {"method": "POST",
                        "path": "/v1/sponsorship/campaigns"},
                       {"method": "POST",
                        "path": "/v1/sponsorship/mission"},
                       {"method": "POST",
                        "path": "/v1/sponsorship/completion"},
                       {"method": "POST",
                        "path": "/v1/sponsorship/order"},
                       {"method": "POST",
                        "path": "/v1/sponsorship/status"},
                       {"method": "GET",
                        "path": "/v1/sponsorship/stats"}]},
        {"id": "inspections", "label_en": "Prove your assets were checked",
         "beskrivning_en": "A register of the customer's own physical objects "
                           "(flagpoles, lifebuoys, ladders, signs, chargers), "
                           "the routines that say how often each must be "
                           "checked, what falls due, an order to a quiXzoom "
                           "field contributor, the verdict, and a compliance "
                           "record that can be shown to a board or an insurer "
                           "afterwards. A verdict without evidence is refused, "
                           "and the photo itself is never stored here — only "
                           "the verdict and the mission reference.",
         "endpoints": [{"method": "GET", "path": "/v1/assets"},
                       {"method": "POST", "path": "/v1/assets"},
                       {"method": "GET", "path": "/v1/routines"},
                       {"method": "POST", "path": "/v1/routines"},
                       {"method": "GET", "path": "/v1/inspections/due"},
                       {"method": "POST", "path": "/v1/inspections/dispatch"},
                       {"method": "POST", "path": "/v1/inspections/verdict"},
                       {"method": "GET",
                        "path": "/v1/inspections/compliance"},
                       {"method": "GET",
                        "path": "/v1/inspections/exceptions"},
                       {"method": "POST",
                        "path": "/v1/inspections/exceptions/report"}]},
        {"id": "sensitive", "label_en": "Sensitive questions",
         "beskrivning_en": "Surfaces associations on protected categories "
                           "(origin, victim status, health…) ONLY with "
                           "k-anonymity, mandatory confounder control (raw vs "
                           "controlled), official sources, and ecological-"
                           "fallacy warnings. Truth, never ammunition.",
         "endpoints": [{"method": "POST", "path": "/v1/sensitive-association"}]},
        {"id": "accountability", "label_en": "Who owns the decision",
         "beskrivning_en": "Commits a decision to a responsible owner + an "
                           "expected outcome, resolves it against the actual, "
                           "and keeps a per-owner ledger. Every result carries "
                           "its framing (a result is always an answer).",
         "endpoints": [{"method": "POST", "path": "/v1/decisions/commit"},
                       {"method": "POST", "path": "/v1/decisions/resolve"},
                       {"method": "GET", "path": "/v1/decisions/ledger"}]},
        {"id": "platform", "label_en": "Platform",
         "beskrivning_en": "Markets, reports, health and metrics.",
         "endpoints": [{"method": "GET", "path": "/v1/catalog"},
                       {"method": "GET", "path": "/v1/agent-manifest"},
                       {"method": "GET", "path": "/v1/audit"},
                       {"method": "GET", "path": "/v1/markets"},
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
