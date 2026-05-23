PYTHON ?= ./.venv/bin/python

DEV_ENV_FILE = config/run/config.development.env
PROD_ENV_FILE = config/run/config.production.env

.DEFAULT_GOAL := help
.PHONY: help install check-docker dev prod test

help:
	@echo "Available commands:"
	@echo "  make install # create venv and install dependencies"
	@echo "  make dev    # run development stack"
	@echo "  make prod   # run production stack"
	@echo "  make test   # run all tests with development env"

install:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

check-docker:
	@docker info >/dev/null 2>&1 || { echo "Docker daemon is not running. Start Docker Desktop, then run the command again."; exit 1; }

dev: check-docker
	set -a; . $(DEV_ENV_FILE); set +a; docker compose up --build

prod: check-docker
	set -a; . $(PROD_ENV_FILE); set +a; docker compose up --build

test: check-docker
	set -a; . $(DEV_ENV_FILE); set +a; docker compose up -d postgres redis
	set -a; . $(DEV_ENV_FILE); set +a; RUN_INTEGRATION_TESTS=1 ALLOW_INTEGRATION_DB_RESET=1 $(PYTHON) -m pytest
