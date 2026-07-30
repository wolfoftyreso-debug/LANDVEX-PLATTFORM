# LANDVEX OPPORTUNITY ENGINE — HANDOFF TO AWS DEV (Bernt)

> **This is the EC2 + systemd + nginx path (port 8087).** For ECS
> Fargate — ECR, Aurora, Secrets Manager, and the preflight gate the
> container runs before it serves traffic — see [`aws.md`](aws.md).
> Both are current; they are different shapes, not different versions.

**From:** Claude Code (Fab build)  ·  **To:** Bernt (bernt.wavult.com)
**Engine version:** 0.10.0  ·  **Repo:** `wolfoftyreso-debug/konditori-joy`
**Branch:** `claude/new-session-d9t6ni`  ·  **Subdir:** `landvex-opportunity-engine/`
**Latest commit:** v0.26 (quiXzoom/commission locked to reality)

This is what you need to deploy and wire the engine into the real
infrastructure. Everything below is built and green (18 test suites,
red-team hardened). Nothing here requires changes to your other
services — the engine mounts alongside them.

---

## 1. WHAT IT IS (in one line)
A zero-dependency Python 3.11+ decision-intelligence API: 12 engines /
34 endpoints, 22 markets / 280 regions (US-first), English, Apple-Native
frontend. Runs as one process. AAMOS + quiXzoom integrations are built
and report **honestly not-connected** until you set two URLs.

---

## 2. DEPLOY — SYSTEMD (the approved path, no pm2)

```bash
# 1. Code
git clone -b claude/new-session-d9t6ni \
  https://github.com/wolfoftyreso-debug/konditori-joy \
  /opt/landvex/opportunity-engine-src
ln -s /opt/landvex/opportunity-engine-src/landvex-opportunity-engine \
  /opt/landvex/opportunity-engine

# 2. Config (see env table below)
sudo install -d /etc/landvex
sudoedit /etc/landvex/opportunity.env

# 3. Service (template committed at infra/landvex-opportunity.service)
sudo cp infra/landvex-opportunity.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now landvex-opportunity

# 4. Verify
curl -sf localhost:8087/health | jq .status      # → "ok"
```

**Port: 8087.** Confirmed free against your 2026-07-23 inventory
(8083 landvex-api/Object, 8084 bounties, 8085 claims, 8086 demo,
7072 admin-api all occupied).

**Runtime is stdlib-only** — no `pip install` needed for the dev-server
path (`python3 -m api.dev_server`, now multithreaded, backlog 256,
survives 500 concurrent requests). If you prefer the FastAPI/uvicorn
path, `pip install fastapi uvicorn mangum` and run
`uvicorn api.main:app --host 0.0.0.0 --port 8087`. Both expose the
identical endpoint surface (locked by tests/test_contract.py).

---

## 3. ENV VARS (`/etc/landvex/opportunity.env`)

