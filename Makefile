PYTHON ?= ./.venv/bin/python
LOCAL_IMAGE ?= mobile-app-backend:local

DEV_ENV_FILE = config/run/config.development.env
PROD_ENV_FILE = config/run/config.production.env

.DEFAULT_GOAL := help
.PHONY: help install check-docker dev prod run stop format format-check lint type-check test-unit test test-all validate

help:
	@echo "Available commands:"
	@echo "  make install # create venv and install dependencies"
	@echo "  make dev    # run development stack"
	@echo "  make prod   # run production stack"
	@echo "  make run    # run Uvicorn locally with reload"
	@echo "  make stop   # stop local stack"
	@echo "  make format # format Python sources"
	@echo "  make validate # run format, lint, mypy, and unit-test checks"
	@echo "  make test-all # run all tests with PostgreSQL and Redis"

install:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

check-docker:
	@docker info >/dev/null 2>&1 || { echo "Docker daemon is not running. Start Docker Desktop, then run the command again."; exit 1; }

dev: check-docker
	docker build -t $(LOCAL_IMAGE) .
	set -a; . $(DEV_ENV_FILE); set +a; APP_ENV_FILE=$(DEV_ENV_FILE) CONTAINER_IMAGE=$(LOCAL_IMAGE) NGINX_HTTP_PORT=8080 NGINX_HTTPS_PORT=8443 docker compose up -d

prod: check-docker
	docker build -t $(LOCAL_IMAGE) .
	set -a; . $(PROD_ENV_FILE); set +a; APP_ENV_FILE=$(PROD_ENV_FILE) CONTAINER_IMAGE=$(LOCAL_IMAGE) docker compose up -d

run:
	set -a; . $(DEV_ENV_FILE); set +a; $(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

stop: check-docker
	set -a; . $(DEV_ENV_FILE); set +a; APP_ENV_FILE=$(DEV_ENV_FILE) CONTAINER_IMAGE=$(LOCAL_IMAGE) NGINX_HTTP_PORT=8080 NGINX_HTTPS_PORT=8443 docker compose down --remove-orphans

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

lint:
	$(PYTHON) -m ruff check .

type-check:
	ENVIRONMENT=test $(PYTHON) -m mypy

test-unit:
	ENVIRONMENT=test $(PYTHON) -m pytest -m "not integration"

test: test-unit

test-all: check-docker
	set -a; . config/run/config.test.env; set +a; APP_ENV_FILE=config/run/config.test.env docker compose up -d postgres redis
	set -a; . config/run/config.test.env; set +a; APP_ENV_FILE=config/run/config.test.env docker compose exec -T postgres sh -c 'psql -U "$$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '\''$$POSTGRES_DB'\''" | grep -q 1 || createdb -U "$$POSTGRES_USER" "$$POSTGRES_DB"'
	set -a; . config/run/config.test.env; set +a; RUN_INTEGRATION_TESTS=1 $(PYTHON) -m pytest

validate: format-check lint type-check test-unit
