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
HTTP_PORT="${HTTP_PORT:-28780}"
HTTPS_PORT="${HTTPS_PORT:-28743}"
WEB_HOST_PORT="${WEB_HOST_PORT:-28790}"

check_port() {
  local port=$1
  local label=$2
  if ss -tln 2>/dev/null | grep -q ":${port} "; then
    echo "ERROR: ${label} port ${port} is already in use. Pick another in .env"
    echo "  ss -tlnp | grep ${port}"
    exit 1
  fi
}

# Skip port checks when this stack is already running (redeploy / git pull update).
stack_running() {
  docker compose -f docker-compose.prod.yml ps --status running -q 2>/dev/null | grep -q .
}

if ! stack_running; then
  if [[ "${CADDY_ENABLED}" == "true" || "${CADDY_ENABLED}" == "1" ]]; then
    check_port "${HTTP_PORT}" "HTTP_PORT"
    check_port "${HTTPS_PORT}" "HTTPS_PORT"
  else
    check_port "${WEB_HOST_PORT}" "WEB_HOST_PORT"
  fi
else
  echo "Stack already running — skipping host port checks (update redeploy)."
fi

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
