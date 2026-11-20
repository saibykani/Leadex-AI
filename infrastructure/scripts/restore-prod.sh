#!/usr/bin/env bash
# PRODUCTION restore of a pg-backup.sh custom-format dump over the live database. DESTRUCTIVE.
# Stops app services (api/web and worker/beat if defined), restores, re-applies the leadex_app password, restarts.
# Practise with restore-drill.sh first.
# Usage: infrastructure/scripts/restore-prod.sh backups/leadex_YYYYmmddTHHMMSSZ.dump [--yes]
set -euo pipefail
if [ $# -lt 1 ] || [ ! -f "$1" ]; then
  echo "Usage: $0 <file.dump> [--yes]" >&2
  exit 1
fi
DUMP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env.production}"
DC=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml)
if [ "${2:-}" != "--yes" ]; then
  read -r -p "This OVERWRITES the production database. Type 'restore' to continue: " ans
  [ "$ans" = "restore" ] || { echo "Aborted"; exit 1; }
fi

APP_SERVICES=$("${DC[@]}" config --services | grep -E '^(api|web|worker|beat)$' | tr '\n' ' ')
# shellcheck disable=SC2086
"${DC[@]}" stop $APP_SERVICES

TS="$(basename "$DUMP" .dump)"; TS="${TS##*_}"
GLOBALS="$(dirname "$DUMP")/globals_${TS}.sql"
if [ -f "$GLOBALS" ]; then
  echo "Applying roles from $GLOBALS (\"already exists\" errors are expected and harmless)"
  "${DC[@]}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres' < "$GLOBALS" || true
fi

"${DC[@]}" exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' < "$DUMP"

# Role passwords are not in the dump: set the runtime role password from the env file.
APP_DB_PASSWORD="$(grep -E '^APP_DB_PASSWORD=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
printf "ALTER ROLE leadex_app WITH LOGIN PASSWORD '%s';\n" "${APP_DB_PASSWORD//\'/\'\'}" \
  | "${DC[@]}" exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# shellcheck disable=SC2086
"${DC[@]}" up -d $APP_SERVICES
echo "Restore complete. Verify: curl -fsS https://<DOMAIN>/health/ready"
