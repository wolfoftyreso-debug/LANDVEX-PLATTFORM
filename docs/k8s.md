# Kubernetes — the runbook

This is the `landvex-prod` EKS path. For the AWS-native ECS path see
[`aws.md`](aws.md); for the EC2/systemd handoff see
[`aws-deployment.md`](aws-deployment.md).

**Status: live.** Deployed for real on 2026-07-30
(`infra/aws-svar-2026-07-30-c.md`) — `https://opportunity.landvex.com/health`
answers 200, 2/2 pods, Postgres persistence (`schema_meta version: 19`),
ALB provisioned, ACM cert issued. Everything below is grounded in that
real run, including the five obstacles it hit and how they were closed
(§6). The gaps in §0 are historical — kept for the record, not because
they're still open.

---

## 0. What that inventory actually found (2026-07-30, before deploy)

`landvex-prod` (eu-north-1, EKS 1.34, VPC `192.168.0.0/16`) existed and
had two `t3.medium` nodes, but was otherwise empty: no other workload
ran there, so there was no existing Helm/Kustomize/namespace convention
to match — the choices below were the first ones made for this cluster,
not a continuation of one. (The nodegroup is now 4 nodes — see §6.)

Five things were missing before the deploy, all closed same-day:

| # | Gap | Blocks |
|---|-----|--------|
| 1 | No ingress-controller (no AWS Load Balancer Controller, no nginx-ingress) | any Service reaching the internet |
| 2 | ECR repo `landvex/opportunity-engine` does not exist | pushing an image at all |
| 3 | OIDC federation not enabled on the cluster (`alpha.eksctl.io/cluster-oidc-enabled: "false"`) | IRSA — the AWS Load Balancer Controller needs this |
| 4 | No database reachable from the EKS VPC — it is not peered with any other VPC, and the running instance's own Postgres (`server-2`, `172.31.x.x`) is on a different, unpeered VPC | persistence with more than one replica |
| 5 | No ACM certificate for `opportunity.landvex.com` (or any `landvex.com` variant) | TLS on the ingress |

And one fact worth being explicit about, **corrected after the 2026-07-30
follow-up** (`infra/aws-svar-2026-07-30.md`): Landvex Opportunity Engine
is already running on `server-2`, port `:8087`, systemd — but against
**SQLite** (`/var/lib/landvex/landvex.db`), not PostgreSQL.
`LANDVEX_PG_DSN` is unset there. A local PostgreSQL database that
happens to be named `landvex` also exists on that host, but it belongs
to an unrelated system (`admin_users`, `data_caches`, `orders`,
`reports`, `users` — none of it Landvex's schema, no PostGIS, no
`schema_meta`). **Do not point `LANDVEX_PG_DSN` at that database** — see
D2 below. That systemd deployment is not affected by anything in this
document; this is a second, additional path, not a replacement in
progress. It is also running an old snapshot of this repo (missing
`scripts/pg_selftest.py` and most of what has shipped since) — worth
refreshing from the current `main`/`claude/new-session-d9t6ni` branch
before relying on it for anything beyond what it already does.

---

## 1. Decisions made in these manifests, and why

Nothing here commits AWS to anything — these are choices baked into
`deploy/k8s/*.yaml`, changeable by editing the files, not the cluster.

