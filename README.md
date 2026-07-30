# LANDVEX Opportunity Engine

**What the data supports — and where it runs out.**

Global decision-support for future workforce and business needs. It does not
answer *"where are the most people?"* but **"where does THIS specific business
have the highest probability of success — and making money?"** — with an
explainable factor breakdown, confidence, assumptions and honest data coverage
in every response. US-first; Sweden is the first fully calibrated market.

---

## Quickstart

**Windows:** double-click `START-WINDOWS.bat` (or run `py run.py`).
**macOS/Linux:** `python3 run.py`.
Either way the launcher picks a free port, binds to loopback only and opens
the console at `/sandbox`. See `START-HERE.txt`.

```bash
# Dependency-free dev server + portal (zero install):
python3 -m api.dev_server            # → http://localhost:8000/
#   LANDVEX_HOST=127.0.0.1 binds loopback only (no Windows Firewall prompt)

# Full test suite (no pytest, no network):
make test          # every suite, no pytest, no network
make preflight     # is THIS environment ready for real traffic?

# Production API:
pip install -r requirements.txt && uvicorn api.main:app --host 0.0.0.0 --port 8087
```

Read **[`docs/dev-sync.md`](docs/dev-sync.md)** first — it is the single entry
point (coverage, endpoints, integrations, activation checklist).

---

## Repository layout

| Path | Purpose |
|------|---------|
| `engine/` | Dependency-free core (stdlib only) — the six decision layers. Runs identically locally, in Lambda and ECS. |
| `engine/datasources/` | Resolver chain + adapters: SCB (live), permits, places, programs, quiXzoom — real source wins, mock is the honest fallback. |
| `api/` | Two interchangeable API layers — `main.py` (FastAPI, production) and `dev_server.py` (stdlib, zero deps), locked equal by a contract test. |
| `integrations/` | AAMOS Capability Platform client (degrades honestly when not connected). |
| `frontend/` | Self-contained portal (no external deps) — Apple-native theme, intro hero, optional real map layer. |
| `tests/` | Every suite runs without pytest and without network. |
| `scripts/` | The start gate (`preflight`), source probes (SCB, AAMOS, sensors, registers), the 90-second demo, and the standalone-demo builder. Ships inside the image on purpose. |
| `deploy/aws/` | ECS task definition and execution-role policy, both held against the code by tests. See [`docs/aws.md`](docs/aws.md). |
| `deploy/k8s/` | Kubernetes manifests for the `landvex-prod` EKS cluster, held against the code and against `deploy/aws/` by tests. See [`docs/k8s.md`](docs/k8s.md). |
| `infra/` | systemd unit, nginx conf, AWS notes, deployment collateral, infrastructure inventories. |
| `docs/` | Documentation — see [`docs/README.md`](docs/README.md). |

## The decision layers

1. **Opportunity Score** — 0–100, personalized: ★ rating, percentile
   (*"Beats 93% of locations for your profile"*), 2-year demand outlook.
2. **Opportunity Intelligence** — support-program fit, "you're missing money",
   hidden opportunities, legal categories, lifecycle & expansion advice.
3. **Risk Intelligence / Business Signals** — a Risk Score beside the
   Opportunity Score, ten risk categories, a cautious counterparty-health model.
4. **Workforce Intelligence** — skills forecasts 1–20 years, shortage maps.
5. **Installed Base** — installed base → future service demand & technician need.
6. **Intelligence Map** — city indices + the Contradiction Index (planned vs
   observed).

## Design principles (do not break)

1. **Everything is data, not code** — new verticals/markets/programs need no
   engine changes.
2. **`engine/` stays dependency-free** — external libs live in `api/`, adapters
   and infra.
3. **Explainability before prediction** — no survival-probability or ROI
   promises until outcome data exists.
4. **Honest coverage** — mock is always `source="mock"`; `data_coverage` is
   never faked; heuristics are labelled; degradation never fabricates a number.
5. **Determinism** — same location + vertical → same report.

## Status

- **SCB (Sweden):** live. **Permits / Places / Programs / quiXzoom:** adapters
  complete, activated by a single environment variable each (see
  [`docs/dev-sync.md`](docs/dev-sync.md) §6).
- Everything not connected is mock and **labelled as simulated**.

## License

Proprietary — add a `LICENSE` file before distribution.
