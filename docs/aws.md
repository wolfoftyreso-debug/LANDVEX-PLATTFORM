# AWS — the runbook

This is the AWS-native path: ECR → ECS Fargate → ALB, Aurora PostgreSQL,
Secrets Manager, CloudWatch. For the EC2/systemd handoff see
[`aws-deployment.md`](aws-deployment.md); for the generic container path
see [`DEPLOY.md`](DEPLOY.md).

Everything below has been run except the four steps marked **needs an
AWS account** — those are the ones nobody can run from a build machine,
and they are written out so that running them is transcription, not
design.

---

## 0. The one thing to know first

The container runs its own preflight before it serves anything:

```
CMD python -m scripts.preflight --gate && exec gunicorn api.main:app ...
```

`LANDVEX_PREFLIGHT` decides what a failed check costs:

| value | effect |
|---|---|
| `strict` | the task refuses to start (**what the task definition sets**) |
| `warn` | it starts, and the reasons are the first lines in CloudWatch |
| `off` | no check at all |

Run the same thing locally at any time:

```bash
make preflight              # exits 1 if this machine is not ready
make env-template           # writes .env.example from the registry
python3 -m scripts.preflight --json | jq .counts
```

The registry behind it is `engine/deployment.py`: 66 variables, each
with the only line that matters at deploy time — **what happens if it is
not set.** A test asserts in both directions, so a variable the code
reads cannot go undocumented and a documented variable cannot be
fiction.

---

## 1. Build and push the image

```bash
make smoke                                        # compile + 72 suites
aws ecr create-repository --repository-name landvex/opportunity-engine
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
docker build -t landvex/opportunity-engine:1.1.0 .
docker tag  landvex/opportunity-engine:1.1.0 \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/landvex/opportunity-engine:1.1.0"
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/landvex/opportunity-engine:1.1.0"
```

The image runs as uid 10001, writes only to `/data` and
`/var/log/landvex`, and contains `engine api integrations frontend
scripts`. The probes travel with it on purpose: `verified_live` can only
be confirmed where the network is open, and that is the deployed
environment, not a build machine.

**needs an AWS account.**

---

## 2. Secrets — five of them

Only five values are secret. Everything else is a URL and belongs in the
task definition where it can be read and reviewed.

```bash
aws secretsmanager create-secret --name landvex/api-keys      \
  --secret-string 'k1:acme:analyst:pro,k2:beta:admin'
aws secretsmanager create-secret --name landvex/jwt-secret    \
  --secret-string "$(openssl rand -hex 32)"
aws secretsmanager create-secret --name landvex/pg-dsn        \
  --secret-string 'postgresql://landvex:...@cluster.eu-north-1.rds.amazonaws.com:5432/landvex'
aws secretsmanager create-secret --name landvex/trafikverket-key --secret-string '...'
aws secretsmanager create-secret --name landvex/openaq-key      --secret-string '...'
```

The execution role policy is written out at
`deploy/aws/execution-role-policy.json`: `GetSecretValue` on exactly
those five ARNs — not on `landvex/*`, which grows silently and makes the
next secret anyone puts under that prefix readable by this task without
a decision. Two tests hold it against the task definition in both
directions, because a secret the task names but the role cannot read
makes the task fail to start with an error that quotes an ARN and
nothing else.

`LANDVEX_API_KEYS` is the one that matters most. Without it **and**
without `LANDVEX_JWT_SECRET`, every caller is an admin of tenant `dev`
on the enterprise plan; tenant isolation is enforced per tenant, and
everyone would be the same tenant. Preflight calls that out as a
blocking combination, and `strict` turns it into a task that never
reaches the load balancer.

**needs an AWS account.**

---

## 3. Database — Aurora PostgreSQL

Set `LANDVEX_PG_DSN` and `LANDVEX_DB=off`. The schema creates itself on
first start with idempotent DDL, which matters because two tasks start
at the same moment and both run it — a test asserts there is no
non-idempotent `CREATE` or `ADD COLUMN` in the Postgres DDL.

Why not SQLite on EFS: one file, one writer. The task definition runs
2 tasks × 2 workers = 4 writers, and quota counting and the decision
ledger would diverge in silence. Preflight computes that number from
`LANDVEX_REPLICAS × WEB_CONCURRENCY` and refuses. A single task with
`WEB_CONCURRENCY=1` and a mounted volume **is** a legitimate SQLite
deployment — preflight lets that one through and prints the ceiling it
buys instead of crying wolf.

PostGIS is not required for anything currently built.

**needs an AWS account.**

---

## 4. Register the task and the service

`deploy/aws/task-definition.json` is ready to register. Substitute
`${AWS_ACCOUNT_ID}`, `${AWS_REGION}`, `${IMAGE_TAG}` and run:

