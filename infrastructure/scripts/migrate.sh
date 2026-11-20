#!/usr/bin/env bash
# Apply all Alembic migrations (uses MIGRATION_DATABASE_URL (schema owner) from the environment / .env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/apps/api"
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -f .venv/Scripts/activate ]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
fi
alembic upgrade head
