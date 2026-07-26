# Baltic Bridge — Runbook

> **Self-owned infrastructure:** the fully self-managed deployment mode
> (own compute, self-managed Postgres 16, MinIO instead of S3, own SMTP relay
> instead of SES) is documented in [SELF-HOSTED.md](./SELF-HOSTED.md) with its
> own compose stack (`docker-compose.selfhost.yml`) and backup procedure.
> Everything below describes the managed-AWS mode; the container image and
> code are identical in both.

## Deployment (Section 3)

One container behind ALB + CloudFront, images in ECR, `eu-north-1` only.

1. CI (`.github/workflows/ci.yml`): lint → typecheck → test → build on every push.
2. Release: build the image from `Dockerfile` (standalone output), push to ECR,
   update the ECS Fargate service (or App Runner). Secrets are injected from
   SSM Parameter Store / Secrets Manager — never baked into the image.
3. Required environment: `DATABASE_URL`, `AUTH_SECRET`, `S3_*`,
   `EMAIL_PROVIDER=ses`, `EMAIL_FROM`, `PUBLIC_BASE_URL`, `ENABLE_JOBS=1`
   (pg-boss in-process), optional `CRON_SECRET` for the EventBridge-hit
   `/api/jobs/expiry` endpoint.
4. Migrations are append-only: run `npm run db:migrate` as a pre-deploy step
   (one-off ECS task) before shifting traffic.
5. Health: ALB target group checks `/api/healthz` (verifies DB connectivity).
   CloudWatch alarms on 5xx rate and pg-boss queue depth.

## Backups & restore (M4 — tested)

**Automatic:** RDS point-in-time recovery ON, automated snapshots (7–35 days).

**Weekly logical dump** (belt and braces, restorable anywhere):

```sh
pg_dump "$DATABASE_URL" -Fc -f baltic_bridge_$(date +%F).dump
aws s3 cp baltic_bridge_$(date +%F).dump s3://<backup-bucket>/pg/ --sse AES256
```

Schedule via EventBridge Scheduler → the ops jump host or a one-off ECS task.

**Restore procedure (tested 2026-07-25 against Postgres 16):**

```sh
# 1. Create an empty target database
psql "$ADMIN_URL" -c 'CREATE DATABASE baltic_bridge_restore OWNER baltic;'

# 2. Restore the custom-format dump
pg_restore -d "$RESTORE_URL" --no-owner baltic_bridge_YYYY-MM-DD.dump

# 3. Integrity check — counts must match expectations from monitoring
psql "$RESTORE_URL" -c 'SELECT count(*) FROM companies;'
psql "$RESTORE_URL" -c "SELECT count(*) FROM verification_cases WHERE state='verified';"
psql "$RESTORE_URL" -c 'SELECT count(*) FROM audit_events;'

# 4. Point the app at the restored DB (staging first), verify /api/healthz,
#    sign in as ops, spot-check a company 360 and the RFQ pipeline.
```

Last test result: full dump/restore round-trip with 32 companies,
9 verified cases, 7 deals and 1 011 audit events intact.

## Jobs

- Nightly expiry sweep: pg-boss cron `0 2 * * *` in-process; can also be
  triggered via `POST /api/jobs/expiry` (Bearer `CRON_SECRET` or ops session).
- Outbox dispatcher: every minute; unprocessed events are retried.
- If jobs stall: check `pgboss.job` table depth (CloudWatch alarm) and app logs.

## Demo / test data

- `npm run db:seed` — corridor LT→SE, ten-requirement catalogue, ops users.
- `npx tsx src/db/seed-demo.ts` — ten test suppliers (6 verified, 2 in review,
  1 auto-expired, 1 draft), capacity listings, buyers, RFQs across the
  pipeline, offers with frozen snapshots and a recorded deal.
- `npx tsx src/db/smoke.ts` — full M1+M2+M3 assertion suite against the DB.

## E2e

`npx playwright test` — three critical flows (verify supplier, publish
profile, RFQ → recorded deal) against `http://localhost:3100`. In CI or
sandboxes with a pre-installed browser, set `CHROMIUM_PATH`.

## Rate limits (tuned for Phase 0–1 scale)

| Endpoint | Limit |
|---|---|
| `POST /api/v1/auth/register` + register action | 10/h per IP |
| `POST /api/v1/rfqs` + request-work action | 20/h per IP |

In-memory store — correct for the single-container deployment; revisit when
scaling out.

## Incident quick checks

1. `/api/healthz` — DB reachability.
2. `SELECT count(*) FROM outbox_events WHERE processed_at IS NULL;` — event
   backlog (dispatcher stalled?).
3. `SELECT state, count(*) FROM verification_cases GROUP BY 1;` — unexpected
   mass-expiry indicates an expiry-engine or clock problem; audit_events has
   the full trail.
4. Badge dispute: `SELECT * FROM audit_events WHERE entity_id = $case_id
   ORDER BY occurred_at;` — the verification history is the source of truth.
