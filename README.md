# Baltic Bridge

Verified cross-border subcontracting marketplace. Launch corridor:
**Lithuania → Sweden**, launch trade group: **welders and industrial fitters**
(entreprenad, not staffing).

The product is the **verification and compliance engine**: proving, with
documents and an audit trail, that a Baltic supplier is fully compliant for
work in Sweden (F-skatt, A1, posted-worker notification, ID06, insurance,
collective-agreement status, welding certifications).

**Read [`CLAUDE.md`](CLAUDE.md) first** — it is the authoritative foundation
(build order, stack, architecture rules). `docs/` contains superseded
historical material only.

## Stack

TypeScript · Next.js App Router (single monolith, one container) ·
PostgreSQL 16 (RDS) + Drizzle · Auth.js · S3 (MinIO in dev) · SES ·
pg-boss · next-intl (sv/en/lt) · Zod · pino · Vitest.

## Getting started

```sh
docker compose up -d       # Postgres 16 + MinIO (versioned documents bucket)
cp .env.example .env.local
npm install
npm run db:migrate         # apply Drizzle migrations
npm run db:seed            # LT→SE corridor, 10-requirement catalogue, ops users
npm run dev
```

Sign in at `/sv/signin` with the seeded ops account
(`ops@balticbridge.example` / `change-me-now` — change immediately).

Enable in-process jobs (nightly expiry sweep + outbox dispatcher) by setting
`ENABLE_JOBS=1`.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server |
| `npm run build` / `start` | Production build / serve |
| `npm run lint` / `typecheck` / `test` | CI steps |
| `npm run db:generate` | Generate a migration from schema changes (append-only) |
| `npm run db:migrate` / `db:seed` | Apply migrations / seed catalogue + users |
| `npx tsx src/db/smoke.ts` | M1 DoD smoke test: onboard → verify → simulated expiry flips the badge |

## Layout

```
src/modules/<name>/{schema,domain,service,...}   # module boundaries (Section 4)
  identity/    users, RBAC guards, password hashing
  catalog/     trades, corridors, requirement definitions (seed data)
  companies/   companies, slugs, contacts, workers, capacity listings
  documents/   S3 presigned upload/download, malware-scan hook
  verification/ cases, items, state machines, expiry engine, ops tasks
  audit/       audit_events, outbox_events, idempotency keys
  notifications/ EmailProvider (console dev / SES prod)
src/app/[locale]/admin/    ops console (kanban, review queue, company 360°, tasks)
src/app/api/v1/            REST API (Zod-validated, idempotency keys)
src/jobs/                  pg-boss: nightly expiry sweep, outbox dispatcher
drizzle/                   append-only SQL migrations
```

## Milestones

- **M1 — Ops backbone (this codebase):** supplier CRM + verification engine ✅
- **M2 — Public layer:** verified profiles + SEO — next
- **M3 — Demand:** RFQ intake, ops-driven matching, offers
- **M4 — Hardening:** e2e tests, backups, runbooks

## Deploy

One container (see `Dockerfile`, standalone output) behind ALB + CloudFront,
RDS + S3 + SES in `eu-north-1`. CI: lint → typecheck → test → build
(`.github/workflows/ci.yml`). IaC follows the org convention — added when the
target account/convention is confirmed.
