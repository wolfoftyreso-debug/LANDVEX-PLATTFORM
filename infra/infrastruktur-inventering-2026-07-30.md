# Infrastrukturinventering — Landvex Opportunity Engine → K8s beta

*Inventerat 2026-07-30. Inga ändringar gjorda.*

---

## 1. Kubernetes-runtime

**Finns: Ja — EKS-kluster `landvex-prod` i eu-north-1**

| Parameter | Värde |
|-----------|-------|
| Klusternamn | `landvex-prod` |
| Region | `eu-north-1` |
| K8s version | 1.34 (platform eks.28) |
| VPC | `vpc-0a555e90cae995e95` — CIDR `192.168.0.0/16` |
| Skapad av | eksctl 0.229.0 (CloudFormation-stack `eksctl-landvex-prod-cluster`) |
| Tagg Project | `vims` (klustret taggas mot VIMS-projektet, inte Landvex) |
| Tagg Environment | `production` |
| Endpoint | Publik (`endpointPublicAccess: true`), privat stängd |
| OIDC | Finns — `oidc.eks.eu-north-1.amazonaws.com/id/A0565AD7CB0CCF716E304711A810C6FE` — **men OIDC-federation är NOT enabled** (`alpha.eksctl.io/cluster-oidc-enabled: "false"`). IRSA (IAM Roles for Service Accounts) fungerar inte utan att OIDC-provisioneringen aktiveras. |
| Control plane logging | **Av** — api, audit, authenticator, controllerManager, scheduler loggar ingenting till CloudWatch |

### Nodgrupp `ng-1356ccad`

| Parameter | Värde |
|-----------|-------|
| Instanstyp | `t3.medium` (2 vCPU, 4 GB RAM) |
| Kapacitet | min 1 / max 4 / desired **2** |
| AMI | AL2023 x86_64 |
| Subnets | 3 subnets i EKS VPC |

**Installerade addons:** `coredns`, `kube-proxy`, `metrics-server`, `vpc-cni`

### Saknas / kritiska luckor

- ❌ **Ingen ingress-controller** — varken AWS Load Balancer Controller eller nginx-ingress finns som EKS-addon eller Helm-release. Ingen Service kan exponeras externt utan detta.
- ❌ **Ingen External Secrets Operator / Secrets Manager CSI-driver** — hemlighetsinjektion till pods saknar infrastruktur.
- ❌ **Ingen OIDC-federation aktiverad** — IRSA-baserade IAM-roller fungerar inte förrän `eksctl utils associate-iam-oidc-provider` körs.
- ❌ **Inget Helm- eller Kustomize-mönster etablerat** — inga andra workloads är driftsatta i klustret, det finns inget befintligt mönster att följa. Klustret är i praktiken tomt.
- ℹ️ Namespace-konvention: okänd — ingen aktiv workload att utgå ifrån.

---

## 2. Migreringsscope

**Svar: Landvex är den enda kandidaten — resten av stacken lever på EC2 och är inte på väg in i klustret.**

Befintliga workloads på `server-2` (16.170.83.169, `vpc-006eefbc6e0546f49`, CIDR `172.31.0.0/16`):

- AMOS Core (systemd, port 3100 via nginx proxy)
- Landvex Opportunity Engine (**redan igång** — se punkt 3)
- quiXzoom-dashboard, BOC, KYC-service, Vyra, n8n, Mailu, Gitea (nginx-reverse-proxy), Grafana, ClickHouse, pgbouncer m.fl.

Det finns ingen signal om att dessa ska in i EKS — klustrets `Project: vims`-tagg tyder på att det skapades för ett annat ändamål och nu repurposeas för Landvex. **Landvex blir first-mover in i klustret.**

---

## 3. Databas

**Kritisk observation: Landvex Opportunity Engine kör redan på `:8087` via systemd — och den databas den använder är lokal PostgreSQL på server-2.**

### Databaser

| Databas | Plats | Anslutning | Status |
|---------|-------|-----------|--------|
| `landvex` | Lokal PostgreSQL på server-2 (pid 7750) | `localhost:5432` (native) / `localhost:6432` (pgbouncer) | ✅ Aktiv, används av :8087-processen |
| `amos`, `wavult_identity` m.fl. | Lokal PostgreSQL server-2 | pgbouncer proxy → `platform-identity-core.cvi0qcksmsfj.eu-north-1.rds.amazonaws.com:5432` | RDS via pgbouncer |
| RDS `quixzoom-db` | `quixzoom-db.cvi0qcksmsfj.eu-north-1.rds.amazonaws.com` | db.t4g.micro, PostgreSQL | ✅ available |

**Aurora PostgreSQL finns inte** — bara `quixzoom-db` som är en vanlig RDS `db.t4g.micro`. Ingen Aurora-kluster hittades i `describe-db-clusters`.

**pgbouncer-konfigurationen** (Docker, `127.0.0.1:6432`) proxar `amos`/`wavult_identity`/`ouroboros` mot RDS:en — men `landvex`-databasen är **inte** konfigurerad i pgbouncer. Den nås direkt lokalt.

