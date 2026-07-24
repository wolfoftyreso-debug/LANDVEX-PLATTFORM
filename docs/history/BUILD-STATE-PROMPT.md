# LANDVEX OPPORTUNITY ENGINE — BUILD STATE PROMPT (v0.19)

> **How to use this document:** Paste it to any agent or team together with
> a truth source (landvex.com, aamos.ai, quixzoom.com, the server
> infrastructure inventory, product sheets, contracts). The task is always
> the same: **compare what is built (below) against the truth source, and
> return (1) mismatches in naming/definitions/pricing/structure,
> (2) things the truth source has that the build lacks, (3) things the
> build has that the truth source does not know about, and (4) the exact
> corrections or missing data needed.** Do not assume anything not written
> here — this document is the complete, honest state of the build.

**Repo:** `wolfoftyreso-debug/konditori-joy`, directory
`landvex-opportunity-engine/`, branch `claude/new-session-d9t6ni`.
**Engine version:** 0.10.0 · **Platform language:** English (all API text
fields `*_en`; the Ask parser also accepts Swedish). **Stack:** pure
Python 3.11+ (zero runtime dependencies), single-file HTML/JS frontend,
optional FastAPI/Mangum/psycopg only where deployed.

---

## 1. WHAT IS BUILT AND VERIFIED (all live, all tested)

### Architecture principles (enforced, not aspirational)
- **API-first:** the frontend is one thin client; every capability is a
  `/v1/*` endpoint. Two identical API layers: `api/main.py` (FastAPI,
  production) and `api/dev_server.py` (stdlib, zero-dependency mirror).
- **Everything-is-data:** industries, occupations, segments, product
  types, indices, markets, plans are data rows — a new entry requires no
  engine change.
- **Honesty rules:** mock data is always `source="mock"` and labeled
  simulated; `data_coverage` is never faked; confidence is marked as
  documented heuristic; intervals widen with horizon; economic figures
  are "standard estimate — NOT a forecast"; no ROI before outcome data;
  deterministic (same input ⇒ same report); every report stamps
  `engine_version`.
- **Resolver chain:** real source wins per signal → cached (TTL per
  source, error-pause with automatic mock fallback) → deterministic
  coordinate-seeded mock. Adapter stubs registered and honestly reported
  in `/health` as not-connected: permits, places, movement, **quiXzoom**.
  Only SCB (Statistics Sweden, PxWeb client + municipality locator) is
  implemented as a real adapter — currently unverified against the live
  API because the build environment blocks api.scb.se.

### The 10 engines (25+ endpoints)
| Engine | Endpoints | What it does |
|---|---|---|
| Ask (NL interface) | `/v1/ask` | English-first deterministic parser (Swedish synonyms kept): ~15 intents — opportunities, best locations, local/national/global shortage, country ranking, risk, establishment plan, imbalances, segments, service demand. City exonyms, number words, horizons ("next five years", "by 2035"). |
| Opportunity | `/v1/analyze`, `/v1/scan`, `/v1/profile-options`, `/v1/profiles` (GET/POST) | Point analysis + market sweep. Business profile (industry, budget, team, model, risk tolerance, horizon, goal) → ranked hotspots with decision cards: Opportunity Score, confidence, time window, competition gap, momentum, risk index, drivers, next steps. |
| Workforce | `/v1/workforce/occupations`, `/forecast`, `/simulate`, `/map`, `/global-map` | Competence forecasts with confidence intervals & explicit assumptions, milestones 1/3/5/10/20 yrs, national shortage maps, education simulation ("N extra places/yr → shortage X→Y, balance year"), cross-country ranking. |
| Risk | `/v1/risk` | Multi-dimension risk profile (incl. data-uncertainty dimension) with bands and mitigations. |
| Compare | `/v1/compare` | Side-by-side location comparison with factor matrix + recommendation. |
| Gap Analysis | `/v1/gaps` | Imbalance score = 0.45·demand + 0.35·supply-deficit + 0.20·momentum (documented heuristic), ranked regions + heatmap. |
| Establishment Plan | `/v1/plan` | Premises, investment ranges, financing options, suppliers, staffing (fed by Workforce forecast), economy standard-estimate, payback, risks, next steps — all 22 industries. |
| Segments | `/v1/segments`, `/analyze`, `/map` | 10 target groups (pet owners, families, seniors, commuters, …) — local over/under-representation + who serves them. |
| Demand Intelligence (installed base) | `/v1/products`, `/v1/service/analyze`, `/v1/service/map` | Generic product model (12 types: heat pumps, solar, EV chargers, elevators, robots, …): installed base → service events → technician demand; replacement-wave detection; mismatch flag (large base + technician shortage = opportunity). |
| Intelligence Map (indices) | `/v1/indices`, `/map`, `/assess` | Infrastructure Risk, Commercial Activity, Safety, Climate Risk, Urban Growth (live-tier) + **Contradiction Index** = divergence between officially planned (permits, plans) and observed (development, renovation), threshold 35 — flagged "contradiction detected". Every value carries per-signal source breakdown ("sourced & traceable"). |
| Platform | `/v1/markets`, `/v1/reports`, `/health`, `/metrics`, `/v1/catalog`, `/v1/agent-manifest`, `/openapi.json`, `/v1/plans`, `/v1/entitlements` | Self-describing API for humans and agents (12 tools with JSON Schema for agent use — built to be mounted as an aamos.ai API). |

