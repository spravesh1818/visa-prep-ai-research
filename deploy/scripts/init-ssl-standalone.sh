#!/usr/bin/env bash
# Let's Encrypt via standalone mode (most reliable on docker-compose v1).
# Briefly stops nginx so certbot can bind port 80 itself.
#
# Usage:
#   chmod +x deploy/scripts/init-ssl-standalone.sh
#   ./deploy/scripts/init-ssl-standalone.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing .env" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a && source .env && set +a

: "${APP_DOMAIN:?Set APP_DOMAIN in .env}"
: "${CERTBOT_EMAIL:?Set CERTBOT_EMAIL in .env}"

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "Neither 'docker compose' nor 'docker-compose' found." >&2
  exit 1
fi

CONF_VOL="${COMPOSE_PROJECT_NAME:-visa-prep-ai-research}_certbot-conf"
WWW_VOL="${COMPOSE_PROJECT_NAME:-visa-prep-ai-research}_certbot-www"

echo "=== Stopping nginx (frees port 80 for certbot) ==="
docker stop visa-prep-nginx 2>/dev/null || $DC stop nginx 2>/dev/null || true

echo "=== Requesting certificate (standalone mode, verbose) ==="
docker run --rm -p 80:80 \
  -v "${CONF_VOL}:/etc/letsencrypt" \
  -v "${WWW_VOL}:/var/www/certbot" \
  certbot/certbot certonly \
  --standalone \
  --preferred-challenges http \
  -d "${APP_DOMAIN}" \
  --email "${CERTBOT_EMAIL}" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  -v

if ! docker run --rm -v "${CONF_VOL}:/etc/letsencrypt:ro" alpine \
  test -f "/etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem"; then
  echo "Certificate not found. Starting nginx again on HTTP." >&2
  sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-http.conf.template|' .env
  docker rm -f visa-prep-nginx 2>/dev/null || true
  $DC up -d --no-deps nginx
  exit 1
fi

echo "=== Certificate OK. Enabling HTTPS nginx ==="
sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-https.conf.template|' .env
docker rm -f visa-prep-nginx 2>/dev/null || true
$DC up -d --no-deps nginx

echo ""
echo "Done. Visit https://${APP_DOMAIN}"
