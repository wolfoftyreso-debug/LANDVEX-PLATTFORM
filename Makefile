# LANDVEX Opportunity Engine — build, test, run, deploy.
.DEFAULT_GOAL := help
PY ?= python3
IMAGE ?= landvex/opportunity-engine:1.1.0

.PHONY: help test lint demo measure measure-live run dev build up prod down logs check readiness smoke deploy preflight env-template

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

test: ## Run all test suites (no pytest, no network)
	@ok=0; fail=0; for t in tests/test_*.py; do \
	  if $(PY) -m "tests.$$(basename $$t .py)" >/dev/null 2>&1; then ok=$$((ok+1)); \
	  else fail=$$((fail+1)); echo "FAIL: $$t"; fi; done; \
	  echo "$$ok green, $$fail failed"; [ $$fail -eq 0 ]

measure: ## Measure engine time against the budgets (deterministic, no network)
	@$(PY) -m scripts.measure_api --runs 20 --out /tmp/lv-mock.json
	@$(PY) -m scripts.perf_budget /tmp/lv-mock.json --budgets docs/landvex-budgets.json

measure-live: ## Same, WITH the live source chain — calls real public APIs
	@echo "This contacts real third-party APIs (api.scb.se and others)."
	@echo "Run it deliberately, not on every build."
	@$(PY) -m scripts.measure_api --runs 20 --live --out /tmp/lv-live.json
	@$(PY) -m scripts.perf_budget /tmp/lv-live.json --budgets docs/landvex-budgets.json

demo: ## 90-second demo against the real API (exits 1 if a step misbehaves)
	@$(PY) -m scripts.demo90

lint: ## Static gate (ruff; rules and rationale in ruff.toml)
	@ruff check . && echo "lint OK"

check: ## Compile-check engine + api
	@$(PY) -c "import compileall,sys; sys.exit(0 if compileall.compile_dir('engine',quiet=1) and compileall.compile_dir('api',quiet=1) else 1)" && echo "compile OK"

dev: ## Run the dependency-free dev server (:8000)
	LANDVEX_DB=off $(PY) -m api.dev_server

run: ## Run the production API locally via uvicorn (:8000)
	uvicorn api.main:app --host 0.0.0.0 --port 8000

build: ## Build the production Docker image
	docker build -t $(IMAGE) .

up: ## Run the app container (http on :8000, localhost)
	docker compose up --build app

prod: ## Run app + nginx TLS for landvex.com (needs .env + certs)
	docker compose --profile prod up -d --build

down: ## Stop everything
	docker compose down

logs: ## Tail app logs
	docker compose logs -f app

readiness: ## Hit every endpoint against a running server (BASE=...)
	$(PY) -m scripts.readiness_check

preflight: ## Is THIS environment ready for real traffic? (exits 1 if not)
	@$(PY) -m scripts.preflight --strict

env-template: ## Write a complete .env, generated from the registry
	@$(PY) -m scripts.preflight --template > .env.example
	@echo "Wrote .env.example — secrets left empty on purpose."

smoke: check test ## Compile + full test suite (pre-deploy gate)
	@echo "smoke OK — ready to deploy"

deploy: smoke build ## Gate (smoke) then build the image
	@echo "Built $(IMAGE). Push + 'make prod' on the host, or use your registry/CD."