### Data footprint
22 industries · 21 occupations · 42 signals (normalization catalog makes
scores comparable across countries) · 10 segments · 12 product types ·
5 indices + Contradiction Index · **16 markets / 238 regions — US FIRST:
the USA is the default market everywhere (60 metro regions, the largest
in the system), followed by SE (40) + DE, ES, PL, FR, IT, NL, BE, AT,
PT, DK, FI, NO, IE, CZ.** Establishment-plan amounts are converted to
each market's currency via documented standard FX rates (local cost
levels honestly flagged as uncalibrated). Only Sweden has a real-source
adapter; all other markets run on labeled simulated data
("calibrated=false" surfaced in UI).

### Commercial layer (enforced in the API, not just displayed)
- Plans: **Free (0)**, **Pro (SEK 4,900/mo list price)**, **Enterprise
  (custom quote)** + 5 add-on modules: Opportunity, Workforce, Demand
  Intelligence, Intelligence Map Live, Partner API & Agents.
- API keys `key:tenant:role[:plan[:addon|addon]]`, RBAC
  (admin>analyst>partner), capability-per-endpoint map, rate limits
  60/600/3000 req/min per plan, live index layers locked for Free
  ("free historical / live requires subscription"), upgrade hints,
  `/v1/entitlements`. Prices marked "list prices (examples)".
- Security baseline: audit log (JSONL, keys never logged), metrics
  p50/p95 + Prometheus export, X-Request-ID.

### Frontend (single file, English, no emojis — SVG icon system)
7 tabs: **Guide** (default; 4 wizard flows that ask step-by-step and run
the engines: start a business / workforce planning / deep-analyze
locations / find imbalances), **Ask**, **Establish**, **Workforce**,
**Index**, **Plans**, **Settings** (default market/target year/top-N/API
key in localStorage, sent as X-API-Key; About-the-system from
/health + /v1/catalog). Zoomable SVG map with heat layers.

### Deployment packaging (built, not yet deployed)
`python3 -m api.dev_server` (zero deps) · FastAPI app · `Dockerfile`
(healthcheck) · `api/lambda_handler.py` (Mangum) · env vars:
`LANDVEX_API_KEYS`, `LANDVEX_DB`, `LANDVEX_PG_DSN` (Postgres/PostGIS
store with selftest), `LANDVEX_AUDIT_LOG`, `LANDVEX_LIVE`,
`LANDVEX_RATE_LIMIT`. SQLite store with schema migrations is default.

### Verification state
15 test suites / 110+ tests, zero dependencies, all green · GitHub
Actions CI (Python 3.11/3.12, compile + suites + auth smoke) · Playwright
browser sweeps of every guide flow in live AND demo mode · standalone
demo (7.9 MB, all offered choices precomputed — no dead ends) published
as a private artifact.

---

## 2. KNOWN GAPS (honestly not built yet)
1. **Real data adapters beyond SCB:** Eurostat/Destatis/US Census, permits,
   places, movement, **quiXzoom observation layer** — stubs only.
2. **SCB live verification** — blocked network in build env; table paths
   need a live probe.
3. **OIDC/OAuth2/JWT** — API-key auth only today.
4. **Multi-tenant storage isolation** — tenant exists in the key model and
   audit log, not yet as columns in the stores.
5. **Usage metering/billing export** per tenant (rate limiting exists).
6. **Deployment onto the real infrastructure** — nothing is deployed; see
   reconciliation questions below.
7. **Docs still in Swedish** (CLAUDE.md, README) — platform itself is English.
8. **Geographies from the landvex.com map not yet modeled:** Canada,
   Mexico, Colombia, Morocco, West Africa.
