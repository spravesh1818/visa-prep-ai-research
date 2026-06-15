#!/usr/bin/env bash
# First-time Let's Encrypt certificate issuance (HTTP-01 / webroot).
#
# Prerequisites:
#   1. DNS A record for APP_DOMAIN points to this server
#   2. docker-compose up -d  (nginx must be running with HTTP template)
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

# Must use HTTP template until the certificate exists.
if grep -q 'app-https.conf.template' .env 2>/dev/null; then
  echo "Reverting NGINX_TEMPLATE to HTTP (certificate not issued yet) ..."
  sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-http.conf.template|' .env
  docker rm -f visa-prep-nginx 2>/dev/null || true
  $DC up -d --no-deps nginx
fi

echo "Requesting certificate for ${APP_DOMAIN} ..."
echo "(This can take 30–90 seconds — do not press Ctrl+C)"

$DC run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d "${APP_DOMAIN}" \
  --email "${CERTBOT_EMAIL}" \
  --agree-tos \
  --no-eff-email \
  --non-interactive

# Verify cert was written to the shared volume.
if ! docker run --rm -v visa-prep-ai-research_certbot-conf:/etc/letsencrypt:ro alpine \
  test -f "/etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem"; then
  echo "Certificate not found after certbot run. Aborting HTTPS switch." >&2
  exit 1
fi

echo ""
echo "Certificate issued. Switching nginx to HTTPS template ..."

if grep -q '^NGINX_TEMPLATE=' .env 2>/dev/null; then
  sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-https.conf.template|' .env
else
  echo 'NGINX_TEMPLATE=/etc/nginx/templates/app-https.conf.template' >> .env
fi

# docker-compose 1.29 + new Docker engine: avoid 'ContainerConfig' recreate bug.
docker rm -f visa-prep-nginx 2>/dev/null || true
$DC up -d --no-deps nginx

echo ""
echo "Done. Visit https://${APP_DOMAIN}"
echo "Certbot renewal runs automatically in the certbot container."
