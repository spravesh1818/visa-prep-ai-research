#!/usr/bin/env bash
# Recover stack after docker-compose 'ContainerConfig' errors or broken nginx SSL.
# Run on the server from the project root:
#   chmod +x deploy/scripts/recover-stack.sh
#   ./deploy/scripts/recover-stack.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "Neither 'docker compose' nor 'docker-compose' found." >&2
  exit 1
fi

# shellcheck disable=SC1091
if [ -f .env ]; then
  set -a && source .env && set +a
fi

echo "=== Step 1: Stop and remove all project containers ==="
$DC --profile voice down --remove-orphans 2>/dev/null || $DC down --remove-orphans

echo "=== Step 2: Use HTTP nginx until SSL cert exists ==="
if [ -f .env ]; then
  if ! docker volume inspect visa-prep-ai-research_certbot-conf >/dev/null 2>&1 \
    || ! docker run --rm -v visa-prep-ai-research_certbot-conf:/etc/letsencrypt:ro alpine \
      test -f "/etc/letsencrypt/live/${APP_DOMAIN:-missing}/fullchain.pem" 2>/dev/null; then
    echo "No SSL cert found — using HTTP nginx template."
    sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-http.conf.template|' .env
  else
    echo "SSL cert found — using HTTPS nginx template."
    sed -i 's|^NGINX_TEMPLATE=.*|NGINX_TEMPLATE=/etc/nginx/templates/app-https.conf.template|' .env
  fi
fi

echo "=== Step 3: Start full stack ==="
$DC up -d
$DC --profile voice up -d 2>/dev/null || $DC up -d voice-agent 2>/dev/null || true

echo "=== Step 4: Status ==="
$DC ps
echo ""
curl -sf http://127.0.0.1/health && echo " — HTTP health OK" || echo "HTTP health FAILED"
echo ""
echo "If HTTP works and you still need HTTPS, run: ./deploy/scripts/init-ssl.sh"
