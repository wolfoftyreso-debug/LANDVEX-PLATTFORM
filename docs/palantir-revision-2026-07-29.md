# Palantir-revisionen 2026-07-29

En plattform som säljer transparens måste själv tåla granskning på
varje punkt där den kan ljuga: om sina källor, sina tal, sina gränser
mellan kunder och sin egen säkerhet. Den här revisionen mätte hela
systemet mot dess egen ambition — och varje fynd nedan bär sitt bevis,
sin allvarsgrad och sin fix-commit eller sitt motiverade icke-fix.

**Utgångsläge** (HEAD `4db265a`): 136 metod+väg-par per API-lager,
80 motor-moduler, 17 datatabeller, 22 källklienter, 87 testsviter
gröna. **Slutläge**: 90 sviter gröna, `GET /v1/integrity/audit` svarar
`passed` med 8/8 kontroller beräknade — och fäller sig själv när nästa
regression införs.

## Metod

Två inventeringsagenter (API-ytan respektive motorn/lagret/doktrinerna)
kartlade hela ytan; en planeringsagent sekvenserade och **korrigerade
fyra av fynden samt fann fem nya** (N1–N5); varje kvarstående fynd
verifierades därefter med en egen mätning **före** fixen. Varje fix
fick ett regressionstest som bevisats bita: mutera koden → testet
faller → återställ. Ingenting nedan är rapporterat på intryck.

Revisionen fällde också sitt eget verktyg två gånger, och det står
här av samma skäl som allt annat:

* Sandlådan rullades tillbaka mitt under kartläggningen (fjortonde
  gången) — agenterna läste månader gammal kod tills trädet
  återställts och båda beordrats börja om.
* En mutation "återställdes" med `git checkout` som även svepte bort
  ostagade riktiga ändringar; allt gjordes om, och senare mutationer
  använder filkopior.

## Fynden

### Kritiskt — intäkt och isolering

| # | Fynd | Bevis | Fix |
|---|------|-------|-----|
| A1/A2/N1 | **Tre ogrindade vägar**: `/v1/verticals` (hela vertikalkatalogen med faktorvikter), `/v1/commercial`, `/v1/entitlements` — giltig nyckel krävdes men VARJE plan släpptes in, även Free | `required_capability()` → `None`, mätt för alla tre; syskonen `/v1/markets`/`/v1/offering` → `core` | `4a56a18`: mappade till `core`; nytt svep-test över ALLA routade vägar i båda lagren (föll med exakt de tre) |
| A3 | Licenstestet svepte bara `API_CATALOG` — därför fångades A1/A2/N1 aldrig | testkällan läste katalogen, inte ytan | `4a56a18`: svepet läser ytan via delade parsare (`api/surface_scan.py`) |
| B1 | **PostgresStore saknade migrationsliggare**: ingen `schema_meta`, ingen `_migrate()`, bara platt `CREATE TABLE IF NOT EXISTS` — som aldrig lägger en kolumn på en befintlig tabell. Nästa schemaändring hade tyst uteblivit i produktion medan sqlite (referensen, den enda testade) fått den | `postgres.py` hade inget av sqlite-kedjans maskineri; nedgraderad från "tenantläcka" efter mätning: idempotenta ALTER-rader råkade täcka tenant-kolumnerna | `79da646`: kedja som delar sqlite:s versionsnummer (baslinjen HÄRLEDS ur sqlite-kedjan och kan inte drifta), `_migrate(conn)` som ren funktion bevisad mot fejkförbindelse |
| N3 | **`PostgresStore.selftest()` kraschade på första raden** — anropade `save_report` utan det keyword-only `tenant` som signaturen kräver. Driftsättningsverifieringen har ALDRIG kunnat köras mot en riktig databas | `TypeError` vid inspektion av anropet mot signaturen | `79da646`: `tenant="selftest"`; källskannande test låser argumentet |
| — | **Inget jämförde de två lagrens scheman alls** — produktionens lager var otestat per konstruktion | drifttest saknades; deploy-testet bar t.o.m. gamla doktrinen som regel ("Postgres behöver ingen schema_meta") | `79da646` + `24fc274` + `9a5cea2`: statisk jämförare sqlite-PRAGMA ↔ postgres-DDL, EN implementation delad av test och `/v1/integrity/audit`, bevisad bitande via mutation |

### Ärlighetsdoktrinen — flaggskeppet utan täckningstal

