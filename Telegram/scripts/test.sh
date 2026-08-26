#!/usr/bin/env bash
# Unit tests only: no network, no other services required.
set -euo pipefail
cd "$(dirname "$0")/.."

npm install
npm run build
npm test
