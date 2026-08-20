#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "agent-core: no pyproject.toml yet, skipping"
  exit 0
fi

pip install -e ".[dev]"
ruff check .
pytest
