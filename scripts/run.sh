#!/usr/bin/env bash
# Starts the local dev stack: Postgres (+migrations), the Agent, and the
# Telegram gateway if TELEGRAM_BOT_TOKEN is set.
set -euo pipefail
cd "$(dirname "$0")/.."

scripts/dev-db.sh

Agent/scripts/run.sh &
agent_pid=$!
trap 'kill $agent_pid 2>/dev/null' EXIT

if [ -f Telegram/.env ] && grep -q '^TELEGRAM_BOT_TOKEN=.\+' Telegram/.env; then
  (cd Telegram && npm run dev)
else
  echo "Telegram/.env has no TELEGRAM_BOT_TOKEN set - running Agent only."
  echo "Agent is up at http://localhost:8000 (Ctrl+C to stop)."
  wait $agent_pid
fi
