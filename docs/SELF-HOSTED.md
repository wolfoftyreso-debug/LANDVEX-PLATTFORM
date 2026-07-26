# Self-owned infrastructure — dependency audit & runbook

**Status:** July 2026 · prepared for the decision to run fully self-owned AWS
infrastructure (own EC2/compute, self-managed Postgres, no managed-service
lock-in, no third-party SaaS).

The application was built as one deployable container against portable
interfaces, so the move is configuration, not a rewrite.

## 1. External-dependency audit

Every integration point in the app, what it binds to, and its self-hosted
replacement:

| Concern | Interface in code | Managed mode (today's default) | Self-owned mode | Switch |
|---|---|---|---|---|
| Database | `pg` Pool via `DATABASE_URL` (`src/lib/db.ts`) | RDS PostgreSQL 16 | Self-managed Postgres 16 (container or EC2 install) | `DATABASE_URL` only — no RDS-specific features are used (no IAM auth, no RDS proxy) |
| Migrations | drizzle-kit, append-only SQL in `drizzle/` | same | same | none — plain SQL over the same connection |
| File storage | S3 API via `@aws-sdk/client-s3` + presigned URLs (`src/modules/documents/service.ts`) | Amazon S3 | MinIO (S3-compatible, self-hosted) | `S3_ENDPOINT` + `S3_FORCE_PATH_STYLE=true` — already how dev runs |
| Email | `EmailProvider` interface (`src/modules/notifications/email.ts`) | SES adapter | **`smtp` adapter (new, dependency-free `node:net`/`node:tls`)** → own Postfix/smarthost; or `console` to disable | `EMAIL_PROVIDER=smtp` + `SMTP_*` vars |
| Auth | Auth.js, JWT sessions, scrypt from `node:crypto` | self-contained | self-contained | nothing external ever (no Cognito, no bcrypt binary) |
| Jobs/cron | pg-boss inside the app container, backed by Postgres | self-contained | self-contained | no SQS/EventBridge required; optional external cron can hit `/api/jobs/expiry` with `CRON_SECRET` |
| Outbox/events | `outbox_events` table + in-process dispatcher | self-contained | self-contained | no broker |
| Search | Postgres FTS (`tsvector`) + `pg_trgm` | in the database | in the database | none |
| Rate limiting | in-memory fixed-window | in-process | in-process | none (single container) |
| Logging | pino → stdout | CloudWatch Logs collects stdout | journald / Loki / plain files — anything that reads stdout | none in code |
| Secrets | env vars validated by Zod (`src/lib/env.ts`) | SSM/Secrets Manager injects at deploy | `.env.selfhost` on the host (root-only perms) or your own vault | none in code |
| Fonts/CDN/analytics | — | — | — | **zero external requests**: system font stack, no CDN scripts, no analytics beacons |

Runtime npm packages that talk to the network: `pg` (your DB),
`@aws-sdk/client-s3`/`s3-request-presigner` (your MinIO), `@aws-sdk/client-sesv2`
(lazy-imported — never loaded unless `EMAIL_PROVIDER=ses`). Nothing phones home;
`NEXT_TELEMETRY_DISABLED=1` is set in the image.

**Conclusion: the only AWS-managed services in use (RDS, S3, SES) are all
behind env-switchable interfaces. Self-owned mode requires zero code changes.**

## 2a. Kubernetes mode (k3s — current default)

The product owner chose Kubernetes as the orchestrator. The Terraform node
(`orchestrator = "k3s"`) runs single-node k3s; the stack (app + Postgres +
MinIO + migrate job + Traefik ingress) is expressed as Kustomize manifests
in [`infra/k8s/`](../infra/k8s/README.md). Same container image, same env
contract (`.env.selfhost` becomes one Kubernetes Secret), same backup
layers. The compose mode below remains fully supported as the simpler
fallback (`orchestrator = "compose"`).

## 2b. Single-node deployment (docker-compose.selfhost.yml)

Production-shaped stack on one machine (EC2 or anything with Docker):
app container + Postgres 16 + MinIO + a one-shot migration runner.

```
cp .env.selfhost.example .env.selfhost      # fill in secrets; chmod 600
docker compose -f docker-compose.selfhost.yml --env-file .env.selfhost up -d --build
docker compose -f docker-compose.selfhost.yml exec app wget -qO- http://localhost:3000/healthz
```

First boot only — seed the catalog and ops users:

```
docker compose -f docker-compose.selfhost.yml run --rm migrate npm run db:seed
```

### Networking / TLS

- The app listens on `127.0.0.1:3000`; put your own reverse proxy (nginx,
  Caddy, or an ALB you operate) in front for TLS on `PUBLIC_BASE_URL`.
- **Presigned URLs:** browsers upload/download directly against
  `S3_ENDPOINT`, so MinIO must be publicly reachable at that exact URL —
  proxy `https://files.<domain>` → `minio:9000` and set `S3_ENDPOINT` to the
  public URL. If the endpoint host differs from what the app signed against,
  every presigned request fails with `SignatureDoesNotMatch`.
- Postgres and the MinIO console stay bound to `127.0.0.1` — reach them over
  SSH only.

### Email without SES

`EMAIL_PROVIDER=smtp` uses the new dependency-free SMTP client
(`src/modules/notifications/smtp.ts`): EHLO → STARTTLS (required whenever
credentials are set — it refuses AUTH over plaintext) → AUTH PLAIN → send.
Point it at your own Postfix container or the org's smarthost. For a mail-less
environment set `EMAIL_PROVIDER=console` (messages go to the logs).

## 3. Backups (self-managed — replaces RDS PITR)

RDS point-in-time recovery does not exist here; own it explicitly:

```
# Nightly logical dump (host cron, 02:30)
docker compose -f docker-compose.selfhost.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" -Fc baltic_bridge > /backups/bb-$(date +%F).dump

# MinIO data: snapshot the miniodata volume or mirror it off-host
docker run --rm -v konditori-joy_miniodata:/data -v /backups:/out alpine \
  tar czf /out/minio-$(date +%F).tgz /data
```

Restore (tested procedure, same as docs/RUNBOOK.md):

```
docker compose -f docker-compose.selfhost.yml exec -T db \
  pg_restore -U "$POSTGRES_USER" -d baltic_bridge --clean --if-exists < bb-YYYY-MM-DD.dump
```

Keep ≥ 14 daily dumps, copy them off the machine (separate account/host), and
**rehearse the restore quarterly** — a backup that has never been restored is
a hope, not a backup. For true PITR later, add WAL archiving
(`archive_command` or pgBackRest) — decide when the deal volume justifies it.

## 4. What stays the same either way

- One deployable container (`Dockerfile`, standalone output) — identical
  image for ECS Fargate or your own Docker host.
- Append-only migrations, audit trail, outbox, RBAC, i18n — all
  infrastructure-agnostic.
- GDPR residency: run the node in `eu-north-1` (or any EU location you
  control); data never leaves your machines in self-owned mode.

## 5. Open decisions before committing to self-owned

1. **IaC convention** — ✅ decided: **Terraform**. The complete layer lives in
   [`infra/terraform/`](../infra/terraform/README.md): VPC, Graviton EC2 node
   (SSM access, no SSH), encrypted data volume + DLM snapshots, S3 backup
   bucket + nightly `pg_dump` cron, CloudWatch alarms with auto-recovery,
   optional Route 53. TLS termination via the optional Caddy front
   (`docker-compose.proxy.yml` + `infra/proxy/Caddyfile`).
2. **S3 vs MinIO in production** — S3 in your own AWS account is not a
   third-party dependency in the SaaS sense; MinIO trades that for
   self-managed durability (versioning is enabled, but replication/erasure
   coding across nodes is on you).
3. **Mail deliverability** — running your own outbound mail means owning
   SPF/DKIM/DMARC and IP reputation; a smarthost you control is usually the
   pragmatic middle ground.
4. **Malware scanning** — GuardDuty S3 scanning doesn't apply to MinIO; the
   scan-hook stub in the documents module needs a ClamAV container behind it
   before public launch.
