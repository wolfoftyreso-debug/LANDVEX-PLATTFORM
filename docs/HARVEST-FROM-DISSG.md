# Harvest from `dissg` — the russin, extracted

Source: `wolfoftyreso-debug/dissg` @ `7b08a5f` — a Swedish "Reality Index / NOGF /
STRIM" platform (React + Supabase edge functions + Postgres). This document is the
extracted, portable substance ("russinen") worth lifting into the LANDVEX engine.
Every item cites the real file + line range in dissg so the port is grounded, not
guessed. Nothing here depends on dissg's React/Supabase plumbing — the load-bearing
logic is deterministic rule tables, pure math, and typed schemas that map 1:1 to the
stdlib-Python "everything-is-data" core.

Two honesty notes carried over from the source: several dissg "AI" functions
(`kpi-forecast`, `kpi-decisions`, `decision` node answers) are LLM prompt wrappers
with **no math** and are stubbed with `Math.random()` — their *schema* is the value,
not the numbers. Those are marked ⚠️ below. The `kpi-ingest` source handlers are
also stubs; the real fetchers are the dedicated `scb-fetch` / `kolada-ingest` /
`svk-ingest` functions.

---

## The map — russin × value × Landvex gap

| # | Russin | Substance | Portability | Landvex today |
|---|--------|-----------|-------------|---------------|
| A | **Weighted-component scorer** | Same shape 3× (relevance 6-factor, action 4-factor, wrapped 5-factor): raw 0–100 → `(raw/100)·maxpts·weight` → clamp → threshold=50 highlight; inversion-aware | Trivial, pure | Has ad-hoc scoring; no generic reusable scorer |
| B | **Neutrality + citation + integrity layer** | Regex input-gate + output-sanitizer; `verifyCitations` blocks unsourced claims; 9-field data-contract; SHA-256 evidence-links; self-audit invariants | Pure `re`+`hashlib` | Principles stated in prose, **not machine-enforced** |
| C | **Lambda 1.0 index** | 8-axis geometric-mean `λ=(Π axis)^(1/8)`, normalize 0–100→0.7–1.3; geo-mean blocks "compensating lies"; 7 interpretation bands | 4-line stdlib | Has `indices.py` (7 city indices) but no λ / anti-compensation |
| D | **Statistics kit** | CUSUM change-point (thr 2.5), Pearson, Spearman, lag cross-corr, z-score anomaly (z>2), lin-reg trend w/ R² | stdlib, no numpy | None — trends are heuristic deltas only |
| E | **Setpoint / tolerance DB** | ECU-style calibrated thresholds per indicator, 4 bands (optimal/acceptable/warning/critical) | Data table | None |
| F | **KPI engine** | Threshold table + invert-aware status/trend rule + 6-factor relevance ranker | Pure | Opportunity/Risk scores exist; no KPI registry/alerts |
| G | **Ingestion source catalog** | Real SCB PX table paths + ContentsCodes, Kolada KPI ids, SVK/ENTSO-E EIC + endpoints | Data dicts | Only SCB (5 signals) wired |
| H | **Feed event bus** | KPI move → dedup'd "why-now" event; checksum dedup, per-feed thresholds, SSE + HMAC webhooks | Pure + I/O | risk_intel says "requires monitoring history" — this IS it |
| I | **Wrapped worthiness engine** | Generic significance selector: 5-factor score, hero/primary/secondary/mention buckets, narrative hooks | Straight port | None |
| J | **Universal Index Object + canonical facts** | Verifiable indexed claim: source/time/jurisdiction/confidence/relations/SHA-256 versioning; append-only SQL | dataclass + hashlib | Reports carry source per signal; no claim graph / versioning |
| K | **NOGF governance** | Indicator ↔ 3 owners (formell/operativ/uppföljning); decision→outcome→effectiveness; k-anonymity gates; language shield | Schema + predicates | None |
| L | **STRIM knowledge graph** | Citable schema.org entity graph, neutral-language validator, immutable-URL versioning | dataclass + regex | None (domain-specific, pattern reusable) |
| M | **Monetization tiers** | Ordered tier cascade, per-key complexity/rate quotas, monthly usage window, mandatory legal-acceptance | enum + dict | `licensing.py` exists — refine, don't rebuild |

---

## A — Weighted-component scorer (the universal primitive)

The single most-reused shape in dissg. Appears identically in three engines; unify it.

