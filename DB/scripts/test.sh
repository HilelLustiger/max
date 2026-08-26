#!/usr/bin/env bash
# All DB tests need a live Postgres at DATABASE_URL with migrations applied
# (see scripts/dev-db.sh at the repo root). Run before pushing, not on every commit.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/env.sh

uv sync
uv run pytest DB