**PostGIS:** Okänt om det är installerat i `landvex`-databasen — behöver verifieras med `\dx` mot den.

**Konsekvens för K8s-deployment:** En pod i EKS VPC (`192.168.0.0/16`) kan inte nå `localhost:5432` på server-2 (`172.31.x.x`). Ni behöver antingen:
- Provisionera en RDS-instans i EKS VPC (eller tillgänglig via peering), **eller**
- Exponera befintlig lokal Postgres via intern DNS/peering (osäker lösning för produktion)

---

## 4. Domän & routing

### Nuläge

| Domän | Var | Certifikat | Backend |
|-------|-----|-----------|---------|
| `landvex.com` | Route53 → CloudFront | ACM saknas för landvex.com i eu-north-1 | Statisk site (CloudFront → `/opt/amos/public`) |
| `api.landvex.com` | Route53 → server-2 (16.170.83.169) | **Let's Encrypt** (self-managed, `/etc/letsencrypt/live/api.landvex.com/`) | nginx → port 7073 och 3250 |
| `admin.landvex.com` | server-2 nginx | Let's Encrypt | lokal admin-UI |
| `cc.landvex.com`, `finance.landvex.com` | server-2 nginx | Let's Encrypt | diverse backends |

**ACM-certifikat i eu-north-1:** Inget utfärdat cert täcker `landvex.com`, `*.landvex.com` eller `opportunity.landvex.com`. Befintliga ACM-cert täcker `*.wavult.com`, `*.aamos.systems`, `quixzoom.*`-varianter.

**`opportunity.landvex.com` existerar inte** — varken som Route53-record eller som ACM-cert.

### För K8s-ingress behöver ni

1. Nytt ACM-cert för `opportunity.landvex.com` (DNS-validerat mot `landvex.com`-zonen i Route53, zon-ID: `Z05966261S4KJRAGIJ6FQ`)
2. Route53 A/ALIAS-record `opportunity.landvex.com` → K8s ingress-controller LB
3. Klargörande: ska den ersätta `api.landvex.com` (som idag pekar mot port 7073) eller köras parallellt?

---

## 5. Nätverksväg till AAMOS/quiXzoom

### VPC-topologi

```
server-2          vpc-006eefbc6e0546f49   172.31.0.0/16
                        ↕ pcx-0e89bc08ed603f2e7 (ACTIVE)
platform-vpc      vpc-0e880ea5814b9f1be   10.0.0.0/16  [aplatform-platform-vpc, Terraform]
                        ↕ pcx-0f5c3881ede98d02b (ACTIVE)
financial-vpc     vpc-06609c6f597a7fd15   10.10.0.0/16 [aplatform-financial-vpc]

EKS-kluster       vpc-0a555e90cae995e95   192.168.0.0/16  ← ISOLERAD, INGEN PEERING
```

**EKS VPC är inte peerat med någon av de andra VPC:erna.** En pod i klustret kan inte nå AMOS Core på `172.31.x.x:3100` via privat nät.

### Alternativ för att nå AAMOS från pods

| Alternativ | Beskrivning | Krav |
|-----------|-------------|------|
| **A) Publik endpoint** | Via `amos.aamos.systems` (nginx-proxad, TLS). Fungerar utan ändringar men exponerar intern-API publikt. | Inga infra-ändringar |
| **B) VPC-peering** | `vpc-0a555e90cae995e95 ↔ vpc-006eefbc6e0546f49`. Privat och säkert. | Peering + route tables + SG-öppningar + DNS-resolution på peering |
| **C) AWS PrivateLink** | Renast isolering, skalbart. | NLB + endpoint-service på server-2-sidan |

Ingen av dessa är på plats idag. **Strategi måste beslutas innan pods kan nå AAMOS/quiXzoom privat.**

---

## 6. Registry & CI

**ECR-repo `landvex/opportunity-engine`: Finns inte.** Sökte explicit — `RepositoryNotFoundException`.

Befintliga Landvex-relaterade ECR-repos: inga (varken `landvex/*` eller `opportunity*`).

### Gitea-repos med Landvex-koppling

| Repo | CI-pipeline | Notering |
|------|------------|---------|
| `platform-admin/landvex-api` | `deploy-landvex-api.yml` ✅ | Finns men ECR-target-repo saknas |
| `platform-admin/landvex-web` | Okänt | — |
| `platform-admin/landvex.com` | Okänt | — |
| `platform-group/youtube-landvex` | Okänt | — |

### Befintlig CI i `landvex-api` (`deploy-landvex-api.yml`)

- **Trigger:** push till `main`, path `apps/landvex-api/**`
- **Auth:** Statiska `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` i Gitea Secrets (ej OIDC)
- **Target ECR:** `155407238699.dkr.ecr.eu-north-1.amazonaws.com/landvex-api:latest`
- **Problem:** ECR-repo `landvex-api` finns **inte** i ECR — pipeline fungerar inte i nuläget

