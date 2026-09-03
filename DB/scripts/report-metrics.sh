#!/usr/bin/env bash
# Needs a live Postgres at DATABASE_URL (see scripts/dev-db.sh at the repo root).
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/env.sh

uv sync
uv run python DB/scripts/report_metrics.py "$@"