- **6-factor relevance** — `calculate-relevance/index.ts:84-319`, weights from migration
  `20260202024835`: impact 0.30 / acceleration 0.20 / breadth 0.15 / persistence 0.15 /
  responsibility 0.10 / dataConfidence 0.10. Caps 30/20/15/15/10/±10. `shouldHighlight = total ≥ 50`.
- **4-factor action priority** — `prioritize-actions/index.ts:52-70`:
  `weighted = effect·0.40 + cost·0.25 + (100−risk)·0.20 + reversibility·0.15`
  (risk inverted). Bands: ≥80 critical, ≥65 high, ≥45 medium, ≥25 low, else monitor.
- **5-factor wrapped worthiness** — `worthinessEngine.ts:106-401` (see I).

**Port:** `engine/scorekit.py` — `WeightedScorer(components: list[Component])` where
`Component = {key, weight, cap, invert, fn}`; returns `{total, breakdown, primary_reason,
highlight}`. Every existing Landvex score can migrate onto it incrementally.

---

## B — Neutrality + citation + integrity (the flagship differentiator)

This is the crown jewel and maps exactly onto Landvex's stated honesty principles —
it turns them from prose into enforced code.

**Neutrality (three gates)** — `ai-observation/index.ts:92-140`, `ai-answer/index.ts:116-136`,
`cqais/index.ts:77-107`:
- Input gate — refuse forecast/normative/value-judgment queries by regex:
  `will|would|going to … happen/increase`, `should|ought|must|recommend`,
  `best|worst|optimal|ideal`, `predict|forecast|projection` → typed block
  `{code, reason ∈ normative|political_directive|speculative|insufficient_data|out_of_scope, suggestion}`.
- Output sanitizer — `FORBIDDEN_PATTERNS` (`caused by, led to, resulted in, because,
  therefore, should, must, better, worse, good, bad, proves, obviously, clearly`);
  `validateResponse()→{valid, violations}`, `sanitizeResponse()` replaces hits with
  `[BLOCKED]` and force-appends disclaimer `"Observed patterns do not imply causation or intent."`
- Fallback: *"Unable to generate neutral observation for this request."*

**Citation / grounding (anti-hallucination)** — `LLM_INTEGRATION_SPEC.md:1147-1206`,
`masterprompt/index.ts:80-97`, `cite/index.ts:27-53`, `API-EVIDENCE-LINKS.md`:
- 9 mandatory provenance fields (reject on any missing): `source_id, source_type,
  update_frequency, temporal_coverage, geographic_coverage, method, uncertainty,
  license, last_verified`. `validation_rule: missing → rejected`.
- `verifyCitations(text, retrievedSet)`: each cited `indexId` must exist in the
  retrieved set AND `valueMatches(claimed, source.value)`; detect uncited factual
  claims; `all_valid = invalid==0 && uncited==0`. **Blocks** unsourced output
  (`min_confidence 0.6`, `require_citations true`).
- Citation IDs: `FACT-{TOPIC}-{LOC}-{YEARS}`, `CITE-{question_id}`,
  `EL-{sha256}-{ts}-{ver}`. Multi-format output text/BibTeX/APA/JSON-LD.
- Trend derivation: `<2% = stable`; uncertainty derived not guessed —
  `low` if ≥10 obs & all conf≥80; `high` if <5 obs or any conf<60; else `medium`
  (`generate-facts/index.ts:195-200`).
- Render states: LIVE / UNAVAILABLE / NOT_SUPPORTED — `no_fourth_state`,
  `final_rule: "Silence is always better than speculation."`

**System integrity (self-audit invariants)** — `super-audit/index.ts`:
- Every observation MUST declare uncertainty; null → critical "TRUTH ENGINE VIOLATION".
- Estimated values MUST carry `estimation_method`; null → critical "epistemic fraud".
- Suspicious-stability detector: ≥5 identical consecutive values → high "possibly
  silently smoothed or stale".
- Response templates scanned for `should/must/recommend/best/worst/always/never`.
- `integrityScore = max(0, 100 − findings·20)`; pass = zero criticals.

**Port:** `engine/integrity.py` — `neutralize(text)→(clean, violations)`,
`classify_query(q)→block|ok`, `verify_citations(claims, retrieved)→report`,
`evidence_link(payload)→id`, `audit(records)→[Finding]`. Pure `re` + `hashlib` +
`json`. Self-contained, no external data. **Port first.**

