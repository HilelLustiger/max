#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/env.sh

cd Agent && uv run uvicorn app.main:app --reload --port 8000
