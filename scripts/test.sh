#!/usr/bin/env bash
# Fast gate: per-service unit tests + lint only. No Docker/Postgres needed.
# This is what the pre-commit hook runs.
set -euo pipefail
cd "$(dirname "$0")/.."

Agent/scripts/lint.sh
Agent/scripts/test.sh
DB/scripts/lint.sh
Telegram/scripts/test.sh
