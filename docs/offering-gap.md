# Erbjudandet mot det byggda — motor för motor

**Mätt 2026-07-28:** 48 motorer, 18 beslut. **36 motorer såldes av
ingenting.** Det här dokumentet går igenom var och en och föreslår ett
beslut — eller argumenterar för att den inte ska bli ett.

Alla förslag är **utkast för din strykning**. Ingenting här är infört i
`engine/offering.py`; det görs när du gått igenom listan. Formuleringarna
följer registrets form: en fråga en människa faktiskt ställer, vem det är
för, vad det avgör, vilken roll och vilken plan.

Rollerna är `engine/entrypoints.py` egna: **citizen · business ·
investor · municipality · journalist · researcher**.

> **Underlag som saknas:** `landvex.com` svarar 403 härifrån
> (policyspärrat utgående nät), så jag har inte kunnat stämma av mot vad
> ni redan säger publikt. Det är den enda källan i den här genomgången
> jag inte kunnat läsa — stäm av rubrikerna mot sajten innan något förs
> in.

---

## A. Föreslås bli beslut (22)

Ordnade efter hur nära ett kundbeslut de ligger, inte efter motor-id.

| # | Motor | Föreslagen fråga | Roll | Plan | Avgör |
|---|---|---|---|---|---|
| 1 | `plan` | Vad krävs för att faktiskt öppna här? | business | pro | Lokal, investering, bemanning, ekonomi — beslutsunderlaget före ett åtagande |
| 2 | `risk` | Vad kan gå fel här, och vad minskar det? | business | pro | Om risken går att bära, och vilken åtgärd som biter |
| 3 | `compare` | Vilken av de här platserna är bäst — och på vad? | business | pro | Valet mellan 2–4 kandidater, faktor för faktor |
| 4 | `opportunity_intel` | Vilket stöd lämnar jag på bordet? | business | pro | Om det finns program, bidrag eller lägen ni missar |
| 5 | `risk_intelligence` | Vad är min riskpoäng bredvid möjligheten? | investor | pro | Om uppsidan står i proportion till nedsidan |
| 6 | `gaps` | Var växer efterfrågan snabbare än utbudet? | investor | pro | Var kapital ska sökas innan andra ser samma sak |
| 7 | `merit` | Vilka platser presterar mätbart, inte bara ser bra ut? | investor | pro | Vilken ort som förtjänar en närmare titt |
| 8 | `segments` | Vilka kundgrupper finns faktiskt här? | business | pro | Om målgruppen finns på plats, inte bara i planen |
| 9 | `installed_base` | Vilket servicebehov är på väg ur det som redan står installerat? | business | pro | Var eftermarknaden växer, och vilken kompetens den kräver |
| 10 | `wages` | Vad kostar den här kompetensen här? | business | pro | Om kalkylen håller på den lönenivå orten faktiskt har |
| 11 | `livability` | Var kan just det här hushållet bygga ett bra liv? | citizen | free | Om orten passar de villkor hushållet faktiskt lever under |
| 12 | `corrections` | Kan jag rätta det som står fel om min ort? | citizen | free | Om lokalkännedom får korrigera registret — med källa |
| 13 | `kpi` | Hur presterar den här platsen på det som räknas? | municipality | pro | Vad som är på väg åt fel håll innan det syns i budgeten |
| 14 | `lambda` | Är samhället i balans, eller lutar det? | municipality | enterprise | Vilken axel som drar ner helheten — geometriskt medel straffar kompensation |
| 15 | `setpoints` | Ligger den här siffran innanför ett kalibrerat spann? | municipality | pro | Om avvikelsen är en avvikelse eller normal variation |
| 16 | `scenario` | Vad kan rimligen hända här? | municipality | enterprise | Vilka utfall som är trovärdiga nog att planera för |
| 17 | `event_study` | Fungerade åtgärden faktiskt? | municipality | enterprise | Om insatsen gav effekt jämfört med kontroller |
| 18 | `outcomes` | Höll våra beslut — kalibrerat? | municipality | enterprise | Om modellen och organisationen träffar rätt över tid |
| 19 | `feeds` | Säg till när något rör sig. | investor | pro | När man ska titta igen, utan att bevaka manuellt |
| 20 | `correlate` | Vad rör sig tillsammans — som hypotes, aldrig orsak | researcher | enterprise | Vad som är värt att undersöka, uttryckligen inte varför |
| 21 | `strim` | Kan jag citera det här i en publikation? | researcher | pro | Om entiteten är citerbar, versionerad och neutral |
| 22 | `ask` | Kan jag bara fråga, med egna ord? | citizen | free | Ingången för den som inte vet vilken endpoint hen behöver |

