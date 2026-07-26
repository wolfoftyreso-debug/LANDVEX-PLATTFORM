# Changelog

Formatet följer [Keep a Changelog](https://keepachangelog.com/); semantisk versionering.

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
