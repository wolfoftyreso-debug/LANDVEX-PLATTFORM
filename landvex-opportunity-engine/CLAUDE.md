# CLAUDE.md — LANDVEX Opportunity + Workforce Engine

Handoff från konceptfas till produktionsutveckling. Denna fil läses
automatiskt av Claude Code och är den auktoritativa projektkontexten.

## Vad detta är

**Globalt beslutsstöd för framtida arbetskrafts- och affärsbehov** –
Sverige är första marknaden, inte hela systemet. Varje land analyseras
med samma modell men lokala datakällor; signalkatalogen äger
normaliseringen, vilket gör **Opportunity Score (0–100) jämförbart
över länder**. Systemet svarar inte "var finns jobben idag?" utan
"var uppstår behoven innan alla andra ser dem" – med förklarbar
faktornedbrytning, konfidens och antaganden i varje svar.
Målgrupper: privatpersoner, företag, investerare, kommuner/regioner,
utbildningsaktörer och myndigheter – på samma plattform och databas.

## Nuläge: v0.9 — global marknadsmodell + production readiness

**Funktionsfrys pågår.** Readiness-status och kvarstående gap:
`docs/production-readiness.md`. Säkerhetslager i `api/security.py`
(API-nycklar/tenant/RBAC/rate limit/audit/metrics – öppet läge utan
`LANDVEX_API_KEYS`), motorversion i varje rapport, schemamigrering i
lagret, CI i `.github/workflows/landvex-ci.yml` (repo-roten).
Största gap före deploy: CDK-stacken (#6), tenant-kolumner i lagret,
OIDC.

- Beroendefri kärna i `engine/` (endast stdlib) → identisk körning i
  Lambda, ECS och lokalt.
- 10 branschprofiler + generisk (frisor, elektriker, gym, restaurang,
  cafe, bygg, tandlakare, bilverkstad, veterinar, lager) — **helt
  datadrivna** i `engine/verticals.py`.
- ~39 signaler med normalisering (saturating/linear/inverse/band) i
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
- **Opportunity Engine-svepet (v0.4):** användaren bygger en
  `BusinessProfile` (`engine/profile.py` – bransch, budget, team,
  affärsmodell, risktolerans, pendlingsgräns, miljötyp, horisont,
  mål; alla val är data i `PROFILE_OPTIONS`) och kör "Analysera
  Sverige" (`engine/scan.py`): kandidatorter → pendlings-/miljöfilter
  → analyze per ort → värmekarta (grön/gul/röd) + rankade hotspots
  med **beslutskort**: Opportunity Score, Confidence (täckning ×
  kvalitet), Risk Index, Market Momentum, Competition Gap, Time
  Window (märkt heuristik), topp-10 drivkrafter, miljötaggar,
  ekonomiskt schablonscenario (märkt "INTE prognos") och
  `expected_roi.status="ej_tillgangligt"` tills utfallsdata finns
  (princip 3). Rapporter bär nu full signalnedbrytning
  (`OpportunityReport.signals`) + `risk_score`. Profiler sparas via
  `POST /v1/profiles`; svep via `POST /v1/scan` (inline profil eller
  `profile_id`); formulärdata via `GET /v1/profile-options`.
- **Analysnivåer (v0.5):** `POST /v1/scan` tar `level`:
  `oversikt` (en punkt per kommun) eller `detaljerad` (5 punkter per
  kommun, ~3 km offset → 200 punkter; bästa punkten representerar
  kommunen i rankingen, korten får `punkt` + `lage_sv`).
- **Kartöversikt (v0.5):** `frontend/index.html` — självförsörjande
  (noll externa beroenden/CDN): profilformulär byggt från
  `/v1/profile-options`, värmekarta (SVG, grön/gul/röd, tooltip,
  klick markerar kommunens kort), hotspotpanel med hela beslutskortet.
  Serveras på `/` av både dev-servern och FastAPI.
- **Workforce Intelligence (v0.6):** `engine/workforce.py` –
  kompetensprognoser per kommun ("vilka yrken behöver samhället om
  5–20 år?") för kommuner, regioner och utbildningsaktörer. Delar
  datakällslager med Opportunity Engine. 13 yrken som ren data
  (`OCCUPATIONS`: täthet/1000 inv, pensionstakt, utbildningsplatser,
  efterfrågedrivare per signal). Transparent regelmodell:
  behov × efterfrågetakt ur drivsignaler, årsvis bana med
  pensionsavgångar + utbildningsinflöde. Varje prognos bär
  **konfidensintervall** (växer med horisont, krymper med
  datakvalitet), **konfidensnivå märkt heuristik**, explicit
  **antagandelista** och caveats — aldrig absoluta sanningar.
  Utbildningssimulering ("30 platser/år → ny bana + balansår"),
  prioriterad utbildningslista med motiveringar, nationell bristkarta
  (balans/ökande/kritisk per kommun). API: `GET /v1/workforce/
  occupations`, `POST /v1/workforce/forecast`, `POST /v1/workforce/
  simulate`, `GET /v1/workforce/map`. Frontend har flik
  Etablering/Kompetens med prognoskarta, antaganden, drivkrafter och
  simulering. Ny signal `population_total` (SCB-adaptern levererar
  den på riktigt; mock som fallback).
- **Risk Engine (v0.7):** `engine/risk.py` – tredje motorn. Fyra
  datadrivna riskdimensioner (marknads-, efterfråge-, kostnads-,
  utvecklingsrisk) + dataosäkerhet som egen dimension. Per dimension:
  score, band, narrativ med största riskfaktor + källa, och
  åtgärdsförslag vid risk ≥ 60. Transparent: dimensionsrisk =
  100 × (1 − viktat normaliserat signalvärde). `POST /v1/risk`.
- **Jämförelsemodul (v0.7):** `engine/compare.py` – 2–4 platser mot
  varandra för samma vertikal: faktormatris med vinnare per faktor,
  totalscore + riskband per plats, marginalmedveten rekommendation.
  `POST /v1/compare`.
- **Interaktiv karta (v0.7):** förenklad Sverigekontur (illustrativ),
  glödande värmepunkter (radial-gradient), zoom mot muspekaren +
  panorering + dubbelklick-återställning, punktstorlek skalar med
  zoomnivå. Riskprofilen kan öppnas direkt i varje hotspotkort.
- **Fråga Landvex (v0.8):** `engine/ask.py` + `POST /v1/ask` –
  naturligt språk in, motordata ut. Två separerade lager:
  (1) deterministisk svensk tolk (intent + kommun/yrke/bransch/
  antal/målår, synonym- och plurallexikon, genitivtålig) som i
  produktionsfasen kan ersättas av LLM-lager i `api/` – aldrig i
  kärnan; (2) routning till motorerna (scan/workforce/risk/scoring)
  – all fakta i svaret kommer därifrån med konfidens, intervall och
  antaganden intakta. Intents: affärsmöjligheter per kommun,
  bristyrken per kommun, nationell yrkesbrist (med Opportunity Map),
  bästa läge för bransch, riskprofil, okänd kommun (ärligt
  hjälpsvar), hjälp. Frontendens startsida är nu Fråga-fliken med
  exempelfrågor, expanderbara svarsrader och följdfrågor.
- **Opportunity Map (v0.8):** 4-gradigt efterfrågeband i workforce-
  svaren (`efterfragan`: extrem/hog/vaxande/mattad → röd/orange/gul/
  grön) + `trend` (stigande/stabil/minskande) och
  `pensionsavgangar`. Yrkeskatalogen bär `medellon_tkr_manad` och
  `automationsrisk_schablon` (schabloner, märkta).
- **Global marknadsmodell (v0.9):** `engine/markets.py` – marknader
  som data: SE (40 kommuner, SCB, kalibrerad) + DE/US/ES/PL/FR
  (region-frön, mock tills lokala adaptrar som Destatis/Eurostat/
  Census kopplas – redovisas ärligt i caveats). Alla motorer tar
  `market`-parameter; `global_map()` + landsranking för
  flerlandsfrågor (grupperna `eu`, `varlden`). Ekonomischabloner
  redovisas bara på kalibrerade marknader (`ej_kalibrerad` annars).
  Frågetolken förstår länder ("i Tyskland"), grupper ("i Europa"),
  utländska regioner ("i Berlin") och flytta-frågor (landsranking
  med regelverkscaveat). Kartan byter projektion per marknad (bbox);
  Sverigekonturen visas bara för SE. Ny bransch: `vvs`.
- **Multi-horisont (v0.9):** varje workforce-prognos bär `milstolpar`
  på 1/3/5/10/20 års sikt (strategisk planering), utöver valfritt
  målår och årsvis bana.
- **Gap Analysis Engine (v0.10):** `engine/gaps.py` – hittar
  obalanser (hög efterfrågan × lågt utbud × positiv utveckling) per
  region och vertikal, med treaxlig nedbrytning, klassning
  (stark/potentiell/svag obalans) och Volvo-stil-förklaringsrader
  per signal med källa. `POST /v1/gaps`.
- **Etableringsplan (v0.10):** `engine/plan.py` – från analys till
  handling: lokalstorlek + hyresläge, investering (schablon),
  finansieringsvägar, personalbehov med VERKLIGT rekryteringsläge
  från Workforce-motorn, leverantörskategorier, omsättning/resultat/
  återbetalningstid (intervall, endast kalibrerade marknader),
  topp-3 risker med åtgärder, nästa steg. `PLAN_DATA` är data per
  vertikal. `POST /v1/plan`. Frågetolken förstår obalans- och
  planfrågor; frontend har "Skapa etableringsplan" i hotspotkorten.
- **Målgruppsmotorn (v0.11):** `engine/segments.py` – 10 segment som
  data (djurägare, barnfamiljer, seniorer, unga vuxna, bilägare,
  pendlare, villaägare, höginkomsttagare, företagare, besökare):
  uppskattat antal (signal × befolkning, märkt uppskattning), index
  mot marknadssnittet, band och vilka vertikaler som betjänar
  segmentet → direkt vidare till svep/gap/plan. Regionprofil
  (`POST /v1/segments/analyze`), segmentkarta
  (`GET /v1/segments/map`), katalog (`GET /v1/segments`).
  Frågetolken: "Var finns flest djurägare?", "Hur ser målgrupperna
  ut i Umeå?", "Hur många barnfamiljer finns i Örebro?".
- **Installed Base Engine (v0.12):** `engine/installed_base.py` –
  "varje installerad produkt är ett framtida servicebehov". EN
  generell modell, produkttyper som data (`PRODUCT_TYPES`, 8 st:
  luft-/bergvärmepumpar, solceller, laddboxar, hissar, personbilar,
  industrirobotar, FTX): basproxy ur signaler, livslängd,
  serviceintervall, certifieringskrav, felmönster, reservdelar,
  säsong, serviceyrke (Workforce-länk) och betjänande vertikal.
  Kedjan bas → ålder (jämn fördelning, dokumenterat) → utbyten →
  servicetillfällen → teknikerbehov → kompetensläge → mismatch
  (stor bas + teknikerbrist = affärsmöjlighet). Nytt yrke:
  kyltekniker. API: `GET /v1/products`, `POST /v1/service/analyze`,
  `GET /v1/service/map`. Frågor: "Vilken region har flest värme-
  pumpar som närmar sig utbytesålder?", "Var är det bäst att starta
  ett företag som servar laddboxar?", "Hur ser servicebehovet ut i
  Umeå?". Verkliga installationsregister (F-gas, elnätsanslutningar,
  besiktningar) är adapterkandidater i samma Resolver-mönster.
- Övriga signaler är mockade. Varje rapport redovisar `data_coverage`
  och bär caveats tills fler källor kopplats in.

## Kommandon

```bash
python3 -m tests.test_scoring      # motortester (8 st, utan pytest)
python3 -m tests.test_scb          # SCB-adaptertester (10 st, utan nätverk)
python3 -m tests.test_storage      # persistens/cachetester (7 st)
python3 -m tests.test_scan         # profil- och sveptester (11 st)
python3 -m tests.test_workforce    # kompetensprognostester (6 st)
python3 -m tests.test_risk_compare # risk- och jämförelsetester (7 st)
python3 -m tests.test_ask          # NL-tolk och svarstester (12 st)
python3 -m tests.test_markets      # marknads- och globaltester (7 st)
python3 -m tests.test_security     # auth/RBAC/rate limit/audit (6 st)
python3 -m tests.test_gaps_plan    # obalanser + etableringsplan (7 st)
python3 -m tests.test_segments     # målgruppsmotorn (4 st)
python3 -m tests.test_installed_base  # installerad bas/service (5 st)
python3 -m api.dev_server          # → öppna http://localhost:8000/ för kartvyn
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
7. ~~**CI**~~ — KLAR: `.github/workflows/landvex-ci.yml` (repo-roten)
   kör kompilering, alla 9 testsviter och API-röktest med auth på
   Python 3.11/3.12, utan beroenden.
8. **Auth & multitenancy** — API-nycklar/Cognito för
   plattformsintegration.
9. **Rörelsedata** (licens, t.ex. Telia Crowd Insights) — sist p.g.a.
   avtalsledtid; `flow_*`, `foot_traffic`, `target_match_pct`.
10. **Frontend-rapportvy** — S3 + CloudFront.
11. **Utfallslogging från dag 1** — etableringar + faktiskt utfall är
    träningsdatan för v2 (viktkalibrering) och v3 (ERP-modell i
    SageMaker). Låser även upp `expected_roi` i beslutskorten.
12. ~~**Fler vertikaler**~~ — bilverkstad, veterinar, lager KLARA
    (v0.5). Fler tillkommer löpande: ny `VerticalProfile` +
    schablonrader i `engine/scan.py`.
13. **Fler signaler ur produktvisionen** — arbetslöshet, konkurser,
    sökvolym, kriminalitet, skolor, vårdcentraler, inflyttning:
    utöka katalogen + resp. adapter, motorn oförändrad.
14. **Finmaskigare svep** — från 40 kommuncentroider till DeSO/rutnät
    när geodata + isokroner finns; kontinuerlig omscanning via
    EventBridge så rekommendationer uppdateras när marknaden ändras.
15. **Workforce-kalibrering** — ersätt yrkesschablonerna med SCB:s
    yrkesregister (RAMS), Skolverkets utbildningsdata och AF:s
    bristindex; utfallslogga prognoser mot faktisk utveckling.
16. **Internationella adaptrar** — Eurostat (EU-bred bas), Destatis
    (DE), INE (ES), GUS (PL), INSEE (FR), US Census/BLS (US) i samma
    Resolver-mönster som SCB; kalibrera ekonomischabloner och
    yrkestätheter per marknad; utöka regionlistorna.

## Filkarta

```
engine/            kärnmotor (stdlib-only)
  models.py        Location, SignalValue, FactorScore, OpportunityReport
  signals.py       signalkatalog + normalize()
  verticals.py     branschprofiler (vikter) + RISK_SIGNALS
  scoring.py       analyze() – huvudingången
  profile.py       BusinessProfile + PROFILE_OPTIONS
  scan.py          Sverigesvepet: profil → hotspots med beslutskort
  workforce.py     kompetensprognoser, simulering, nationell bristkarta
  risk.py          riskdimensioner med narrativ + åtgärdsförslag
  compare.py       jämför 2–4 platser: faktormatris + rekommendation
  ask.py           Fråga Landvex: svensk NL-tolk → motorroutning
  markets.py       marknader som data (SE/DE/US/ES/PL/FR) + grupper
  gaps.py          Gap Analysis: obalanser (efterfrågan/utbud/utveckling)
  plan.py          etableringsplan: analys → konkret beslutsunderlag
  explain.py       narrativ + pattern_insights()
  datasources/     base.py (Resolver), mock.py, adapters.py,
                   scb.py (PxWeb-klient + kommunlokalisering),
                   cache.py (CachedSource, TTL per källa)
  storage/         base.py (Store), sqlite.py (referens),
                   postgres.py (Aurora + PostGIS)
api/               main.py (FastAPI) + dev_server.py (stdlib)
frontend/          index.html – kartöversikt, serveras på /
tests/             test_scoring.py, test_scb.py, test_storage.py,
                   test_scan.py
infra/             aws-notes.md (deploymentblueprint)
ARCHITECTURE.md    designbeslut, dataflöde, roadmap
```

## Kända begränsningar v0.1

Mockdata överallt; radie utan riktig isokron; ingen persistens, auth
eller rate limiting; rekommendationstexter formulerade som
beslutsunderlag — inte garantier. Det är avsiktligt och dokumenterat.
