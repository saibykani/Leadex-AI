#!/usr/bin/env bash
# First-time TLS issuance (Let's Encrypt, HTTP-01 webroot). Run once on the server AFTER DNS points at it.
# 1) temporary self-signed cert so nginx can start, 2) start nginx, 3) request the real cert via webroot,
# 4) reload nginx and start the renewal loop (`certbot` service).
# Usage: infrastructure/scripts/init-letsencrypt.sh [--staging]
#   DOMAIN / LETSENCRYPT_EMAIL are read from the environment or .env.production.
#   Use --staging first to avoid Let's Encrypt rate limits while testing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env.production}"
DC=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml)
getenv() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//'; }
DOMAIN="${DOMAIN:-$(getenv DOMAIN)}"
EMAIL="${LETSENCRYPT_EMAIL:-$(getenv LETSENCRYPT_EMAIL)}"
if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "DOMAIN and LETSENCRYPT_EMAIL are required" >&2
  exit 1
fi
STAGING_ARG=""
[ "${1:-}" = "--staging" ] && STAGING_ARG="--staging"
LIVE="/etc/letsencrypt/live/$DOMAIN"

echo "### Temporary self-signed certificate for $DOMAIN"
"${DC[@]}" run --rm --no-deps --entrypoint sh certbot -c "
  if [ -f $LIVE/fullchain.pem ] && [ ! -f $LIVE/.dummy ]; then echo 'real certificate already present'; exit 0; fi
  mkdir -p $LIVE && openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout $LIVE/privkey.pem -out $LIVE/fullchain.pem -subj /CN=localhost && touch $LIVE/.dummy"

echo "### Starting nginx (also starts api/web and their dependencies)"
"${DC[@]}" up -d nginx

echo "### Requesting Let's Encrypt certificate"
"${DC[@]}" run --rm --no-deps --entrypoint sh certbot -c "
  if [ -f $LIVE/.dummy ]; then rm -rf $LIVE /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf; fi
  certbot certonly --webroot -w /var/www/certbot $STAGING_ARG -d $DOMAIN --email $EMAIL \
    --rsa-key-size 4096 --agree-tos --no-eff-email --non-interactive --keep-until-expiring"

"${DC[@]}" exec nginx nginx -s reload
"${DC[@]}" up -d certbot
echo "### Done. Check: curl -I https://$DOMAIN"
