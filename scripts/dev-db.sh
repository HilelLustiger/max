#!/usr/bin/env bash
# Brings up local Postgres and applies migrations. Used by both scripts/run.sh
# and scripts/test-integration.sh so they share one source of truth for the
# local DATABASE_URL.
set -euo pipefail
cd "$(dirname "$0")/.."

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://max:max@localhost:5432/max}"

docker compose up -d postgres

echo "waiting for postgres..."
for _ in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U max >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

DB/scripts/migrate.sh
