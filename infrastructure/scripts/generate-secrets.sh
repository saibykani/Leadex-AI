#!/usr/bin/env bash
# Prints strong random secrets for .env.production. Nothing is written to disk by this script.
# Usage: infrastructure/scripts/generate-secrets.sh            (copy the values into .env.production)
# Requires openssl.
set -euo pipefail
command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }

# URL-safe, no padding: safe inside Postgres/Redis URLs and env files.
tok() { openssl rand -base64 "$1" | tr -d '\n=' | tr '+/' '-_'; }
# Fernet key = urlsafe base64 of exactly 32 random bytes, WITH '=' padding (44 chars).
fernet() { openssl rand 32 | openssl base64 -A | tr '+/' '-_'; }
alnum() { openssl rand -hex "$1"; }

echo "# Generated $(date -u +%FT%TZ) by generate-secrets.sh. Also store these in a password manager."
echo "JWT_SECRET=$(tok 48)"
echo "POSTGRES_PASSWORD=$(tok 32)"
echo "APP_DB_PASSWORD=$(tok 32)"
echo "ENCRYPTION_KEY=$(fernet)"
echo "REDIS_PASSWORD=$(tok 32)"
echo "QDRANT_API_KEY=$(tok 32)"
echo "S3_ACCESS_KEY=leadex$(alnum 8)"
echo "S3_SECRET_KEY=$(tok 32)"
echo "GRAFANA_ADMIN_PASSWORD=$(tok 24)"