```bash
aws ecs register-task-definition --cli-input-json file://deploy/aws/task-definition.json
aws ecs create-service --cluster landvex \
  --service-name opportunity-engine \
  --task-definition landvex-opportunity-engine \
  --desired-count 2 --launch-type FARGATE \
  --health-check-grace-period-seconds 30 \
  --load-balancers targetGroupArn=$TG_ARN,containerName=app,containerPort=8000
```

Four things in that file are load-bearing, and each has a test:

- every name under `environment` and `secrets` exists in the registry —
  a task that sets `LANDVEX_DATABASE_URL` would register without protest
  and do nothing;
- no variable marked secret appears under `environment`, where its value
  is visible to anyone with `ecs:DescribeTaskDefinition`;
- `stopTimeout` (35 s) outlives gunicorn's `--timeout` (30 s), so
  in-flight requests finish instead of being cut;
- the published port, `LANDVEX_PORT`, `EXPOSE` and the health check URL
  are the same number.

`desired-count` must match `LANDVEX_REPLICAS` in the task definition.
That is the one value in the file duplicated outside it — preflight
judges the storage choice from it, and if the service runs 6 tasks while
the definition says 2, preflight will judge a smaller deployment than
the real one.

**needs an AWS account.**

---

## 5. Load balancer

Target group: HTTP, port 8000, health check path `/health`, interval
15 s, healthy threshold 2, matcher 200. Idle timeout 65 s — above the
slowest endpoint's ceiling.

`/health` answers without auth and reports which sources are live, which
are mock, and the engine version. Everything under `/v1/` requires
`X-API-Key` or a Bearer token once section 2 is done.

---

## 6. Logs

`awslogs` to `/ecs/landvex-opportunity-engine`. Every request writes one
JSON line to stdout — `ts, request_id, tenant, role, key_id, method,
path, status, duration_ms` — so a CloudWatch Logs Insights query works
without any parsing rule:

```
fields @timestamp, tenant, path, status, duration_ms
| filter ispresent(tenant)
| stats count(), pct(duration_ms, 95) by tenant, path
```

The query string is stripped from `path` before it is logged, so a key
passed as a query parameter cannot end up in CloudWatch.

`LANDVEX_AUDIT_LOG` additionally keeps a file for `GET /v1/audit`. On
Fargate that file is per-task and dies with the task — the durable copy
is CloudWatch, and `/v1/audit` shows only what the answering task saw.
That is a known limit, not a bug to be surprised by later.

---

## 7. After the first deploy — the part only AWS can do

Two things are unverifiable from a build machine and become verifiable
the moment the service has open egress:

```bash
# Inside a running task, or anywhere with real network:
python3 -m scripts.sensor_probe all      # which sensor feeds actually answer
python3 -m scripts.register_probe all    # which business registers answer
```

Every adapter currently carries `verified_live = False`. That is not
pessimism — it is that nothing here has ever received a byte from those
hosts, because this repository is built behind a proxy that refuses
outbound CONNECT. The probes classify a firewall block differently from
a broken adapter (a TCP check that succeeds through a proxy while the
fetch fails once wrote down a blocked firewall as a broken adapter —
that is fixed and tested). Set `verified_live = True` by hand for the
sources that answered, and only those.

`engine/datasources/verified.json` is gitignored deliberately: it is the
result from one machine's network, and committing it would make the
whole project look verified everywhere it has never been tried.

Then:

```bash
make readiness BASE=https://opportunity.landvex.com    # every endpoint
make measure-live                                      # the live path's real latency
```

`make measure` runs in CI, deliberately without `--live`: a build must
not depend on a third party's uptime or hit a public authority API on
every push. The live number is measured where someone chose to call out.

---

## 8. Rollback

The image tag is the unit of rollback. Re-register the previous task
definition revision and update the service:

```bash
aws ecs update-service --cluster landvex --service opportunity-engine \
  --task-definition landvex-opportunity-engine:<previous-revision>
```

Schema migrations are additive (`ADD COLUMN IF NOT EXISTS`), so an older
image runs against a newer schema. The reverse — a newer image against
an older schema — is what the idempotent DDL handles at start.

---

## Checklist

- [ ] `make smoke` green
- [ ] image pushed to ECR
- [ ] five secrets created, execution role scoped to those five ARNs
- [ ] Aurora reachable from the task's security group
- [ ] `desired-count` == `LANDVEX_REPLICAS`
- [ ] first task started (preflight `strict` — a start means it passed)
- [ ] `/health` green through the ALB
- [ ] probes run, `verified_live` set only for sources that answered
- [ ] `make measure-live` recorded once, as the live baseline
