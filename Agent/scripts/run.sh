#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

uv run --package agent uvicorn app.main:app --app-dir Agent --reload --port 8000