---

## C — Lambda 1.0 index

`src/lib/lambda/lambda-1.0.ts:297,304-329`. `LambdaAxis = ECON|HEALTH|LABOR|EDUC|
SOCIAL|CLIMATE|GOV|DEMO`. Each axis 0–100 → 0.7–1.3 via `0.7 + (raw/100)·0.6`
(median 50→1.0). `λ = (Π axes)^(1/8)`. Interpretation (`lambda-calculator.ts:60-67,
350-407`): balanced 0.90–1.10, warning 0.85/1.15, critical 0.70/1.30; 7 bands with
colors. Geometric mean is the point — one strong axis can't mask a weak one.

**Port:** `engine/lambda_index.py` — `lambda_score(axes: dict[str,float])→{lambda,
band, drivers, coverage}`. ~30 lines.

---

## D — Statistics kit

`analyze-kpi/index.ts` (all pure, no AI):
- `analyzeTrend:56-91` — consecutive-step counter, `strength = min(100,(max/n)·100+20)`.
- `detectChangePoint:94-133` — **CUSUM**: standardize `(v−mean)/std`, accumulate,
  `detected = maxCusum > 2.5`.
- `calculateCorrelation:136-152` — Pearson r.
- `analyzeLag:155-181` — cross-corr over lag 0..6, best |r|.
- anomaly `:305-318` — `z=|v−mean|/std`; z>2 → anomaly, `conf=min(0.5+(z−2)·0.15,0.95)`.
- `normalization.ts` — z-score, min-max, PPP, winsorize 1/99, percentile rank,
  CI `1.96/√n · sourceFactor · coverageFactor`, lin-reg trend w/ R² (2% significance).
- `correlation-engine.ts` — Spearman via ranks, p-value (Abramowitz-Stegun normalCDF),
  confidence tiers, spurious warning `|r|>0.8 & n<20`.

**Port:** `engine/stats.py` — stdlib only.

---

## E — Setpoint / tolerance DB

`src/lib/lambda/setpoint-tolerance.ts:83-323`. Per-indicator ECU-style calibration,
4 nested bands + derivation provenance. Hard numbers to port verbatim: TFR 2.1
(optimal 2.0–2.4), dependency ratio 50 (>60 stress), CPI 2.0 (1.5–2.5), unemployment
4.5, debt/GDP 60 (Maastricht), life expectancy 82, infant mortality 3, Gini 0.30,
social trust 65. `assessZone(value)→{zone, deviation%}`.

**Port:** `engine/setpoints.py` — a data table + `assess_zone()`.

---

## F — KPI engine

- Schema: migration `20260201214947` — `kpi_definitions` (kpi_index 1..100, code,
  category enum, is_inverted, red_flag_conditions, calculation_formula),
  `kpi_values` (period, granularity national|regional|municipal, value, status
  enum, trend enum, trend_percent, confidence, UNIQUE(kpi,period,granularity,region)).
- Status/trend rule (`kolada-ingest/index.ts:197-227`): `trendPct=(v−prev)/|prev|·100`;
  `|·|<0.5 stable`; `isImproving = is_inverted ? down : up`; `status: improving→positive,
  declining & |Δ|>5%→critical, declining→warning`.
- Threshold table (`kpi-alerts/index.ts:19-44`): per-KPI `{warning, critical, direction,
  velocityWarning, velocityCritical}`; absolute breach then velocity breach; dedup same
  `(kpi,alert_type)` within 24h.
- 6-factor relevance ranker → see A.

**Port:** `engine/kpi.py` (registry + status rule + alerts) reusing A + D.

---

## G — Ingestion source catalog (the expensive-to-rediscover data)

