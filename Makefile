PYTHON ?= ./.venv/bin/python
UVICORN = $(PYTHON) -m uvicorn
ENV_FILE = config/run/config.$(ENVIRONMENT).env
COMPOSE = set -a; . $(ENV_FILE); set +a; ENVIRONMENT=$(ENVIRONMENT) docker compose

.DEFAULT_GOAL := help

.PHONY: help install test test-unit test-integration run i18n-extract i18n-compile postgres-up docker-up docker-build docker-restart docker-down docker-config check-environment
.PHONY: docker-dev docker-dev-down docker-dev-build docker-dev-restart docker-dev-config
.PHONY: dev-db-up dev-run dev-docker-up dev-docker-down dev-docker-build dev-docker-restart dev-docker-config
.PHONY: prod-docker-build prod-docker-up prod-docker-down prod-docker-restart prod-docker-config

help:
	@echo "mobile_app_backend — Postgres + FastAPI"
	@echo ""
	@echo "=== Development (ENVIRONMENT=development) ==="
	@echo ""
	@echo "  Local uvicorn + Postgres in Docker:"
	@echo "    make install                         # once: venv + pip deps"
	@echo "    make dev-db-up                       # docker compose up -d postgres"
	@echo "    make dev-run                         # uvicorn with --reload"
	@echo ""
	@echo "  Or explicit:"
	@echo "    ENVIRONMENT=development make postgres-up"
	@echo "    ENVIRONMENT=development make run"
	@echo ""
	@echo "  Full stack in Docker (api + postgres):"
	@echo "    make docker-dev                     # alias for make dev-docker-up"
	@echo "    make dev-docker-up"
	@echo "    make dev-docker-down                 # stop stack"
	@echo ""
	@echo "  Or explicit:"
	@echo "    ENVIRONMENT=development make docker-up"
	@echo "    ENVIRONMENT=development make docker-down"
	@echo ""
	@echo "=== Production (ENVIRONMENT=production) ==="
	@echo ""
	@echo "  Edit config/run/config.production.env first, then:"
	@echo "    make prod-docker-build"
	@echo "    make prod-docker-up"
	@echo "    make prod-docker-down"
	@echo ""
	@echo "  Or explicit:"
	@echo "    ENVIRONMENT=production make docker-build"
	@echo "    ENVIRONMENT=production make docker-up"
	@echo "    ENVIRONMENT=production make docker-down"
	@echo ""
	@echo "=== Other ==="
	@echo "    make test                            # run all tests"
	@echo "    make test-unit                       # run unit tests"
	@echo "    make test-integration                # run real DB integration tests"
	@echo "    make docker-config                   # resolved compose YAML (needs ENVIRONMENT)"
	@echo "    make i18n-extract                    # update app/locales/messages.pot"
	@echo "    make i18n-compile                    # compile app/locales/*/messages.po"

install:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

test:
	RUN_INTEGRATION_TESTS=1 ALLOW_INTEGRATION_DB_RESET=1 $(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/auth tests/users -m "not integration" -q

test-integration:
	RUN_INTEGRATION_TESTS=1 ALLOW_INTEGRATION_DB_RESET=1 $(PYTHON) -m pytest tests -m integration -q

i18n-extract:
	.venv/bin/pybabel extract -F babel.cfg --keywords=api_http_exception:2 -o app/locales/messages.pot app

i18n-compile:
	.venv/bin/pybabel compile -d app/locales -D messages

check-environment:
	@if [ -z "$(ENVIRONMENT)" ]; then \
		echo "Set ENVIRONMENT=development or ENVIRONMENT=production"; \
		exit 1; \
	fi
	@if [ "$(ENVIRONMENT)" != "development" ] && [ "$(ENVIRONMENT)" != "production" ]; then \
		echo "ENVIRONMENT must be development or production, got '$(ENVIRONMENT)'"; \
		exit 1; \
	fi
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "Missing $(ENV_FILE)"; \
		exit 1; \
	fi

run: check-environment
	ENVIRONMENT=$(ENVIRONMENT) $(UVICORN) main:app --host 0.0.0.0 --port 8000 $(if $(filter development,$(ENVIRONMENT)),--reload,)

postgres-up: check-environment
	$(COMPOSE) up -d postgres

docker-up: check-environment
	$(COMPOSE) up --build

docker-build: check-environment
	$(COMPOSE) build

docker-restart: check-environment
	$(COMPOSE) up -d --build api

docker-down: check-environment
	$(COMPOSE) down

docker-config: check-environment
	$(COMPOSE) config

# --- Development shortcuts (ENVIRONMENT=development) ---

docker-dev:
	@$(MAKE) docker-up ENVIRONMENT=development

docker-dev-down:
	@$(MAKE) docker-down ENVIRONMENT=development

docker-dev-build:
	@$(MAKE) docker-build ENVIRONMENT=development

docker-dev-restart:
	@$(MAKE) docker-restart ENVIRONMENT=development

docker-dev-config:
	@$(MAKE) docker-config ENVIRONMENT=development

dev-db-up:
	@$(MAKE) postgres-up ENVIRONMENT=development

dev-run:
	@$(MAKE) run ENVIRONMENT=development

dev-docker-up:
	@$(MAKE) docker-up ENVIRONMENT=development

dev-docker-down:
	@$(MAKE) docker-down ENVIRONMENT=development

dev-docker-build:
	@$(MAKE) docker-build ENVIRONMENT=development

dev-docker-restart:
	@$(MAKE) docker-restart ENVIRONMENT=development

dev-docker-config:
	@$(MAKE) docker-config ENVIRONMENT=development

# --- Production shortcuts (ENVIRONMENT=production) ---

prod-docker-build:
	@$(MAKE) docker-build ENVIRONMENT=production

prod-docker-up:
	@$(MAKE) docker-up ENVIRONMENT=production

prod-docker-down:
	@$(MAKE) docker-down ENVIRONMENT=production

prod-docker-restart:
	@$(MAKE) docker-restart ENVIRONMENT=production

prod-docker-config:
	@$(MAKE) docker-config ENVIRONMENT=production
