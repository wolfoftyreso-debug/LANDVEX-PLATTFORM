# Deploying LANDVEX on landvex.com

Two supported paths. Both serve the frontend at `/` and the API under `/v1`
from the same origin, behind nginx with TLS.

- **A — Docker Compose** (recommended: one command, reproducible).
- **B — systemd + venv** (no Docker on the host).

The engine core is dependency-free; only the API layer needs `requirements.txt`.
Everything degrades honestly to labelled mock until real source URLs are set —
so it is safe to deploy first and connect data sources incrementally.

---

## 0. Pre-flight (on any machine)

```bash
make smoke            # compile + all 39 test suites — must pass before deploy
```

## 1. Configure

```bash
cp .env.example .env
# Edit .env — at minimum for production:
#   LANDVEX_API_KEYS=<key>:<tenant>:<role>:<plan>[,...]   # never run open in prod
#   LANDVEX_DB=/data/landvex.db      (or LANDVEX_PG_DSN + LANDVEX_DB=off)
```

`.env` is git-ignored. Keys, tokens and DSNs live only there / in the host's
secret store — never in the repo.

## 2. TLS certificate (once, on the host)

DNS: point `landvex.com` (and `www`) A/AAAA records at the host. Then:

```bash
sudo certbot certonly --webroot -w /var/www/certbot \
     -d landvex.com -d www.landvex.com
```

`infra/nginx-landvex.conf` already references
`/etc/letsencrypt/live/landvex.com/`.

---

## Path A — Docker Compose

```bash
make prod            # docker compose --profile prod up -d --build
# app (localhost:8000) + nginx on 80/443 serving landvex.com
```

Managed Postgres: set `LANDVEX_PG_DSN` and `LANDVEX_DB=off` in `.env`.
Bundled Postgres instead: `docker compose --profile prod --profile postgres up -d`.

Update / rollback:

```bash
git pull && make prod            # rebuilds the image, zero-config
docker compose logs -f app       # tail
```

## Path B — systemd + venv

```bash
sudo mkdir -p /opt/landvex/opportunity-engine
sudo rsync -a --exclude .git ./ /opt/landvex/opportunity-engine/
cd /opt/landvex/opportunity-engine
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

sudo mkdir -p /etc/landvex && sudo cp .env /etc/landvex/opportunity.env
sudo cp infra/landvex-opportunity.service /etc/systemd/system/
# For the FastAPI mode, set ExecStart to:
#   .venv/bin/gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8087
sudo systemctl daemon-reload && sudo systemctl enable --now landvex-opportunity

sudo cp infra/nginx-landvex.conf /etc/nginx/conf.d/landvex.conf
# point proxy_pass at 127.0.0.1:8087 for this mode, then:
sudo nginx -t && sudo systemctl reload nginx
```

---

## 3. Verify (from the host)

```bash
curl -fsS https://landvex.com/health | jq .status          # -> "ok"
BASE=https://landvex.com LANDVEX_API_KEY=<key> \
  python3 -m scripts.readiness_check                        # every endpoint 2xx
```

Open `https://landvex.com/` — the portal loads; the **Console** tab shows the
λ oscilloscope, glowing map and KPI signals live from `/v1/lambda`.

## 4. Connect live data (incremental, optional)

Each is one env var; the adapter goes live and `/health` `source_status`
flips to connected. Verify first with the probes:

```bash
LANDVEX_KOLADA_URL=https://api.kolada.se/v2 python3 -m scripts.kolada_probe
LANDVEX_SVK_URL=<controlroom-url>           python3 -m scripts.svk_probe
python3 -m scripts.scb_probe 59.33 18.06
AAMOS_CORE_URL=http://127.0.0.1:3100        python3 -m scripts.aamos_smoke
```

Set the ones that pass in `.env`, then `make prod` (A) or restart the unit (B).

## 5. Operate

- **Health / readiness:** `GET /health`, `scripts/readiness_check`.
- **Metrics:** `GET /metrics?format=prometheus` (nginx restricts it to the
  internal network — open deliberately).
- **Audit:** `GET /v1/audit` (admin capability) + `LANDVEX_AUDIT_LOG`.
- **Catalog / self-description:** `GET /v1/catalog`, `GET /v1/agent-manifest`.
- **Auth:** every `/v1` call carries `X-API-Key` (or a JWT bearer). Running
  without `LANDVEX_API_KEYS` is open mode — staging only.

## Security checklist before going live

- [ ] `LANDVEX_API_KEYS` (or JWT) set — not open mode.
- [ ] `.env` not committed; secrets only on the host.
- [ ] `/metrics` and `/v1/audit` restricted to the internal network / admin.
- [ ] TLS valid (HSTS is emitted); `www` → apex redirect works.
- [ ] AAMOS uses a real service-account token — never a forged one.
- [ ] Postgres reachable and `PostgresStore.selftest()` passes if used.
- [ ] **Outcome logging:** the `/v1/outcomes` registry is process-local. If you
      use it, run `WEB_CONCURRENCY=1` (or back it with the store) so records
      aren't split across workers or lost on restart. All other endpoints are
      stateless and scale to any worker count.