| # | Fynd | Bevis | Fix |
|---|------|-------|-----|
| C1 | **`indices.py` — kontradiktionsindexet, plattformens signaturanalys — bar inget `data_coverage`** trots samma Resolver som scoring/risk/workforce (som alla räknar talet). Ett index på 100 % simulering såg identiskt ut med ett på riktiga källor | `grep -c data_coverage engine/indices.py` → 0; `city_assessment("0180")` på ren mock: ingen nyckel | `e8447ce`: `data_coverage` på svaret och per indexrad; kontradiktionsraden bär `sides_real {planned, observed}` — regeln "båda sidor eller inget fynd" bodde i analysis-svepet medan raden teg; nu läser svepet radens egen sanning |
| C2 | `segments.py` kastade bort `sv.source` — en skattad huvudräkning (signal × befolkning) kunde inte spåras; `installed_base.py` samma lucka | källfältet försvann i `_resolve_market`; caveaten sa "estimates, not registers" men aldrig "simulated" | `e8447ce`: `kalla` per rad, `data_coverage` på svaren, caveat som säger vad 0.0 betyder |
| C2-korr | Ursprungsfyndet överdrev: `livability.py` och `lambda_index.py` HAR täckning per dimension; `kpi.py` har ingen resolver | planeringsagentens motläsning, verifierad | ingen åtgärd — felaktigt fynd, struket |
| C3 | Sju motorer bar varsin mock-only-defaultresolver — ett glömt `resolver=` gav 100 % simulering utan märkning | mätt: API-lagren skickar redan riktiga `RESOLVER` överallt; fällan gällde interna anropare | `e8447ce` + `699019c`: EN delad default. **Första försöket (produktionskedjan som default) var fel och återtogs efter CI-mätning**, se nedan |

**Revisionens eget fel, mätt och återtaget** (`699019c`): grupp 4
gjorde produktionskedjan till motordefault. CI med öppet nät bevisade
att det bröt doktrinen: `gap_analysis` utan resolver tog **72 sekunder
och gav olika svar två gånger i rad** — SCB/Kolada är nyckellösa med
default-adresser och ansluter så fort nätet är öppet. Lokalt doldes
felet av nätspärren. Regeln som håller: motorernas default är **märkt
simulering** (deterministisk, nätfri, med `data_coverage` som säger
det); produktionskedjan är API-lagrets och bakgrundssvepens
uttryckliga val. Ett lås i `test_scoring` håller defaulten mock-only.

### Feldoktrinen

| # | Fynd | Bevis | Fix |
|---|------|-------|-----|
| D1 | `risk_intel.py` **svalde `ImportError` — en medlem i själva OUR_BUGS**. En trasig nyhetsmodul lästes som "ingen rapportering"; kategorierna stod som lugn monitoring medan koden var sönder | breda exceptet omslöt två import-satser | `6a4021b`: `except OUR_BUGS: raise` med platsens skäl |
| D2–D3 | `admin.py` (nätadapter i fel katalog), `opportunity_intel.py`, `livability_scan.py` — vår bugg kläddes ut till "källan nere"/"marknad utan underlag" | 12 ovaktade breda except mätta i hela kodytan, 4 verkliga | `6a4021b`: vakter + svepet breddat till hela `engine/` + `integrations/` + `api/` |
| D4 | `test_faults` svepte bara datasources/registers/aamos — därför sågs D1–D3 aldrig | katalogavgränsningen i testet | `6a4021b`: skannern bor i `engine/selfaudit`, delad av test och yta; de 8 försvarbara platserna står i **allowlist som data med skäl per rad**, och en död rad faller |
| D5/N5 | `probe_all` bar en kopia av OUR_BUGS under kommentaren "Samma lista" — och kopian hade REDAN driftat (extra `TypeError`) | tupeljämförelse mot `faults.OUR_BUGS` | `6a4021b`: härledd ur källan; avsteget står namngivet med skäl |

### API-ytan i övrigt

