#!/bin/sh
# Entrypoint of the `backup` service (postgres:16-alpine): installs a crontab for pg-backup.sh and runs
# busybox crond in the foreground. Job output goes to the container log (docker compose logs backup).
set -eu
SCHEDULE="${BACKUP_SCHEDULE:-0 2 * * *}"
if [ -n "${BACKUP_S3_BUCKET:-}" ] && ! command -v aws >/dev/null 2>&1; then
  echo "BACKUP_S3_BUCKET set: installing aws-cli (needs outbound network on container start)"
  apk add --no-cache aws-cli >/dev/null
fi
# crond does not pass the container environment to jobs; persist the needed variables (root-only file).
: > /etc/backup.env
chmod 600 /etc/backup.env
env | grep -E '^(PG|BACKUP_|AWS_|TZ=)' | while IFS='=' read -r k v; do
  printf "export %s='%s'\n" "$k" "$(printf '%s' "$v" | sed "s/'/'\\\\''/g")" >> /etc/backup.env
done
mkdir -p /etc/crontabs
echo "$SCHEDULE . /etc/backup.env && /bin/sh /usr/local/bin/pg-backup.sh > /proc/1/fd/1 2>&1" > /etc/crontabs/root
echo "backup schedule: '$SCHEDULE' retention=${BACKUP_RETENTION_DAYS:-14}d s3=${BACKUP_S3_BUCKET:-<disabled>}"
exec crond -f -l 8
