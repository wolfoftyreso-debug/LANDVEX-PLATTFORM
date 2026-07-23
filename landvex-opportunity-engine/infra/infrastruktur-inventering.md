# LANDVEX / AAMOS / QUIXZOOM — KOMPLETT INFRASTRUKTURINVENTERING

> Inklistrad av användaren 2026-07-23 från `LANDVEX_INFRASTRUCTURE_INVENTORY.md`
> (skapad av agenten "Bernt" på servern). **OBS: innehållet klipptes av
> mitt i Docker-tabellen (raden `gitea`) – avsnitten efter Docker
> (Gitea-repos, databaser, REXO-pipeline m.m.) saknas och behöver
> klistras in på nytt.**

**Datum:** 2026-07-23
**Server:** bernt.wavult.com (AWS EC2, eu-north-1, arm64)
**Inventerad av:** Bernt (AI-agent)
**Syfte:** Underlag för Landvex-plattformsimplementation i Claude

---

## 1. SERVER & HARDWARE

| Egenskap | Värde |
|----------|-------|
| **Host** | bernt.wavult.com |
| **AWS Instance** | i-09b2204a52c2f33c9 |
| **Region** | eu-north-1 (Stockholm) |
| **OS** | Amazon Linux 2023 (Linux 6.18.30-61.116.amzn2023.aarch64) |
| **Arch** | ARM64 (aarch64) |
| **Node.js** | v24.16.0 (via nvm) |
| **Shell** | bash |
| **Docker** | Aktiv, 40+ containrar |
| **Reverse Proxy** | nginx |
| **SSL** | Let's Encrypt (aamos.ai, aamos.systems) + self-signed (landvex) |

### SSH / Access
- Användare: `bernt` (primär), `ec2-user`, `amos`, `root`
- `bernt` har NOPASSWD sudo för systemctl/journalctl
- Full root via AWS SSM (instance-id: `i-09b2204a52c2f33c9`)
- SELinux: permissive

---

## 2. DOMÄNER & DNS

### Landvex
| Domän | Användning | SSL | Nginx-conf |
|-------|-----------|-----|-----------|
| `api.landvex.io` | Landvex API (v0) | Self-signed | `landvex-ssl.conf` |
| `demo.landvex.com` | Demo UI | HTTP | `demo.landvex.com.conf` |
| `pilot.landvex.com` | Pilot-plattform | HTTP | `pilot.landvex.com.conf` |

### AAMOS
| Domän | Användning | SSL | Nginx-conf |
|-------|-----------|-----|-----------|
| `aamos.ai` | Huvuddomän | Let's Encrypt | — |
| `admin.aamos.systems` | Admin-panel | Let's Encrypt | `admin.aamos.systems.conf` |
| `cc.aamos.systems` | Command Center | Let's Encrypt | `cc.aamos.systems.conf` |
| `city.aamos.systems` | SimCity-demo | Let's Encrypt | `city.aamos.systems.conf` |
| `kyc.aamos.systems` | KYC-kärna | Let's Encrypt | `kyc.aamos.systems.conf` |
| `vd.aamos.systems` | VD-dashboard | Let's Encrypt | `vd.aamos.systems.conf` |
| `developer.aamos.ai` | Dev API-gateway | Let's Encrypt | `developer.aamos.ai.conf` |

### quiXzoom
| Domän | Användning | Notering |
|-------|-----------|----------|
| `app.quixzoom.com` | quiXzoom-app | PWA, React |
| `api.quixzoom.com` | API (zombie, bakad upp) | `.bak-zombie` |

### Övrigt
| Domän | Användning |
|-------|-----------|
| `vyra.gg` | VYRA (fysisk FPS-plattform) |

---

## 3. TJÄNSTER — SYSTEMD

### Landvex (aktiva)
| Tjänst | Port | Språk | Status |
|--------|------|-------|--------|
| `landvex-api.service` | 8081 | Python/FastAPI | Running |
| `landvex-bounties.service` | 8083 | Python/FastAPI | Running |
| `landvex-claims.service` | 8084 | Python/FastAPI | Running |
| `landvex-demo.service` | 8086 | Python/http.server | Running |
| `landvex-engine.service` (Rust) | 3391 | Rust | Running |
| `landvex-invoice-reader.service` | — | Node.js | Running |

### Landvex (timers/oneshot)
| Tjänst | Syfte | Schema |
|--------|-------|--------|
| `landvex-aamos-integration.service` | Sync ledger→artiklar | Manuell |
| `landvex-artikel-erik@.service` | Artikelproduktion (Erik) | 06:00, 14:00 |
| `landvex-artikel-johan@.service` | Artikelproduktion (Johan) | 10:00 |
| `landvex-kontrollintelligens@.service` | Incidentanalys | — |

