#!/usr/bin/env bash
# First-time Let's Encrypt certificate issuance (HTTP-01 / webroot).
#
# Prerequisites:
#   1. DNS A record for APP_DOMAIN points to this server
#   2. docker compose up -d  (nginx must be running with HTTP template)
#   3. .env contains APP_DOMAIN and CERTBOT_EMAIL
#
# Usage:
#   chmod +x deploy/scripts/init-ssl.sh
#   ./deploy/scripts/init-ssl.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.production.example to .env first." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a && source .env && set +a

: "${APP_DOMAIN:?Set APP_DOMAIN in .env}"
: "${CERTBOT_EMAIL:?Set CERTBOT_EMAIL in .env}"

# Pick docker-compose v1 or compose v2 plugin.
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "Neither 'docker compose' nor 'docker-compose' found." >&2
  exit 1
fi

echo "Requesting certificate for ${APP_DOMAIN} ..."

$DC run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d "${APP_DOMAIN}" \
  --email "${CERTBOT_EMAIL}" \
  --agree-tos \
  --no-eff-email \
  --non-interactive

echo ""
echo "Certificate issued. Switching nginx to HTTPS template ..."

# Update .env to use HTTPS template (idempotent)
if grep -q '^NGINX_TEMPLATE=' .env 2>/dev/null; then
  sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-https.conf.template|' .env
else
  echo 'NGINX_TEMPLATE=/etc/nginx/templates/app-https.conf.template' >> .env
fi

$DC up -d nginx

echo ""
echo "Done. Visit https://${APP_DOMAIN}"
echo "Certbot renewal runs automatically in the certbot container."
