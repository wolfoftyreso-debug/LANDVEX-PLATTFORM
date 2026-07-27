# Baltic Bridge — Nuläge & fortsatt plan (handoff-prompt)

> **Så använder du filen:** klistra in den som första meddelande i en ny
> Claude Code-session (eller be Claude läsa `docs/HANDOFF.md`). Den ger
> nuläget, fattade beslut och den prioriterade planen. Regelverket i
> `CLAUDE.md` (repo-roten) gäller alltid — denna fil kompletterar, den
> ersätter inte. Verifiera nuläget mot koden innan du bygger vidare.

---

## 1. Vad produkten är

Baltic Bridge är en **verifierad marknadsplats för gränsöverskridande
underentreprenad** (entreprenad, inte bemanning). Kärnprodukten är
**verifierings- och compliance-motorn**: dokumentbevisad efterlevnad
(F-skatt, A1, utstationeringsanmälan, ID06, försäkring, kollektivavtal,
svetsarkvalifikationer) med fullt revisionsspår. Köpare betalar för att
beställaransvaret försvinner. Binär verifiering — aldrig till salu, inga
nivåer/poäng. Kärnbudskap: **"Rätt kompetens. Rätt pris. Rätt kvalitet."**
Tonregel (bindande, `docs/POSITIONING.md`): framställ aldrig baltisk
arbetskraft som "billig" — kompetens/tillgänglighet/kvalitet först.

## 2. Nuläge (2026-07-27) — allt nedan är byggt, testat och pushat

**Milstolpar M1–M4 klara** enligt `CLAUDE.md` §5, plus beställda utökningar:

- **M1 Verifieringsmotor:** ärende- och punktstatusmaskiner (rena funktioner,
  enhetstestade), 10-kravskatalog som DATA per korridor, expirymotor
  30/14/3 dagar med simulerad klocka i test, ops-kanban, dokumentgranskning,
  företags-360, badge styrs enbart av ärendestatus.
- **M2 Publikt lager:** permanenta profil-URL:er med redirects, verifierad
  facts-panel (endast plattformsverifierat), kapacitetslistningar, Postgres
  FTS+trigram-sök (verified först), SEO (JSON-LD, sitemap, hreflang),
  självbetjäningsportal för leverantörer.
- **M3 Efterfrågan:** RFQ-intag (anonym → auto-konto), ops-driven matchning
  (concierge), offerter med **fryst verifieringssnapshot vid inlämning**
  (enhetstestat att senare ändringar inte påverkar), deal-registrering +
  CSV-export, meddelandetrådar med e-postnotiser.
- **M4 Härdning:** 3 Playwright-e2e (verifiera/publicera/RFQ→deal), testad
  pg_dump/restore-rutin, rate limiting, demo-seed, ops-dashboard, runbook.

**Utökningar utöver foundation:**

- **Självbetjäning:** registrering företag/kund ("tänk Alibaba/Blocket"),
  portal med profil, dokument, kapacitet, portfolio.
- **Katalog: 46 researchade riktiga företag** (14 LT, 11 LV, 11 EE, 10 PL)
  som *Unclaimed* med källattribution per faktum; 32 med publikt angivna
  certifikat (ISO 3834, EN 1090 t.o.m. EXC4, ISO 9001/14001/45001, ASME,
  IATF 16949), 2 med utmärkelser (Diamenty Forbesa, Gazele Biznesu). Visas
  som "angivna (ej verifierade)" — skilt från verifieringspanelen.
  Claim-flöde: ansökan → ops-granskning → ägarskap (ger ALDRIG verifiering).
- **Profiler v2:** modererade projektbilder (pending→approved/rejected,
  endast ops publicerar) + referenser insamlade av ops (inget review-system).
- **6 språk:** sv, en, lt, lv, et, pl — fullständiga kataloger med
  nyckelparitet; trades/krav har namn per språk i DB (fallback en).
- **2 korridorer som seeds:** `lt-se` och `pl-se` (KRS/CEIDG + ZUS för
  Polen). Admin väljer korridor efter företagets hemland.
- **Blocket-inspirerad publik design:** sökhero, kategorirutnät (13 yrken),
  radannons-kort i katalogen, chip-filter — egen färgidentitet.
- **SEO-kampanjsidor** för Sverige/Norge/Danmark (kompetens-first copy).

**Självägd infra (förberedd, beslut fattade):**