**Not till 20:** `correlate` får aldrig formuleras som orsak. Frågan är
medvetet "vad rör sig tillsammans", och svaret bär redan sin egen
brasklapp — men rubriken i ett gränssnitt är det första någon läser fel.

**Not till 14 och 18:** dessa två är de starkaste enterprise-argumenten
i hela katalogen och säljs idag inte alls. λ straffar kompensation
(en axel kan inte köpa sig fri med en annan), och `outcomes` är det enda
i systemet som mäter om plattformen själv har rätt.

---

## B. Ska INTE bli beslut (13)

De här är inte produkter utan **instrumentets egen bevisapparat**. Att
paketera dem som kundbeslut vore att sälja mätaren i stället för
mätningen — och att blåsa upp antalet till 40 skulle motsäga hela
poängen med att paketera efter beslut.

De ska däremot **synas**, för det är de som bevisar att verktyget är ett
instrument: de hör hemma i "why this is an instrument, not a guess",
inte i en prislista.

| Motor | Varför inte ett beslut |
|---|---|
| `surface` | Beskriver erbjudandet självt |
| `offering` | Är erbjudandet självt |
| `entrypoints` | Är dörrarna, inte något bakom en dörr |
| `provenance` | Var plattformens EGNA konstanter kommer ifrån — bevis, inte vara |
| `corroboration` | Hur säkert ett svar är — en egenskap hos varje svar |
| `sensors` | Vad som kan mätas — förutsättningen, inte leveransen |
| `data_sources` | Kopplingsstatus, ärligt icke-kopplad |
| `admin` | Geografiregistret 18 länder — infrastruktur |
| `customer` | Var en kund står i onboarding — intern process |
| `visitor` | Sömmen onboarding levererar in i — intern |
| `aamos_integration` | Plattformsintegration, degraderar ärligt |
| `worthiness` | Rangordnar vad som är värt att visa — driver `feeds` |
| `decision` | Beslutsunderlagets struktur — bärs redan av `bind_decision_to_owner` |

---

## C. Ett eget fall: `sensitive`

Motorns egen rad: *"Känsliga kategorier — till ytan, men som sanning,
inte som vapen."* Den ytar samband på skyddade kategorier (ursprung,
brottsofferstatus, hälsa).

**Förslag: paketera den inte alls, i någon plan.** Inte för att den är
dålig utan för att en betald "decision" ovanpå skyddade kategorier
skapar exakt det incitament motorn är byggd för att stå emot. Den bör
finnas som en yta med sina egna spärrar, inte som något någon köper.

Det här är det enda stället i genomgången där jag rekommenderar att
INTE sälja något som är byggt, och skälet är avsiktligt inte tekniskt.

---

## Vad det landar i

| | Idag | Efter genomgången |
|---|---|---|
| Beslut i erbjudandet | 18 | **40** |
| Motorer som säljs av något | 12 av 48 | **34 av 48** |
| Motorer som medvetet inte säljs | — | 13 (bevisapparat) + 1 (`sensitive`) |

Skillnaden mot idag är inte kosmetisk: **fjorton av de tjugotvå
föreslagna besluten är enterprise- eller pro-argument som ingen säljare
i dag har på sin lista** — λ-balansen, event-studier, kalibrerade utfall,
scenarier, setpoints, gap-analys, merit.

---

## Nästa steg

1. Du stryker, formulerar om eller ändrar roll/plan i tabell A.
2. `landvex.com` stäms av — jag kommer inte åt den härifrån.
3. Det du godkänner förs in i `engine/offering.py`. Testerna som redan
   finns fångar resten: varje beslut måste ha roll, ingen roll får sakna
   byggt beslut, och planerade beslut måste märkas planerade.
4. Ingången (`make front`) och lägesrapporten (`make standing`) plockar
   upp allt automatiskt — de läser registret, de beskriver det inte.
