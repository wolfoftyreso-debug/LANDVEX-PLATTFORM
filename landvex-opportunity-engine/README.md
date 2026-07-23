# LANDVEX Opportunity Engine

**Globalt beslutsstöd för framtida arbetskrafts- och affärsbehov.**
Systemet svarar inte på "var finns jobben idag?" utan på "var uppstår
behoven innan alla andra ser dem?" – med förklarbar nedbrytning,
konfidens och antaganden i varje svar. Sverige är första marknaden;
samma modell körs för DE/US/ES/PL/FR med lokala datakällor.

API-first: webbportalen är en klient av flera. All intelligens ligger
bakom `/v1/*`.

## Nio motorer, ett datalager

| Motor | Fråga den besvarar | Endpoint |
|---|---|---|
| Ask | Fritext på svenska → rätt motor | `POST /v1/ask` |
| Opportunity | Var lyckas min verksamhet? | `/v1/analyze`, `/v1/scan` |
| Workforce | Vilka yrken behövs om 1–20 år? | `/v1/workforce/*` |
| Risk | Varför är detta riskabelt? | `POST /v1/risk` |
| Compare | Vilken av platserna är bäst? | `POST /v1/compare` |
| Gaps | Var är efterfrågan hög, utbudet lågt, trenden upp? | `POST /v1/gaps` |
| Plan | Vad krävs konkret för att etablera? | `POST /v1/plan` |
| Segments | Var finns djurägarna/barnfamiljerna? | `/v1/segments/*` |
| Installed Base | Var uppstår servicebehovet? | `/v1/service/*` |

Självbeskrivning för integration: `GET /v1/catalog` (motorer +
endpoints), `GET /v1/agent-manifest` (verktygsform med JSON Schema för
AI-agenter), `GET /openapi.json` + `/docs` (FastAPI).

## Kom igång

```bash
python3 -m tests.test_scoring        # hela sviten kräver noll beroenden
python3 -m api.dev_server            # stdlib-server → http://localhost:8000/
pip install -r requirements.txt && uvicorn api.main:app   # produktions-API
python3 -m scripts.build_demo demo.html   # fristående demo med bakade svar
```

Kärnan (`engine/`) är beroendefri – identisk körning i Lambda, ECS
och lokalt. Se `CLAUDE.md` för full projektkontext och backlog.

## Deploy till AWS

Tre färdiga ingångar, välj spår i `infra/aws-notes.md`:

- **Lambda:** handler `api.lambda_handler.handler` (Mangum ingår i
  requirements) bakom API Gateway.
- **Container:** `Dockerfile` (ECS Fargate/valfri runtime), healthcheck
  mot `/health` inbyggd.
- **Persistens:** `LANDVEX_PG_DSN` → Aurora PostgreSQL + PostGIS
  (kör `PostgresStore.selftest()` vid driftsättning); annars SQLite
  via `LANDVEX_DB`.

### Miljövariabler

| Variabel | Funktion |
|---|---|
| `LANDVEX_API_KEYS` | `nyckel:tenant:roll,...` (admin/analyst/partner). Tom = öppet dev-läge |
| `LANDVEX_RATE_LIMIT` | anrop/minut per nyckel (default 300) |
| `LANDVEX_DB` / `LANDVEX_PG_DSN` | SQLite-sökväg (`off` stänger av) / Postgres-DSN |
| `LANDVEX_AUDIT_LOG` | revisionsloggfil (`off` stänger av; stdout loggar alltid JSON) |
| `LANDVEX_LIVE` | `0` stänger av live-datakällor (endast mock) |

### Observability

`GET /health` (motorversion, persistens, källstatus inkl. felpausade
adaptrar) · `GET /metrics` (JSON, eller `?format=prometheus`) ·
`GET /v1/audit` (admin) · `X-Request-ID` på alla svar.

## Ärlighetsprinciper (gäller alla motorer)

Mockdata märks alltid `source="mock"` och `data_coverage` fejkas
aldrig. Konfidens är märkt heuristik, intervall breddas med horisont,
antaganden listas explicit, schabloner kallas schabloner och ROI
utlovas inte före utfallsdata. Determinism: samma indata ⇒ samma svar,
stämplat med `engine_version`.

## Test & CI

12 testsviter (97 tester), körbara utan pytest/nätverk/beroenden.
CI: `.github/workflows/landvex-ci.yml` – kompilering, hela sviten och
API-röktest med autentisering på Python 3.11/3.12.

Status inför enterprise-deploy: `docs/production-readiness.md`.
