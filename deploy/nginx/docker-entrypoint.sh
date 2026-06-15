#!/bin/sh
set -eu

: "${APP_DOMAIN:?APP_DOMAIN is required}"

TEMPLATE="${NGINX_TEMPLATE:-/etc/nginx/templates/app-http.conf.template}"
OUTPUT="/etc/nginx/conf.d/default.conf"

if [ ! -f "$TEMPLATE" ]; then
    echo "nginx entrypoint: template not found: $TEMPLATE" >&2
    exit 1
fi

envsubst '${APP_DOMAIN}' < "$TEMPLATE" > "$OUTPUT"
echo "nginx entrypoint: rendered $TEMPLATE for domain ${APP_DOMAIN}"

# Fail fast with a clear error if TLS files are missing.
if grep -q 'ssl_certificate' "$OUTPUT"; then
  CERT="/etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem"
  KEY="/etc/letsencrypt/live/${APP_DOMAIN}/privkey.pem"
  if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "nginx entrypoint: missing TLS files:" >&2
    echo "  $CERT" >&2
    echo "  $KEY" >&2
    exit 1
  fi
fi

exec nginx -g 'daemon off;'