**SCB** (`scb-fetch/index.ts`): base `https://api.scb.se/OV0104/v1/doris/sv/ssd`
(v2beta `.../v2beta/api/v2/sv/ssd`). Table→KPI (code = ContentsCode):
- life_expectancy `BE/BE0101/BE0101I/Medellivsl` `000000NH`
- excess_mortality `BE/BE0101/BE0101G/ManadBefStat` `000001S4`
- working_age `BE/BE0101/BE0101A/BefolkningNy` `BE0101N1` agg Ålder5år
- employment `AM/AM0401/AM0401A/NAKUBefAkeLArb` `000000CK`; unemployment `000000CL`
- productivity `NR/NR0103/NR0103B/NR0103ENS2010T04Kv` `0000003X`
- tax_base `OE/OE0107/OE0107A/SkijRegLanK` `OE0107A2`
- dependency_ratio `BE/BE0101/BE0101C/BefijPrognRevN` `BE0101U1`
- school `UF/UF0107/UF0107A/Grunderslag` `UF0107A3`; housing `BO/BO0101/BO0101A/LaijFardBoAr` `BO0101B1`
Query: `{query:[{code, selection:{filter:'item'|'top'|'all'|'agg:…', values:[]}}], response:{format:'json'}}`.

**Kolada** (`kolada-ingest/index.ts:15-30,136`): base `https://api.kolada.se/v2`;
`/v2/data/kpi/{id}/municipality/{code|0000}/year/{...}`; pick `gender=="T"`. Ids:
life_expectancy `N00914`, excess_mortality `N00401`, long_term_exclusion `N31813`,
violent_crime `N07403`, healthcare_queue `N20401`, school_grade9 `N15428`.

**SVK / ENTSO-E** (`svk-ingest/index.ts:17-24,289,321`): ENTSO-E `https://web-api.tp.entsoe.eu/api`
(`ENTSOE_API_KEY`), Sweden EIC `10YSE-1--------K`, `documentType=A75&processType=A16`,
psrType B14 nuclear / B12 hydro / B19 wind. SVK controlroom `/productionmix`,
`/getproductionbalance`; Mimer primary regulation. Derived:
`stabilityScore = max(0, 100 − |freq−50.0|·100)`; `balance_mw = prod − cons + import − export`.

**open-data-aggregator** (`:26-43`): SMHI metfcst, Sveriges Radio news, exchangerate,
EU data hub, thesportsdb. Health rule (`kpi-api:268-291`): overdue if hours-since >
`{realtime:1, daily:36, weekly:192, monthly:768, quarterly:2400}`.

**Port:** extend `engine/datasources/` with `scb` table catalog + new `kolada.py`,
`svk.py` adapters in the existing Resolver pattern.

---

## H — Feed event bus

Schema `feed_events` (migration `20260202032717:132-168`): `severity, scope_type,
scope_code, summary, why_now JSONB[], metrics[], kpi_ids[], confidence, checksum,
UNIQUE(feed_id, checksum)`. Feed def `:18-40`: `tier open|plus|pro, min_effect_threshold
(2.0), min_confidence (0.7), max_events_per_day (10)`. 13 seeded feeds.
Generators (`generate-feed-events/index.ts:161-557`): daily_top_changes,
emerging_trends, regional_anomalies (≥2 indicators/region), priority_alerts
(signal≥0.7), structural_decline (≥3 declining periods, Δ≤−2%), early_warning.
Dedup `checksum = sha256(json(dedupKey))`. SSE severity ordering + 30s ping.
Webhook HMAC `X-NOGF-Signature: sha256=HMAC(payload, secret)`, retry <3.

**Port:** `engine/feeds.py` — generators as pure `(rows, feed)→[Event]`; checksum
dedup; delivery is API-layer.

---

## I — Wrapped worthiness engine

`worthinessEngine.ts:106-401` (mirrored in `wrapped-api/index.ts`). `IndicatorSnapshot`
+ `WorthinessScore`. Hard-exclude `relevanceLevel L0` or `insufficient`. Factors:
relevance max40 (`{L0:0,L1:10,L2:20,L3:30,L4:40}` + pop bonus), magnitude max25
(|Δ| breakpoints 50/25/10/5/2), velocity max15, quality max10 (`conf·5` + source
bonus), impact max10 (cross-domain links). `WORTHINESS_THRESHOLD 50`; priorities
hero 85 / primary 70 / secondary 55 / mention 50. Caps hero2/primary5/secondary10/
mention20. `detectPatternBreak` = outside 2·std of ≥6 points. Forbids hype words.

**Port:** `engine/worthiness.py` — reusable significance selector for digests/alerts.

---

## J — Universal Index Object + canonical facts

