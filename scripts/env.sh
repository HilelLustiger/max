#!/usr/bin/env bash
# Sourced by other scripts (from repo root) to load local dev env vars from
# .env - the single source of truth, not duplicated as literals in scripts.
set -a
[ -f .env ] && source .env
set +a

: "${DATABASE_URL:?DATABASE_URL not set - copy .env.example to .env at the repo root}"