### För Opportunity Engine behöver ni

1. Skapa ECR-repo `landvex/opportunity-engine`
2. Ny pipeline eller utöka befintlig i `platform-admin/landvex-api` (eller eget repo för engine-koden)
3. Beslut: OIDC-baserad IAM-roll (rekommenderat, kräver OIDC aktiverat på klustret) eller fortsätta med statiska nycklar

---

## 7. Kompletterande inventering — saknade avsnitt

### Gitea-repos (inventerade)

Landvex-specifika: `landvex-api`, `landvex-web`, `landvex.com`, `youtube-landvex`.
Inget repo heter `landvex-opportunity-engine` eller liknande.

### Databaser på server-2 (lokal PostgreSQL, port 5432)

| Databas | Ägare | Notering |
|---------|-------|---------|
| `landvex` | postgres | Aktiv — används av Opportunity Engine på :8087 |
| `aamos` | amos | AAMOS Core |
| `aamos_api_gateway` | postgres | — |
| `aamos_ledger` | postgres | — |
| `agent_communication` | postgres | — |
| `amos` | wavult_admin | RDS-spegel via pgbouncer |
| `boc` | postgres | BOC-stack |
| `putte_platform` | putte | — |
| `quixzoom_dev_api` | postgres | — |
| `quixzoom_shop` | postgres | — |
| `wavult_identity` | wavult_admin | Identity/Auth |

### pgbouncer

Docker `pgbouncer-arm64:1.23.1`, lyssnar `127.0.0.1:6432`.
Proxar `amos`, `wavult_identity`, `ouroboros` → `platform-identity-core.cvi0qcksmsfj.eu-north-1.rds.amazonaws.com`.
Wildcard `*`-regel mot samma RDS.
**`landvex`-databasen är inte konfigurerad i pgbouncer.**

### RDS

| Instans | Engine | Klass | Status |
|---------|--------|-------|--------|
| `quixzoom-db` | postgres | db.t4g.micro | available |
| `platform-identity-core` | postgres | okänt | används via pgbouncer men syns ej i describe-db-instances — sannolikt i annan VPC |

### Redis

| Instans | Port | Notering |
|---------|------|---------|
| `mailu-redis-1` | intern | Mailu-stack |
| `boc-redis` | 0.0.0.0:6381 | BOC-stack |
| Okänd | 0.0.0.0:6380 | Ej identifierad i denna körning |
| Cloud Map `redis.wavult.local:6379` | intern | ECS-worker-nät |

### ClickHouse

Docker `clickhouse/clickhouse-server:24.4-alpine`, portar 8123 (HTTP) och 9000 (native). Auth-konfigurerad.

### REXO-pipeline (`/opt/amos/rexo-build/`)

Innehåll: `army-orchestrator.mjs`, `rufus-burst.mjs`, `sven-burst.mjs`, `worker.mjs`, `parallel-burst.mjs`, `ollama-worker.mjs`, `artifacts/`, `logs/`, `plan/`.
Senast modifierad Jul 2026.
**Inte kopplat till Kubernetes** — kör direkt mot lokal Ollama/GPU på server-2.

---

## Sammanfattning — vad som måste vara på plats före K8s-driftsättning

| # | Vad saknas | Prioritet |
|---|-----------|-----------|
| 1 | Ingress-controller (AWS LB Controller eller nginx-ingress) i `landvex-prod` | 🔴 Blocker |
| 2 | ECR-repo `landvex/opportunity-engine` skapad | 🔴 Blocker |
| 3 | OIDC-federation aktiverad på klustret (för IRSA) | 🔴 Rekommenderas starkt |
| 4 | Databas nåbar från EKS VPC — RDS i rätt VPC, eller VPC-peering | 🔴 Blocker |
| 5 | ACM-cert för `opportunity.landvex.com` | 🟡 Krävs för TLS |
| 6 | Route53-record `opportunity.landvex.com` | 🟡 Krävs för routing |
| 7 | Nätverksväg EKS → AAMOS (VPC-peering eller publik endpoint) | 🟡 Beroende på engine-krav |
| 8 | Secrets Operator eller CSI-driver för Secrets Manager i K8s | 🟡 Krävs för deployment.py-variabler |
| 9 | CI-pipeline för `opportunity-engine` → ECR → K8s | 🟡 Krävs för automatiserat flöde |
| 10 | Control plane logging aktiverat | 🟢 Best practice |

### Det som redan finns och fungerar

- EKS-klustret är aktivt med 2 noder
- OIDC-provider existerar (men inte kopplad till federation)
- Engine kör live på `:8087` med lokal Postgres (dev_server, systemd)
- Domänzonen `landvex.com` i Route53 redo för nya records (zon-ID: `Z05966261S4KJRAGIJ6FQ`)
- CI-infrastrukturen i Gitea existerar med fungerande deploy-mönster
