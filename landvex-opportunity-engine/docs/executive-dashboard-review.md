# Executive Dashboard Governance Review — LANDVEX v0.10

Granskning mot "Executive Dashboard Governance Standard" (kontroll-
prompt v1.0), utförd mot faktisk kodbas med sökverifiering. Grund-
regeln följs strikt: befintligt återanvänds, inget dupliceras, och
**det som inte existerar rapporteras som icke-existerande – det
uppfinns inte.**

## Executive Summary

Implementationen följer standardens kärnprinciper väl: API-first,
Business/Action First i UI:t (score och rekommendation först, teknik
bakom drill-down), spårbara widgets (varje siffra går till en motor)
och ett designsystem som används konsekvent. **Men standarden
refererar till en driftmiljö som inte finns i denna kodbas** –
Kubernetes, Kafka, Neo4j, Grafana, Prometheus, Redis, incidenttjänst,
notifieringsmotor och bolagsstrukturen (Landvex Group/Quixzoom/Calyx)
förekommer ingenstans i repot (verifierat med grep; enda träffen är
Redis/ElastiCache som *planerad* rad i infra/aws-notes.md).
Granskningen godkänner därför det som kan verifieras och listar
resten som verkliga luckor – i linje med standardens egen regel
"endast verkliga luckor implementeras".

## Återanvändbara komponenter (finns – bygg endast presentation)

| Standardens begrepp | Befintlig komponent | Var |
|---|---|---|
| Health/Global Status | `GET /health` i båda API-lagren | api/main.py, api/dev_server.py |
| Metrics/KPI Engine | `Metrics.snapshot()`: uptime, anrop, 5xx, latens p50/p95, per path, rate limit → `GET /metrics` (admin) | api/security.py |
| AI/Executive Summary | `ask()` – motorbaserade sammanfattningar (`svar_sv`), aldrig fri text; `sammanfattning_sv` i gaps, rekommendationer i scoring/compare | engine/ask.py, gaps.py, scoring.py |
| Risk Score/Dashboard | Risk Engine: `total_risk`, band, 5 dimensioner, åtgärder; `risk_score` i varje rapport | engine/risk.py |
| Decision Engine | `recommendation_sv`, `utbildningsprioriteringar`, `atgard_sv`, `nasta_steg_sv`, hela etableringsplanen | scoring, workforce, risk, plan |
| Business Impact | Ekonomiscenarier: omsättning, resultat, återbetalningstid, budget_fit (schablonmärkta) | scan.py, plan.py |
| "AI Confidence" | `konfidens` (märkt heuristik) + `data_coverage` i varje svar | workforce, scan, risk |
| Audit/Compliance | `AuditLog` (JSONL: tenant, roll, request_id, status, duration), nycklar maskeras | api/security.py |
| Ledger/PostgreSQL | `Store`-gränssnitt, SqliteStore (migrationshanterad), PostgresStore (ej provisionerad) | engine/storage/ |
| Service-hälsa (delvis) | ScbSource felpaus (circuit breaker per källa) | engine/datasources/adapters.py |
| Governance-evidens | production-readiness.md, CI-pipeline | docs/, .github/workflows/ |
| Designsystem | CSS-tokens (:root-variabler), delade kort-/metrik-/chipkomponenter, en klient utan egen logik | frontend/index.html |

## Saknade kopplingar (befintligt som inte är ihopkopplat)

1. **/metrics och auditloggen saknar presentationsyta** – en
   Operations-flik i befintlig frontend som läser `GET /metrics` är
   ren presentation av existerande data. Auditloggen saknar
   läs-endpoint (`GET /v1/audit`, admin) – filen finns, API:t saknas.
2. **Datakällornas hälsa syns inte i /metrics** – ScbSource:s
   felpaus-tillstånd (`_down_until`) är systemets enda
   "incident"-signal men exponeras inte. Koppling, inte nybygge.
3. **Persistensen används bara av /v1/analyze** – scan-, gap- och
   plansvar sparas inte trots att `Store` finns. `save_report`
   återanvänds rakt av.
4. **`engine_version` saknas i /health** – stämplas i rapporter men
   hälsoendpointen svarar bara `{"status": "ok"}`.

## Dubbletter (verifierade)

1. **Testrunner-blocket** (`if __name__ == "__main__": fns = ...`)
   duplicerat i alla 10 testfiler → konsolidera till `tests/_runner.py`.
2. **"Persistens avstängd (LANDVEX_DB=off)"** hårdkodad 8× i
   API-lagren → en konstant.
3. **Tre `_band`-funktioner** (scan/risk/workforce) med samma form men
   olika semantik och trösklar – *medveten* separation (olika skalor);
   dokumenteras hellre än tvångskonsolideras.
4. **Route-logik dev_server vs FastAPI** – parallell per design
   (beroendefritt dev-läge är arkitekturprincip 2, båda delar redan
   `api/security.py` och all motorloggik). Ingen omskrivning motiverad.
5. Frontendens kortrendering har tre varianter (hotspot/svar/komp) med
   delade byggstenar (metrik-grid, driver-rад, esc) – acceptabel nivå.

Inga duplicerade API:er eller datamodeller hittades. `KOMMUNER` har en
källa (scb.py) som markets.py återanvänder.

## Verkliga luckor (existerar inte – får därför byggas enligt standard)

Incidenttjänst/notifieringsmotor, event bus (Kafka), Prometheus/
Grafana-export (dagens /metrics är eget JSON-format – en
Prometheus-textexport av samma `Metrics`-objekt vore återanvändning),
Kubernetes/Redis/Neo4j, provisionerad PostgreSQL (CDK, backlog #6)
samt bolagsstruktur/koncernvy (ingen datamodell för bolag finns –
kräver beslut om huruvida den ska finnas).

## Rekommenderad refaktorering (prioriterad)

1. **Återanvändning:** Operations-drilldown i frontend på befintliga
   /metrics + audit-läsendpoint; exponera källfelpaus i /metrics;
   spara scan/gap/plan via befintliga `save_report`.
2. **Konsolidering:** testrunner + persistens-felsträng.
3. **Förenkling:** inga fynd som motiverar omskrivning.
4. **Standardisering:** Prometheus-textformat som alternativ
   serialisering av befintliga Metrics (samma data, ny content-type).

## Definition of Done — status

| Krav | Status |
|---|---|
| Executive-vyn bygger på befintliga tjänster/data | ✅ (varje widget spårbar till motor) |
| Ingen funktionalitet duplicerad | ✅ med två små konsolideringar kvar (testrunner, felsträng) |
| Befintliga API:er/datakällor återanvänds | ✅ |
| Designsystem används konsekvent | ✅ (tokens + delade komponenter, en klient) |
| Affärsvärde före teknisk detalj | ✅ (score/rekommendation först, drill-down för detalj) |
| Widget→tjänst-spårbarhet | ✅ |
| Endast verkliga luckor byggs | 🟡 luckorna ovan är identifierade men inte beslutade |

**Slutsats:** godkänd som beslutsplattform enligt standardens
återanvändningsprinciper; ej godkänd som "Operations Command Center"
eftersom driftinfrastrukturen standarden räknar upp inte existerar i
kodbasen ännu – den ligger som blueprint (infra/aws-notes.md) och
backlog (#6, #16).