**D1 — Ingress: AWS Load Balancer Controller, not nginx-ingress.**
The cluster has no established pattern either way, and the ECS path
already terminates on an ALB (`aws.md` §5) — staying on the same load
balancer family keeps target-group health checks, logging and cert
handling consistent across both deploy paths. Cost: needs OIDC
federation (gap #3) enabled first, since the controller authenticates
via IRSA.

**D2 — Database: a new RDS Postgres instance inside the EKS VPC, with a
database name that is NOT `landvex`.** Not peering to `server-2`'s local
Postgres, and not the existing `quixzoom-db` (different, unpeered VPC).
The inventory itself calls peering-to-a-local-Postgres "an uncertain
solution for production" — a fresh instance inside `192.168.0.0/16` has
zero cross-VPC dependency and needs no peering decision at all. Aurora
is not required — nothing built uses PostGIS yet (same conclusion
`aws.md` §3 already reached for the ECS path).

The name matters because of a real incident found on 2026-07-30: a
database on `server-2` happens to be named `landvex` and already has an
unrelated `reports` table (a different system's schema).
`CREATE TABLE IF NOT EXISTS` silently no-ops against a same-named,
wrong-shaped table — the first real `save_report()` would then fail
with a confusing column error. `PostgresStore.selftest()` now checks
for exactly this (`_verify_shape` in `engine/storage/postgres.py`,
`tests/test_storage.py`) and refuses early with a clear message instead
— but the simplest defense is still to never create the new instance
with that name in the first place.

**D3 — Network path to AAMOS/quiXzoom: the public endpoint
(`amos.aamos.systems`) for beta**, not VPC peering or PrivateLink. Zero
infrastructure change needed, so it does not block getting to beta; the
`configmap.yaml` sets `AAMOS_CORE_URL` to it already. Revisit for a
private path (peering or PrivateLink) once the pilot moves past beta —
routing platform-internal traffic over the public internet is a
deliberate, temporary trade, not the intended end state.

**D4 — Domain: `opportunity.landvex.com` runs alongside
`api.landvex.com`**, not in place of it. `api.landvex.com` already
proxies unrelated ports (7073, 3250) on `server-2` — there is no reason
to touch it.

**D5 — CI auth: OIDC-based IAM role once federation is enabled
(gap #3), static keys as an interim fallback.** The existing
`landvex-api` Gitea pipeline already uses static
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` — that pattern can unblock a
first image push before OIDC is worth the setup cost, but should not be
the permanent answer for a second pipeline.

---

## 2. What must happen in AWS before `kubectl apply` does anything

Each of these **needs cluster-admin access to landvex-prod** — nothing
here can be run from this repository.

```bash
# Gap #3 — OIDC federation (do this first; #1 depends on it)
eksctl utils associate-iam-oidc-provider --cluster landvex-prod --approve

# Gap #1 — AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system --set clusterName=landvex-prod \
  --set serviceAccount.create=true

# Gap #2 — ECR repo
aws ecr create-repository --repository-name landvex/opportunity-engine --region eu-north-1

# Gap #4 — database reachable from the EKS VPC (D2)
# --db-name is deliberately NOT "landvex": a database with that exact
# name already exists on server-2, owned by a different system.
aws rds create-db-instance --db-instance-identifier landvex-opportunity \
  --db-name landvex_opportunity \
  --engine postgres --db-instance-class db.t4g.micro --allocated-storage 20 \
  --vpc-security-group-ids <sg-in-vpc-0a555e90cae995e95> \
  --db-subnet-group-name <subnet-group-in-eks-vpc> \
  --master-username landvex --manage-master-user-password

# Gap #5 — ACM certificate, DNS-validated against the existing zone
aws acm request-certificate --domain-name opportunity.landvex.com \
  --validation-method DNS --region eu-north-1
# then add the validation CNAME to zone Z05966261S4KJRAGIJ6FQ, and once
# issued, put the certificate ARN into deploy/k8s/ingress.yaml
```

**needs cluster-admin access to landvex-prod.**

---

## 3. Secrets — before an Operator exists

Gap #8 (no External Secrets Operator / Secrets Manager CSI driver) means
there is no automated path from Secrets Manager into the cluster yet.
Until that is provisioned, create the `Secret` object directly —
`deploy/k8s/secret.example.yaml` is the template, never the real file:

```bash
kubectl create secret generic landvex-secrets -n landvex \
  --from-literal=LANDVEX_API_KEYS='k1:acme:analyst:pro' \
  --from-literal=LANDVEX_JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=LANDVEX_PG_DSN='postgresql://landvex:...@<rds-endpoint>:5432/landvex' \
  --from-literal=LANDVEX_TRAFFIC_KEY='...' \
  --from-literal=LANDVEX_AIR_KEY='...'
```

Same five values as the ECS path (`aws.md` §2) — `tests/test_k8s.py`
holds the two lists equal so they cannot drift apart.

---

## 4. Build, push, deploy

The `landvex-prod` nodegroup is AL2023 **x86_64**. Build for that
architecture explicitly — a build machine that's arm64 (server-2 is)
produces an image that fails every pod with `exec format error` and
never says why. `buildx` targets the right platform regardless of what
the build machine itself is:

```bash
make smoke                                                  # compile + every suite
docker buildx build --platform linux/amd64 \
  --tag $AWS_ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/landvex/opportunity-engine:1.1.0 \
  --push .
```

(`aws ecr get-login-password ... | docker login ...` first, same as
`aws.md` §1, if the registry session has expired.)

```bash
cd deploy/k8s
```

If `kustomize` is installed: `kustomize edit set image
landvex/opportunity-engine=$AWS_ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/landvex/opportunity-engine:1.1.0`.
If it isn't (it wasn't on the box used for the first deploy), edit
`kustomization.yaml`'s `images:` block by hand with the same values —
`newName` + `newTag`, not a raw string substitution.

**`${ACM_CERTIFICATE_ARN}` in `ingress.yaml` needs a manual edit too** —
`kustomize`'s `images:` transformer only rewrites the image reference,
it does not substitute arbitrary `${...}` placeholders in annotations.
Replace that one line with the real ACM ARN from gap #5 before
applying (or add a proper `replacements:` transformer to
`kustomization.yaml` if this becomes a recurring redeploy step worth
automating).

```bash
kubectl apply -k .
kubectl -n landvex rollout status deployment/landvex-opportunity-engine --timeout=120s
```

**needs cluster-admin access to landvex-prod.**

---

## 5. Verify

```bash
kubectl -n landvex get pods                     # 2/2 Running
kubectl -n landvex logs deploy/landvex-opportunity-engine | head  # preflight's own summary
curl -sf https://opportunity.landvex.com/health  # once gaps #1 and #5 are closed
```

`/health` reports engine version and per-source status the same way it
does on every other deploy path — nothing about that response changes
because the runtime is Kubernetes.

---

## 6. Lessons from the first real deploy (2026-07-30)

Five obstacles came up that nothing above predicted. Kept here so the
next redeploy — or the next cluster — doesn't rediscover them the hard
way.

| Obstacle | Cause | Fix |
|---|---|---|
| `exec format error` at pod start | Image built arm64 (server-2's own architecture) against amd64 nodes | `docker buildx build --platform linux/amd64` (now the documented command in §4) |
| `ModuleNotFoundError: No module named 'psycopg'` at pod start | `psycopg[binary]` was commented out in `requirements.txt` | Uncommented — it's a hard production dependency now that both deploy paths promise Postgres. `tests/test_deploy.py::test_psycopg_ships_whenever_a_deploy_path_promises_postgres` holds this from drifting back |
| Pods stuck `Pending` — `Insufficient cpu/memory` | The two `t3.medium` nodes were already ~80% allocated before this deployment's requests | Nodegroup scaled 2 → 4. If the cluster stays this size, `deployment.yaml`'s resource requests (`500m`/`1Gi` × 2 replicas) are worth revisiting against whatever else lands in the cluster |
| ALB address never appeared, `ec2:CreateSecurityGroup` 403 in the controller's logs | The IRSA role backing the AWS Load Balancer Controller had `ElasticLoadBalancingFullAccess` attached instead of the controller's own `AWSLoadBalancerControllerIAMPolicy` | Swapped the policy, recycled the controller pods so they picked up a fresh IRSA token |
| `${ACM_CERTIFICATE_ARN}` left as a literal string in the applied Ingress | `kustomize` wasn't installed on the deploy box, so the substitution never ran (and even with `kustomize` present, `images:` doesn't touch annotations — see §4) | Edited `ingress.yaml`'s annotation directly with the real ARN before applying |

What that run confirmed working exactly as designed: `pg_selftest`
against the new RDS instance printed `schema_meta version: 19` and
`PostgresStore matches the reference migration chain` on the first try;
preflight's `strict` gate started cleanly with no open-API warning
(`landvex-secrets` was mounted correctly); and `/health` came up
reporting **more** connected sources than server-2 ever had — not a
bug, just that `deploy/k8s/configmap.yaml` mirrors the full source URL
list from `deploy/aws/task-definition.json` (Kolada included), while
server-2's hand-written `/etc/landvex/opportunity.env` only ever set
the minimum to get the service running.

---

## Checklist

- [x] OIDC federation enabled on `landvex-prod` (gap #3)
- [x] AWS Load Balancer Controller installed (gap #1)
- [x] ECR repo `landvex/opportunity-engine` created (gap #2)
- [x] Database reachable from the EKS VPC (gap #4, decision D2) — RDS
      `landvex_opportunity`, schema at version 19
- [x] ACM cert for `opportunity.landvex.com` issued (gap #5)
- [x] Route53 record for `opportunity.landvex.com` pointed at the ALB
- [x] `landvex-secrets` created in the `landvex` namespace (§3)
- [x] image pushed, `kubectl apply -k deploy/k8s` rolled out
- [x] `/health` green (confirmed pod-internal; ALB target health was
      still `RegistrationInProgress` as of the last report — re-check
      `curl -sf https://opportunity.landvex.com/health` if it's been a
      while since 2026-07-30)
- [ ] control plane logging turned on (gap #10 in the inventory — best
      practice, not a blocker)
