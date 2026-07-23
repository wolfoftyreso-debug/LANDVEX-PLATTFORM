# CLAUDE.md — LANDVEX Opportunity Engine

Handoff från konceptfas till produktionsutveckling. Denna fil läses
automatiskt av Claude Code och är den auktoritativa projektkontexten.

## Vad detta är

Location intelligence-tjänst som analyserar en plats innan någon
investerar. Levererar ett förklarbart **Opportunity Score (0–100)** med
faktornedbrytning, riskbedömning, mönsterinsikter och rekommendation –
branschanpassat ("Know before you build"). En modul i Landvex-plattformen;
datakällslagret ska på sikt delas med Risk/Investment/Retail-motorerna.

## Nuläge: v0.3 — SCB-adapter + persistens

- Beroendefri kärna i `engine/` (endast stdlib) → identisk körning i
  Lambda, ECS och lokalt.
- 7 branschprofiler + generisk (frisor, elektriker, gym, restaurang,
  cafe, bygg, tandlakare) — **helt datadrivna** i `engine/verticals.py`.
- ~35 signaler med normalisering (saturating/linear/inverse/band) i
  `engine/signals.py`.
- Riskmotor, rekommendationslogik, svenska narrativ och mönsterinsikter
  (t.ex. "arbete för ytterligare 2 elektriker", caféets morgon/
  eftermiddags-obalans) i `engine/scoring.py` + `engine/explain.py`.
- Datakällslager med Resolver-kedja: verklig källa vinner per signal,
  MockSource (deterministisk, platsseedad) som fallback.
- API: `api/main.py` (FastAPI, produktion) och `api/dev_server.py`
  (stdlib, noll beroenden). Båda kör källkedjan verkliga adaptrar →
  mock; `LANDVEX_LIVE=0` stänger av live-källor.
- **SCB-adapter (v0.2):** `ScbSource` i `engine/datasources/adapters.py`
  + PxWeb-klient i `engine/datasources/scb.py` (stdlib, injicerbar
  transport, metadatadriven frågebyggnad, cache, felpaus med
  mock-fallback). Levererar `pop_growth_pct`, `income_index`,
  `age_20_45_share`, `share_65plus`, `residential_density` på
  KOMMUNNIVÅ (lat/lon → kommun via närmaste-centroid-lokalisering).
  **Tabellsökvägarna ska live-verifieras** mot api.scb.se med
  `python3 -m engine.datasources.scb <lat> <lon>` — utvecklingsmiljöns
  nätverkspolicy tillät inte SCB-anrop vid implementationen; tester
  körs mot fixturer i PxWeb-format.
- **Persistens (v0.3):** `engine/storage/` — `Store`-gränssnitt,
  `SqliteStore` (stdlib, testad referens; default `landvex.db`, styrs
  med `LANDVEX_DB`, `off` stänger av) och `PostgresStore`
  (Aurora + PostGIS, lazy psycopg, `LANDVEX_PG_DSN`; kör
  `.selftest()` mot riktig databas vid driftsättning). Rapporter
  sparas vid analyze (svaret får `report_id`); `GET /v1/reports`
  + `GET /v1/reports/{id}` i båda API-lagren. `CachedSource` i
  `engine/datasources/cache.py` cachar verkliga källor per plats
  med TTL per källa (`DEFAULT_TTLS`).
- Övriga signaler är mockade. Varje rapport redovisar `data_coverage`
  och bär caveats tills fler källor kopplats in.

## Kommandon

```bash
python3 -m tests.test_scoring      # motortester (8 st, utan pytest)
python3 -m tests.test_scb          # SCB-adaptertester (10 st, utan nätverk)
python3 -m tests.test_storage      # persistens/cachetester (7 st)
python3 demo.py                    # exempelrapporter frisör/elektriker/café
python3 -m api.dev_server          # dev-API utan beroenden, port 8000
python3 -m engine.datasources.scb 59.31 18.07   # live-prob mot SCB (kräver nät)
pip install -r requirements.txt && uvicorn api.main:app   # produktions-API
```

## Arkitekturprinciper — bevara dessa

