# Kubernetes — the runbook

This is the `landvex-prod` EKS path. For the AWS-native ECS path see
[`aws.md`](aws.md); for the EC2/systemd handoff see
[`aws-deployment.md`](aws-deployment.md).

Everything here is grounded in a real inventory of the cluster, run by
the infrastructure agent on 2026-07-30 (kept in full at
`infra/infrastruktur-inventering-2026-07-30.md`). Nothing below has been
applied to `landvex-prod` — the manifests exist in this repo
(`deploy/k8s/`), and every step that touches AWS is marked **needs
cluster-admin access to landvex-prod**.

---

## 0. What that inventory actually found

`landvex-prod` (eu-north-1, EKS 1.34, VPC `192.168.0.0/16`) exists and
has two `t3.medium` nodes, but it is otherwise empty: no other workload
runs there, so there is no existing Helm/Kustomize/namespace convention
to match — the choices below are the first ones made for this cluster,
not a continuation of one.

Five things are missing that block a real deployment:

| # | Gap | Blocks |
|---|-----|--------|
| 1 | No ingress-controller (no AWS Load Balancer Controller, no nginx-ingress) | any Service reaching the internet |
| 2 | ECR repo `landvex/opportunity-engine` does not exist | pushing an image at all |
| 3 | OIDC federation not enabled on the cluster (`alpha.eksctl.io/cluster-oidc-enabled: "false"`) | IRSA — the AWS Load Balancer Controller needs this |
| 4 | No database reachable from the EKS VPC — it is not peered with any other VPC, and the running instance's own Postgres (`server-2`, `172.31.x.x`) is on a different, unpeered VPC | persistence with more than one replica |
| 5 | No ACM certificate for `opportunity.landvex.com` (or any `landvex.com` variant) | TLS on the ingress |

And one fact worth being explicit about: **Landvex Opportunity Engine is
already running** — on `server-2`, port `:8087`, systemd, against a
local PostgreSQL database named `landvex`. That deployment is not
affected by anything below; this is a second, additional path, not a
replacement in progress.

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

**D2 — Database: a new RDS Postgres instance inside the EKS VPC**, not
peering to `server-2`'s local Postgres and not the existing
`quixzoom-db` (which lives in a different, unpeered VPC). The inventory
itself calls peering-to-a-local-Postgres "an uncertain solution for
production" — a fresh instance inside `192.168.0.0/16` has zero
cross-VPC dependency and needs no peering decision at all. Aurora is not
required — nothing built uses PostGIS yet (same conclusion `aws.md` §3
already reached for the ECS path).

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
aws rds create-db-instance --db-instance-identifier landvex-opportunity \
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

```bash
make smoke                                                  # compile + every suite
docker build -t landvex/opportunity-engine:1.1.0 .
aws ecr get-login-password --region eu-north-1 \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com
docker tag  landvex/opportunity-engine:1.1.0 \
  $AWS_ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/landvex/opportunity-engine:1.1.0
docker push $AWS_ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/landvex/opportunity-engine:1.1.0

cd deploy/k8s
kustomize edit set image \
  landvex/opportunity-engine=$AWS_ACCOUNT_ID.dkr.ecr.eu-north-1.amazonaws.com/landvex/opportunity-engine:1.1.0
kubectl apply -k .
kubectl -n landvex rollout status deployment/landvex-opportunity-engine
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

## Checklist

- [ ] OIDC federation enabled on `landvex-prod` (gap #3)
- [ ] AWS Load Balancer Controller installed (gap #1)
- [ ] ECR repo `landvex/opportunity-engine` created (gap #2)
- [ ] Database reachable from the EKS VPC (gap #4, decision D2)
- [ ] ACM cert for `opportunity.landvex.com` issued (gap #5)
- [ ] Route53 record for `opportunity.landvex.com` pointed at the ALB
- [ ] `landvex-secrets` created in the `landvex` namespace (§3)
- [ ] image pushed, `kubectl apply -k deploy/k8s` rolled out
- [ ] `/health` green through the ALB
- [ ] control plane logging turned on (gap #10 in the inventory — best
      practice, not a blocker)
