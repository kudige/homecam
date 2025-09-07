#!/usr/bin/env bash
set -e

# render nginx config with MEDIA_ROOT
if [ -f /etc/nginx/nginx.conf.template ]; then
  envsubst '${MEDIA_ROOT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
fi

SERVICE_MODE="${SERVICE:-all}"

start_backend() {
  /start.sh &
}

start_frontend() {
  nginx -g 'daemon off;' &
}

case "$SERVICE_MODE" in
  backend)
    exec /start.sh
    ;;
  frontend)
    exec nginx -g 'daemon off;'
    ;;
  *)
    start_backend
    start_frontend
    wait -n
    ;;
esac
