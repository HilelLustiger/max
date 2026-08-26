#!/usr/bin/env bash
# Needs a live Postgres at DATABASE_URL (see scripts/dev-db.sh at the repo root) with
# migrations applied. Run before pushing, not on every commit.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/env.sh

uv sync
uv run pytest Agent -m integration
