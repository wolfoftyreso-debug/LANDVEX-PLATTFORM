# REXO-leverabler för Opportunity Engine-deployment

Underlag för att stänga deployment-tasken enligt REXO-pipelinen
(`/opt/amos/rexo-build/`, 7 steg). Körs på servern av Bernt eller
manuellt – detta repo kan inte nå servern.

## Task-utkast (PLAN.json)

```json
{
  "title": "Deploy Landvex Opportunity Engine behind api.landvex.io",
  "scope": "systemd service on :8087, nginx /v1/ mount, env config,
            pgbouncer DSN, LANDVEX_QUIXZOOM_URL wiring",
  "artifacts": ["infra/landvex-opportunity.service",
                 "infra/nginx-opportunity.conf"],
  "verification": "curl -sf https://api.landvex.io/health → 200;
                   /v1/ask answers; /metrics scrapes in Prometheus"
}
```

## Manual-utkast (rexo_docs.manuals)

**Landvex Opportunity Engine – drift**
1. Kod: klona repot till `/opt/landvex/opportunity-engine`
   (katalogen `landvex-opportunity-engine/`).
2. Konfig: `/etc/landvex/opportunity.env` – se kommentarerna i
   `infra/landvex-opportunity.service` (API-nycklar, pgbouncer-DSN
   `127.0.0.1:6432`, `LANDVEX_QUIXZOOM_URL=http://127.0.0.1:3209`,
   auditlogg).
3. Start: `systemctl enable --now landvex-opportunity` (port 8087).
4. nginx: inkludera `infra/nginx-opportunity.conf` i
   `landvex-ssl.conf`-serverblocket, `nginx -s reload`.
5. Övervakning: `/health` (källstatus, quixzoom = "ok" när URL satt),
   `/metrics` → befintlig Prometheus (:9090) / Grafana (:3050).
6. Verifiering: `curl -sf localhost:8087/health`,
   `curl -s -X POST localhost:8087/v1/ask -H "X-API-Key: …"
    -d '{"question":"Where should I open a café?"}'`.
7. Tester: `python3 -m tests.test_scoring` … (15 sviter, inga beroenden).

## Artifact-utkast (`artifacts/<TID>-DONE.md`)

- Tjänst: landvex-opportunity.service aktiv på :8087 (systemd, ej pm2)
- Mount: api.landvex.io/v1/ → 127.0.0.1:8087 (v0 orörd – parallell drift)
- Design: Apple iPhone Native (iOS 18) – #007AFF, #F2F2F7, SF Pro,
  13px squircle, Liquid Glass. Inga bannade färger (verifierat).
- Priser: USD-först ($499/mo Pro), SEK förekommer inte (låst regel).
- quiXzoom: klient implementerad mot /v1/observations, aktiveras med
  LANDVEX_QUIXZOOM_URL; /health visar ansluten/ej ansluten ärligt.
- Kvarstående beslut: se "Öppna frågor" i docs/BUILD-STATE-PROMPT.md.