9. **LLM layer for Ask** — parser is deterministic by design; an optional
   LLM interpreter in the API layer (never in the engine core) is planned.

---

## 2b. RECONCILIATION STATUS (against Bernt's report, 2026-07-23)
**Fixed in build:** pricing is USD-first with no SEK anywhere (locked
rule; Pro $499/mo, add-ons $149–$499, list-price note in USD) · frontend
rebuilt to the REXO Apple iPhone Native theme (iOS 18: `--ios-blue
#007AFF`, `#F2F2F7` background, SF Pro stack, 13px squircle, Liquid
Glass blur; banned color check clean) · "Commercial Activity" renamed
**Commercial Vitality** and a **City Health** composite index added
(7 indices total incl. Contradiction) · tagline "Decision Intelligence
for the Physical World" + RIOS family stamped in `/v1/catalog` ·
**QuixzoomSource is now a real HTTP client** against
`/v1/observations` (set `LANDVEX_QUIXZOOM_URL=http://127.0.0.1:3209`;
error-pause + honest /health status; fixture-tested) · systemd unit
(port 8087 proposal) and nginx `/v1/` mount drafts in `infra/`, plus
REXO task/manual/artifact drafts in `infra/rexo-deliverables.md` ·
`LANDVEX_PORT` env var supported.
**Open decisions (Erik/Johan):** domain mount (replace v0 vs parallel
/v1/), final port, quiXzoom direct vs via AAMOS Core, register as an
AAMOS product (`/v1/opportunity/<action>` path convention) vs
standalone Landvex product, plan names (Free/Growth/Enterprise?) and
final USD price points, who claims the REXO deployment task.
**Built after Bernt's AAMOS integration prompt (v0.22):** stdlib
AAMOS client (`integrations/aamos.py`) covering identity/graph/
analytics/alerts/control-plane/cognition/Apollo/agent-loop · five new
endpoints (/v1/platform/status, /v1/watch, /v1/agents, /v1/agents/chat,
/v1/cognition/brief) with capability gating and honest not-connected
degradation until `AAMOS_CORE_URL` is set · **JWT bearer auth (HS256,
stdlib)** alongside API keys (`LANDVEX_JWT_SECRET`; claims
sub/tenant/role/plan/addons; same RBAC/capability enforcement; tokens
never logged) · plan naming per AAMOS convention: "Landvex Growth"
($499/mo; plan id "pro" kept as key-format contract, alias "growth"
accepted) · Watch tab in the UI (platform status, data sources,
alerts, agent chat) · mandatory dark mode (prefers-color-scheme, iOS
dark palette) + spring-physics transitions · 16th test suite.
**Accepted follow-ups (not yet built):** AAMOS Core check-permission
delegation for opaque tokens, Vision/Reality/Change engine wiring into
the Contradiction Index (needs schemas), monthly usage quotas
(rate-per-minute exists), geographies Canada/Mexico/Colombia/Morocco/
West Africa, RALE (documented concept, not yet an engine).

## 3. RECONCILIATION QUESTIONS — what we need from the truth sources
When matching against **landvex.com**: exact index names/definitions/tiers
shown publicly; city list on the Intelligence Map; wording of
"official sources + quiXzoom observations"; public pricing if any.
When matching against **aamos.ai / developer.aamos.ai**: API conventions
(auth, versioning, error format, manifest format) so `/v1/agent-manifest`
and the key model mount cleanly as an aamos API.
When matching against **the server inventory (bernt.wavult.com)**: still
open — Gitea repos, database DSNs (RDS `wavult-identity-core` + local
Postgres via pgbouncer :6432), Redis/NATS roles, the REXO pipeline
contract (`/opt/amos/rexo-build/` — required delivery format), the domain
that fronts this API (api.landvex.io v0 exists — replace or mount as v1
alongside?), and whether quiXzoom's API (:3209 /v1/observations, AVO
:7070) exposes the observation data the Contradiction Index needs.
Port resolved: the 8087 proposal is free — inventory 2026-07-23 shows
8083 landvex-api (Object), 8084 bounties, 8085 claims, 8086 demo, 7072
admin-api occupied. AAMOS Core :3100 and quiXzoom :3209/:7070 confirmed,
matching the built adapters.
When matching against **product/pricing truth**: confirm plan names,
list prices per market/currency, add-on packaging, and what Enterprise
includes contractually.

**Output format requested from the reconciling agent:** a table per truth
source: `item · build says · truth says · action (fix build / extend
build / update truth / need decision)`.
