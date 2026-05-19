PYTHON ?= ./.venv/bin/python

DEV_ENV_FILE = config/run/config.development.env
PROD_ENV_FILE = config/run/config.production.env

.DEFAULT_GOAL := help
.PHONY: help install dev prod test

help:
	@echo "Available commands:"
	@echo "  make install # create venv and install dependencies"
	@echo "  make dev    # run development stack"
	@echo "  make prod   # run production stack"
	@echo "  make test   # run all tests with development env"

install:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

dev:
	set -a; . $(DEV_ENV_FILE); set +a; ENVIRONMENT=development docker compose up --build

prod:
	set -a; . $(PROD_ENV_FILE); set +a; ENVIRONMENT=production docker compose up --build

test:
	set -a; . $(DEV_ENV_FILE); set +a; ENVIRONMENT=development docker compose up -d postgres redis
	set -a; . $(DEV_ENV_FILE); set +a; ENVIRONMENT=development RUN_INTEGRATION_TESTS=1 ALLOW_INTEGRATION_DB_RESET=1 DEV_OTP_CODE=111111 OTP_EMAIL_ENABLED=false $(PYTHON) -m pytest
