#!/bin/sh
# Nightly Postgres backup. Runs inside the `backup` service of docker-compose.prod.yml (cron), or manually:
#   docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml exec backup sh /usr/local/bin/pg-backup.sh
# Env: PGHOST PGUSER PGPASSWORD PGDATABASE BACKUP_DIR BACKUP_RETENTION_DAYS
# Optional S3-compatible upload: BACKUP_S3_BUCKET BACKUP_S3_ENDPOINT BACKUP_S3_PREFIX AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
set -eu
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-14}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
DB="${PGDATABASE:?PGDATABASE required}"
mkdir -p "$BACKUP_DIR"
umask 077

DUMP="$BACKUP_DIR/${DB}_${TS}.dump"
GLOBALS="$BACKUP_DIR/globals_${TS}.sql"
SUMS="$BACKUP_DIR/${DB}_${TS}.sha256"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

log "backup start db=$DB"
# Custom format: compressed, supports selective/parallel pg_restore. Includes RLS policies and grants.
pg_dump --format=custom --compress=6 --no-password --file="$DUMP.partial" "$DB"
mv "$DUMP.partial" "$DUMP"
# Roles (e.g. leadex_app) without passwords; restore re-applies the password from the env file.
pg_dumpall --globals-only --no-role-passwords --no-password > "$GLOBALS"
pg_restore --list "$DUMP" > /dev/null   # integrity check: archive TOC readable
(cd "$BACKUP_DIR" && sha256sum "$(basename "$DUMP")" "$(basename "$GLOBALS")") > "$SUMS"
log "wrote $DUMP ($(du -h "$DUMP" | cut -f1))"

if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
  command -v aws >/dev/null 2>&1 || { log "aws cli missing; cannot upload" >&2; exit 2; }
  DEST="s3://$BACKUP_S3_BUCKET/${BACKUP_S3_PREFIX:-leadex}"
  for f in "$DUMP" "$GLOBALS" "$SUMS"; do
    if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
      aws --endpoint-url "$BACKUP_S3_ENDPOINT" s3 cp --only-show-errors "$f" "$DEST/$(basename "$f")"
    else
      aws s3 cp --only-show-errors "$f" "$DEST/$(basename "$f")"
    fi
  done
  log "uploaded to $DEST (use bucket lifecycle rules for remote retention)"
fi

# Local retention.
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name 'globals_*.sql' -o -name '*.sha256' \) \
  -mtime +"$RETENTION" -print -delete
log "backup done (retention ${RETENTION}d)"
