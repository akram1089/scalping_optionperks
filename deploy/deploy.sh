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
echo "Deploying ScalpDesk -> https://${DOMAIN}"

docker compose -f docker-compose.prod.yml build --pull
docker compose -f docker-compose.prod.yml up -d

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

docker compose -f docker-compose.prod.yml ps

echo ""
echo "Deployed: https://${DOMAIN}"
echo "API docs: https://${DOMAIN}/api/docs"
echo "Health:   https://${DOMAIN}/api/health"
