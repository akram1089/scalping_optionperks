#!/usr/bin/env bash
# Deploy or update ScalpDesk on VPS
# Usage: bash deploy/deploy.sh [--first-run]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FIRST_RUN=false
if [[ "${1:-}" == "--first-run" ]]; then
  FIRST_RUN=true
fi

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.production.example to .env and set secrets."
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

if [[ -z "${SECRET_KEY:-}" || "${SECRET_KEY}" == "change-me"* ]]; then
  echo "Set a strong SECRET_KEY in .env"
  exit 1
fi

if [[ -z "${ENCRYPTION_KEY:-}" ]]; then
  echo "Set ENCRYPTION_KEY in .env (Fernet key)"
  exit 1
fi

DOMAIN="${DOMAIN:-scalping.optionperks.com}"
CADDY_ENABLED="${CADDY_ENABLED:-false}"
HTTP_PORT="${HTTP_PORT:-8088}"
HTTPS_PORT="${HTTPS_PORT:-8448}"
WEB_HOST_PORT="${WEB_HOST_PORT:-8090}"

COMPOSE_FILE="-f docker-compose.prod.yml"
COMPOSE_PROFILES=""
if [[ "${CADDY_ENABLED}" == "true" || "${CADDY_ENABLED}" == "1" ]]; then
  COMPOSE_PROFILES="--profile caddy"
  echo "Deploying ScalpDesk with Caddy on ports ${HTTP_PORT}/${HTTPS_PORT} -> https://${DOMAIN}:${HTTPS_PORT}"
else
  echo "Deploying ScalpDesk (host proxy mode) -> web on 127.0.0.1:${WEB_HOST_PORT}"
  echo "Point your host nginx/caddy at 127.0.0.1:${WEB_HOST_PORT} for https://${DOMAIN}"
fi

docker compose ${COMPOSE_FILE} ${COMPOSE_PROFILES} build --pull
docker compose ${COMPOSE_FILE} ${COMPOSE_PROFILES} up -d

echo "Waiting for API health..."
for i in $(seq 1 30); do
  if docker compose -f docker-compose.prod.yml exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "Migration status:"
docker compose -f docker-compose.prod.yml exec -T api alembic current

if $FIRST_RUN; then
  echo "First run — seeding demo user and syncing instruments..."
  docker compose -f docker-compose.prod.yml exec -T api python scripts/seed.py || true
  docker compose -f docker-compose.prod.yml exec -T api python scripts/sync_instruments.py || true
fi

docker compose ${COMPOSE_FILE} ${COMPOSE_PROFILES} ps

echo ""
if [[ "${CADDY_ENABLED}" == "true" || "${CADDY_ENABLED}" == "1" ]]; then
  echo "App:      https://${DOMAIN}:${HTTPS_PORT}"
  echo "API docs: https://${DOMAIN}:${HTTPS_PORT}/api/docs"
  echo "Health:   https://${DOMAIN}:${HTTPS_PORT}/api/health"
else
  echo "Web (internal): http://127.0.0.1:${WEB_HOST_PORT}"
  echo "Public URL (after host proxy): https://${DOMAIN}"
  echo "API docs: https://${DOMAIN}/api/docs"
  echo "Health:   https://${DOMAIN}/api/health"
fi
