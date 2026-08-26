#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/env.sh

uv sync
cd DB && uv run alembic upgrade head
