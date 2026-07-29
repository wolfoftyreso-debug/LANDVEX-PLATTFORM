# Sponsored Rewards Engine — designbeslut före bygget

Spec mottagen 2026-07-29. Beställarens egen tudelning är styrande, och
den sammanfaller med en spärr som redan är lag i kodbasen
(`engine/inspections.audience`, fotokontrollerna): **personen och
samtycket bor hos quiXzoom — Landvex lagrar referensen, aldrig
människan.**

## Snittet: vad som byggs VAR

| Del | Var | Varför |
|-----|-----|--------|
| Campaign Engine (sponsor, målgruppsgeo, budget, belöningsutbud, pacing, caps, co-sponsring, ROI) | **Landvex** | Kampanjer är data om uppdrag och pengar, inte om personer. Samma mönster som rutiner/jobb: en kampanj är rader. |
| Mission Generator | **Landvex** | Sponsrade uppdrag är dispatch med kampanjreferens + belöningsutbud — bygger på befintlig `quixzoom_dispatch` och `audience` (riktade zoomers). |
| Sponsor Analytics | **Landvex, ENDAST aggregat** | Samma doktrin som `outcomes`: rådata lämnar aldrig motorn, bara aggregat. Individnivå kräver rättsligt stöd + uttryckligt samtycke och ligger då hos quiXzoom, inte här. |
| Rapportexport | **Landvex** | Redan byggt: `engine/pushes` (CSV/NDJSON/GeoJSON till webhook, schemalagt). Sponsorrapporter blir en datamängd i exportkatalogen. |
| Reward Wallet (saldo, kuponger, historik per person) | **quiXzoom** | En plånbok är persondata om zoomern. Landvex bär belönings-UTBUDET på uppdraget och en avräkningsreferens — aldrig en persons saldo. |
| Utbetalning (kontant, presentkort, voucher, poäng) | **quiXzoom** | Betalning till person = KYC/AML/skatt på quiXzoom-sidan. Landvex räknar kampanjens kostnad, inte personens inkomst. |
| User Preference Engine (individens vanor, tider, favoriter) | **quiXzoom, med samtycke** | Individprofilering är exakt det `engine/sensitive.py`-doktrinen är byggd för att stå emot i Landvex. Aggregerad efterfrågeanalys ("vilka uppdragstyper löses snabbast i område X") är Landvex-sidan. |

## Belöningsformer som data

`REWARD_KINDS` blir en tabell, inte grenar: `cash`, `gift_card`,
`voucher`, `discount_code`, `loyalty_points`, `choice` (zoomern väljer).
En kampanjrad bär sitt utbud; kombinationer är flera rader. Beloppet är
kampanjens KOSTNAD i Landvex — vad zoomern får ut betalas och redovisas
av quiXzoom mot avräkningsreferensen.

## Spärrar som gäller från rad ett

1. **Aldrig individnivå i sponsorstatistiken.** Aggregat med golv
   (`k ≥ 5`-regel eller motsvarande) — en "aggregerad" cell med en
   person i är individnivå med ett medelvärde på.
2. **Budget är ett tak, inte en prognos.** En kampanj vars budget är
   slut beställer ingenting och SÄGER det — pacing får aldrig tyst
   överskrida cap.
3. **Co-sponsring är rader** (kampanj ↔ sponsor med andel), och
   ROI-beräkningen namnger sina antaganden i `basis`.
4. **Ingen leverans utan mission-id** — samma regel som
   `quixzoom_dispatch`: ett påhittat id ser beställt ut tills någon
   frågar var uppdraget tog vägen.
5. **Exponering ≠ data.** En sponsor som köper exponering får
   statistik om SINA uppdrag; en sponsor som vill ha "marknadsinsikter"
   får aggregat under samma golv som alla andra.

## Tillägg: Sponsored Content Missions (spec 2, samma dag)

Varumärkesfinansierade uppdrag där zoomers skapar autentiskt
bildmaterial (Garmin-klockan på löprundan, McFlurryn utomhus,
IKEA-produkten i hemmet). Samma kampanjmotor — en uppdragsKLASS, inte
en egen modul:

* **Uppdragsklass `content`** vid sidan av `verification` (fota gatan,
  verifiera skylten): kampanjraden bär klass, brief, sponsorns namn
  (SYNLIGT för zoomern — "det framgår vilken sponsor som finansierar"
  är ett fältkrav, inte en policy), belöningsutbud och
  verifieringskrav.
* **AI-verifieringen är quiXzoom Vision-ledet**: Landvex lagrar
  DOMEN som data (produkt i bild: ja/nej, utomhus: ja/nej, kvalitet:
  band, färskhet: ja/nej) — aldrig bilden. Samma regel som
  fotokontrollerna: verdict + referens här, media och rättighetskedja
  hos quiXzoom.
* **Rättigheter enligt avtal** är ett avtalsobjekt mellan sponsor och
  quiXzoom/zoomer. Landvex bär avtalsreferensen på kampanjen och
  vägrar generera content-uppdrag utan en — ett uppdrag vars material
  ingen får använda är ett löfte som inte kan hållas.
* **Sponsordashboard = aggregaten**: genomförandegrad, geografisk
  spridning (aggregerad nivå), tidsfördelning, kvalitetsband,
  trender. Samma k-golv som all annan sponsorstatistik. Väder/
  tidpunkt-analys körs mot skördad öppen data (Open-Meteo finns
  redan) — aldrig mot zoomerns rörelsemönster.
* **Tidsserier** över exponering är kampanjens serie (uppdrag över
  tid), inte personens.

## Byggordning (uppgift #15)

1. `engine/sponsorship.py`: kampanjrader, REWARD_KINDS, budget/pacing/
   cap-aritmetik med vägran, co-sponsringsandelar, aggregerad statistik
   med k-golv, ROI med öppna antaganden.
2. Dispatch-koppling: sponsrat uppdrag = befintlig dispatch + kampanj-
   referens + belöningsutbud i uppdragskroppen.
3. API: `/v1/sponsorship` (katalog + kampanj-CRUD + statistik),
   kapabilitet egen rad (`sponsor_portal`?) — prissättningsbeslut hör
   till offering-processen, inte till koden.
4. Sponsorrapport som exportdatamängd → pushbar via `/v1/pushes`.
5. Tester: budgettak biter, k-golvet biter (4 personer → vägran),
   individdata finns inte i något sponsorssvar (fältsvep), co-sponsrade
   andelar summerar till 1.0.
