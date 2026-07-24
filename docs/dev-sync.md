# LANDVEX Opportunity Engine — Dev Sync Handoff

**Snapshot date:** 2026-07-24
**Branch:** `claude/new-session-d9t6ni` · **commit:** `b800532`
**Engine version:** `0.10.0` (stamped in every report; marketing versions v0.1–v0.30 track features)

This is the single entry point for the dev team. It summarizes the whole
system and points at the detailed docs. Everything here is code that runs
today — see **Test status** below.

> **Source of truth is the git branch above.** The container this was built
> in is ephemeral; always `git fetch && git reset --hard origin/claude/new-session-d9t6ni`
> if a checkout looks stale.

---

## 1. What this is

Global decision-support for future workforce and business needs. It does
not answer "where are the most people?" but **"where does THIS specific
business have the highest probability of success and making money?"** —
with explainable factor breakdowns, confidence, assumptions and honest
data coverage in every response. US-first; Sweden is the only calibrated
real-data market so far.

**Architecture principles (do not break these):**
1. Verticals/markets/segments/programs are **data, not code** — new options
   need no engine changes.
2. `engine/` stays **dependency-free** (stdlib only) → identical run in
   Lambda, ECS and locally. External libs live in `api/`, adapters, infra.
3. **Explainability before prediction** — no survival-probability / ROI
   promises until outcome data exists (v2/v3).
4. **Honest coverage** — mock is always `source="mock"`; `data_coverage`
   is never faked; heuristics are labelled; degradation never fakes a number.
5. **Determinism** — same location + vertical → same report.

## 2. Coverage (as of this snapshot)

- **35 markets / 344 regions.** US-first (`DEFAULT_MARKET="us"`).
  - **USA: all 50 states** (75 regions; Alaska/Hawaii are inset territories
    outside the continental bbox).
  - **All 27 EU member states** are markets.
  - Plus Canada, Mexico, Colombia, Morocco, Nigeria, Senegal, Norway.
- **22 industries, 21 occupations, 12 product types, 10 segments,**
  specializations per industry, work-styles, company forms.
- Only Sweden (SCB) is calibrated; every other market is mock and **labelled
  as simulated**. Local adapters are the backlog (§6).

## 3. API surface

- **14 engines, 36 endpoints, `v1`.** Machine-discoverable at
  `GET /v1/catalog`; OpenAPI 3.0 at `GET /openapi.json` (also exported to
  `docs/openapi.json` in this package); agent manifest at
  `GET /v1/agent-manifest`.
- **Two interchangeable API layers, locked equal by a contract test:**
  - `api/main.py` — FastAPI (production; needs `requirements.txt`).
  - `api/dev_server.py` — stdlib `http.server`, **zero dependencies**.
- **Key endpoints (new since the last AWS handoff in bold):**
  - Opportunity: `POST /v1/analyze`, `/v1/scan`, `/v1/report`,
    `GET /v1/profile-options`, `/v1/profiles`
  - **`POST /v1/opportunities`** — Opportunity Intelligence / Business
    Navigation (support programs, "you're missing money", hidden
    opportunities, legal guide, lifecycle, expansion advisor)
  - **`POST /v1/risk-intelligence`** — dual Opportunity/Risk score, 10 risk
    categories, Business Signals framework, counterparty-health framework
  - Workforce, Risk, Compare, Gaps, Plan, Segments, Installed Base, Indices
  - AAMOS: `GET /v1/platform/status`, `/v1/watch`, `/v1/agents`,
    `POST /v1/agents/chat`, `/v1/cognition/brief`
  - Platform: `GET /v1/markets`, `/v1/reports`, `/health`, `/metrics`

## 4. The decision layers (what makes it unique)

Personalized flow: **who are you** (industry, specialization, company form,
size) → **how do you want to work** (commute, move, work style) → **what do
you want** → **Opportunity Score** with ★ rating, drivers ("why?"),
percentile ("Beats 93% of 60 locations in USA for your profile"), and a
2-year demand outlook (momentum heuristic, not a forecast).

- **Opportunity Intelligence** (`engine/opportunity_intel.py`,
  `POST /v1/opportunities`): support-program fit (archetypes as data, amounts
  scaled by local signals), unclaimed-support value, hidden opportunities
  (signal patterns → niche), legal categories per trade, lifecycle stage,
  expansion advice. **Never invents a specific live grant/amount/deadline** —
  a live programs registry adapter makes those real.
- **Risk Intelligence / Business Signals** (`engine/risk_intel.py`,
  `POST /v1/risk-intelligence`): a Risk Score (0–100) beside the Opportunity
  Score, 10 categories (computed from signals where possible, else honest
  "monitoring" awaiting a feed), the Business Signals framework (financial,
  customer, staffing, business, project, market, public, supplier), and a
  **cautious** counterparty-health framework (objective signals + suggested
  precautions — never a legal conclusion, never "don't do the deal").
  Trend/change is "requires monitoring history" until a feed with history is
  connected.

## 5. Integration points (confirm against live before flipping on)

- **AAMOS Capability Platform** (`integrations/aamos.py`): stdlib client,
  degrades honestly to `ej_ansluten` until `AAMOS_CORE_URL` is set
  (target `http://127.0.0.1:3100`). XML/RSS→JSON fallback for `contents`.
  Self-registers best-effort at `/api/services/register` on startup.
