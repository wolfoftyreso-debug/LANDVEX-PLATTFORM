# LANDVEX Opportunity Engine — build, test, run, deploy.
.DEFAULT_GOAL := help
PY ?= python3
IMAGE ?= landvex/opportunity-engine:1.1.0

.PHONY: help test lint run dev build up prod down logs check readiness smoke deploy

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

test: ## Run all test suites (no pytest, no network)
	@ok=0; fail=0; for t in tests/test_*.py; do \
	  if $(PY) -m "tests.$$(basename $$t .py)" >/dev/null 2>&1; then ok=$$((ok+1)); \
	  else fail=$$((fail+1)); echo "FAIL: $$t"; fi; done; \
	  echo "$$ok green, $$fail failed"; [ $$fail -eq 0 ]

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

smoke: check test ## Compile + full test suite (pre-deploy gate)
	@echo "smoke OK — ready to deploy"

deploy: smoke build ## Gate (smoke) then build the image
	@echo "Built $(IMAGE). Push + 'make prod' on the host, or use your registry/CD."
