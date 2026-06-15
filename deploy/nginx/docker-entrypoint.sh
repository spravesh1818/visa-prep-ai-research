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

exec nginx -g 'daemon off;'
