# Landvex ↔ dissg — gap-analys (domän A–N)

Grundad i faktisk kod: Landvex = `wolfoftyreso-debug/konditori-joy` @ branch
`claude/new-session-d9t6ni` (beroendefri Python-motor i roten); dissg =
`wolfoftyreso-debug/dissg` @ `7b08a5f` (Vite/React + Supabase edge functions).
Substansen ur dissg är utgrävd i `docs/HARVEST-FROM-DISSG.md` (russin A–M med
fil:rad-referenser). Denna rapport är kontrollpromptens format: status +
byggbehov + komplexitet + MVP-prioritet + beroenden per domän.

> **Strukturnot.** Kontrollprompten antar en monorepo (`apps/`, `server/`,
> `packages/types/`). Den finns inte. Landvex är en stdlib-Python-motor +
> FastAPI/stdlib-API + självförsörjande `frontend/index.html`. Alla
> "bygg"-förslag och skelettet nedan följer den faktiska arkitekturen och
> kärnprincipen *engine förblir beroendefri*. Node/Express/React-sökvägar ur
> prompten är därför medvetet inte återgivna som om de fanns.

## Steg 1 — Landvex nuläge (faktisk kartläggning)

- **Motor** (`engine/`, stdlib): `scoring, scan, plan, compare, gaps, ask,
  risk, risk_intel, opportunity_intel, workforce, installed_base, indices,
  segments, markets, specialization, commission, report, explain, signals,
  verticals, profile` + `integrity` (nyss portad). `datasources/` med Resolver +
  adaptrar (`scb` live, `permits/places/programs/quixzoom_direct`, `mock`,
  `cache`). `storage/` (sqlite/postgres).
- **API** (`api/`): `dev_server.py` (stdlib) + `main.py` (FastAPI), låsta lika av
  `test_contract`. ~40 `/v1/*`-endpoints. `security.py` (API-nyckel/JWT/RBAC/
  rate-limit/audit), `licensing.py` (Free/Pro/Enterprise + tillägg + kvoter),
  `health/catalog/agent_manifest/lambda_handler`.
- **Frontend**: en `frontend/index.html`, självförsörjande (noll CDN), iOS-tema,
  flikar (Fråga/Guide/Karta/Index/Watch/Paket/Inställningar).
- **Täckning**: 35 marknader / 344 regioner (alla 50 US-delstater, alla 27 EU).
  Endast SCB är verklig källa; övrigt mock, ärligt märkt.
- **Tester**: 25 sviter, utan pytest, utan nät.

## Steg 2–3 — Gap-rapport per domän

| Dom | Domän | Status | Komplexitet | MVP-prioritet | Beroenden |
|-----|-------|--------|-------------|---------------|-----------|
| A | Lambda-index | **SAKNAS** (indices.py har 7 stadsindex, ej λ) | M | HÖG | C, E |
| B | Kommun/City-lager | **DELVIS** (markets+indices; ej djupdyk/barometrar) | L | MEDIUM | C, A |
| C | KPI-motor | **DELVIS** (scoring finns; ej KPI-registry/alerts/relevans) | L | KRITISK | — |
| D | Datainsamling | **DELVIS** (SCB live; Kolada/SVK/intl saknas) | L | KRITISK | C |
| E | AI-neutralitetslager | **DELVIS → PORTAD kärna** (`integrity.py`) | M | KRITISK | — |
| F | Governance & ansvar | **SAKNAS** | L | MEDIUM | C, I |
| G | Global expansion | **FINNS** (344 regioner; data mock utom SCB) | — | — | D |
| H | Intelligence feeds | **SAKNAS** | M | HÖG | C, D |
| I | Kanonisk data & citat | **DELVIS** (verify/provenance/evidence portat; ej fakta-generering/cite-API) | M | HÖG | C, E |
| J | Beslutsstöd | **DELVIS** (report/scan/plan/compare/ask; ej Decision Graph/krisdetektion) | M | MEDIUM | C |
| K | Systemintegritet | **DELVIS** (`audit`/`integrity_score` portat; ej Brier/kalibrering/kausalgraf) | M | MEDIUM | E, I |
| L | Wrapped | **SAKNAS** | S | FRAMTIDA | C, H |
| M | STRIM | **SAKNAS** | M | FRAMTIDA | I |
| N | Monetarisering | **DELVIS** (3 tiers + kvoter; ej 4-tier/Stripe/komplexitetsbudget) | M | MEDIUM | — |

