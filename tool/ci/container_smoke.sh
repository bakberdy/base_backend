#!/usr/bin/env bash

set -euo pipefail

readonly image="${1:-mobile-app-backend:local}"
readonly project_name="${CONTAINER_SMOKE_PROJECT:-backend-container-smoke}"
readonly app_port="${CONTAINER_SMOKE_APP_PORT:-58000}"

cleanup() {
  docker compose \
    --project-name "${project_name}" \
    down \
    --volumes \
    --remove-orphans \
    >/dev/null 2>&1 || true
}

trap cleanup EXIT

export ENVIRONMENT=test
export APP_ENV_FILE=config/run/config.example.env
export CONTAINER_IMAGE="${image}"
export POSTGRES_SCHEME=postgresql
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_DB=mobile_app_test
export POSTGRES_DOCKER_HOST=postgres
export POSTGRES_PORT=5432
export POSTGRES_HOST_PORT="${CONTAINER_SMOKE_POSTGRES_PORT:-55432}"
export REDIS_SCHEME=redis
export REDIS_DOCKER_HOST=redis
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_HOST_PORT="${CONTAINER_SMOKE_REDIS_PORT:-56379}"
export APP_PORT="${app_port}"

docker compose \
  --project-name "${project_name}" \
  up \
  --detach \
  postgres \
  redis \
  app

for _ in $(seq 1 60); do
  if curl \
    --fail \
    --silent \
    --show-error \
    "http://127.0.0.1:${app_port}/health"; then
    exit 0
  fi
  sleep 2
done

docker compose \
  --project-name "${project_name}" \
  logs \
  --tail=100 \
  app

exit 1
