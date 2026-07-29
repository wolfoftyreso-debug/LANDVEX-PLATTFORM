# Changelog

Formatet följer [Keep a Changelog](https://keepachangelog.com/); semantisk versionering.

## [Ej släppt] — Palantir-revisionen: hela systemet mätt mot sin egen ambition

Full rapport med bevis per fynd: `docs/palantir-revision-2026-07-29.md`.
Åtta fixgrupper, varje regressionstest bevisat bitande via mutation:

- **Grupp 1** (`4a56a18`): tre ogrindade vägar (`/v1/verticals`,
  `/v1/commercial`, `/v1/entitlements`) → `core`; svep-test över ALLA
  routade vägar; `_OPEN_PATHS`-paritet; `/docs` i dev-servern (kontrakts-
  kommentaren "båda serverar dem" var osann); `/v1/verticals` samma
  nyttolast i båda lagren; CORS i dev via samma variabel som FastAPI.
- **Grupp 2** (`ee650be`): öppna vägar syns i `/metrics` — en driftbild
  där startsidan aldrig hänt är gladare än verkligheten. Ingen
  audit-rad, medvetet.
- **Grupp 3** (`79da646`, `24fc274`): postgres får sqlite-kedjans
  migrationsliggare (baslinjen härledd, kan inte drifta) och ett
  statiskt schemadrifttest; `selftest()` kunde aldrig starta
  (TypeError på tenant-kravet) — fixad; deploy-testet bar gamla
  doktrinen som regel och godkände avsaknaden av liggare.
- **Grupp 4** (`e8447ce`, `699019c`): `data_coverage` + `sides_real` på
  kontradiktionsindexet (flaggskeppet kunde stå på 100 % simulering
  omärkt); `kalla` + täckning i segments/installed_base; EN delad
  motordefault. Första defaultvalet (produktionskedjan) FÄLLDES AV CI —
  72 s och icke-determinism med öppet nät — och återtogs: defaulten är
  märkt simulering, produktionskedjan ett uttryckligt val.
- **Grupp 5** (`6a4021b`): fyra `except OUR_BUGS: raise`-vakter (en
  plats svalde `ImportError` — medlem i OUR_BUGS); svepet gäller hela
  kodytan med allowlist som data; `probe_all`:s "Samma lista"-kopia
  hade redan driftat och härleds nu ur källan.
- **Grupp 6** (`b2ebeed`): fällkatalogen `landvex-opportunity-engine/`
  raderad; intäktsmodellen och ordlistan riktat testade.
- **Grupp 7** (`9a5cea2`): **`GET /v1/integrity/audit`** — revisionens
  mätningar som stående yta, åtta kontroller med `what_en`/`cannot_en`,
  refused utan API-kontext i stället för gissning, innehållsadresserat
  `audit_id`, `core`-kapabilitet. Lagersömmarna som data
  (`LAYER_SEAMS`) ersatte en osann "ALDRIG"-regel.

Medvetet icke-fixat, med skäl i rapporten: audit-loggblobbarna i
git-historiken (4 rader dev-metadata, inga hemligheter — history-
rewrite är användarens beslut). 87 → **90 sviter gröna**.

## [Ej släppt] — bygglov ur öppna register, och sveparen som inte såg dem

Den fjärde blockeraren var inte en blockerare. Jag rapporterade
"ingen öppen nyckellös bygglovskälla finns" och det var **fel för USA**:
amerikanska städer publicerar sina bygglov på **Socrata utan nyckel**.

- **`socrata_permits`** (nyckellöst) — sju stadsregister som data
  (NYC, Chicago, Seattle, Austin, San Francisco, LA, Dallas), ett
  `count(1)`-anrop per stad och dygn. `/v1/coverage?market=us`:
  14,5 → **16,8 %**. Räckvidden är KOMMUNEN och står på raden; de 68
  regioner som saknar register får **tomt, inte en skattning**. Ingen
  `permitted_m2` hämtas — registren bär ingen area, och att räkna om
  byggkostnad till kvadratmeter är en gissning med en enhet på.
- **Rättat: motsägelsesvepet såg inte det skörden hämtat hem.**
  `relationships` fick sin egen resolver; `contradictions` fick den
  aldrig och föll till scoring-modulens mock-only-resolver. Med sju
  bygglovsregister i lagret rapporterade svepet ändå **varenda region som
  "allt simulerat"** — ett besked om sig själv presenterat som ett besked
  om världen. Efter fixen blir samma regioner `skipped_one_sided`.
- **Rättat: `permitted_m2` stod i `indices._PLANNED` med vikt 0,3 utan
  att finnas i signalkatalogen.** Ingen källa fyllde den, så den bidrog
  tyst med noll — och den dag en källa gjorde det hade
  `normalize(CATALOG[sid], …)` rest KeyError mitt i plattformens
  signaturanalys. Signalen finns nu, med **samma enhet och samma
  normalisering som `development_m2`**: normaliseras de två sidorna
  olika mäter "motsägelsen" skalvalet. Ett nytt test i
  `tests/test_coverage.py` låser att inget index pekar utanför katalogen.

`public_data_alignment` står **fortfarande som `refused`**, och nu av ett
skarpare skäl än förut: den planerade sidan är verklig i sju amerikanska
städer, men den **observerade** sidan (`development_m2`,
`renovation_index`) har ingen öppen nyckellös motsvarighet. Overpass ger
ett ANTAL byggnader, inte en area, och att lägga ett antal i en signal
som mäter kvadratmeter är samma enhetslögn som räknas som fel överallt
annars i den här kodbasen.

## [Ej släppt] — nyhetsskörden bevisad, och två spärrar som saknades

`independent_verification` gick från vägran till räknad — och på vägen
dit föll två fel som båda hade gett tal om fel land.

- **Skörden körd hela vägen mot en riktig HTTP-server**
  (`tests/test_news_harvest.py`): fyra RSS-flöden, ingen fejkad
  transport, hela kedjan urllib → Breaker → parsning → checksumma →
  `news_items`. Tre titlar med samma telegram i två ägargrupper blir
  **ett kluster, två nät**; den fjärde står ensam och får inte påverka
  något. Andra körningen lagrar samma rader, inte dubbelt så många —
  bevisat även över en omstart av lagret.
- **Sverige passerar viktgolvet för första gången**: `of_weight`
  0,25 → **0,55**, index **63,6**. `public_data_alignment` och
  `event_coverage_ratio` står kvar som `refused` och namnges i svaret.
- **Rättat: `independent_verification` läste HELA nyhetslagret oavsett
  marknad.** Två svenska tidningar gav **Tyskland och Japan 100 %**
  oberoende verifiering. Det är precis det modulens egen inledning säger
  sig undvika — ett tal om ETT lands press räknat på ett ANNATS.
  `news.all_items` tar nu `market`, och ett kluster måste innehålla minst
  en rad från landets egen press. Globala telegram får bekräfta en
  inhemsk uppgift, men ett kluster som bara är telegram är ingen tysk
  journalistik.
- **Rättat: motsägelsesvepet krävde bara att NÅGON drivare var verklig.**
  Med enbart den observerade sidan verklig rapporterades Solna som en
  kontradiktion på 36 med `sources: ["mock", "osm"]`, presenterat som
  "a finding about the place" — hela avståndet kom ur mockdata. Spärren
  gäller nu **per sida**: verkligt papper OCH verklig mark, annars
  `skipped_one_sided`. Felet var latent i dag och hade slagit till i
  samma stund som den första riktiga bygglovskällan kopplades in.

Fortfarande blockerat med angivet skäl: **ingen öppen nyckellös
bygglovskälla finns** — Boverket har inget publikt API och kommunernas
portaler är fragmenterade. Fixtur bevisar parsning och lagring, aldrig
att en adress svarar: **inget `verified_live` sätts av det här**, och ett
test låser det.

## [Ej släppt] — referensdata som lyfter USA över grinden

Tre av MRAI:s fyra blockerare, angripna där de faktiskt satt.

- **US Census CBP** (nyckellöst) som skördekälla → arbetsställen per
  delstat. Mätt mot fixtur, 75 regioner: `/v1/coverage?market=us` gick
  från **real_weight 0,0 (none) till 14,5 % (thin)** — **över MRAI:s
  10 %-grind**. Första gången plattformen kan säga något alls om en
  marknad utanför Sverige utan att gissa. CBP svarar per DELSTAT och inte
  per metro; talet märks med sin räckvidd i stället för att låtsas vara
  stadens.
- **Kolada N07403** (nyckellöst) → anmälda våldsbrott per 100 000, den
  anmälda halvan av uppmärksamhetsindexet. Sverige: 24,5 → **39,0 %**.
- **`event_coverage_ratio` bygger nu sina egna rader** ur det som
  faktiskt är skördat — anmält per 100k, befolkning och publicerade
  artiklar per region. En rad utan alla tre tas inte med: att skicka in
  halva rader hade gjort funktionens vägran till en gissning om vad som
  saknades.

Båda marknaderna vägrar fortfarande på **viktgolvet** — bara 25 % av den
avsedda vikten går att räkna — och det är rätt svar. Komponenterna visas,
talet gör det inte.

Kvar för ett publicerbart index: en bygglovskälla (kontradiktionsindexet
är annars ren mock) och en körd nyhetsskörd. Båda är namngivna i svaret,
inte bortmedelvärdade.

## [Ej släppt] — MRAI: index där vi kan se, vägran där vi inte kan

Media Reality Alignment Index per marknad, 0–100, sammansatt av motorer
som redan finns — `engine/mrai.py`, `GET /v1/mrai`, `GET /v1/mrai/compare`.

**Det finns exakt ett sätt att göra ett sådant här index skadligt: att
räkna det på underlag vi inte har.** `/v1/coverage` mäter real_weight 0,0
för 34 av 35 marknader. Ett index på det underlaget ger låg alignment åt
länder där VI saknar referensdata — inte åt länder där medierna avviker.
Ett land med svag statistikmyndighet skulle få dåligt betyg för att vi
inte kan se, och talet läses som ett omdöme om deras press.

Därför två absoluta spärrar:

- **Under 10 % referenstäckning finns inget indexvärde.** Inte ett lågt —
  inget. `status: "insufficient"`, skälet i klartext, och en lista på
  vilka källor som skulle öppna det.
- **Under 50 % av den avsedda vikten publiceras inget sammanvägt tal.**
  Ett index ur en fjärdedel av sina komponenter ser likadant ut som ett
  ur alla, och läsaren kan inte se skillnaden utan att öppna det.
  Komponenterna visas ändå — vägran är inte tystnad.

Fyra viktade komponenter, alla ur befintliga motorer: källdiversitet
(oberoende nät per sensorklass), oberoende verifiering (ägare, inte
titlar), överensstämmelse med offentliga register (kontradiktionsindexet)
och händelsetäckning (publicerat mot anmält per 100k). Referenstäckningen
är en **grind med vikt noll** — den betygsätter ingenting, den avgör om
något alls får betygsättas.

Varje komponent går att öppna: vad den vilar på, hur många källor, och
vad den inte kan avgöra. Vikterna är data och säger själva att de är en
dokumenterad heuristik.

Jämförelsen behåller de omätbara **i listan**, utan värde, med sitt skäl:
en ranking som tyst tappar det den inte kan mäta ser fullständig ut och
är det inte. Och indexet säger rakt ut att det inte är en
pressfrihetsranking — låg alignment kan betyda avvikande rapportering,
svaga offentliga register eller tunn referensdata hos oss, och indexet
kan inte skilja dem åt.

Katalogen kräver bara `core`: ett index som bara betalande kan öppna är
ett omdöme med en siffra på.

## [Ej släppt] — nyheterna kopplade till bedömningen

Nyhetsmodulen kunde bedöma men ingen matade den och ingen läste den. Nu
gör båda det — och den enda farliga raden i hela kopplingen är låst av
ett test.

- **`risk_score` rör sig aldrig av en nyhet.** Talet väger ihop endast
  kategorier som går att räkna ur signaler; ett Risk Score som kunde
  flyttas av en rubrik vore inte längre härlett. Ett test kör samma
  plats före och efter en bekräftad uppgift och kräver identiskt tal,
  identisk `computed_coverage` och identisk `data_coverage`.
- **Ett tredje läge: `observed`.** En kategori utan drivsignaler som
  träffas av en uppgift med **två oberoende ägare** går från
  `monitoring` till `observed` — med band, utgivare och länkar, men utan
  tal. En ensam ägare lämnar den på `monitoring`. En BERÄKNAD kategori
  behåller sitt tal och får rapporteringen bredvid sig, aldrig i det.
- **Åtta flöden som data** (`news.FEEDS`), nyckellösa. Varje rad pekar
  på en utgivare vars ägare vi känner — ett flöde med okänd ägare gör
  syndikering till bekräftelse, och ett test håller det.
- **Migration 10, `news_items`.** En rubrik är ingen signal med ett
  värde, så den bor inte i `harvested`.
- Nyheter äldre än sju dygn är inte "vad som hänt" och räknas som
  frånvarande.
- Regionmatchning på namn, och `cannot_en` säger att en omnämnande inte
  är ett ämne. Nyckelordsmatchning mot riskkategori likaså: artikeln
  följer med så att en människa kan kasta ut den.
- **Uppmärksamhetsindexet fick sin metod rätt.** Kolada N07403 är
  *anmälda våldsbrott per 100 000* — en kvot. Ett rått artikelantal mot
  en kvot hade till hälften mätt ortens storlek, så båda sidor
  normaliseras nu per 100 000, och funktionen **vägrar** när
  befolkningen saknas i stället för att blanda en kvot med ett antal.

## [Ej släppt] — nyheter som underlag, med grinden före

Nyhetsflöden ska mata den samlade analysen. Det är rätt beslut och också
det farligaste: ett system som låter en rubrik röra ett tal är en
ryktesförstärkare med API. `engine/news.py` är byggd runt den risken.

- **Fem tidningar med samma telegram är EN källa.** Syndikering är det
  som gör "bekräftat av flera medier" värdelöst. Poster klustras på
  texten och räknas per **ÄGARE**, inte per titel: DN och Di är Bonnier,
  SvD och Aftonbladet är Schibsted — fyra tidningar, **två** röster.
  Telegrambyråer (TT, Reuters, AP) märks separat så läsaren kan räkna
  bort dem. Räkningen använder `corroboration.assess` med `network`,
  fältet som tillkom tidigare i den här sessionen.
- **En ensam ägare får aldrig röra en bedömning.** Uppgiften
  registreras och går att läsa, men `may_inform_analysis` är False —
  samma tak som gäller allt annat.
- **Nyheter rör BAND, aldrig värden.** Det som passerar grinden får höja
  eller sänka ett riskband och namnge utgivarna bakom. Det får aldrig
  sätta ett numeriskt signalvärde: ett band går att argumentera emot,
  ett tal ser ut som en mätning.
- **Samstämmighet mellan utgivare är samstämmighet om en RAPPORT**, inte
  om världen — tio redaktioner kan upprepa en enda felaktig källa, och
  måttet kan bara se att de är olika bolag. Det står i svaret.
- RSS och Atom, nyckellöst. Samma dokumentspärr som ENTSO-E:
  entitetsdeklarationer avvisas oparsade.

**Uppmärksamhetsindexet: anmält mot publicerat.** Två register om samma
verklighet som inte behöver stämma överens — myndighetens och
redaktionernas. Kvoten är artiklar per anmäld händelse, jämförd mot
medianen för liknande platser, och den vägrar helt under fem jämförbara
platser: ett tal är varken högt eller lågt i sig självt.

Vad den INTE mäter, och det är hela dess integritet: **inte hur mycket
som skett**. Anmälningsbenägenheten varierar kraftigt mellan brottstyper
och grupper, och mörkertalet är olika stort överallt — kvoten är
publicerat mot ANMÄLT, aldrig publicerat mot inträffat. Låg täckning är
inte bevis för tystnad, hög är inte bevis för överdrift, och att läsa
den som ett omdöme om en plats vore att göra ett mått till en anklagelse.

## [Ej släppt] — leta efter samband och motsägelser, och vägra oftare än man rapporterar

Plattformen kunde redan RÄKNA ett samband (`engine/correlate.py`) och ett
kontradiktionsindex för en plats (`engine/indices.py`). Vad som saknades
var någon som **letade** — svepte en marknad och lade fynden i ett
register någon kan öppna i efterhand.

`engine/analysis.py`, `GET /v1/analysis` (registret) och
`POST /v1/analysis/run` (sökningen).

- **Mock mot mock rapporteras aldrig.** Två simulerade serier korrelerar
  exakt som generatorn byggde dem; ett sådant "samband" är ett eko av
  vår egen kod som ser ut som ett fynd om världen. På ren mockdata
  hoppas **alla 2 145 par** över och noll fynd rapporteras — det är
  sökningen som fungerar, inte som är trasig.
- **Antalet prövade par står på VARJE fynd**, inte bara i en
  sammanfattning som går att klippa bort. Ett samband ur tio par och ett
  ur tvåtusen är inte samma påstående.
- **Minst 12 regioner och |r| ≥ 0,5**, annars ingenting. En korrelation
  på fem punkter är en linje genom brus.
- **`sources_seen` i svaret:** utan det går en körning där allt var mock
  inte att skilja från en där inget samband fanns.
- **Tvärsnitt, inte tidsserie** — plattformen har ännu ingen historik att
  korrelera över tid, och att låtsas annat vore att uppfinna en tidsaxel.
- Motsägelser kräver inget urval: när pappret säger en sak och marken en
  annan är det ett fynd även på en enda plats. Men indexet får inte vila
  enbart på mock — vår egen generator som motsäger sig själv säger
  ingenting om världen.
- Fynden dedupliceras på checksumma. Samma motsägelse två dygn i rad är
  ETT fynd, och `new_findings` räknar bara det registret inte hade.
- Ny jobbtyp `analyse` i schemaläggaren.

**Tre fynd, alla samma sort — kod som tyst letade på fel ställe:**
`city_assessment` returnerar listan under nyckeln `index`, inte
`indices`, så motsägelsesökningen hittade aldrig indexet och rapporterade
"inga fynd" med full tillförsikt. Ingen av API-lagren kopplade
skördelagret till lagret, så `make harvest` skrev till en databas API:t
inte läste. Och sökningen föll tillbaka på en mock-only resolver, vilket
gjorde varje par till mock mot mock. Alla tre gav svaret "inga fynd" —
det farligaste möjliga felet i just den här modulen, eftersom det ser
korrekt ut. Kontraktstestet räknar nu modulerna var för sig.

## [Ej släppt] — öppna källor, skördade i stället för frågade

**`competition_pressure` var mock i alla 35 marknader.** `places.py`
väntar på att någon ska ställa upp en egen tjänst, och ingen sådan
finns — samtidigt som signalen bär utbudssidan i beslutskortet och 0,35
av vikten i obalansformeln. OpenStreetMap fyller precis den luckan,
nyckellöst och globalt.

**Skördat, inte frågat.** Ett marknadssvep träffar 75 regioner,
svarsbudgeten är 700 ms och ett Overpass-anrop tar sekunder. Att fråga i
förfrågningsvägen hade varit tre fel samtidigt: långsamt, ovänligt mot en
gratistjänst, och oreproducerbart. Källorna läses därför in en gång per
dygn (ett anrop per region) och lagras; `HarvestedSource` läser lagret
och kan bevisligen inte göra ett nätanrop — ett test byter ut
`urllib.request.urlopen` mot något som kastar.

- **`engine/harvest.py`** med `SOURCES` och `OSM_TAGS` som data: en ny
  källa är en rad, en ny bransch en rad. Nu: OpenStreetMap (Overpass,
  20 branscher) och Open-Meteo (det enda VÄDERnätet med global räckvidd
  — SMHI är SE, NWS är US).
- **Migration 9, `harvested`.** Ingen tenant-kolumn med flit: hur många
  frisörer OSM känner till i Nacka är samma sak för varje kund, och att
  skopa raden per kund vore att antyda att en kund kan ha en egen
  sanning om det.
- **Tre regler som inte är kosmetiska.** En rad äldre än källans
  `max_age_days` läses som FRÅNVARANDE, inte som ett värde (OSM 30 dygn,
  väder 1). En punkt matchas mot närmaste skördade region inom 25 km, och
  avståndet följer med ut. En kartlagd plats är aldrig en
  etableringsräkning — `/v1/saturation` vägrar fortfarande där inget
  företagsregister är anslutet.
- **`LANDVEX_OPEN_DATA=on`** slår på varje NYCKELLÖS källa på en gång.
  Källor som kräver nyckel rörs aldrig av den. `make open-data` visar
  vad som är på; `make harvest` kör en skörd i förgrunden.
- **`/v1/coverage` får `switchable_today`** — vad som går att slå på nu,
  utan att ansöka om någonting.

**Mätt effekt, inte påstådd.** Mot en fixtur-Overpass, 75 US-regioner:
`data_coverage` för ett gym-svep i USA gick från **0,0 till 0,09**,
rankningen ändrades (mock-konkurrens ersattes av observerad), och
`/v1/coverage?market=us` gick från `real_weight 0,0 (none)` till
**0,076 (thin)**. Sverige stod stilla på 0,245, som sig bör — den
databasen skördades inte.

Fynd: `Breaker.fetch` lägger själv på sin timeout sist, så skördarna
skickade fyra argument till en transport som tar tre. I produktion hade
det gett TypeError, tyst tomma skördar och noll lagrade rader — fångat av
ett test, inte av en användare.

## [Ej släppt] — ett andra oberoende nät

**En källa kan aldrig bekräfta sig själv.** Sju sensorklasser hade exakt
ett nät och satt därför fast i bandet `weak`, hur väl de än stämde med
sig själva. Klasser med två oberoende nät går från **2 av 9 till 8 av 9**.

Nya leverantörer — alla med injicerbar transport, `verified_live = False`
och en `basis_en` som säger vad mätningen inte kan avgöra:

| Klass | Andra nätet | Varför det är oberoende |
|---|---|---|
| `air_quality` | Sensor.Community | Medborgarsensorer: annan ägare **och** annan mätprincip än OpenAQ:s referensinstrument |
| `water_level` | USGS NWIS | Annan hydrologisk myndighet, annan flod |
| `earth_observation` | NASA CMR (Landsat) | **En annan konstellation** än Copernicus Sentinel |
| `seismic` | EMSC | Två FDSN-kataloger som magnitudsätter samma skalv var för sig |
| `vessel_traffic` | BarentsWatch | Kystverket vs Fintraffic, med OAuth2-utbyte före anropet |
| `grid_telemetry` | ENTSO-E | Sensorraden namngav redan ENTSO-E som operatör — bara SVK var byggd |

**Tre fynd som gjorde arbetet större än fem klienter:**

- **Motorn kunde inte se ett andra nät inom samma klass.**
  `corroboration.assess()` räknade oberoende som antal unika
  `sensor_class`. Modulens EGET exempel — Trafikverket och Digitraffic —
  har båda `road_flow`, så koden räknade dem som en källa och satte taket
  *"a single network cannot corroborate itself"* på just det par
  docstringen valt för att visa vad oberoende betyder. Källor bär nu ett
  valfritt `network`; utan fältet är varje tal identiskt med förut, vilket
  ett test bevisar. Två nät i samma klass når `moderate` men **aldrig**
  `strong` — de delar modalitet och kan bära samma systematiska fel.
- **Proben kunde bara nå det första nätet per klass.** `PROBES` var
  nycklad på sensorklass, så NWS och Digitraffic road hade legat i
  registret utan någon väg att bli bekräftade. Nycklarna är nu
  `klass:klient`, och `sensor_probe air_quality` betyder fortfarande hela
  klassen. Raden sa dessutom åt den som ville koppla in det andra nätet
  att sätta det FÖRSTAS miljövariabel.
- **Två nät räknades som noll.** `grid_telemetry` och `field_observation`
  stod som `independent_providers: 0` fast båda hade ett nät — deras
  klienter byggdes före leverantörstabellen. Nollan gjorde mer skada än
  att se snål ut: klasserna föll ur listan över dem som saknar ett ANDRA
  nät, så luckan syntes inte alls i lägesrapporten.

Övrigt: `_sammanfatta_medborgarluft` skapade nyckeln före värdet lästes,
så en oläslig avläsning gav en tom lista och division med noll (fångat av
testet innan koden kördes skarpt). USGS konverterar cfs→m³/s och fot→cm i
klienten och **namnger konverteringen i svaret** — två nät jämförda i
olika enheter blir `conflicting` av ren aritmetik. NWIS-sentinelvärdet
`-999999` avvisas i stället för att bli ett vattenstånd på minus tre
kilometer. ENTSO-E svarar med XML: dokument som deklarerar entiteter
avvisas oparsade och storleken har ett tak, eftersom `defusedxml` är ett
beroende kärnan inte får ta.

**Ansökningar som krävs för att verifiera live:** BarentsWatch
(client credentials), ENTSO-E (token via mejl), Trafikverket och OpenAQ
(gratis nycklar, ej ansökta än). Ingen klient har fått `verified_live =
True` — proben har körts mot fixturer, inte mot riktiga värdar.

## [Ej släppt] — vad vi kan svara på HÄR

Tredje Tier 1-posten. Hela alt-data-branschen döljer att den är
enkelkällad; att publicera sin egen täckning är därför en kil och inte en
svaghet. `engine/coverage.py`, `GET /v1/coverage` — **utan API-nyckel med
flit**: en kund som måste köpa för att få veta vad talen vilar på har
redan fått fel produkt.

- **`real_weight`** är talet: hur stor andel av en bransch VIKTADE
  signalbild som en ansluten källa faktiskt kan svara för på den
  marknaden. Inte hur många signaler som finns (lika många överallt, och
  lika intetsägande överallt). För Sverige 0,245. För USA och alla andra
  34 marknader **0,0**. Det är obekvämt, det är sant, och det ska stå
  innan någon frågar.
- **Två olika luckor hålls isär.** En adapter som är skriven men inte
  ansluten är ett avtal; en adapter som inte NÅR marknaden är en ny
  integration. Svaret säger vilket, per källa, med antal signaler den
  skulle öppna.
- **Ny räckviddsdeklaration:** `DataSource.markets`. SCB-adaptern är
  kopplad och `/health` säger "ok" — men den kan inte svara för en punkt
  i Texas, och det stod ingenstans. För US-marknaden var därför varenda
  signal mock medan statusraden såg lika grön ut som för Sverige.
- **Anslutningsregeln bodde bara i `api/health`** och var därmed
  oåtkomlig för motorn. Den ligger nu i `DataSource.connected`, och
  health läser samma regel — annars hade täckningsytan behövt en kopia,
  och två kopior av samma regel glider isär. (Första utkastet gissade,
  och gissningen räknade mock som verklig data: 0,505 för Sverige och
  0,227 för USA, båda fel.)
- **Startsidans bevisrader räknas nu.** "0 of 14 source adapters" var
  handskrivet — sant den dagen, och just den sortens rad som blir falsk i
  tysthet. Ny rad: plattformens egen täckning, marknad för marknad.
- **`GET` mappar fältfel till 422 i båda servrarna.** `?market=atlantis`
  gav "Internal error" med ett request-id i stdlib-servern medan FastAPI
  svarade 422 med listan över marknader. Två servrar som beter sig olika
  på samma felstavning är samma drift som en saknad endpoint, bara
  svårare att upptäcka.

## [Ej släppt] — ut ur systemet, och igång utan att bli tillfrågad

Två av lägesrapportens tre oblockerade Tier 1-poster. Båda stod som
`planned` i erbjudandet, och båda är sådant en företagskund frågar om
innan den frågar om något annat.

**Export (`engine/export.py`, `POST /v1/export`).** Det farliga med
export är inte formatet — det är att ett Opportunity Score i en CSV-fil
ser ut som ett mätvärde så fort det lämnat skärmen där täckningsgraden
och förbehållen stod. Varje format bär därför sin proveniens i själva
filen: CSV som `#`-kommentarrader (pandas läser dem med `comment="#"`),
NDJSON som en första `_landvex`-rad, GeoJSON som ett `landvex`-medlems-
fält. Fem datamängder (svep, obalanser, bristkarta, efterlevnadsregister,
avvikelseflöde) som data — ny rad, ingen motorändring.

- **PDF, XLSX, Parquet och shapefile vägras vid namn** i stället för att
  approximeras. En CSV med filändelsen `.xlsx` får Excel att varna för
  att filen är trasig; shapefile trunkerar kolumnnamn till tio tecken.
  Skälet står i katalogen, för den som letar efter PDF ska hitta
  beskedet och inte tystnaden.
- **Exporten är ingen väg runt paketet.** Datamängden kräver samma
  kapabilitet som den endpoint den kommer ifrån — en Professional-nyckel
  får 403 på kontrollregistret, precis som på `/v1/inspections/
  compliance`. Katalogen (GET) är däremot öppen: man ska kunna se vad
  som går att få ut innan man köpt något.
- Kundens egna rader kan inte exporteras utan tenant. Utan den hade
  filen innehållit allas.

**Schemaläggning (`engine/scheduler.py`, `api/ticker.py`,
`POST /v1/schedules`).** En bevakningsprodukt som bara svarar när någon
frågar är en rapport.

- **En kadensdialekt, inte två.** Förfallologiken är `monitors.due` —
  samma ord, samma epoch-disciplin där tiden skickas in.
- **Fyra jobbtyper som data:** beställ fältuppdrag för det som förfaller,
  räkna om efterlevnadsregistret, kör om ett svep **och spara det**,
  väck bevakningarna.
- **Gränsen står i klartext på varje körning.** En bevakning som väcks
  utan historik har ingenting att titta på; att utvärdera en tom serie
  ger "inget triggat", vilket läses som lugn men betyder blind. Jobbet
  hoppar därför över med skäl — och pekar på `scan_refresh`, som är det
  som faktiskt bygger historiken.
- **Dubbelkörning.** Två processer som kör samma jobb ger kunden två
  beställda fältuppdrag för samma objekt. Jobbet claimas i lagret med
  villkoret i UPDATE-satsen (migration 8, `scheduled_jobs`); utan lager
  gäller spärren bara den egna processen, och körningen säger det i
  stället för att låtsas vara ett klusterlås.
- **Tickern är avstängd som standard** (`LANDVEX_SCHEDULER=on`). En
  bakgrundstråd som startar för att någon importerat en modul, och sedan
  beställer fältuppdrag åt en kund, är en dyr överraskning. Produktions-
  vägen är `deploy/aws/scheduler-rule.json`: EventBridge mot
  `POST /v1/schedules/run`, med rubriknamnet låst mot det `api/security.py`
  faktiskt läser och kö för döda brev — en tick som tyst slutar komma ser
  annars ut precis som en tick där ingenting förföll.
- **Schemaläggning är ingen egen produkt.** Vägen är öppen och jobbtypen
  grindas: annars kunde flaggleverantören — vars hela behov är "beställ
  kontrollerna varje vecka utan att jag ber om det" — inte schemalägga
  det hon just köpt. Ett jobb vars paket upphört pausas med angivet skäl
  och raderas inte.
- `scheduled_runs` flyttad från enterprise till pro: Professional-planens
  egen funktionslista lovade redan "scheduled watches (cron)". Två
  ställen som säger olika om samma sak är ett prisfel.

## [Ej släppt] — kontroller som förfaller

**Plattformen kunde svara på frågor om platser, men inte hålla reda på
objekt över tid.** En flaggleverantör som sköter flaggor och flaggstänger
i stora delar av Stockholm, eller en kommun som ska kontrollera livbojar
på badplatser, har samma behov: ett register över egna objekt, ett
intervall, en förfallodag, någon som åker dit, en dom — och något att
visa en nämnd eller en försäkringsgivare efteråt. Ingen del av det fanns.
Det är också luckan som gjorde paketeringen `per_mission` märkt NOT
DELIVERABLE.

- **`engine/inspections.py`** — tillgångar, rutiner, kontroller.
  Kadensen är `every_days` + valfri veckodag + valfri säsong, och
  **vägrar** det den inte kan uttrycka exakt: "var 10:e dag, på tisdagar"
  avvisas med ett skäl som går att åtgärda i stället för att tolkas. En
  rutin som tyst blir något annat än vad någon skrev är farligare än en
  som avvisas — den som skrev den tror att kontrollen sker.
- **Ingen dom utan bevis.** Ett `pass` utan uppdrags-id eller
  mediereferens avvisas (422). Endast `unclear` får sakna bevis, för det
  är vad `unclear` betyder.
- **`never_checked` är inte `ok`.** Ett objekt ingen har tittat på
  räknas inte som aktuellt, och ett underkänt objekt rankas över
  schemat oavsett när nästa kontroll infaller.
- **`integrations/quixzoom_dispatch.py`** beställer fältuppdrag — eller
  vägrar med namngivet skäl. Utan `LANDVEX_QUIXZOOM_URL` hittas *inget*
  uppdrags-id på: ett påhittat id ser ut som en beställd kontroll ända
  fram till dagen någon frågar varför ingen varit på plats. Kontraktet är
  inte bekräftat mot riktig värd härifrån (nätet är policyspärrat), så
  `verified_live = False` står kvar.
- **Sju endpoints i båda API-lagren**, låsta av kontraktstestet, och en
  egen kapabilitet `asset_inspections`. Den ligger i Enterprise **och**
  som tillägg: den första riktiga kunden har några hundra flaggstänger,
  inte ett enterpriseavtal. Utan kapabilitetsraden hade endpointerna
  varit helt ogrindade — `required_capability` returnerar None för okända
  vägar, och då släpper auth-lagret igenom vem som helst.
- **Migration 7** (SQLite + Postgres): `assets`, `routines`, `checks` med
  tenant som kolumn. Ett efterlevnadsregister i processminnet är inget
  register. FastAPI-lagret kopplade inte in lagret alls — ytan var
  identisk och kontraktstestet grönt, medan produktionsvägen tappade allt
  vid omstart. Ett test läser numera båda filerna.
- **Mediet lagras aldrig här.** En fältbild på en badplats innehåller
  människor. Landvex bär domen och en referens; bilden stannar hos
  quiXzoom, som har samtycket. Ett test faller om en kolumn som ser ut
  att bära media läggs till.
- **Ansvarskort per rutin** (`accountability_card`) går in i samma
  register som alla andra beslut, med de tre rollnamnen från
  `engine/claims.OWNER_ROLES` och ett mätbart förväntat utfall.
  Avvikelser normaliseras till inkorgens händelseform — men routningen
  **vägrar** utan uttryckliga prenumerationer: de bär ingen tenant, och
  ett fallback till "alla prenumeranter" hade skickat en kunds adresser
  till en annans inkorg.
- **Demokund i konsolen:** flaggleverantören i Stockholm, åtta stänger,
  veckovis rutin, blandade utfall — aktuellt, underkänt, aldrig
  kontrollerat och försenat. Märkt `source="mock"`; gatorna är riktiga,
  raderna är det inte. Ny flik **Checks** ritar objekten på kartan i
  statusfärg. `make seed-checks` lägger samma fixtur i lagret.

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