### Byggbehov per domän (konkret, Landvex-arkitektur)

- **A Lambda:** `engine/lambda_index.py` — `lambda_score(axes)` (geometriskt
  medel, 0.7–1.3-normalisering, 7 band); `/v1/lambda` i båda API-lagren; koppla
  in i `indices.py` + Index-fliken. *Ref: HARVEST §C.*
- **B Kommun/City:** utöka `markets.py`-regioner till stadsdjup + `engine/city.py`
  (13 indikatorer/6 kategorier, jämförelse-barometrar, tidsserier); UI: ny
  City-vy i `index.html`. Kräver C (KPI-värden) + A (λ per stad).
- **C KPI-motor:** `engine/kpi.py` (registry `kpi_definitions`, invert-medveten
  status/trend-regel, `kpi-alerts`-trösklar), `engine/scorekit.py` (6-faktors
  relevans + generisk viktad scorer), `engine/stats.py` (CUSUM/Pearson/lag/
  z-score); `/v1/kpi/{overview,timeseries,alerts}`. *Ref: HARVEST §A,D,F.*
- **D Datainsamling:** `datasources/kolada.py`, `datasources/svk.py`, utöka
  `scb.py`-tabellkatalog (40+ tabeller m. ContentsCode); `open_data.py`
  (SMHI/SR/ECB). Allt i befintligt Resolver-mönster, ärlig degradering. *§G.*
- **E Neutralitet:** kärnan **portad** (`integrity.py`: `classify_query`,
  `neutralize`, förbjudna ord, disclaimer). Kvar: koppla `classify_query` in i
  `ask.py`-ingången och `neutralize` på narrativ-utgången; `masterprompt` som
  data i API-lagret. *§B.*
- **F Governance:** governance-fält på claims (`engine/claims.py`) — 3
  ansvarsroller/indikator, decision→outcome→effektivitet, k-anonymitetsgrind,
  språksköld (återanvänder `integrity`); `trust_log` append-only i `storage/`.
  *§K.*
- **H Feeds:** `engine/feeds.py` (6 generatorer, checksum-dedup, per-feed-
  trösklar); `/v1/feeds` + `/v1/feeds/events`; SSE/webhook i API-lagret (HMAC).
  Detta ÄR det `risk_intel` kallar "requires monitoring history". *§H.*
- **I Kanon & citat:** `engine/claims.py` (UIO + kanon-fakta, SHA-256-
  versionering) + `generate_facts` (mallar, härledd osäkerhet via redan portade
  `derive_uncertainty/trend`); `/v1/cite/{id}` (BibTeX/APA/text) i API-lagret.
  Grounding-grinden redan portad. *§B,J.*
- **J Beslutsstöd:** `engine/decision.py` (Decision Graph: noder med
  answer_type, confidence-tröskel, data_gaps) ovanpå befintlig report/scan;
  krisdetektion (suicid/självskada → lokala nödresurser) som hård grind i
  `ask.py`/API. *§3b i STRIM-agentens rapport.*
