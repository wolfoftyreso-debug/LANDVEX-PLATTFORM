# Changelog

Formatet följer [Keep a Changelog](https://keepachangelog.com/); semantisk versionering.

## [Ej släppt] — driftsättning

**Imagen var trasig.** `Dockerfile` kopierade `engine`, `api` och
`frontend` — men inte `integrations`, som `api/main.py`,
`api/dev_server.py` och två datakällsadaptrar importerar. Containern
kraschade på import, och hela sviten var grön, eftersom testerna kör mot
arbetskatalogen där allt finns. Ett bygge som är grönt i CI och dött i
containern är den dyraste sorten: felet upptäcks av den som driftsätter,
inte av den som skriver.

- **`engine/deployment.py`** — ett register över alla 66 miljövariabler
  med den enda rad som spelar roll vid en driftsättning: *vad händer om
  den inte är satt?* Nivå (`required`/`recommended`/`optional`), syfte,
  konsekvens, och `secret` för de elva vars värde aldrig får lämna
  processen.
- **Ett test hävdar åt BÅDA håll.** Varje variabel koden läser står i
  registret, och varje registrerad variabel läses av koden. Första
  körningen hittade sex odokumenterade — och när regexen bara sökte
  `os.environ` missade den åtta till, som sensorklienterna läser via
  klassattributet `ENV`. En dokumentation som får glida ifrån
  verkligheten är sämre än ingen, för då tror man på den.
- **`scripts/preflight.py`** — kontrollen körs, den beskrivs inte. Den
  SKRIVER en riktig temporärfil till lagersökvägarna: en sökväg som ser
  rätt ut men ligger på en read-only mount upptäcks annars av första
  kunden som sparar något. Den öppnar däremot medvetet ingen
  databasanslutning — ett preflight som hänger trettio sekunder på en
  felaktig security group blir självt problemet det skulle upptäcka.
- **Startspärren ligger i containerns startväg**, inte i ett dokument:
  `CMD python -m scripts.preflight --gate && exec gunicorn …`.
  `LANDVEX_PREFLIGHT` avgör vad ett underkänt resultat kostar — `strict`
  vägrar ta trafik, `warn` startar och lägger skälen överst i loggen,
  `off` hoppar över. Ett okänt värde tolkas som `warn`, aldrig som av:
  ett stavfel får inte stänga av spärren. CI kör spärren mot en TOM
  miljö och faller om den godkänner den.
- **Två kombinationer är farligare än summan av delarna** och fälls
  därför var för sig: utan både nycklar och JWT är API:et ÖPPET — varje
  anropare blir admin i tenant `dev` på enterprise-planen, och
  tenant-isoleringen skyddar då ingen från någon.
- **SQLite-varningen räknar nu skrivare** (`LANDVEX_REPLICAS ×
  WEB_CONCURRENCY`) i stället för att alltid gå igång. Ett medvetet
  enprocessbygge med monterad volym är ett giltigt val och blir grönt,
  med taket utskrivet. En varning som aldrig går att bli av med lär
  läsaren att klicka förbi varningarna — och då fyller de ingen funktion
  när det gäller.
- **`deploy/aws/task-definition.json`** — ECS Fargate, redo att
  registreras. Fyra saker i den är bärande och har varsitt test: varje
  namn under `environment`/`secrets` finns i registret (en uppgift som
  sätter `LANDVEX_DATABASE_URL` registreras utan protest och gör
  ingenting); ingen hemlighet ligger i klartext där alla med
  `ecs:DescribeTaskDefinition` ser den; `stopTimeout` överlever
  gunicorns `--timeout`; publicerad port, `LANDVEX_PORT`, `EXPOSE` och
  hälsokontrollens URL är samma tal. Ett femte test kör startspärren mot
  exakt den miljö ECS sätter — och hittade en sökväg som ingen skapade.
- **`.env.example` genereras** ur registret, och ett test faller om den
  incheckade filen glidit isär från det. Hemligheter lämnas tomma:
  ett värde i en fil checkas in förr eller senare.
- **`docs/aws.md`** — körboken. Varje steg som kräver ett AWS-konto är
  utmärkt som sådant, så att det som återstår är transkribering, inte
  design.

## [Ej släppt] — tenant-isolering

**Säkerhetsfel.** Plattformen autentiserade tenant, loggade tenant i varje
revisionsrad — och kastade den innan lagret rördes. Bara `usage_meter` bar
en tenant-kolumn.

Bevisat mot en körande server med två API-nycklar: "Konkurrent AB" kunde
lista OCH läsa "Tyresö kommuns" affärsprofil i klartext, se kommunens
rapporter, och läsa dess ansvarskort med beslutsfattarnas namn, antal
beslut och infriandegrad.

- **`tenant` är nu obligatoriskt** på de sex lagermetoder som rör
  kunddata. Nyckelordsargument utan default: ett argument man KAN glömma
  är en läcka som väntar. Alla anropsställen bröt vid ändringen — vilket
  var meningen.
- **Migration 6** lägger tenant-kolumn och index på `reports` och
  `profiles`. Befintliga rader får `''` och blir därmed osynliga för alla
  riktiga tenants: att gissa vem gamla rader tillhör vore att gissa fel
  för någon. Fail closed.
- **PostgresStore speglar SQLite.** Ett lager som isolerar i utveckling
  men inte i produktion vore värre än inget — det ser säkert ut precis
  där ingen kund finns. Ett test jämför båda kontrakten.
- **Ansvarskortet** (`/v1/decisions/ledger`) filtreras på tenant stämplad
  i posten. Beslutstabellen har ännu ingen tenant-KOLUMN; filtrering på
  fältet ger samma skydd med mindre ingrepp i schemat.
- **Ett statiskt test** läser båda API-lagren och faller om ett nytt
  anrop till en kundddata-metod saknar `tenant`.

- **Bevakningar** (`monitors`) bar samma fel och stängdes på samma sätt.
  `all_monitors()` gav alla kunders regler och `/v1/monitors/run` matade
  exakt den listan till evalueringen: en kund körde cron och fick svar på
  en annans bevakningar — vilken mätare de vakar på, vilken tröskel de
  satt, vem hos dem som är ansvarig. `get_monitor()` tar nu också tenant,
  eftersom det annars räckte att KÄNNA id:t.

**Vad som delas, och varför** står i klartext i
`tests/test_tenancy.NOT_YET_ISOLATED`, med ett test som faller om en
tabell isoleras utan att listan uppdateras:

  * `outcomes` delas **med flit**. Kalibreringen blir bättre ju fler
    utfall den sett, och det enda som lämnar motorn är aggregat (Brier,
    hinkar, n). Mätt: kalibreringsrapporten innehåller ingen råpost, och
    varken `all_records` eller `all_outcomes` refereras av någon endpoint.
    Ett test håller fast vid båda halvorna — delad inlärning, inga läckta
    poster — och faller om någon börjar servera råposterna.
  * `corrections` är en medborgarallmänning; `signal_cache` är offentlig
    källdata där en delad cache är hela poängen. Båda avsiktliga, båda
    utskrivna så att valet är uttalat och inte antaget.

En halvt isolerad plattform som tros vara helt isolerad är farligare än
en ingen litar på.

## [Ej släppt] — samstämmighet

**Fler sensorer gör inte ett underlag robustare av sig självt.** Tio
mätpunkter på samma väg, från samma myndighet, genom samma insamlings-
kedja, faller tillsammans när kedjan gör det — och tio samstämmiga tal
från ett trasigt system ser precis ut som tio samstämmiga tal från ett
fungerande.

- **`engine/corroboration.py` (GET/POST /v1/corroboration)** poängsätter
  hur väl underbyggt ett påstående är: hur många OBEROENDE nät som säger
  det, om de mäter olika fysiska storheter, och om de är överens.
- **En källa kan aldrig bekräfta sig själv**, hur perfekt den än stämmer
  med sina egna avläsningar. Taket är `weak`.
- **Oenighet är ett eget utfall.** Två nät som pekar åt olika håll är
  sämre underlag än ett ensamt: minst ett har fel och det går inte att
  veta vilket. Första versionen gav dem `strong` — oberoende och olik
  modalitet räknades in medan oenigheten bara lät bli att lägga till.
- **Modalitet skiljer sig från leverantör.** Två vägräknarnät är
  oberoende men mäter samma storhet och kan dela systematiskt fel; en
  vägräknare och en luftkvalitetsmätare kan inte det.
- **Flera leverantörer per sensorklass.** Strukturen tillät bara en, och
  dolde därmed att skillnaden fanns. `road_flow` och `weather` har nu två
  oberoende nät var.
- **Fyra nya klienter**, alla öppna: USGS seismik (GeoJSON, ingen nyckel),
  Digitraffic AIS och väg (Fintraffic, ingen nyckel), NOAA/NWS väder.
  Sjuttonde sensorklassen: seismik.

## [Ej släppt] — sensorer

Upptäcktslagret känner igen nio sorters FYSISK förändring medan varenda
inkopplad källa är statistik som uppdateras kvartalsvis. Plattformen kunde
upptäcka saker den inte hade någon möjlighet att se.

- **`engine/sensors.py` (GET /v1/sensors)** — 16 sensorklasser, från
  elnätstelemetri och satellitpassager till avfallsvolymer och
  parkeringsbeläggning. Varje klass namnger vilka upptäckter den kan mata,
  hur ofta den säger något nytt, och — den viktiga delen — vad den ALDRIG
  kan avgöra.
- **Tre lägen, inte två.** `adapter` = adapter mot ett publikt API.
  `contract` = ingen publik API finns, men det finns en dokumenterad form
  en ägare kan leverera in i. `none` = ingenting. Skillnaden är inte
  kosmetisk: `contract` väntar på ett AVTAL, `adapter` på en nyckel, och
  det är helt olika sorters arbete. Fördelningen är 7 · 7 · 2.
- **Sex adaptrar** mot riktiga protokoll: Trafikverket TrafficFlow, SMHI
  metobs, SMHI hydrologi, OpenAQ v3, Copernicus STAC, och en generisk
  ägarfeed som sju klasser delar i stället för att få var sin halvfärdig
  adapter mot ett API som inte finns publikt.
- **Copernicus-klienten hämtar inga bilder.** Den svarar på frågan som
  avgör om en jämförelse alls är möjlig: finns två tillräckligt molnfria
  passager? Moln över en tomt är inte bevis för att inget hänt — det är
  frånvaro av observation, och de två får aldrig blandas ihop.
- **Strömbrytaren flyttades till `faults.py`** och delas av register- och
  sensorklienterna. Ett mätnät har hundratals punkter; en nere källa får
  kosta ett misslyckat anrop, inte ett per punkt.
- **`scripts/sensor_probe.py`** bekräftar adaptrarna där nätet är öppet.
  Den skriver aldrig `verified_live` själv — ett enda lyckosamt anrop ska
  inte kunna märka kod som bevisad.
- **`/explore` visar landskapet** med "Cannot"-raden som huvudsak. Läget
  bärs av ett ord OCH en punkt, aldrig av färgen ensam.

Sensordata frestar värre än statistik: en mätning i minuten KÄNNS som
kunskap. En trafikräknare som visar fyrtio procent mindre flöde vet inte
om vägen stängdes, arbetsgivaren flyttade eller slingan gick sönder.

## [Ej släppt] — kundytan

Namnen på kundytan beskrev hur plattformen är BYGGD, inte vad någon får.
"Lambda Index", "STRIM Knowledge Graph", "Significance Selector",
"Setpoint & Tolerance", "Installed Base Engine" — en kund kan inte vilja
ha något hon inte kan namnge.

- **43 motoretiketter omdöpta** till frågan de besvarar. `Lambda Index` →
  `Balance across the board`; `Significance Selector` → `Is this worth
  reacting to?`; `Setpoint & Tolerance` → `Reference levels: what counts
  as normal`; `Market Saturation` → `Is the market full?`. Namnen kommer
  ur vad motorerna faktiskt gör — beskrivningarna lästes först, eftersom
  ett felaktigt namn är sämre än ett fult.
- **Id:na är orörda.** `label_en` är ytan, `id` är kontraktet som löften,
  kapabiliteter och maskiner hänger på. Ett test hävdar skillnaden.
- **Taglinen** var en marknadskategori: "Decision Intelligence for the
  Physical World" är vad ett analysföretag kallar facket, inte vad en kund
  säger till en kollega. Nu: **"What the data supports — and where it runs
  out"** — ett löfte som dessutom namnger vägran, vilket är positionen.
- **Ett test spärrar återfall**: interna ord (engine, adapter, selector,
  seam, loop, graph, index, registry …) får inte förekomma i ett namn en
  kund läser. Beskrivningarna får vara tekniska; namnen inte.

Testet fällde direkt en av mina egna nya etiketter — "How much service
this place needs" — på ordet `service`. Ordet är tvetydigt: mikrotjänst är
ett byggord, servicebesök är kundens eget och hela den motorns ämne. En
regel som slår på rätt namn är fel regel, så ordet togs bort ur listan i
stället för att etiketten undantogs.

## [1.1.0] — 2026-07-25
Skörd ur `dissg` (Reality Index / NOGF / STRIM) — 13 russin (A–N) portade in i
den beroendefria kärnan och wire:ade i båda API-lagren. Kedjan mät → upptäck
förändring → poängsätt signifikans → strukturera beslut → citera.

- **Integritet** (`engine/integrity.py`): neutralitetsgrind, kausal/normativ
  sanering, citat-verifiering (anti-hallucination), evidence-links, självrevision.
- **Fundament**: `scorekit.py` (generisk viktad scorer), `stats.py` (CUSUM,
  Pearson, Spearman, lag, z-score, linreg), `kpi.py` (registry + invert-medveten
  status + alerts).
- **Index & kalibrering**: `lambda_index.py` (geometrisk λ över 8 axlar),
  `setpoints.py` (Maastricht 60, Gini 0.30, TFR 2.1 …).
- **Påståenden & governance**: `claims.py` (innehållshashade versionerade
  påståenden, NOGF 3-ägar-governance, k-anonymitet, citat i text/APA/BibTeX).
- **Förändringsdetektion**: `feeds.py` (why-now-händelser, checksum-dedup),
  `worthiness.py` (signifikans-väljare), `decision.py` (Decision Graph +
  krisgrind före `/v1/ask`).
- **Data & paketering**: `datasources/kolada.py`, `datasources/svk.py` (riktiga
  endpoint-id, ärlig degradering), `strim.py` (citerbar neutral entitetsgraf),
  komplexitetsbudget + månadsfönster i `api/licensing.py`.
- **Frontend**: ny Console-flik — λ-oscilloskop, glödande karta, KPI-signaler
  (λ live från `/v1/lambda`).
- Nya endpoints: `/v1/kpi`, `/v1/lambda`, `/v1/setpoints`, `/v1/cite`,
  `/v1/feeds`, `/v1/worthiness`, `/v1/decision`, `/v1/strim`, `/v1/kolada`,
  `/v1/svk`. 38 testsviter gröna, båda API-lagren i synk.
- Fullständig skördekarta + provenienser i `docs/HARVEST-FROM-DISSG.md`.

## [1.0.0] — 2026-07-24
Första fristående releasen — utlyft ur monorepo till eget, rent repo.

- Beroendefri motorkärna (`engine/`, stdlib) + dubbla API-lager (FastAPI +
  stdlib-server), låsta lika av kontraktstest.
- 6 beslutslager (Opportunity Score, Opportunity Intelligence, Risk
  Intelligence/Business Signals, Workforce, Installed Base, Intelligence Map).
- 35 marknader / 344 regioner (alla 50 US-delstater, alla 27 EU-länder).
- Datakällor via Resolver-kedja: SCB live; permits/places/programs/quiXzoom
  kod-klara, aktiveras per env-variabel; ärlig degradering till mock.
- Självförsörjande portal med intro-hero. 24 testsviter, självupptäckande CI.
