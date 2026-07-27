# Changelog

Formatet följer [Keep a Changelog](https://keepachangelog.com/); semantisk versionering.

## [Ej släppt] — prober som går att tolka

**Ett spärrat nät är inte en trasig adapter.** Skillnaden är hela poängen
med en probe, och den var borttappad: `RegisterProvider.fetch` kastade
bort felet den svalde, så svaret på "kom vi fram?" fanns inte kvar
någonstans. Proben kunde bara räkna upp vad som kan ha hänt — och skrev
det också: *"unreachable, path wrong, or the response shape differs"*.
Tre möjligheter i en mening är inget utfall.

- **`scripts/probe_all.py` (`make probe`)** kör alla prober och ger ett
  verdikt per källa: `answered`, `wrong_shape`, `blocked`,
  `not_configured`, `bad_args`, `our_bug`, `unclear`. Den skriver ut
  `file:line` för de källor som svarat — och bara dem. En bock satt på
  känsla är värre än ingen bock.
- **Tre fel i första körningen, alla samma sort: den läste ord ur
  brasklappar.** Ordet "unreachable" plockades ur meningen ovan och
  kallades ett verdikt. `livability_probe` avslutar med 0 utan att prova
  något ("nothing to probe") och räknades som *svarade* — en avbockad
  verifiering som aldrig skett. Och "no industry code mapped", som var
  ett felaktigt argument från min sida, lästes som ADAPTERFEL och hade
  skickat någon att leta efter en parserbugg som inte finns.
- **Providern bär nu `last_error`** och nollar det vid lyckat anrop,
  precis som `Breaker` i `faults.py` gör av samma skäl.
  `scripts/register_probe.py` returnerar därmed exit 3 för "kom aldrig
  fram", skilt från 1 för "kom fram men formen stämde inte".
- **`unreachable()` flyttad till `engine/datasources/faults.py`** och
  används av båda proberna. Ett test hävdar att definitionen finns exakt
  en gång — två kopior av samma regel glider isär, samma skäl som att
  `percentile` bor på ett ställe.
- **`verified_live` satt bara på basklassen.** En enda ändrad rad hade
  bockat av alla tio klienterna samtidigt; det gick alltså inte att säga
  att SMHI svarat men OpenAQ inte. Varje klient bär nu ett eget fält.
- Utfall i byggmiljön: **0 svarade · 6 spärrade · 14 ej konfigurerade**,
  ingenting avbockat. Proxyn nekar CONNECT med 403 och registrerar
  avslaget själv. Det är ett svar, inte ett fel.

## [Ej släppt] — lägesbilden svarar på affärsfrågorna också

Rapporten var teknisk. En VD, en säljchef och en investerare letar efter
tre andra saker, och de saknades — så de har lagts till, **härledda på
samma villkor som resten**: inga inskrivna tal.

- **Reality intelligence status** överst: marknader, källadaptrar,
  liveverifierade, modaliteter, och detektionstäckning i TVÅ nivåer —
  vad vi KAN läsa (9 av 9) mot vad som är BEVISAT (0 av 9). Skillnaden
  är hela rapportens poäng.
- **Ingen "genomsnittlig samstämmighet i procent"**, trots att en sådan
  rad efterfrågades. `engine/corroboration.py` vägrar med flit uttrycka
  samstämmighet som procentsats — en siffra som "84 % säkert" inbjuder
  till att multipliceras vidare i kalkyler den inte tål — och en
  säljsiffra får inte smyga in den bakvägen. Det som redovisas är
  strukturellt och räknebart: hur många klasser som har ett andra
  oberoende nät (2 av 9). Ett test faller om en procentsats införs.
- **Commercial readiness**: en rad per förmåga, härledd. `Billing` fick
  först en bock med brasklappen "men ingen betalintegration" — en bock
  med brasklapp är ingen bock, och ett test förbjuder nu just den
  konstruktionen.
- **Trust index** med komponenter och totalsumma, plus raden som gör
  talet ofarligt: **måttet gäller BYGGET, aldrig ett enskilt svar.** Ett
  tillitstal som läses som "hur säkert är det här svaret" är farligare
  än inget tal alls. `--with-tests` kör sviten på riktigt i stället för
  att hitta på en testprocent — en påhittad siffra bland mätta ärver de
  andras trovärdighet.
- **Competitive position** som fakta, **utan konkurrentkolumn**: vi kan
  mäta oss själva, men vad en konkurrent gör kan vi bara påstå, och ett
  påstående i en tabell full av mätvärden ser ut som ett mätvärde.
- Totalsumman räknas på de PUBLICERADE talen, inte på de oavrundade. En
  läsare som adderar raderna ska få rapportens egen summa — annars är
  siffrorna inte kontrollerbara, vilket var hela skälet att mäta dem.

Utfall nu: overall **33,1 %** utan sviten mätt, **42,7 %** med. Den
siffran ska stiga månad för månad, och de två nollorna som håller ner
den — `live_sources` och `calibration` — är exakt de två översta
punkterna i planen.

## [Ej släppt] — lägesbilden mäts

**Ett lägesdokument åldras i tysthet.** Siffror skrivna för hand var
sanna den dag någon skrev dem och blir felaktiga utan att någon märker
det — och en läsare som upptäcker EN fel siffra slutar tro på hela sidan.

- **`scripts/standing.py` (`make standing`)** mäter nuläget ur koden vid
  körning: marknader, byggda mot planerade beslut, sensorlägen,
  leverantörer per klass, verifierade källor, testsviter, och om miljön
  skulle klara startspärren. Luckorna HÄRLEDS ur samma mätning.
- **Planen räknar av sig själv.** Varje post bär ett `done_when` som
  läser mätningen; en punkt som blivit klar markeras klar och försvinner.
  Bevisat med ett test som lägger till ett byggt beslut och kräver att
  posten stänger sig.
- **Två noggrannheter som annars hade gjort bilden bättre än den är:**
  registerklienterna bär `verified_live` som fält i sin katalograd och
  sensorklienterna som klassattribut — räknas bara den ena blir det 10 av
  10 obekräftade i stället för 14 av 14. Och en klass utan adapter saknar
  inte ett ANDRA nät, den saknar det första.
- **`--md` skriver en överlämning** med doktrinen som inte får förhandlas
  bort, så att en mottagande session ärver omdömet och inte bara talen.
  Konkurrensbilden är märkt som analys, inte mätning.

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
- **CI bygger och startar imagen.** Sviten kör mot arbetskatalogen, där
  allting finns; imagen är en annan maskin. Jobbet bygger, importerar
  båda API-lagren inne i containern, kräver att startspärren vägrar utan
  nycklar, och ställer tre riktiga frågor till den körande servern:
  `/health` svarar 200, `/v1/catalog` utan nyckel ger 401, med nyckel
  200. Revisionsraden i containerloggen visar `key_id: "cite…"` —
  nyckeln själv hamnar aldrig i loggen.
- **Jobbet hittade ett fel på sin första körning, och det var mitt.**
  `COPY scripts ./scripts` stod i Dockerfile — och `scripts` stod i
  `.dockerignore`. Bygget föll på COPY-raden, alltså hade raden aldrig
  fungerat. Testet som skulle skydda saken läste bara Dockerfile och sa
  god dag: halva sanningen ser precis ut som hela. Ett nytt test
  korsläser filerna, prövat genom att lägga tillbaka raden.
- **`deploy/aws/execution-role-policy.json`** — `GetSecretValue` på
  exakt de fem hemligheter uppgiften nämner, inte på `landvex/*`, som
  gör nästa hemlighet under prefixet läsbar utan att någon beslutat det.
  Två test håller policyn mot uppgiftsdefinitionen åt båda håll: en
  hemlighet uppgiften begär men rollen inte får läsa gör att uppgiften
  inte startar, med ett felmeddelande som citerar ett ARN och ingenting
  annat.
- **`preflight --egress`** skriver ut vilka värdar den KÖRANDE miljön
  ringer ut till, med den variabel som orsakar varje anrop. En brandvägg
  öppnad efter en handskriven lista stänger ute den källa någon la till
  i veckan — och det felet ser exakt ut som en trasig adapter.
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
