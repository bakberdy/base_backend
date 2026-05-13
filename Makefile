PYTHON ?= ./.venv/bin/python
UVICORN = $(PYTHON) -m uvicorn
ENV_FILE = config/run/config.$(ENVIRONMENT).env
COMPOSE = set -a; . $(ENV_FILE); set +a; ENVIRONMENT=$(ENVIRONMENT) docker compose

.PHONY: install run docker-up docker-build docker-restart docker-down docker-config check-environment

install:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

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
