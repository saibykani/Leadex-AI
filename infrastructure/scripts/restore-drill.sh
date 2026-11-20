#!/usr/bin/env bash
# Restore drill: restores the newest (or given) backup into a SCRATCH database, runs sanity checks, drops it.
# Never touches the live database. Run monthly and record the timing (docs/deployment/DISASTER_RECOVERY.md).
# Usage: infrastructure/scripts/restore-drill.sh [backups/leadex_YYYYmmddTHHMMSSZ.dump]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DC=(docker compose --env-file "${ENV_FILE:-.env.production}" -f docker-compose.yml -f docker-compose.prod.yml)
BACKUP_DIR="${BACKUP_HOST_DIR:-./backups}"
DUMP="${1:-$(ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | head -n1 || true)}"
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "No dump found (looked in $BACKUP_DIR)" >&2
  exit 1
fi
DRILL_DB="leadex_restore_drill"
START=$(date +%s)
echo "Drill: restoring $DUMP into $DRILL_DB"

SUMS="${DUMP%.dump}.sha256"
if [ -f "$SUMS" ]; then
  (cd "$(dirname "$DUMP")" && grep -F "$(basename "$DUMP")" "$(basename "$SUMS")" | sha256sum -c -)
else
  echo "WARN: no checksum file $SUMS"
fi

owner_psql() {
  # $1 = database; SQL on stdin
  "${DC[@]}" exec -T postgres sh -c "psql -v ON_ERROR_STOP=1 -At -U \"\$POSTGRES_USER\" -d $1"
}

echo "DROP DATABASE IF EXISTS $DRILL_DB; CREATE DATABASE $DRILL_DB;" | owner_psql postgres
"${DC[@]}" exec -T postgres sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $DRILL_DB --no-owner --exit-on-error" < "$DUMP"

echo "Sanity checks:"
owner_psql "$DRILL_DB" <<'SQL'
SELECT 'alembic_version=' || version_num FROM alembic_version;
SELECT 'public_tables=' || count(*) FROM information_schema.tables WHERE table_schema = 'public';
SELECT 'rls_enabled_tables=' || count(*) FROM pg_class WHERE relrowsecurity;
SELECT 'organizations=' || count(*) FROM organizations;
SELECT 'users=' || count(*) FROM users;
SQL

echo "DROP DATABASE $DRILL_DB;" | owner_psql postgres
echo "Drill OK in $(( $(date +%s) - START ))s - record this as the measured restore time."
