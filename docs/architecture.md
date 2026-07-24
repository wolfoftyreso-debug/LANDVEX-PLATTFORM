# Arkitektur – LANDVEX Opportunity Engine v0.1

## Designprinciper

1. **Vertikalspecifik som data, inte kod.** En frisör och en elektriker får
   helt olika analyser för att deras profiler pekar på olika signaler med
   olika vikter – motorn är densamma. Ny bransch tar minuter, inte veckor.
2. **Förklarbarhet före prediktion.** v1 är en transparent viktmodell där
   varje faktor kan förklaras med en svensk mening och råvärden. Ett score
   ingen kan förklara tappar förtroende. ML-prediktion (överlevnad/ERP)
   införs först när utfallsdata finns – se roadmap.
3. **Beroendefri kärna.** `engine/` kräver endast Pythons standardbibliotek
   och kan därför köras identiskt i Lambda, ECS, batch-jobb och lokalt.
4. **Ärlig datatäckning.** Varje rapport redovisar `data_coverage` – andelen
   signaler från verkliga källor. Mockdata är tydligt märkt och rapporterna
   bär caveats tills produktionskällorna är inkopplade.

## Dataflöde

```
Förfrågan (lat, lon, vertikal, radie)
        │
        ▼
Resolver ──► [ScbSource] ─► [PermitsSource] ─► [PlacesSource] ─► [MovementSource] ─► MockSource
        │        (källor i prioritetsordning; första träff per signal vinner)
        ▼
Normalisering (signals.py: saturating / linear / inverse / band → 0..1)
        ▼
Faktorscore per bransch (verticals.py: vikter per faktor & signal)
        ▼
Opportunity Score 0–100  +  Riskmotor (vakans, hyra, tillväxt, konkurrens)
        ▼
Narrativ & mönsterinsikter (explain.py, svenska)
        ▼
OpportunityReport (JSON via API)
```

## Plats i Landvex-plattformen

Opportunity Engine är en fristående tjänst bakom plattformens API-gateway.
Datakällslagret (Resolver + adaptrar) är designat för att delas med Risk
Engine, Investment Engine och Retail Intelligence – samma signaler, olika
motorer ovanpå. Signalkatalogen blir därmed en plattformsgemensam tillgång.

## Konkurrens- och efterfrågemodellen

Konkurrens mäts inte som antal aktörer utan som *effektivt tryck*:
fullbokade aktörer, svaga recensioner och nischade premiumaktörer viktas
ner eftersom de lämnar utrymme i marknaden. Efterfrågeproxy per bransch
delat med effektivt utbud ger `provider_gap` – grunden för insikter som
"Här finns sannolikt arbete för ytterligare 2 elektriker."

## Roadmap

| Version | Innehåll |
|---|---|
| v0.1 (denna) | Regelbaserad viktmodell, 7 vertikaler, mockdata, API, tester |
| v0.2 | SCB-adapter (öppna API:er), bygglovsadapter, frontend-rapportvy |
| v1.0 | Rörelsedata (licens), konkurrensdata, kartrendering, PDF-export |
| v2.0 | Viktkalibrering mot verkliga utfall (etableringar som följts upp) |
| v3.0 | ERP-modell (Expected Revenue Potential) i SageMaker, konfidensintervall |

## Kända begränsningar v0.1

- All data är simulerad (deterministisk, platsseedad) tills adaptrarna kopplas.
- "Sannolikhet att verksamheten överlever" utlovas medvetet inte ännu –
  rekommendationstexterna är formulerade som beslutsunderlag, inte garantier.
- Radie räknas i minuter men utan verklig isokron-beräkning (kommer med
  ruttdata i v0.2, t.ex. OSRM/Valhalla eller AWS Location Service).