| # | Fynd | Bevis | Fix |
|---|------|-------|-----|
| N4 | Dev-servern serverade INTE `/docs`, medan kontraktstestets `_FRAMEWORK`-kommentar påstod "båda serverar dem" — och mängden EXKLUDERADE vägen ur jämförelsen, så ingen kunde se det | `grep '"/docs"' dev_server.py` → 0 träffar | `4a56a18`: 307 → `/openapi.json`; `_FRAMEWORK`-rader verifieras numera i stället för antas |
| N2 | `/v1/verticals` svarade med faktornedbrytning i FastAPI och bara id/label i dev — samma väg, olika nyttolast, osynligt för ett kontrakt som låser vägar | jämförelse av de två handlerkropparna | `4a56a18`: samma form + riktat lås |
| A4 | `_OPEN_PATHS` kunde drifta mellan lagren utan att något test såg det; PUT/DELETE-rutter kan inte ens upptäckas av dev-parsern | tuplarna skiljde (`/docs`) | `4a56a18`: paritetslås + förbudstest tills parsern byggts ut |
| A5 | Tio öppna vägar lämnade inget spår i `/metrics` — en driftbild där startsidan aldrig hänt | räknaren saknade vägarna | `ee650be`: metrik utan audit-brus (medvetet val, dokumenterat); bevisat via no-op-mutation |
| A6 | Dev-servern saknade CORS helt medan FastAPI hade det — odokumenterad skillnad som gav tysta preflight-fel | `grep -i cors dev_server.py` → 0 | `4a56a18`: samma `LANDVEX_CORS_ORIGINS`, origin ekas aldrig oprövad; verifierat mot körande server |
| A4-korr | "`_MIN_ROLE` saknar paritetslås" var FELAKTIGT: tabellen är en, i delade `api/security.py` | planeringsagentens motläsning | ingen åtgärd |

### Lagergränser och hygien

| # | Fynd | Bevis | Fix |
|---|------|-------|-----|
| — | `integrations/__init__` påstod att motorn "importerar ALDRIG härifrån" — **osant**: fyra lata importer vid medvetna sömmar, plus `engine/surface.py` → `api.catalog` | ast-svep över alla importer | `9a5cea2`: sömmarna som data (`LAYER_SEAMS`) med skäl per rad; docstringen säger sanningen; en onämnd smygväg faller i självrevisionen |
| E1 | "commission/glossary/specialization otestade" var ÖVERDRIVET (täckta i andra filer) — men intäktsmodellens beräkning var olåst och ordlistans substans oprövad | planeringsagentens motläsning + riktad genomgång | `b2ebeed`: `test_commission` (nivåtäckning utan hål, monotoni, båda skalorna, fakturan == katalogen == `/v1/plans`), `test_glossary` (cannot_en med substans, proveniens i from_en, boostar bara på faktorer som finns) |
| E2 | Kvarglömd `landvex-opportunity-engine/` på disk — månader gammal motorkopia som redan lurat två av revisionens egna agenter | ospårad vid HEAD, 980K | `b2ebeed`: raderad |
| E3 | `landvex-audit.log` ligger kvar i git-HISTORIKEN (borttagen ur spårning i `6f9e711`, men blobbar består) | `git show 235c172:landvex-audit.log` → **4 rader dev-tenant-metadata: tenant/roll/nyckel-id/väg/tid. Inga hemligheter, inga riktiga kunder** | **Medvetet icke-fix.** En history-rewrite bryter varje klon och kostar mer än 4 rader utvecklingsmetadata motiverar. Beslutet är ditt: `git filter-repo --path-glob '*landvex-audit.log' --invert-paths` + force-push om repot någonsin delats och raderna bedöms känsliga. Ingen nyckelrotation behövs — nyckel-id:t i raderna är maskerat (`open`) |

## Revisionen som produktyta

Mätningarna ovan åldras inte i den här filen: de körs som **åtta
kontroller** i `engine/selfaudit.py`, exponerade på
**`GET /v1/integrity/audit`** (kapabilitet `core` — den som ska lita på
plattformen får se granskningen utan att köpa något; `/v1/audit`,
säkerhetsloggen, är en annan yta och förblir admin + platform_ops).

Varje kontroll bär `what_en` OCH `cannot_en`: en statisk skanning
bevisar att en vakt *finns*, aldrig att koden bakom den är korrekt, och
det står på svaret. Grindkontrollen kräver API-lagrets kontext — utan
den **redovisas den som refused i stället för att gissas**. Aggregatet
är innehållsadresserat (`audit_id`), fälls av ett enda fynd, och
`tests/test_selfaudit.py` bevisar varje kontroll mot syntetiskt
underlag där felet finns — plus att den riktiga kodbasen passerar sin
egen revision. Det sista testet är plattformens gröna stämpel, och det
faller när nästa regression införs.

## Vad revisionen INTE prövade

* **Nätverkande verkligheten**: 0 av 22 källklienter är live-
  verifierade — nätet är policyspärrat här, och `verified_live` sätts
  aldrig av något annat än en riktig probe. Oförändrat blockerat.
* **Postgres mot en riktig databas**: driftjämföraren läser DDL-text;
  `selftest()` (nu körbar för första gången) är driftsättningens sak.
* **Beteende bakom vakterna**: självrevisionen ser struktur. Att talen
  är rätt bevisas av motorernas egna sviter, inte av den.
