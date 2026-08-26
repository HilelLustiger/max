#!/usr/bin/env bash
# Needs a live Postgres at DATABASE_URL with migrations applied (see
# scripts/dev-db.sh at the repo root). Boots a real Agent process itself.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv sync
uv run --package integration pytest Integration
