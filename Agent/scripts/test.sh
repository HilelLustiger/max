#!/usr/bin/env bash
# Unit tests only: no Postgres required. Safe to run on every commit.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv sync
uv run pytest Agent -m "not integration"
