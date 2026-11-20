#!/usr/bin/env bash
# Restore a plain SQL dump (from backup.sh / backup.ps1) into the postgres container.
# Usage: infrastructure/scripts/restore.sh backups/leadex_YYYYmmdd_HHMMSS.sql [--yes]
set -euo pipefail
if [ $# -lt 1 ] || [ ! -f "$1" ]; then
  echo "Usage: $0 <dump.sql> [--yes]" >&2
  exit 1
fi
DUMP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DB_USER="${POSTGRES_USER:-leadex}"
DB_NAME="${POSTGRES_DB:-leadex}"
if [ "${2:-}" != "--yes" ]; then
  read -r -p "This overwrites database '$DB_NAME'. Continue? [y/N] " ans
  case "$ans" in y|Y) ;; *) echo "Aborted"; exit 1 ;; esac
fi
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$DUMP"
echo "Restore complete."
