PYTHON ?= ./.venv/bin/python
LOCAL_IMAGE ?= mobile-app-backend:local

DEV_ENV_FILE = config/run/config.development.env
PROD_ENV_FILE = config/run/config.production.env

.DEFAULT_GOAL := help
.PHONY: help install check-docker dev prod stop test

help:
	@echo "Available commands:"
	@echo "  make install # create venv and install dependencies"
	@echo "  make dev    # run development stack"
	@echo "  make prod   # run production stack"
	@echo "  make stop   # stop local stack"
	@echo "  make test   # run all tests with development env"

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

stop: check-docker
	set -a; . $(DEV_ENV_FILE); set +a; APP_ENV_FILE=$(DEV_ENV_FILE) CONTAINER_IMAGE=$(LOCAL_IMAGE) NGINX_HTTP_PORT=8080 NGINX_HTTPS_PORT=8443 docker compose down --remove-orphans

test: check-docker
	set -a; . $(DEV_ENV_FILE); set +a; APP_ENV_FILE=$(DEV_ENV_FILE) docker compose up -d postgres redis
	set -a; . $(DEV_ENV_FILE); set +a; RUN_INTEGRATION_TESTS=1 ALLOW_INTEGRATION_DB_RESET=1 $(PYTHON) -m pytest
