# Production Readiness Review — LANDVEX

*Uppdaterad 2026-07-30 (motorversion 1.1.0). Ursprungligen skriven vid
v0.9-frysen; status nedan är nuläget, med evidens i kodbasen.*

Detta dokument svarar på granskningsfrågorna inför första
enterprise-deploy. Statusskala: ✅ klart · 🟡 delvis/plan finns ·
🔴 saknas.

## Arkitekturprincipen som allt vilar på

```
Klienter (web · mobil · Power BI · partner-API)
   ↓
Enterprise API        api/main.py (FastAPI) · api/dev_server.py (stdlib)
   ↓                  api/security.py (auth, RBAC, rate limit, audit, metrics)
Beslutsmotorer        engine/: scoring · scan · workforce · risk · compare · ask
   ↓
Datalager             engine/storage/ (SQLite-referens, Postgres/PostGIS)
   ↓                  engine/datasources/ (Resolver, cache-TTL per källa)
Datakällor            SCB (live-redo) · mock · adapterstubbar per källa
```

Webbportalen (`frontend/index.html`) är EN klient av API:t – den äger
ingen logik, bara inloggnings-/fråge-/kartyta. All intelligens ligger
bakom `/v1/*`.

## Svar på granskningsfrågorna

### 1. Är alla API-kontrakt versionerade? ✅
Alla endpoints ligger under `/v1/`. Motorn stämplar dessutom
`engine_version` (engine/version.py) i varje rapport, så ett svar kan
alltid härledas till den logik som producerade det. Regel: brytande
kontraktsändring ⇒ `/v2/`, aldrig ändrad semantik under `/v1/`.

### 2. Är autentisering och behörighetsmodell färdig? 🟡 (baslinje klar)
`api/security.py`, delad av båda API-lagren:
- API-nycklar `nyckel:tenant:roll` via `LANDVEX_API_KEYS`; tom = öppet
  utvecklingsläge (dokumenterat).
- RBAC: `admin > analyst > partner`; partner är read/analyze-only,
  `/metrics` kräver admin. Prefixmatchning täcker underresurser.
- Rate limiting: token bucket per nyckel (`LANDVEX_RATE_LIMIT`).
- Nycklar loggas aldrig (maskerat key_id) – testat.

Sedan v0.9 tillkommet: JWT-bearer-auth (HS256, stdlib) bredvid
API-nycklarna med samma RBAC/kapabilitets-enforcement; plan- och
tilläggsenforcement per endpoint (`api/licensing.py`); persistent
månadskvot (`usage_meter`, DB-atomisk `bump_usage`); tenant-kolumner
i lagringen (se fråga 3). Självrevisionen `GET /v1/integrity/audit`
vaktar ogrindade endpoints och tenant-kontraktet vid körning.

Kvar till enterprise-nivå: OIDC/Cognito med JWKS/RS256 (samma
`authorize()`-kontrakt, bytet är isolerat till nyckeluppslaget —
HS256-JWT finns redan) och kryptering i vila via KMS på Aurora
(infra-fråga). Sponsorbudgetens beställningsskriv är processlåst;
flera processer mot samma databas kräver ett villkorat lager-skriv
(redovisat i `engine/sponsorship.py`).

### 3. Är datamodellen stabil och migrationshanterad? 🟡
- Modellprincipen är rätt enligt review: vi lagrar observationer
  (signalvärden med källa/kvalitet/tidsstämpel), profiler och
  beräknade rapporter med full härledning – inte lösa "slutsatser".
- Migrationsrunner med `schema_meta`-versionstabell i BÅDA lagren;
  sqlite och postgres delar versionsnummer (kedjan är på version 12),
  och ett statiskt drifttest fäller schemadrift mellan dem.
- Tenant-kolumner: KLART. reports/profiles fick tenant via migration
  (befintliga rader blir medvetet osynliga för riktiga tenants — att
  gissa ägare vore värre); kundtabellerna (assets, routines, checks,
  scheduled_jobs, observations, sponsor_campaigns/completions) har
  tenant i primärnyckeln. Skördad/publicerad data har INGEN
  tenant-kolumn, med flit och dokumenterat skäl.
- Kvar: köra `PostgresStore.selftest()` mot riktig Aurora —
  runbook-steget är `LANDVEX_PG_DSN=... python3 -m scripts.pg_selftest`
  (kör rundturen, skriver migrationsläget, jämför mot referenskedjan;
  vägrar utan DSN i stället för att ge ett falskt grönt kvitto).

### 4. Finns strukturerad loggning, metrics och tracing? 🟡
- Requestlogg + revisionslogg som JSON-rader (ts, request_id, tenant,
  roll, path, status, duration_ms) – CloudWatch-redo.
- `X-Request-ID` sätts på alla svar (korrelations-id).
- `/metrics`: anrop totalt, 5xx, latens p50/p95, per path.
- Kvar: distribuerad tracing (X-Ray/OTel) när systemet blir
  flertjänst – idag är det en process och request_id räcker långt.