- **quiXzoom missions** via AAMOS Core. Default path
  `AAMOS_QUIXZOOM_PATH=/api/qz/missions` — **route still to be confirmed**;
  the smoke script probes candidates. Real signal derived:
  `field_observation_density` (missions near a point). Never fabricates
  `development_m2` (that needs the Vision pipeline).
- **Commission model** (`engine/commission.py`): Growth plan is
  commission-based — quiXzoom **QZ TOKEN per qualified lead**, score-tiered
  `0.80–1.0→0.15`, `0.50–0.80→0.10`, `<0.50→0.05`; `1 QZ ≈ $0.15` (schablon,
  AAMOS Core settles the real rate). Open question: does it fully replace the
  monthly fee?
- **SCB PxWeb** (`engine/datasources/scb.py`): the one calibrated source.
  Table paths written from metadata but **never live-verified** (dev network
  blocked). Verify before trusting.

## 6. Pre-flight checklist before real APIs

Run these read-only probes in a networked environment (both documented in
`CLAUDE.md` commands):

```bash
AAMOS_CORE_URL=http://127.0.0.1:3100 python3 -m scripts.aamos_smoke
python3 -m scripts.scb_probe 59.31 18.07
```

Then, in priority order:
1. **AAMOS handshake** — confirm the exact quiXzoom route + mission shape
   (`location.lng`), JSON vs XML/RSS, and service registration.
2. **SCB live probe** — confirm PxWeb table paths against api.scb.se.
3. **Capture real fixtures** for SCB + quiXzoom and pin the adapter tests.
4. **Auth/secrets** — `LANDVEX_API_KEYS` (`key:tenant:role[:plan[:addons]]`),
   `LANDVEX_JWT_SECRET`; RBAC/capability/quota enforcement with real keys.
5. **Persistence** — `PostgresStore.selftest()` against real Aurora/PostGIS;
   `usage_meter` migration (monthly quota must survive restarts).
6. **Commission settlement** — confirm QZ→USD and monthly-fee scope with
   AAMOS-dev.

**First live feed to build (recommended):** the **programs registry**
adapter (EU Funding & Tenders / Vinnova / Energimyndigheten / regional
funds) — turns support-program amounts/deadlines from archetype estimates
into real data via the same Resolver pattern as SCB.

## 7. Deployment

- Domain: `opportunity.landvex.com` (nginx conf in `infra/`).
- Port: `:8087` (`LANDVEX_PORT`), systemd unit `infra/landvex-opportunity.service`.
- `Dockerfile` with healthcheck; Lambda entry `api/lambda_handler.py` (Mangum).
- Config env: `LANDVEX_LIVE`, `LANDVEX_DB`/`LANDVEX_PG_DSN`, `LANDVEX_API_KEYS`,
  `LANDVEX_JWT_SECRET`, `AAMOS_CORE_URL`, `AAMOS_QUIXZOOM_PATH`, `LANDVEX_PORT`.
- **Maps:** the frontend ships an offline SVG map. Production can switch to
  real tiles (MapLibre GL + OpenStreetMap, free, no key) in one step — set
  `window.LANDVEX_MAP_TILES` / `<meta name="landvex-map-tiles">` / `?maptiles=`
  and include MapLibre GL; dormant skeleton already in `frontend/index.html`.
- Detailed deployment: `docs/aws-deployment.md`, `infra/aws-notes.md`,
  `infra/rexo-deliverables.md`, `infra/infrastruktur-inventering.md`.

## 8. Test status

**20 test suites, all green, no pytest / no network required:**

```bash
cd landvex-opportunity-engine
for t in tests/test_*.py; do python3 -m "tests.$(basename "$t" .py)"; done
```

Includes a contract test locking the two API layers equal, a red-team suite,
and per-engine suites (opportunity_intel, risk_intel, markets, scan, ask,
gaps/plan, licensing, security, …). CI: `.github/workflows/landvex-ci.yml`
(repo root) on Python 3.11/3.12.

## 9. Doc map (all included in this package)

| File | What |
|------|------|
| `CLAUDE.md` | **Authoritative project context** — full feature history v0.1–v0.30 |
| `docs/architecture.md` | Design decisions, data flow, roadmap |
| `README.md` | Overview + run instructions |
| `docs/aws-deployment.md` | AWS deployment handoff |
| `docs/production-readiness.md` | Readiness status + gaps |
| `docs/history/BUILD-STATE-PROMPT.md` | Open decisions (domain/port, quiXzoom, plans) |
| `docs/openapi.json` | Exported OpenAPI 3.0 spec |
| `infra/*` | systemd unit, nginx conf, AWS notes, REXO deliverables, inventory |
| `scripts/aamos_smoke.py`, `scripts/scb_probe.py` | Pre-flight probes |

## 10. Run it

```bash
cd landvex-opportunity-engine
python3 -m api.dev_server                 # zero-dependency API + portal → http://localhost:8000/
pip install -r requirements.txt && uvicorn api.main:app   # production API
python3 -m scripts.build_demo             # rebuild the standalone offline demo (landvex-demo.html)
```

The offline demo (`landvex-demo.html`) is a shareable snapshot with
precomputed engine responses; it is **not** in this zip (regenerate with the
command above). The live server has none of the demo's precompute limits.