- **K Systemintegritet:** `audit`/`integrity_score` **portat**. Kvar:
  Brier-scoring + `calibration_snapshots` (kräver utfallsdata — bakvänt beroende
  på Landvex backlog #11) och valfri kausalgraf (DAG). *§B (systemintegritet).*
- **L Wrapped:** `engine/worthiness.py` (5-faktors signifikans-väljare + hero/
  primary/secondary/mention-buckets); `/v1/wrapped`. Generisk — återanvänds för
  digests/alerts. *§I.*
- **M STRIM:** `engine/strim.py` (citerbar versionerad neutral entitetsgraf,
  schema.org-mappning) — domänen i dissg är beroende (missbruk); för Landvex är
  *mönstret* russinet. *§L.*
- **N Monetarisering:** utöka `licensing.py` till 4 tiers + komplexitetsbudget +
  månadsfönster + juridisk-acceptans-fält; Stripe hör till API-/infra-lagret,
  inte kärnan. *§M.*

## Steg 4 — Byggordning (justerad efter faktiskt repo)

Prompten föreslog databas-först. Landvex har redan storage + 344 regioner + 40
endpoints, så grunden finns. Ordningen är i stället **värde × portabilitet ×
oberoende-av-extern-data**, och sammanfaller med `HARVEST-FROM-DISSG.md`:

- **Fas 1 — Fundament (rent, självförsörjande):** E ✅ (`integrity.py` klar) ·
  C-kärnan (`scorekit.py` + `stats.py`) · resten av C (`kpi.py`).
- **Fas 2 — Index + kalibrering:** A (`lambda_index.py`) + `setpoints.py`
  (kalibrerade trösklar) → in i `indices.py`/Index-fliken. B (city-djup).
- **Fas 3 — Påstående-substrat + governance:** I (`claims.py` + cite) → gör varje
  Landvex-siffra till ett citerbart versionerat påstående; F (governance-fält).
- **Fas 4 — Förändringsdetektion (det saknade "monitoring"):** H (`feeds.py`) +
  J (`decision.py`) + L (`worthiness.py`).
- **Fas 5 — Riktig data + expansion:** D (Kolada/SVK/intl-adaptrar) · N (kvoter/
  tiers) · M (STRIM-mönstret) · K (Brier/kalibrering när utfallsdata finns).

Kritiska stigar: allt beslutsnära bygger på **C** (KPI + scorekit + stats); allt
citerbart bygger på **I** som bygger på redan-portade **E**.

## Steg 5 — Skelett (Landvex-arkitektur, ingen kod)

```
engine/
  integrity.py          ✅ PORTAD  (E, delar av I & K)
  scorekit.py           ⬜ C  – generisk viktad scorer (6/4/5-faktor)
  stats.py              ⬜ C  – CUSUM, Pearson, Spearman, lag, z-score, lin-reg
  kpi.py                ⬜ C  – kpi_definitions-registry, status/trend, alerts
  lambda_index.py       ⬜ A  – geometrisk λ, band, drivers
  setpoints.py          ⬜ E(kalib) – kalibrerade trösklar (TFR/Gini/Maastricht…)
  claims.py             ⬜ I,F – UIO + kanon-fakta, SHA-256-versionering, ägare
  feeds.py              ⬜ H  – 6 generatorer, checksum-dedup, per-feed-trösklar
  worthiness.py         ⬜ L  – signifikans-väljare + buckets
  decision.py           ⬜ J  – Decision Graph (noder, data_gaps, krisgrind)
  city.py               ⬜ B  – stadsdjup: 13 indikatorer/6 kategorier
  strim.py              ⬜ M  – citerbar neutral entitetsgraf (mönster)
  datasources/
    kolada.py           ⬜ D  – Kolada v2 (N00914, N07403…)
    svk.py              ⬜ D  – SVK/ENTSO-E (EIC 10YSE-1--------K, stabilitet)
    open_data.py        ⬜ D  – SMHI/SR/ECB
    scb.py  (utökas)    ⬜ D  – 40+ tabellkonfig m. ContentsCode
api/
  dev_server.py/main.py (utökas) – /v1/{kpi,lambda,feeds,cite,wrapped,decision}
  licensing.py (utökas) ⬜ N  – 4 tiers + komplexitetsbudget + månadsfönster
  masterprompt.py       ⬜ E  – systemkonstitution som data (prompt-lager)
storage/
  (append-only trust_log, claims-revision) ⬜ F,I
frontend/index.html (utökas)   – Lambda-oscilloskop, City-vy, Feeds, Wrapped
tests/
  test_integrity.py     ✅  (19)
  test_scorekit.py test_stats.py test_kpi.py test_lambda.py test_claims.py
  test_feeds.py test_worthiness.py test_decision.py …  ⬜ (en per modul)
```

Varje modul är stdlib, deterministisk, med egen pytest-fri testsvit — Landvex-
konventionen. Inga Node/Express/React-filer: det motsäger repots faktiska
arkitektur.