### quiXzoom (aktiva)
| Tjänst | Port | Språk | Status |
|--------|------|-------|--------|
| `quixzoom-api.service` | 3209 | Node.js | Running |
| `quixzoom-avo.service` | 7070 | Node.js | Running |
| `quixzoom-mission.service` | 7060 | Node.js | Running |
| `quixzoom-damage.service` | 7010 | Node.js | Running |
| `quixzoom-enterprise.service` | 7020 | Node.js | Running |
| `quixzoom-regulatory.service` | 7050 | Node.js | Running |
| `quixzoom-engine.service` (Rust) | 3390 | Rust | Running |
| `quixzoom-dev-api.service` | 3002 | Node.js | Running |
| `quixzoom-3d-atlas.service` | — | Rust | Running |
| `quixzoom-3d-ingest.service` | — | Rust | Running |
| `quixzoom-3d-viewer.service` | — | Node.js | Running |
| `quixzoom-payouts.service` | — | curl/oneshot | Månadsvis |

### AAMOS Core (aktiva)
| Tjänst | Port | Språk | Status |
|--------|------|-------|--------|
| `amos-core` (huvud) | 3100 | Node.js | Running |
| `aamos-admin-v2.service` | 9091 | Go | Running |
| `aamos-ledger.service` | 3250 | Rust | Running |
| `aamos-audit-engine.service` | 3251 | Node.js | Running |
| `aamos-bank-import.service` | 3253 | Node.js | **Down (health fail)** |
| `aamos-sie-import.service` | 3254 | Node.js | Running |
| `aamos-identity-rust.service` | 3207 | Rust | Running |
| `aamos-command-center.service` | — | Rust | Running |
| `aamos-academy.service` | — | Node.js | Running |
| `aamos-intelligence.service` | — | Node.js | Running |
| `aamos-code.service` | — | Node.js | Running |
| `aamos-issues.service` | — | Node.js | Running |
| `aamos-wiki.service` | 3320 | Node.js | Running |

### AAMOS Rust-motorerna (alla på 127.0.0.1)
| Tjänst | Port |
|--------|------|
| `rust_rule_engine` | 3201 |
| `rust_stammregister` | 3205 |
| `rust_tolkserver` | 3204 |
| `rust_api_gateway` | 3206 |
| `rust_financial_engine` | 3203 |
| `rust_dynasty_engine` | 3262 |
| `rust_gecl_chain` | 3263 |
| `rust_analytics` | 3211 |
| `rust_health_aggregator` | 3213 |
| `rust_commerce` | 3280 |
| `rust_crm` | 3282 |
| `rust_campaign` | 3283 |
| `rust_hr` | 3284 |
| `rust_payroll` | 3285/3315 |
| `rust_invoice` | 3286 |
| `rust_compliance` | 3287 |
| `rust_operations_core` | 3272 |
| `rust_people_core` | 3271 |
| `rust_meeting_service` | 3308 |
| `rust_dissg_engine` | 3360 |
| `rust_mlcs_engine` | 3370 |
| `rust_seep` | 3350 |
| `rust_venture` | 3306/3316 |
| `rust_billing_engine` | 3392 |
| `rust_landvex_engine` | 3391 |
| `rust_quixzoom_engine` | 3390 |

### AAMOS Go-tjänster
| Tjänst | Port |
|--------|------|
| `aamos-gateway.service` | 8080 |
| `aamos-core.service` | 3500 |
| `aamos-ads.service` | 3308 |
| `aamos-campaigns.service` | 3302 |
| `aamos-crm.service` | 3301 |
| `aamos-incidents.service` | 3303 |
| `aamos-meetings.service` | 3309 |
| `aamos-payroll.service` | 3305 |
| `aamos-talent.service` | 3307 |
| `aamos-zoomer.service` | 3304 |

### AAMOS Ticket Agents (30 st)
`aamos-ticket-agent-01` … `agent-30` via `nats://localhost:4222` — alla running.

### AAMOS Restaurant (La Marea / Torrevieja)
| Tjänst | Port | Syfte |
|--------|------|-------|
| `aamos-restaurant-pos` | 3300 | Kassa |
| `aamos-restaurant-inventory` | 3301 | Lager |
| `aamos-restaurant-hr` | 3302 | Personal |
| `aamos-restaurant-ops` | 3303 | KDS + Bokning |
| `aamos-restaurant-onboarding` | 3304 | Onboarding |
| `aamos-restaurant-menu` | 3305 | Meny |
| `aamos-restaurant-licensing` | 3310 | Alkohol + Loyalty |
| `aamos-restaurant-kiosk` | 3311 | Självbeställning |
| `aamos-restaurant-es-tax` | 3312 | Spansk skatt |
| `aamos-restaurant-es-local` | 3313 | Lokal betalning (Redsys) |
| `aamos-restaurant-screens` | 3314 | Workstation |
| `aamos-restaurant-process-designer` | 3315 | Processdesign |
| `aamos-restaurant-tickets` | 3318 | Felrapportering |
| `aamos-restaurant-analytics` | 3307 | Analys |
| `aamos-restaurant-compliance` | 3306 | HACCP/Miljö |
| `aamos-restaurant-delivery` | 3309 | Foodora/Wolt/UberEats |

