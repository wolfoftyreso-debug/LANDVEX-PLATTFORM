# LANDVEX Opportunity Engine

*Know before you build.* Analyserar en plats innan någon investerar och
levererar ett förklarbart Opportunity Score (0–100) med nedbrytning,
riskbedömning, mönsterinsikter och rekommendation – anpassat per bransch.

## Snabbstart (inga beroenden krävs)

```bash
python3 demo.py                    # kör frisör-, elektriker- och café-exempel
python3 -m tests.test_scoring      # kör testsviten
python3 -m api.dev_server          # startar API på http://localhost:8000
```

Produktions-API (AWS/lokal miljö med pip):

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Anropsexempel:

```bash
curl -X POST http://localhost:8000/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"lat":59.3145,"lon":18.0705,"vertical":"frisor","address":"Hornsgatan 52"}'
```

## Struktur

```
engine/               Kärnmotor – endast stdlib, körs var som helst
  models.py           Datamodeller (Location, OpportunityReport, ...)
  signals.py          Signalkatalog + normalisering (0..1)
  verticals.py        Branschprofiler: faktorer, vikter, signaler
  scoring.py          Normalisera → vikta → aggregera → risk → rekommendation
  explain.py          Svenska narrativ + mönsterinsikter
  datasources/        Resolver + MockSource + produktionsadaptrar (stubbar)
api/
  main.py             FastAPI (produktion)
  dev_server.py       Stdlib-server (utveckling, noll beroenden)
tests/                Testsvit (körbar utan pytest)
infra/aws-notes.md    Deploy-blueprint för AWS-fasen
```

## Lägga till en vertikal

Ny bransch = en `VerticalProfile` i `engine/verticals.py` (faktorer, vikter,
signaler) + ev. narrativmall i `engine/explain.py`. Inga motorändringar.

## Koppla in riktiga datakällor

Implementera `fetch()` i `engine/datasources/adapters.py` och lägg källan
före `MockSource` i Resolver-kedjan. Verklig data tar då automatiskt över
per signal, och `data_coverage` i varje rapport stiger. Prioritetsordning:
SCB (öppet, gratis) → bygglov/detaljplaner → platsdata/konkurrens →
rörelsedata (licens).

## Status v0.1

- 7 branschprofiler + generisk (frisör, elektriker, gym, restaurang, café,
  bygg, tandläkare), ~35 signaler, transparent viktmodell
- Förklarbara rapporter på svenska, riskmotor, mönsterinsikter
  (t.ex. caféets morgon/eftermiddags-obalans, elektrikerns marknadsutrymme)
- Deterministisk mockdata (platsseedad) → körbar end-to-end idag
- Roadmap: v2 kalibrering av vikter mot verkliga utfall,
  v3 ERP-modell (Expected Revenue Potential) i SageMaker
