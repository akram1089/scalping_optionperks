#!/usr/bin/env bash
# Run DB migrations only (safe to run during deploy)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head
docker compose -f docker-compose.prod.yml exec -T api alembic current
