#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

environment="${1:?Usage: enable_https.sh <development|production> <domain> <email>}"
domain="${2:?Usage: enable_https.sh <development|production> <domain> <email>}"
email="${3:?Usage: enable_https.sh <development|production> <domain> <email>}"
project_name="${PROJECT_NAME:-mobile-app-backend}"
app_directory="/opt/${project_name}-${environment}"
env_file="${app_directory}/.env"

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
[[ "${domain}" =~ ^[A-Za-z0-9.-]+$ ]] || {
  echo "Domain contains unsupported characters." >&2
  exit 1
}
[[ "${email}" =~ ^[^[:space:]@]+@[^[:space:]@]+$ ]] || {
  echo "Email is invalid." >&2
  exit 1
}

if [[ ! -f "${env_file}" ]]; then
  echo "Missing ${env_file}. Deploy the application first." >&2
  exit 1
fi

upsert_env() {
  local key="$1"
  local value="$2"

  if grep -q "^${key}=" "${env_file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${env_file}"
  fi
}

cd "${app_directory}"
upsert_env "DOMAIN_NAME" "${domain}"
docker compose up -d --force-recreate nginx

docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --domain "${domain}" \
  --email "${email}" \
  --agree-tos \
  --non-interactive

upsert_env "NGINX_SSL_CERTIFICATE" "/etc/letsencrypt/live/${domain}/fullchain.pem"
upsert_env "NGINX_SSL_CERTIFICATE_KEY" "/etc/letsencrypt/live/${domain}/privkey.pem"
docker compose up -d --force-recreate nginx

cat >"/etc/cron.d/${project_name}-${environment}-certbot" <<EOF
17 3 * * * root cd ${app_directory} && /usr/bin/docker compose run --rm certbot renew --quiet && /usr/bin/docker compose exec -T nginx nginx -s reload
EOF
chmod 0644 "/etc/cron.d/${project_name}-${environment}-certbot"

curl --fail --silent --show-error "https://${domain}/health"
