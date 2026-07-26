# QUIXZOOM — responsivitetsdoktrin

> **Användaren ska aldrig vänta på systemet. Systemet ska ligga ett steg
> före användaren.**

Det här är en grundprincip, inte en optimering. Den gäller Mobile-Only,
Camera-First, Offline-First — en fältarbetare med telefonen i ena handen
och arbetet i den andra, ofta i en källare utan täckning.

---

## Den konflikt som måste lösas först

Optimistic UI säger: *anta att det lyckas och visa det direkt.*
Landvex-doktrinen säger: *visa aldrig något du inte kan stå för.*

De kolliderar på riktigt, och kollisionen är inte akademisk. quiXzoom
matar `field_observation_density` in i Landvex beslutsmotor. En
observation som appen visade som klar men som aldrig synkade blir
**tyst saknad data** i ett beslutsunderlag — exakt den felklass som är
farligast: den som ser rätt ut.

### Regeln som löser den

**Var optimistisk om det enheten kan garantera. Var ärlig om det bara
servern kan bekräfta.**

| Händelse | Vad enheten vet | Vad UI:t får påstå |
|---|---|---|
| Foto taget | Filen finns i lokal lagring | ✅ **Sparad** — direkt, utan väntan |
| Formulär ifyllt | Posten är skriven lokalt | ✅ **Sparad** — direkt |
| Uppladdning startad | Ingenting ännu | ⏳ **Skickas** — aldrig ✅ |
| Servern kvitterat | Kvittot är mottaget | ✅ **Levererad** |
| Uppladdning misslyckad | Felet är känt | ⚠️ **Ligger kvar** + antal |

Två distinkta tillstånd, aldrig ett. "Sparad" är sant i samma sekund och
kräver ingen väntan — det är den optimistiska vinsten, tagen fullt ut.
"Levererad" är ett påstående om en annan dator och får aldrig visas innan
den datorn svarat.

**Praktisk konsekvens:** en synlig, alltid närvarande räknare för *osynkat*.
Fältarbetaren som fotograferat 40 objekt i en källare ska se `40 väntar`
när hon kommer upp — och `3 väntar` om 37 gick igenom. Aldrig en tom
skärm som betyder två helt olika saker.

---

## Principerna

**Instant feedback.** Varje tryck ger visuell respons omedelbart, även när
servern arbetar. Responsen bekräftar *att trycket registrerades*, inte att
operationen lyckades.

**Optimistic UI, avgränsad.** Enligt regeln ovan. Lokal avsikt visas
direkt; fjärrbekräftelse visas när den kommit.

**Offline-first på riktigt.** Bilder, formulär och uppdrag fungerar utan
uppkoppling och synkas automatiskt. Kön är synlig och räknebar.

**Predictive prefetch.** Nästa uppdrag, nästa kartruta, nästa vy hämtas
innan användaren öppnar dem — men aldrig på ett sätt som stjäl bandbredd
från en pågående uppladdning. **Uppladdning av fältdata har alltid
företräde framför prefetch.**

**Skeleton screens, inte spinners.** Visa strukturen direkt. En spinner
säger "vänta"; ett skelett säger "här kommer det, och så här ser det ut".

**Lokal AI som hint, aldrig som dom.** Skärpekontroll, OCR och
kvalitetskontroll på enheten ger lägre latens och ska användas. Men en
lokal modell som säger "suddig, ta om" och har fel kostar fältarbetaren en
resa. Därför: **lokalt ger förslag, servern ger utfall** — samma
uppdelning som `measured` vs `estimated` i Landvex. Ett lokalt utfall
märks som lokalt.

**Mikroanimationer.** Korta, konsekventa, samma kurva överallt. En
animation som är längre än den operation den döljer är en fördröjning
förklädd till artighet.

**Ingen blockerande logik.** Nätverksanrop får aldrig frysa gränssnittet.
Inte ens vid inloggning, inte ens vid start.

---

## Budgetar

Ett tal utan mätpunkt är en åsikt. Varje budget nedan definierar därför
**varifrån** och **vart** den mäts, och vid vilken percentil — annars mäter
två personer olika saker och båda har rätt.

Budgetarna ligger som data i `docs/quixzoom-budgets.json` och kontrolleras
av `scripts/perf_budget.py`, som ska köras i CI. Överskriden budget är ett
fel, inte en varning.

| Mätvärde | Mål | Mäts från → till | Percentil |
|---|---|---|---|
| Appstart | < 1 000 ms | processtart → första interaktiva bildruta | p95 |
| Reaktion på tryck | < 50 ms | touchstart → första målad förändring | p95 |
| Byte mellan vyer | < 100 ms | navigering utlöst → ny vy målad | p95 |
| Kamerastart | < 300 ms | kameraknapp → första förhandsbilden | p95 |
| Kartvisning | < 500 ms | vy öppnad → första kartrutorna målade | p95 |
| Uppladdning påbörjad | < 100 ms | slutare → posten i den lokala kön | p99 |
| Bildfrekvens | ≥ 60 FPS | scroll, andel bildrutor inom budget | p99 |

p95 för det användaren gör ofta, p99 för det som aldrig får fallera: att
en observation hamnar i kön. Att tappa den är att tappa arbete.

---

## Granskningsregeln

Varje ny funktion prövas mot två frågor:

1. **Gör den användaren snabbare?**
2. **Påverkar den den upplevda responsen?**

Är svaret på den andra ja, omarbetas den före släpp.

Jag skulle lägga till en tredje, av samma skäl som ovan:

3. **Kan den visa något som ännu inte är sant?**

Om ja — dela tillståndet i två innan den släpps.

---

## Varför detta hör ihop med Landvex

Landvex vägrar visa en siffra den inte kan stå för: ett uppskattat antal
märks som uppskattat, en blockerad källa registreras aldrig som ett
saknat värde, en okänd ort besvaras aldrig med en annan orts data.

quiXzoom är där den datan föds. En app som är snabb för att den ljuger
lite gör hela kedjan opålitlig. Doktrinen ovan ger snabbheten **utan**
den kostnaden: allt som kan visas direkt visas direkt, och det som bara
en annan dator kan bekräfta väntar på den bekräftelsen — synligt, räknat
och aldrig tyst.