- **Noll externa beroenden i drift:** Postgres via `DATABASE_URL` (inga
  RDS-features), S3-API mot MinIO (`S3_ENDPOINT`), **egen SMTP-klient utan
  paket** (`src/modules/notifications/smtp.ts`, STARTTLS/AUTH PLAIN, vägrar
  klartext-AUTH), Auth.js+scrypt, pg-boss i Postgres, outbox utan broker.
- **Terraform** (beslutat): `infra/terraform/` — VPC, Graviton-EC2 (SSM,
  ingen SSH), krypterad datavolym + DLM-snapshots, S3-backuphink + nattlig
  pg_dump-cron, alarm med auto-recovery, valfri Route 53.
  `orchestrator`-variabel: **k3s (default, beslutat av produktägaren)**
  eller compose.
- **Kubernetes:** `infra/k8s/` Kustomize (Postgres/MinIO StatefulSets,
  migrate-Job, app-Deployment, Traefik-ingress, cert-manager-issuer).
  OBS: `CLAUDE.md` §7 listar fortfarande K8s som out-of-scope — beslutet
  är taget muntligt av produktägaren; uppdatera CLAUDE.md vid tillfälle.
- **Compose-spår:** `docker-compose.selfhost.yml` + `docker-compose.proxy.yml`
  (Caddy TLS). Dokument: `docs/SELF-HOSTED.md`, `docs/RUNBOOK.md`.

**Verifieringsstatus:** 40 enhetstester, 34+ assertions i DB-smoke
(`npx tsx src/db/smoke.ts`), 3/3 e2e mot produktionsbygge, lint+typecheck
gröna. Migrationer 0000–0008 (append-only; 0007 dedupe+unik nyckel på
kravkatalogen, 0008 awards).

## 3. Köra lokalt

```sh
npm run sandbox        # docker compose + migrate + seed + demo + dev-server
# eller manuellt:
npm run db:migrate && npm run db:seed && npm run db:seed-demo
npx tsx src/db/seed-catalog.ts   # 46 unclaimed-profiler
npm run test           # vitest
npx tsx src/db/smoke.ts          # kräver DB
npm run build && PORT=3100 node .next/standalone/server.js  # + kopiera .next/static → standalone
E2E_NO_SERVER=1 E2E_BASE_URL=http://localhost:3100 npx playwright test
```
Inlogg (seed): `admin@balticbridge.example` / `ops@…` pw `change-me-now`;
demo-leverantörer `supplier1..10@demo.balticbridge.example` pw
`demo-password-123`. Chromium: förinstallerad — kör ALDRIG
`playwright install`.

## 4. Fortsatt plan (prioriterad)

**Före publik lansering (blockerande):**
1. **Manuell källkontroll av katalogens 46 profiler** — researchen gjordes
   via sökmotor-återgivningar (direkthämtning blockerad i byggmiljön);
   omverifiera varje citerad sida, korrigera/stryk vid avvikelse.
2. **Riktig driftsättning** på egen AWS-nod: `terraform apply` →
   k3s-deploy enligt `infra/k8s/README.md`; DNS + TLS + `S3_ENDPOINT`
   (presignerade URL:er kräver exakt värdnamn). Öva restore-rutinen.
3. **Malware-skanning:** ClamAV-container bakom scan-hook-stubben
   (GuardDuty finns inte i MinIO-läget).
4. **E-post i drift:** peka SMTP-adaptern mot egen relä; äg SPF/DKIM/DMARC.

**Kort därefter:**
5. LV→SE- och EE→SE-korridorer (samma seed-mönster; Uzņēmumu
   reģistrs/VSAA resp. Äriregister/Sotsiaalkindlustusamet).
6. Magic-link-inloggning + e-postverifiering (EmailProvider klar).
7. Ops-UI för att provisionera ops/admin-konton (idag endast seed).
8. GDPR: per-användar-export + schemalagd purge av soft-deleted PII.
9. Cursor-paginering på `/api/v1`-listor; OpenAPI-spec ur Zod-scheman.
10. CI/CD: GitHub Actions → bygg image → deploy till noden via SSM.
11. Uppdatera `CLAUDE.md` §3/§7 med fattade beslut (egen infra, Terraform,
    k3s, 6 språk, 4 länder) så foundation och verklighet stämmer.

**Principer som aldrig ruckas** (se `CLAUDE.md` §8): append-only-migrationer,
audit på varje mutation, modulgränser via service-interfaces, binär
verifiering, all UI-text via i18n, fråga innan nya beroenden.