| Variable | Purpose | Example / default |
|----------|---------|-------------------|
| `LANDVEX_PORT` | Listen port | `8087` |
| `LANDVEX_API_KEYS` | API-key store: `key:tenant:role[:plan[:addon\|addon]]` | `k1:acme:admin,k2:beta:analyst:growth` |
| `LANDVEX_JWT_SECRET` | HS256 secret to accept `Authorization: Bearer` (AAMOS-style). Empty ⇒ JWT off, keys only | `<32+ random bytes>` |
| `LANDVEX_PG_DSN` | Postgres/PostGIS DSN (via pgbouncer). Empty ⇒ SQLite | `postgresql://user:pw@127.0.0.1:6432/landvex` |
| `LANDVEX_DB` | SQLite path, or `off` when using Postgres | `off` |
| `AAMOS_CORE_URL` | AAMOS Capability Platform base. Empty ⇒ honest not-connected | `http://127.0.0.1:3100` |
| `AAMOS_QUIXZOOM_PATH` | AAMOS Core route for quiXzoom missions (quiXzoom is reached VIA AAMOS Core, decision #2) | `/api/quixzoom/missions` |
| `LANDVEX_LIVE` | `0` = mock only (no real adapters) | `1` |
| `LANDVEX_RATE_LIMIT` | Fallback per-minute cap when a key has no plan | `300` |
| `LANDVEX_AUDIT_LOG` | JSONL audit path, or `off` | `/var/log/landvex/audit.jsonl` |

Roles: `admin > analyst > partner`. Plans: `free` (\$0) / `growth`
(=`pro` id; **quiXzoom commission 0.05–0.15 QZ per lead by opportunity
score — no monthly fee**) / `enterprise` (custom). Monthly quotas enforced and **persistent** across
restarts once `LANDVEX_PG_DSN`/`LANDVEX_DB` is set: Free 100/mo,
Growth 10 000/mo, Enterprise unlimited.

---

## 4. DATABASE
- Set `LANDVEX_PG_DSN` to your RDS `wavult-identity-core` (or a
  dedicated `landvex` DB) **via pgbouncer :6432**, and `LANDVEX_DB=off`.
- Schema auto-creates on first start (idempotent `CREATE TABLE IF NOT
  EXISTS`): `reports`, `profiles`, `signal_cache`, `extras_cache`,
  `usage_meter`. PostGIS not required for current features.
- Selftest before go-live:
  `python3 -c "from engine.storage.postgres import PostgresStore; PostgresStore('<dsn>').selftest()"`

---

## 5. NGINX
Template committed at `infra/nginx-opportunity.conf` (mounts `/v1/`,
`/health`, `/openapi.json` → `127.0.0.1:8087`).

**Open decision — pick one:**
- **A) Own subdomain** `opportunity.landvex.com` → clean, no collision.
- **B) Mount on `api.landvex.io/v1/`** alongside the v0 service (the
  template does this without touching v0's upstream).

---

## 6. WIRE THE INTEGRATIONS (this is the payoff)
Both adapters are real clients today; they just need URLs.

- **quiXzoom (via AAMOS Core, decision #2)** → set `AAMOS_CORE_URL`;
  the client calls `GET {AAMOS_QUIXZOOM_PATH}?lat&lon&radius_km`
  (default `/api/quixzoom/missions` — this superseded the earlier
  `/api/qz/missions` in this section once server-2 confirmed the live
  route on 2026-07-30) and reads the mission list
  (real shape locked: `id, title, location{lat,lng}, reward, currency,
  status, required_media, deadline, created_at` — note `lng`). It
  filters missions client-side to a 10 km radius and derives
  `field_observation_density` (local mission count) — genuinely real.
  It does **not** fabricate `development_m2`; that observed-development
  signal for the Contradiction Index awaits the Vision pipeline that
  analyses the submitted media. If AAMOS Core proxies missions at a
  different path, set `AAMOS_QUIXZOOM_PATH`.
- **AAMOS Core** → `AAMOS_CORE_URL=http://127.0.0.1:3100`. Powers
  `/v1/platform/status`, `/v1/watch`, `/v1/agents`, `/v1/agents/chat`,
  `/v1/cognition/brief`, and enriches `/v1/ask` with a strategic note.
  Endpoints used: `/api/aamos/identity/agents`, `/api/aamos/alerts`,
  `/api/aamos/control-plane/{services,health-summary}`,
  `/api/aamos/cognition/strategic-{analysis,brief}`,
  `/api/aamos/agent-loop/chat`. **Any AAMOS failure degrades honestly —
  it never breaks an endpoint.**

Confirm the response shapes match; if quiXzoom/AAMOS differ, send me one
sample payload per endpoint and I'll adjust the parser (fixture-tested,
so it's a small change).

---

## 7. VERIFY AFTER DEPLOY
```bash
curl -sf localhost:8087/health                     # sources + versions
curl -sf localhost:8087/v1/catalog | jq .engines   # self-describing API
curl -s -X POST localhost:8087/v1/ask \
  -H "X-API-Key: <key>" \
  -d '{"question":"Where should I open a café?"}'
curl -sf localhost:8087/metrics -H "X-API-Key: <admin-key>"  # Prometheus
# Full offline test suite (no network, no pip):
python3 -m tests.test_contract   # both servers in sync
# ...15 more suites; CI runs all 18 on push.
```
`/metrics` exports Prometheus format → point your existing Prometheus
(:9090) / Grafana (:3050) at it. `X-Request-ID` on every response.

---

## 8. REXO
Drafts ready in `infra/rexo-deliverables.md` (PLAN.json task, manual,
`<TID>-DONE.md` artifact). Design passes the Apple-Native spec-gate
(iOS 18: #007AFF, #F2F2F7, SF Pro, 13px squircle, Liquid Glass, dark
mode; zero banned colors). Pricing is USD-only (locked rule).

---

## 9. DECISIONS — RESOLVED (from AAMOS-dev)
1. ✅ **Domain:** `opportunity.landvex.com` (nginx conf ready, reuses
   the landvex.com cert).
2. ✅ **quiXzoom:** via AAMOS Core (`/api/quixzoom/missions` — corrected
   2026-07-30 against the live route on server-2, see §6), never fails
   the endpoint on AAMOS error.
3. ✅ **Service registration:** `landvex-opportunity-engine` posts to
   `/api/services/register` at startup (best-effort, non-blocking).
4. ✅ **Pricing:** Growth = quiXzoom commission 0.05–0.15 QZ per lead by
   opportunity score, no monthly fee (built in — each decision card
   carries its `commission`). A "lead" = an engine-identified
   opportunity (a delivered decision card).
5. ✅ **REXO:** Bernt claims the deploy task.
6. ✅ **Schemas:** quiXzoom mission shape + AAMOS XML/RSS `contents`
   locked into the parsers.

### Still helpful to confirm on the live box
- Exact query params `/api/quixzoom/missions` accepts (we send
  `?lat&lon&radius_km` and also filter client-side to 10 km, so it works
  either way).
- Whether commission applies platform-wide beyond Growth (Free stays
  $0, Enterprise stays custom in the build).

_(Historical — superseded by the resolved list above:_
6. **quiXzoom / AAMOS response schemas:** send one sample payload each so
   I can lock the parsers to reality (replaces the last assumptions).

---

## 10. WHAT'S DELIBERATELY NOT BUILT (needs your input, no guessing)
Vision/Reality/Change engine wiring into the Contradiction Index (need
schemas), RALE (undefined concept), OIDC delegation for opaque tokens,
i18n Swedish-response layer, geographies beyond the current 22
(Canada/Mexico/Colombia/Morocco/Nigeria/Senegal are in). All tracked in
`docs/BUILD-STATE-PROMPT.md` §2b with exactly what each needs.
