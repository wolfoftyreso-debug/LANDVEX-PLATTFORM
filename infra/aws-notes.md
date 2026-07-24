# AWS-deployment – blueprint för nästa fas

Kärnan är beroendefri, så båda spåren nedan fungerar utan kodändringar.

## Rekommenderad väg (enkel start, skalar med er)

| Lager | Tjänst | Kommentar |
|---|---|---|
| API | API Gateway + Lambda (Python 3.12) | `engine/` zippas rakt in; FastAPI via Mangum, eller Lambda-handler direkt på `analyze()` |
| Alternativ API | ECS Fargate + ALB | Om ni hellre kör containern (`uvicorn api.main:app`) |
| Databas | Aurora PostgreSQL + PostGIS | Platser, rapporter, signalcache, geodata. `PostgresStore` finns i `engine/storage/postgres.py` (DSN via `LANDVEX_PG_DSN`, DDL ingår) – kör `.selftest()` vid driftsättning. SQLite är lokal referens |
| Datalake | S3 + Glue | Rådata från SCB, bygglov, rörelsedata; partitionerat per källa/datum |
| Ingestion | EventBridge Scheduler + Lambda/Step Functions | Nattliga hämtningar per adapter |
| Hemligheter | Secrets Manager | API-nycklar för rörelsedata, platsdata m.m. |
| Isokroner | AWS Location Service (Routes) | Verklig "inom 10 minuter"-radie |
| Cache | ElastiCache (Redis) | Rapporter per (plats, vertikal) – dyra signaler återanvänds |
| Frontend | S3 + CloudFront | Rapportvy/dashboard |
| Observability | CloudWatch + X-Ray | Latens per datakälla, täckningsgrad per rapport |
| Framtida ML | SageMaker | ERP-modellen (v3), tränas på utfallsdata i datalaken |

## Driftsteg

1. IaC med CDK (TypeScript/Python) – repo:t är strukturerat för det.
2. CI: kör `python3 -m tests.test_scoring` i pipeline (inga beroenden krävs).
3. Deploya API:t med enbart MockSource först → plattformsintegration kan
   börja direkt mot riktiga endpoints.
4. Koppla adaptrar i ordning: SCB (öppet) → bygglov → platsdata → rörelsedata
   (licensavtal). `data_coverage` i rapporterna visar progressionen.
5. Börja logga utfall (etableringar + hur det gick) från dag 1 – det är
   träningsdatan för v2/v3.
