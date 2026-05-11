PYTHON ?= ./.venv/bin/python
UVICORN = $(PYTHON) -m uvicorn

.PHONY: install dev prod docker-dev docker-prod restart-backend

install:
	test -d .venv || python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

dev:
	APP_ENV=development $(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload

prod:
	APP_ENV=production $(UVICORN) main:app --host 0.0.0.0 --port 8000

docker-dev:
	docker compose up --build

restart-backend:
	docker compose up -d --build api

docker-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
