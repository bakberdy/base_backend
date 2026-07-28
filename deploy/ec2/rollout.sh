#!/usr/bin/env bash
set -euo pipefail

mode="${1:?Usage: rollout.sh <deploy|rollback> <development|production> <image-reference>}"
environment="${2:?Usage: rollout.sh <deploy|rollback> <development|production> <image-reference>}"
image_reference="${3:?Usage: rollout.sh <deploy|rollback> <development|production> <image-reference>}"
project_name="${PROJECT_NAME:-mobile-app-backend}"
target_repository="${image_reference%@*}"

case "${mode}" in
  deploy | rollback) ;;
  *)
    echo "Mode must be deploy or rollback." >&2
    exit 1
    ;;
esac
case "${environment}" in
  development | production) ;;
  *)
    echo "Environment must be development or production." >&2
    exit 1
    ;;
esac
[[ "${image_reference}" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com(\.cn)?/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || {
  echo "Image reference must be an exact private ECR repository@sha256 digest." >&2
  exit 1
}

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_base_directory="${APP_BASE_DIRECTORY:-/opt}"
app_directory="${app_base_directory}/${project_name}-${environment}"
state_directory="${app_directory}/.deployment"
current_file="${state_directory}/current-image"
previous_file="${state_directory}/previous-image"
bootstrap_script="${ROLLOUT_BOOTSTRAP_SCRIPT:-${script_directory}/bootstrap.sh}"

internal_health() {
  if [[ -n "${ROLLOUT_HEALTH_PROBE:-}" ]]; then
    "${ROLLOUT_HEALTH_PROBE}" "${app_directory}"
    return
  fi
  cd "${app_directory}"
  for _ in $(seq 1 30); do
    if docker compose exec -T app python -c \
      "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)"; then
      return 0
    fi
    sleep 2
  done
  docker compose logs --tail=100 app
  return 1
}

bootstrap() {
  AWS_REGION="${AWS_REGION}" PROJECT_NAME="${project_name}" \
    bash "${bootstrap_script}" "${environment}" "$1"
}

install -d -m 0750 "${state_directory}"
previous_image=""
if [[ -f "${current_file}" ]]; then
  previous_image="$(<"${current_file}")"
elif [[ -f "${app_directory}/docker-compose.yml" ]]; then
  container_id="$(cd "${app_directory}" && docker compose ps -q app 2>/dev/null || true)"
  if [[ -n "${container_id}" ]]; then
    image_id="$(docker inspect --format '{{.Image}}' "${container_id}" 2>/dev/null || true)"
    previous_image="$(
      docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' \
        "${image_id}" 2>/dev/null |
        grep -F "${target_repository}@sha256:" |
        head -1 ||
        true
    )"
  fi
fi

if [[ "${mode}" == "deploy" ]]; then
  printf '%s\n' "${previous_image}" >"${previous_file}"
  echo "PREVIOUS_IMAGE=${previous_image}"
  if bootstrap "${image_reference}" && internal_health; then
    printf '%s\n' "${image_reference}" >"${current_file}"
    echo "DEPLOYMENT_STATUS=success"
    exit 0
  fi

  echo "Deployment health failed; starting automatic rollback." >&2
  if [[ "${previous_image}" =~ @sha256:[0-9a-f]{64}$ ]] &&
    bootstrap "${previous_image}" &&
    internal_health; then
    printf '%s\n' "${previous_image}" >"${current_file}"
    echo "DEPLOYMENT_STATUS=rolled_back"
  else
    echo "DEPLOYMENT_STATUS=rollback_failed"
  fi
  exit 1
fi

bootstrap "${image_reference}"
internal_health
printf '%s\n' "${image_reference}" >"${current_file}"
echo "DEPLOYMENT_STATUS=rolled_back"
