#!/usr/bin/env bash
# Full gate: brings up Postgres, then runs per-service integration tests plus
# the cross-service integration suite. This is what the pre-push hook runs.
set -euo pipefail
cd "$(dirname "$0")/.."

scripts/dev-db.sh

DB/scripts/test.sh
Agent/scripts/test-integration.sh
Integration/scripts/test.sh