### Övriga tjänster
| Tjänst | Port | Syfte |
|--------|------|-------|
| `vyra.service` | 3200 | VYRA FPS-plattform (Next.js) |
| `kyc-service-v3` | 8765 | KYC (Docker) |
| `boc-api` | 9092/9096 | Business Operations Center |
| `boc-rust` | 9093 | BOC Rust-backend |
| `event-bus.service` (Go) | — | AAMOS Event Bus |

---

## 4. DOCKER-CONTAINRAR

| Namn | Bild | Portar |
|------|------|--------|
| `boc-api` | boc-boc-api | 9096→9092 |
| `boc-postgres` | postgres:16 | 5435→5432 |
| `boc-redis` | redis:7 | 6381→6379 |
| `kyc-service-v3` | kyc-service:v3 | 127.0.0.1:8765 |
| `pgbouncer` | pgbouncer-arm64 | 127.0.0.1:6432 |
| `clickhouse` | clickhouse:24.4 | 8123, 9000 |
| `quixzoom-sso-auth` | quixzoom-sso-auth | 8088→8080 |
| `quixzoom-sso-redis` | redis:7 | — |
| `quixzoom-dashboard` | quixzoom-dashboard | 3003→80 |
| `amos-ai-inference` | amos-ai-inference | 3207→3207 |
| `boc-c-runtime` | boc-boc-c-runtime | — |
| `boc-rust` | boc-boc-rust | 9093→9093 |
| `vyra` | node:20 | 127.0.0.1:3200 |
| `mailu-front-1` | mailu/nginx:2.0 | 25, 465, 587, 993 |
| `mailu-webmail-1` | mailu/webmail:2.0 | — |
| `mailu-admin-1` | mailu/admin:2.0 | — |
| `mailu-imap-1` | mailu/dovecot:2.0 | — |
| `mailu-antispam-1` | mailu/rspamd:2.0 | — |
| `mailu-smtp-1` | mailu/postfix:2.0 | 10025 |
| `mailu-redis-1` | redis:7 | — |
| `quixzoom-passwordless` | quixzoom-passwordless-auth | 8082→8080 |
| `cursor-grafana` | grafana | 3050→3000 |
| `cursor-n8n` | n8n | 5678→5678 |
| `cursor-postgres` | postgres:16 | 5433→5432 |
| `cursor-kong` | kong:3.5 | 8001-8002, 8080→8000 |
| `cursor-prometheus` | prom/prometheus | 9090→9090 |
| `cursor-frontend` | node:20 | 3010→3000 |
| `cursor-redis` | redis:7 | 6380→6379 |
| `cursor-kong-db` | postgres:13 | — |
| `gitea-act-runner` | gitea/act_runner | — |
| `quixzoom-auth-redis` | redis:7 | — |
| `cursor-plane-web` | makeplane/plane-frontend | 3001→3000 |
| `cursor-plane-worker` | makeplane/plane-backend | — |
| `cursor-plane-db` | postgres:15 | — |
| `cursor-plane-redis` | redis:7 | — |
| `landvex-api-1` | landvex-api | 8081→8080 |
| `plane-api` | makeplane/plane-backend | 127.0.0.1:8091 |
| `plane-web` | makeplane/plane-frontend | 8092→3000 |
| `plane-beat-worker` | makeplane/plane-backend | — |
| `plane-worker` | makeplane/plane-backend | — |
| `plane-minio` | minio/minio | 9000 |
| `plane-rabbitmq` | rabbitmq:3.12 | 5671-5672 |
| `plane-redis` | redis:7.2 | — |
| `plane-db` | postgres:15.5 | — |
| `wstunnel` | erebe/wstunnel | — |
| `gitea-postgres` | postgres:15 | — |
| `gitea` | *(avklippt här – resten av inventeringen saknas)* | |

---

## SAKNADE AVSNITT (klistra in vid tillfälle)

Enligt sammanfattningen fanns även: Gitea-repos (5 st), 1200+ kataloger
i workspace, databaser (RDS PostgreSQL, lokal PostgreSQL, Redis,
ClickHouse), REXO-pipeline (`/opt/amos/rexo-build/` – godkänd väg för
kodning), Landvex-artikelautomation (10 poster/dygn), quiXzoom Auth
Core och Frilans Payout (nya produkter juli 2026).
