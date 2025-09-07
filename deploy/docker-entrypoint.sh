#!/usr/bin/env bash
set -e

MODE="all"
PORT="${PORT:-8090}"
API_PORT="${API_PORT:-8091}"

# parse options
while [[ $# -gt 0 ]]; do
  case "$1" in
    --frontend-only)
      MODE="frontend"
      shift
      ;;
    --backend-only)
      MODE="backend"
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --api-port)
      API_PORT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

export PORT API_PORT

# render nginx config with env vars
if [ -f /etc/nginx/nginx.conf.template ]; then
  envsubst '${MEDIA_ROOT} ${PORT} ${API_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
fi

start_backend() {
  /start.sh &
}

start_frontend() {
  nginx -g 'daemon off;' &
}

case "$MODE" in
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
