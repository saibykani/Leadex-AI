#!/usr/bin/env bash
# Dump the postgres container database into ./backups/<db>_<timestamp>.sql
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DB_USER="${POSTGRES_USER:-$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || true)}"
DB_NAME="${POSTGRES_DB:-$(grep -E '^POSTGRES_DB=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || true)}"
DB_USER="${DB_USER:-leadex}"
DB_NAME="${DB_NAME:-leadex}"
mkdir -p backups
OUT="backups/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
docker compose exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner > "$OUT"
echo "Backup written to $OUT"
