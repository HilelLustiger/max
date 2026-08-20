#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f package.json ]; then
  echo "telegram-gateway: no package.json yet, skipping"
  exit 0
fi

npm ci
npm run lint --if-present
npm test --if-present
npm run build --if-present
