#!/usr/bin/env bash
# Server-side deploy / upgrade: check out a ref, build images, take a backup, roll services (api runs
# `alembic upgrade head` on start), wait for readiness. Used by .github/workflows/deploy.yml over SSH and
# runnable by hand on the server.
# Usage: infrastructure/scripts/deploy.sh <git-ref>     (tag such as v1.4.0, or a commit SHA)
set -euo pipefail
REF="${1:?usage: deploy.sh <git-ref>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env.production}"
DC=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml)

PREV="$(git rev-parse --short HEAD)"
git fetch --tags --prune origin
git checkout --detach "$REF"
NEW="$(git rev-parse --short HEAD)"
echo "$PREV" > .previous-deployed-ref
echo "Deploying $NEW (previous $PREV)"
export IMAGE_TAG="$NEW"

"${DC[@]}" build api web

echo "### Pre-deploy backup"
"${DC[@]}" up -d backup
"${DC[@]}" exec -T backup sh -c '. /etc/backup.env && sh /usr/local/bin/pg-backup.sh'

"${DC[@]}" up -d --remove-orphans
for _ in $(seq 1 36); do
  if "${DC[@]}" exec -T nginx wget -q -O /dev/null http://api:8000/health/ready 2>/dev/null; then
    "${DC[@]}" ps
    echo "Healthy: $NEW"
    exit 0
  fi
  sleep 5
done
echo "API did not become ready. See docs/deployment/DEPLOYMENT.md#rollback (previous ref: $PREV)" >&2
exit 1
