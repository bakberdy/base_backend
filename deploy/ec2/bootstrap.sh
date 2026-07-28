#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root (for example: sudo bash deploy/ec2/bootstrap.sh ...)." >&2
  exit 1
fi

environment="${1:?Usage: bootstrap.sh <development|production> <container-image>}"
container_image="${2:?Usage: bootstrap.sh <development|production> <container-image>}"
project_name="${PROJECT_NAME:-mobile-app-backend}"
aws_region="${AWS_REGION:?AWS_REGION is required for private ECR authentication.}"

case "${environment}" in
  development | production) ;;
  *)
    echo "Environment must be development or production." >&2
    exit 1
    ;;
esac
[[ "${project_name}" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
  echo "PROJECT_NAME may contain only lowercase letters, digits, and hyphens." >&2
  exit 1
}
[[ "${container_image}" =~ ^[A-Za-z0-9._/@:-]+$ ]] || {
  echo "Container image contains unsupported characters." >&2
  exit 1
}
[[ "${aws_region}" =~ ^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$ ]] || {
  echo "AWS_REGION must be a valid AWS region name." >&2
  exit 1
}
ecr_registry="${container_image%%/*}"
[[ "${ecr_registry}" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com(\.cn)?$ ]] || {
  echo "Container image must belong to a private Amazon ECR registry." >&2
  exit 1
}

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_directory="$(cd "${script_directory}/../.." && pwd)"
app_directory="/opt/${project_name}-${environment}"

install_docker() {
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y docker openssl cronie
    if ! command -v curl >/dev/null 2>&1; then
      dnf install -y curl-minimal
    fi
    systemctl enable --now crond
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io curl openssl cron
    systemctl enable --now cron
  else
    echo "Only Amazon Linux/RHEL-family and Ubuntu/Debian-family hosts are supported." >&2
    exit 1
  fi

  systemctl enable --now docker
}

install_compose_plugin() {
  if docker compose version >/dev/null 2>&1; then
    return
  fi

  local architecture
  case "$(uname -m)" in
    x86_64 | amd64) architecture="x86_64" ;;
    aarch64 | arm64) architecture="aarch64" ;;
    *)
      echo "Unsupported CPU architecture: $(uname -m)" >&2
      exit 1
      ;;
  esac

  install -d -m 0755 /usr/local/lib/docker/cli-plugins
  curl --fail --silent --show-error --location --retry 3 \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${architecture}" \
    --output /usr/local/lib/docker/cli-plugins/docker-compose
  chmod 0755 /usr/local/lib/docker/cli-plugins/docker-compose
  docker compose version
}

install_aws_cli() {
  if command -v aws >/dev/null 2>&1; then
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    dnf install -y awscli2 || dnf install -y awscli
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y awscli
  else
    echo "Unable to install AWS CLI on this host." >&2
    exit 1
  fi
}

upsert_env() {
  local key="$1"
  local value="$2"
  local env_file="$3"

  if grep -q "^${key}=" "${env_file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${env_file}"
  fi
}

if ! command -v docker >/dev/null 2>&1; then
  install_docker
else
  systemctl enable --now docker
fi
install_compose_plugin
install_aws_cli

aws ecr get-login-password --region "${aws_region}" |
  docker login --username AWS --password-stdin "${ecr_registry}"

install -d -m 0750 "${app_directory}/nginx"
install -m 0644 "${source_directory}/docker-compose.yml" "${app_directory}/docker-compose.yml"
install -m 0644 \
  "${source_directory}/nginx/default.conf.template" \
  "${app_directory}/nginx/default.conf.template"

env_file="${app_directory}/.env"
if [[ ! -f "${env_file}" ]]; then
  jwt_secret_key="$(openssl rand -hex 32)"
  postgres_password="$(openssl rand -hex 24)"

  if [[ "${environment}" == "development" ]]; then
    dev_otp_code="000000"
    otp_email_enabled="false"
  else
    dev_otp_code=""
    otp_email_enabled="true"
  fi

  cat >"${env_file}" <<EOF
ENVIRONMENT=${environment}
CONTAINER_IMAGE=${container_image}
DOMAIN_NAME=_
NGINX_SSL_CERTIFICATE=/etc/nginx/self-signed/fullchain.pem
NGINX_SSL_CERTIFICATE_KEY=/etc/nginx/self-signed/privkey.pem
LOG_LEVEL=INFO
CORS_ALLOWED_ORIGINS=
CORS_ALLOW_CREDENTIALS=false
POSTGRES_SCHEME=postgresql
POSTGRES_ASYNC_SCHEME=postgresql+asyncpg
POSTGRES_HOST=postgres
POSTGRES_DOCKER_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=mobile_app
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_DB=mobile_app
REDIS_SCHEME=redis
REDIS_HOST=redis
REDIS_DOCKER_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
DATABASE_CONNECT_TIMEOUT=30
JWT_SECRET_KEY=${jwt_secret_key}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
OTP_EXPIRE_SECONDS=600
OTP_MAX_ATTEMPTS=5
DEV_OTP_CODE=${dev_otp_code}
OTP_EMAIL_ENABLED=${otp_email_enabled}
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_SENDER_EMAIL=
SMTP_SENDER_NAME=Mobile App
SMTP_USE_TLS=true
SMTP_USE_SSL=false
RATE_LIMIT_LOGIN=10/minute
RATE_LIMIT_VERIFY=20/minute
APP_TITLE=Mobile app API
APP_DESCRIPTION=Localized responses support en, kk, and ru through the Accept-Language header.
HEALTH_STATUS=ok
EOF
  chmod 0600 "${env_file}"
fi

upsert_env "ENVIRONMENT" "${environment}" "${env_file}"
upsert_env "CONTAINER_IMAGE" "${container_image}" "${env_file}"

cd "${app_directory}"
docker compose pull
docker logout "${ecr_registry}" >/dev/null
docker compose up -d --remove-orphans
docker compose ps