### 5. Är alla externa datakällor abstraherade bakom adapters? ✅
Resolver-kedjan (`engine/datasources/base.py`) är enda vägen in:
verklig källa vinner per signal, mock som fallback, `source` +
`quality` följer varje värde. SCB implementerad; Movement/Permits/
Places är typade stubbar; internationella adaptrar (Eurostat m.fl.)
går i samma mönster (backlog #16). Motorn har inga källberoenden.

### 6. Finns cache-strategi för dyra beräkningar? ✅
`CachedSource` med TTL per källa (SCB 7 dygn, rörelsedata 6 h) lagrad
i Store; källfel ger felpaus + mock-fallback utan att ljuga om
täckning. Beräkningarna själva är deterministiska och billiga;
rapportcache per (plats, vertikal) kan läggas i ElastiCache-fasen.

### 7. Är varje Opportunity Score reproducerbar och spårbar? ✅
Varje rapport bär: `engine_version`, full signalnedbrytning (värde,
källa, kvalitet, normaliserat värde per signal), faktorvikter,
`data_coverage`, antaganden (workforce) och caveats. Determinism är
testad (samma indata ⇒ identisk rapport). En sparad rapport kan
därmed förklaras och räknas om i efterhand – "varför fick vi 87?"
besvaras rad för rad, ingen svart låda.

### 8. Finns tester för de viktigaste affärsflödena? ✅
106 sviter, körbara utan pytest/beroenden/nätverk (`make test`).
Utöver v0.9-flödena: kontraktstest som statiskt låser att FastAPI-
och stdlib-lagret exponerar samma endpoint-yta, red-team-svit,
självrevision (fäller varje ny modulfil utan test), tenancy-svit,
mutationsbevisade lås (budgettak, färskhetsexport, resolver-kedjan),
en Kubernetes-svit (`tests/test_k8s.py`, 16 tester) som håller
`deploy/k8s/` lika mot `deploy/aws/task-definition.json`. CI kör
dessutom ett API-röktest med auth påslagen.

### 9. Kan systemet driftsättas från grunden med en enda pipeline? ✅ (K8s-spåret bevisat live)
- CI (`.github/workflows/ci.yml`): kompilering + hela sviten +
  API-röktest på Python 3.11/3.12 – noll beroenden krävs, vilket gör
  pipelinen trivial att lita på. Speglad i `.gitea/workflows/ci.yml`
  (samma steg, drift mellan de två filerna hålls av ett test) för
  driftsättning via egen Gitea.
- IaC: inte CDK (backlog #6 syftade på CDK specifikt, och det är
  fortfarande oskrivet) – i stället två hand-skrivna, testade spår:
  `deploy/aws/task-definition.json` (ECS Fargate) och `deploy/k8s/`
  (Kubernetes, se `docs/k8s.md`).
- **Kubernetes-spåret är driftsatt på riktigt, 2026-07-30**
  (`infra/aws-svar-2026-07-30-c.md`): `https://opportunity.landvex.com/health`
  svarar 200, 2/2 repliker, Postgres-persistens (RDS
  `landvex_opportunity`, `schema_meta version: 19`, bekräftat med
  `scripts.pg_selftest`), ALB + ACM-cert + Route53 klara. Fem verkliga
  problem uppstod på vägen och är åtgärdade (se `docs/k8s.md` §6):
  fel CPU-arkitektur i imagen (byggd arm64, klustret kör amd64),
  `psycopg` var utkommenterad i `requirements.txt` (rättat – testat
  mot drift av `tests/test_deploy.py`), nodgruppen behövde skalas
  2→4, en fel IAM-policy på LB-kontrollerns IRSA-roll, och
  ACM-ARN:et i `ingress.yaml` behövde ett manuellt fyll-i eftersom
  `kustomize` inte fanns installerat på driftsättningsmaskinen.
  quiXzoom-routen visade sig också vara `/api/quixzoom/missions`, inte
  det tidigare gissade `/api/qz/missions` – rättat genomgående i koden.
- ECS-spåret (`deploy/aws/`) är fortfarande enbart skrivet och testat,
  inte kört mot riktig infrastruktur – men K8s-körningen bevisade att
  samma persistenslager (`PostgresStore`, migrationskedjan, preflight)
  fungerar mot en riktig Aurora-fri RDS-instans, vilket var den stora
  obekräftade delen för båda spåren.

## Sammanfattning

| Område | Status |
|---|---|
| API-first, versionerade kontrakt | ✅ |
| Modulär arkitektur (4 lager) | ✅ |
| Adapterabstraktion av källor | ✅ |
| Cache-strategi | ✅ |
| Förklarbarhet & reproducerbarhet | ✅ |
| Affärsflödestester + CI (GitHub + Gitea) | ✅ |
| Säkerhet | 🟡 nycklar+JWT+RBAC+planer klart; OIDC/JWKS kvar |
| Datamodell/migrationer | ✅ Postgres bevisad live i K8s (RDS `landvex_opportunity`, schema v19, `pg_selftest` grönt). server-2:8087 kör fortfarande SQLite (ett separat, äldre spår); den lokala `landvex`-Postgres-databasen där tillhör ett annat system och ska aldrig återanvändas |
| Observability | 🟡 logg/metrics/request-id klart; tracing senare |
| CI/CD & IaC | ✅ K8s-spåret driftsatt och verifierat live (`opportunity.landvex.com`); ECS-spåret skrivet och testat, ej ännu kört mot riktig infrastruktur |

**Rekommendation:** K8s-betan är uppe – nästa steg är att låta
`AWS Load Balancer`-hälsokontrollen bli `healthy` (automatiskt, minuter)
och sedan skicka riktig trafik mot den. Kvarstående punkter: aktivera
control plane-loggning (`docs/k8s.md` gap #10, best practice, inte
blockerande); OIDC/JWKS för RS256-tokens (HS256-JWT är redan i drift,
täcker det mesta); ta ställning till server-2:s SQLite-baserade
körning (fortsätt parallellt, eller migrera dess data med
`scripts/migrate_sqlite_to_postgres.py` in i samma RDS-instans).
