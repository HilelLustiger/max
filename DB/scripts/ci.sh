#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if [ ! -f pyproject.toml ]; then
  echo "db: no workspace pyproject.toml yet, skipping"
  exit 0
fi

uv sync
uv run ruff check DB
uv run alembic -c DB/alembic.ini upgrade head