1. **Vertikaler är data, inte kod.** Ny bransch = ny `VerticalProfile` +
   ev. narrativmall. Inga motorändringar.
2. **`engine/` förblir beroendefri.** Externa bibliotek hör hemma i
   `api/`, adaptrar och infra — aldrig i kärnan.
3. **Förklarbarhet före prediktion.** Varje faktor ska kunna förklaras
   med en svensk mening och råvärden. Utlova inte
   "överlevnadssannolikhet" förrän utfallsdata finns (v2/v3).
4. **Ärlig datatäckning.** Mock märks alltid `source="mock"`;
   `data_coverage` ska aldrig fejkas.
5. **Determinism.** Samma plats + vertikal → samma rapport
   (viktigt för test, cache och förtroende).
6. Identifierare utan å/ä/ö (`frisor`, `tandlakare`); narrativ och
   etiketter på svenska. Tester ska förbli körbara utan pytest.

## Produktionsbacklog (prioriterad)

1. ~~**SCB-adapter**~~ — KLAR (v0.2) på kommunnivå. Återstår:
   (a) live-verifiera tabellsökvägar med proben när nätverk finns,
   (b) DeSO/rutnätsnivå + `pop_radius`/`families_share` när geodata
   (PostGIS) finns, (c) ersätta närmaste-centroid-lokalisering med
   riktiga kommunpolygoner.
2. ~~**Persistens**~~ — KLAR (v0.3): Store-gränssnitt, SqliteStore
   (referens), PostgresStore (Aurora + PostGIS), rapportendpoints,
   signalcache med TTL per källa. Återstår: provisionera Aurora (via
   backlog #6) och köra `PostgresStore.selftest()` mot den.
3. **Isokroner** — AWS Location Service (Routes) för verklig
   "inom X minuter"-radie i stället för dagens approximation.
4. **Bygglovs-/detaljplansadapter** — kommunala öppna data eller
   aggregator (`building_permits`, `detail_plans`, `development_m2`).
5. **Konkurrensadapter** — Google Places + recensionsdata →
   `competitors`-extras, `competition_pressure`, `provider_gap` på
   verklig data.
6. **IaC med CDK** — API Gateway + Lambda (Mangum) eller ECS Fargate,
   Secrets Manager, EventBridge-ingestion, S3-datalake.
   Se `infra/aws-notes.md`.
7. **CI** — kör testsviten + lint på varje PR (inga beroenden krävs).
8. **Auth & multitenancy** — API-nycklar/Cognito för
   plattformsintegration.
9. **Rörelsedata** (licens, t.ex. Telia Crowd Insights) — sist p.g.a.
   avtalsledtid; `flow_*`, `foot_traffic`, `target_match_pct`.
10. **Frontend-rapportvy** — S3 + CloudFront.
11. **Utfallslogging från dag 1** — etableringar + faktiskt utfall är
    träningsdatan för v2 (viktkalibrering) och v3 (ERP-modell i
    SageMaker).

## Filkarta

```
engine/            kärnmotor (stdlib-only)
  models.py        Location, SignalValue, FactorScore, OpportunityReport
  signals.py       signalkatalog + normalize()
  verticals.py     branschprofiler (vikter) + RISK_SIGNALS
  scoring.py       analyze() – huvudingången
  explain.py       narrativ + pattern_insights()
  datasources/     base.py (Resolver), mock.py, adapters.py,
                   scb.py (PxWeb-klient + kommunlokalisering),
                   cache.py (CachedSource, TTL per källa)
  storage/         base.py (Store), sqlite.py (referens),
                   postgres.py (Aurora + PostGIS)
api/               main.py (FastAPI) + dev_server.py (stdlib)
tests/             test_scoring.py, test_scb.py, test_storage.py
infra/             aws-notes.md (deploymentblueprint)
ARCHITECTURE.md    designbeslut, dataflöde, roadmap
```

## Kända begränsningar v0.1

Mockdata överallt; radie utan riktig isokron; ingen persistens, auth
eller rate limiting; rekommendationstexter formulerade som
beslutsunderlag — inte garantier. Det är avsiktligt och dokumenterat.