`UNIVERSAL_INDEX_OBJECT_SPEC.md:35-250`, `SYSTEM-CONTRACT.md:100-176`, migrations
`20260201214947` + `20260202154849`. UIO = `{id:SHA256(canonical), claim, source,
jurisdiction, time, confidence, relations[], immutability:{version, previous, checksum,
merkle_proof}}`. ClaimValue union numeric|text|categorical|boolean|range|vector|
timeseries. ~25 typed relations (versioning/derivation/dependency/conflict/correlation).
Canonical SQL: append-only `raw_data_ingest` (trigger blocks UPDATE/DELETE),
`canonical_facts` (fact_code, geo_level, statement, uncertainty, method observed|
estimated|calculated, version). Relevance_score weighted sum (`:168-176`).

**Port:** `engine/claims.py` — dataclass + `hashlib.sha256(json.dumps(sort_keys=True))`
id/checksum; relations as edge dicts; append-only in-memory/store record.

---

## K — NOGF governance

`NOGF-FRAMEWORK.md`, `LEGAL_POLITICAL_SHIELD_SPEC.md`. 5 axioms
(measurement→context→traceability→visibility→follow-up). **Every KPI carries 3
owners** (formellt/operativt/uppföljning); "no owner → indicator may not exist".
Decision→outcome→effectiveness%; "decision without follow-up = invalid".
Language shield: agentless/passive/time-bound ("timeline points, we never point").
"We Don't Say" table: claims/recommendations/predictions/judgments → neutral
restatements. Attribution chain → `chain_hash SHA256` + public verify URL.
Privacy: k-anonymity min 5, min cell 10, +2% noise on deep zoom.

**Port:** schema fields on claims (K reuses J) + predicates (min-N gate, 3-owner
requirement) + the language map (reuse B).

---

## L — STRIM knowledge graph

`strim-api/index.ts`. 6 entity types → schema.org (`Drug/MedicalCondition/…`),
`canonical_slug` immutable PK, `version`+`checksum`, `sources[]`. 10 relation types
(`causes, treated_by, regulated_by, …`). Read-only JSON-LD API, `cite` → APA/Harvard/
BibTeX/JSON-LD + trust block. Editorial: eternal URLs, neutral-language validator
(forbidden `bör/ska/måste`, `bra/dålig/bäst`, `studier visar`, `!`), ≥2 sources incl
1 primary. Domain here is addiction — for LANDVEX the **pattern** (citable versioned
neutral entity graph) is the reusable part; reuse J + B.

---

## M — Monetization tiers

`API-BUSINESS-MODEL.md`, migrations `20260203003614` + `20260202040302`. Tiers
Free/Plus/Pro (+ institutional). Feature-gating matrix (KPIs/query 1/3/∞, history
5y/20y/∞, correlation ❌/✅/✅, simulation/white-label Pro). `has_tier_access` ordered
cascade. `api_keys`: `rate_limit_per_minute 60, per_day 10000, query_complexity_limit
100`, capability booleans, `allowed_endpoints/countries/nuts_levels[]`. `feature_usage`
monthly window `UNIQUE(user,feature,period_start)`. Checkout hard-blocks without 4
legal-acceptance timestamps. Sell "indikationer", never "rekommendationer".

**Port:** refine existing `api/licensing.py` + `api/security.py` — add complexity
budget, monthly usage window, legal-acceptance capture. Do not rebuild.

---

## Prioritised port plan (5 phases)

Ordered by value × portability × independence-from-external-data.

1. **Foundation (pure, self-contained, biggest differentiator).**
   `engine/integrity.py` (B) + `engine/scorekit.py` (A) + `engine/stats.py` (D).
   No external data, aligns with Landvex honesty principles, unlocks everything else.
2. **Composite index + calibration.** `engine/lambda_index.py` (C) +
   `engine/setpoints.py` (E). Plug λ into `indices.py`.
3. **Claims substrate + governance.** `engine/claims.py` (J) + governance fields/
   predicates (K). Makes every Landvex number a citable versioned claim.
4. **Change detection = the missing "monitoring".** `engine/kpi.py` (F) +
   `engine/feeds.py` (H) + `engine/worthiness.py` (I). This is exactly what
   `risk_intel.py` flagged as "requires monitoring history".
5. **Real data + packaging.** Ingestion adapters (G: Kolada, SVK) in the Resolver
   pattern; refine licensing/quotas (M). STRIM pattern (L) only if a citable
   entity-graph product is wanted.

Each phase ships with its own `tests/test_*.py` (no pytest, no network — Landvex
convention) and keeps `engine/` dependency-free.
