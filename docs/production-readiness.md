# Production Readiness Review — LANDVEX v0.9

Funktionsfrys genomförd. Detta dokument svarar på granskningsfrågorna
inför första enterprise-deploy, med status och evidens i kodbasen.
Statusskala: ✅ klart · 🟡 delvis/plan finns · 🔴 saknas.

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

Kvar till enterprise-nivå: OIDC/Cognito (samma `authorize()`-kontrakt,
bytet är isolerat till nyckeluppslaget), tenant-kolumner i lagringen
(se fråga 3) och kryptering i vila via KMS på Aurora (infra-fråga).

### 3. Är datamodellen stabil och migrationshanterad? 🟡
- Modellprincipen är rätt enligt review: vi lagrar observationer
  (signalvärden med källa/kvalitet/tidsstämpel), profiler och
  beräknade rapporter med full härledning – inte lösa "slutsatser".
- Migrationsrunner med `schema_meta`-versionstabell i SqliteStore;
  basschema = version 1, nya ändringar läggs som versionerade
  migrationer. PostgresStore delar DDL-mönstret.
- Kvar: tenant-kolumn på reports/profiles (idag skiljs tenants åt i
  audit-loggen men inte i lagringen – krav före fleranvändardrift),
  samt att köra `PostgresStore.selftest()` mot riktig Aurora.

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
78 tester i 9 sviter, körbara utan pytest/beroenden/nätverk:
scoring/determinism, SCB-adapter (fixturer i PxWeb-format),
persistens+cache, profil→svep→beslutskort, workforce-prognoser+
simulering, risk+jämförelse, NL-tolken, marknader/globala flöden,
säkerhet (auth/RBAC/rate limit/audit). CI kör dessutom ett
API-röktest med auth påslagen.

### 9. Kan systemet driftsättas från grunden med en enda pipeline? 🟡
- CI (`.github/workflows/landvex-ci.yml`): kompilering + hela sviten
  + API-röktest på Python 3.11/3.12 – noll beroenden krävs, vilket
  gör pipelinen trivial att lita på.
- Kvar: CD-steget. Blueprint finns (infra/aws-notes.md: CDK,
  API Gateway+Lambda/Mangum eller ECS, Aurora, Secrets Manager) men
  IaC-koden är inte skriven (backlog #6). Detta är den enskilt
  största kvarvarande punkten före deploy.

## Sammanfattning

| Område | Status |
|---|---|
| API-first, versionerade kontrakt | ✅ |
| Modulär arkitektur (4 lager) | ✅ |
| Adapterabstraktion av källor | ✅ |
| Cache-strategi | ✅ |
| Förklarbarhet & reproducerbarhet | ✅ |
| Affärsflödestester + CI | ✅ |
| Säkerhet | 🟡 baslinje klar; OIDC + tenant-isolering i lagret kvar |
| Datamodell/migrationer | 🟡 runner klar; tenant-kolumner + Aurora-selftest kvar |
| Observability | 🟡 logg/metrics/request-id klart; tracing senare |
| CI/CD & IaC | 🟡 CI klar; CDK-stack är största gapet |

**Rekommendation:** skriv CDK-stacken (backlog #6) och tenant-
kolumnerna före första enterprise-deploy; OIDC kan gå i samma sprint.
Allt annat är deploybart som det står.
