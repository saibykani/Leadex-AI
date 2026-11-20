# LEADEX AI: Production Deployment

Single-server Docker Compose deployment. Stack: nginx (TLS, the only public entry point), Next.js `web`,
FastAPI `api`, Celery `worker` + `beat`, Postgres 16, Redis, Qdrant, SeaweedFS (S3), certbot, a backup cron
container, and an optional Prometheus/Grafana monitoring profile.

```
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml [--profile monitoring] <cmd>
```

`docker-compose.prod.yml` is used **instead of** `docker-compose.dev.yml`; never combine them. Tip: on the server,
`alias dcp='docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml'`.
All commands below use `dcp`.

## 1. Server sizing

| Tier | Use | vCPU | RAM | Disk |
|---|---|---|---|---|
| Minimum | pilot, < 20 users, no local LLM | 4 | 8 GB | 80 GB SSD |
| Recommended | small production, monitoring on | 8 | 16 GB | 160 GB SSD + separate backup volume |
| With Ollama (`--profile ai`) | local LLM inference | 8+ | 32 GB (or GPU) | +50 GB for models |

Sum of container memory limits in the prod override is about 10 GB with monitoring, so 8 GB hosts should run
without `--profile monitoring` or lower the limits. Ubuntu 22.04/24.04 LTS, x86_64.

## 2. Server preparation (Ubuntu)

```bash
# as root
apt-get update && apt-get -y upgrade
apt-get -y install ca-certificates curl git ufw fail2ban unattended-upgrades
adduser --disabled-password --gecos "" deploy
# Docker Engine + compose plugin (official repo)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker deploy
docker compose version   # must be >= 2.24 (the override uses the !reset tag)

# Firewall: only SSH + HTTP/HTTPS
ufw default deny incoming && ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
# SSH: key-only auth. In /etc/ssh/sshd_config set PasswordAuthentication no, PermitRootLogin no; then systemctl reload ssh
```

Note: Docker-published ports bypass ufw. That is why only nginx publishes ports in production.

## 3. DNS

Create an `A` (and `AAAA` if IPv6) record for your domain, e.g. `app.example.com`, pointing at the server.
Wait until `dig +short app.example.com` returns the server IP before issuing certificates. Use a low TTL
(300s) initially so you can fail over quickly (see DISASTER_RECOVERY.md).

## 4. Code, secrets and config

```bash
sudo mkdir -p /opt/leadex /etc/leadex && sudo chown deploy: /opt/leadex
sudo -iu deploy
git clone <your-repo-url> /opt/leadex && cd /opt/leadex
git checkout <release-tag>
cp .env.production.example .env.production && chmod 600 .env.production
infrastructure/scripts/generate-secrets.sh      # paste the values into .env.production
```

Fill in `DOMAIN`, `LETSENCRYPT_EMAIL`, all secrets, and backup settings. Store `ENCRYPTION_KEY`,
`POSTGRES_PASSWORD` and `APP_DB_PASSWORD` in a password manager as well: **losing `ENCRYPTION_KEY` makes encrypted
columns unrecoverable, even from backups.**

SeaweedFS S3 credentials (outside the repo), using the generated `S3_ACCESS_KEY`/`S3_SECRET_KEY`:

```bash
sudo tee /etc/leadex/s3.json >/dev/null <<'JSON'
{ "identities": [ { "name": "leadex",
    "credentials": [ { "accessKey": "<S3_ACCESS_KEY>", "secretKey": "<S3_SECRET_KEY>" } ],
    "actions": ["Admin", "Read", "Write", "List", "Tagging"] } ] }
JSON
sudo chown root:deploy /etc/leadex/s3.json && sudo chmod 640 /etc/leadex/s3.json
```

Validate the configuration (fails loudly if a required secret is missing):

```bash
dcp config --quiet && echo OK
```

Integration keys (Google, SMTP, WhatsApp, LiveKit, billing; see `.env.example`) are only passed to containers if
they are listed in the api/worker `environment` in `docker-compose.yml`. Check that before enabling a provider.

## 5. Build and first start

```bash
export IMAGE_TAG=$(git rev-parse --short HEAD)
dcp build
dcp up -d postgres redis qdrant objectstore
dcp up -d api          # runs `alembic upgrade head` as the schema owner, then serves as leadex_app
dcp logs -f api        # wait for "Application startup complete"
```

The first migration creates the schema, row-level-security policies and the restricted `leadex_app` role. The
api connects with `DATABASE_URL` (leadex_app, RLS enforced) and migrates with `MIGRATION_DATABASE_URL` (owner).
In production the api refuses to start with a weak `JWT_SECRET` or the default `APP_DB_PASSWORD`.

If the role password was set before the role existed, make sure it matches `.env.production`:

```bash
dcp exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<< "ALTER ROLE leadex_app PASSWORD '<APP_DB_PASSWORD>';"
```

## 6. TLS issuance (Let's Encrypt, webroot)

```bash
infrastructure/scripts/init-letsencrypt.sh --staging   # dry run against LE staging (avoids rate limits)
infrastructure/scripts/init-letsencrypt.sh             # real certificate
dcp up -d                                              # everything else (web, worker, beat, backup, certbot)
curl -I https://app.example.com                        # expect 200 and a Strict-Transport-Security header
```

The `certbot` service renews twice daily; nginx reloads every 6 hours to pick up new certificates.
Check at https://www.ssllabs.com/ssltest/ (target: A or A+).

## 6a. Customer custom domains (generated websites)

Published websites can be served on a customer's own domain. The platform verifies ownership by DNS TXT record and
only then serves the site and allows a certificate to be issued.

1. In the website editor, open **Custom domain**, enter e.g. `www.customer.com` and add the shown record at the
   customer's DNS provider: `TXT  _leadex-verify.www.customer.com  <token>`. Click **Verify**.
2. The customer points the domain at the platform: a `CNAME` for subdomains (`www.customer.com CNAME sites.example.com`)
   or an `A`/`AAAA` record to the server IP for an apex domain. `sites.example.com` is a hostname you control that
   resolves to the server.
3. Run Caddy as the edge for customer domains (separate from the nginx app domain, or on another IP/port). Caddy
   asks the API before issuing any certificate (`GET /api/v1/public/domain-check?domain=<host>` returns 200 only for
   verified domains) and rewrites every request to the Host-header route:

```caddyfile
{
    on_demand_tls {
        ask http://api:8000/api/v1/public/domain-check
    }
}

https:// {
    tls {
        on_demand
    }
    rewrite * /api/v1/public/custom-site
    reverse_proxy api:8000 {
        header_up Host {host}
    }
}
```

The `ask` endpoint is rate limited and reveals only whether a domain is verified. Removing the domain in the editor
stops serving immediately. Needs `dnspython` (in `requirements.txt`) for the TXT lookup; migration `0025` adds the
domain columns and the `website_org_for_verified_domain()` SQL function used by the public routes.

## 7. Create the superadmin

1. Register a normal account through the web UI at `https://<DOMAIN>` (password hashing happens in the app).
2. Promote it as the schema owner (the restricted role cannot do this, by design):

```bash
dcp exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
UPDATE users SET is_superadmin = true WHERE lower(email) = lower('admin@example.com');
SELECT id, email, is_superadmin FROM users WHERE is_superadmin;
SQL
```

3. Log out and back in. Keep the number of superadmins minimal and enable MFA if the app offers it.

## 8. Backups and restore

- The `backup` service runs `pg-backup.sh` on `BACKUP_SCHEDULE` (default 02:00): `pg_dump -Fc` + roles
  (`pg_dumpall --globals-only`, no passwords) + sha256, into `BACKUP_HOST_DIR`, pruned after
  `BACKUP_RETENTION_DAYS`. If `BACKUP_S3_BUCKET` is set, files are also uploaded to that S3-compatible bucket
  (configure lifecycle and object lock / versioning on the bucket for remote retention).
- Manual backup: `dcp exec backup sh -c '. /etc/backup.env && sh /usr/local/bin/pg-backup.sh'`
- Logs: `dcp logs backup`
- **Restore drill** (safe, scratch DB): `infrastructure/scripts/restore-drill.sh [file.dump]`, run monthly.
- **Production restore** (destructive): `infrastructure/scripts/restore-prod.sh backups/<file>.dump`
- Not covered by pg_dump: Qdrant vectors (`qdrantdata`), uploaded objects (`objectdata`), Redis (transient queue).
  Snapshot these volumes with your provider's disk snapshots, or `docker run --rm -v leadex_objectdata:/d -v $PWD:/b alpine tar czf /b/objectdata.tgz -C /d .`.
- Also back up `.env.production` and `/etc/leadex/s3.json` (encrypted, off-server).

## 9. Upgrades

```bash
cd /opt/leadex && infrastructure/scripts/deploy.sh v1.5.0
```

`deploy.sh` checks out the ref, builds images tagged with the commit SHA, takes a pre-deploy backup, runs
`up -d` (api migrates on start) and waits for `/health/ready`. The same script runs from GitHub Actions via the
manual **Deploy (manual)** workflow (`.github/workflows/deploy.yml`) once its secrets are configured.
Read migration notes in the release before upgrading; migrations that rewrite large tables need a maintenance window.

## 10. Rollback

- **Code-only change (no migration):** `infrastructure/scripts/deploy.sh <previous-ref>` (the previous ref is stored
  in `.previous-deployed-ref`).
- **Release included a migration:** prefer a forward fix. If you must go back:
  1. `dcp stop api worker beat web`
  2. `dcp run --rm api alembic downgrade <previous_revision>` (only if the migration has a working downgrade), or
     restore the pre-deploy backup with `restore-prod.sh` (data written since is lost).
  3. `infrastructure/scripts/deploy.sh <previous-ref>`

## 11. Monitoring

```bash
dcp --profile monitoring up -d
```

- Grafana: `https://<DOMAIN>/grafana/` (user `admin`, `GRAFANA_ADMIN_PASSWORD`). Dashboard "LEADEX Overview":
  service up/down, disk, CPU, memory, Postgres connections/size, Redis memory/ops.
- Prometheus scrapes node, postgres and redis exporters (`infrastructure/monitoring/prometheus/prometheus.yml`).
  The api has no `/metrics` endpoint yet; a commented job is ready for it.
- No alerting is configured. At minimum add an external uptime check on `https://<DOMAIN>/health/ready`
  and Grafana alerts for disk < 15% free and Postgres down.
- Logs: `dcp logs -f --tail=200 <service>`; json-file logs rotate at 10 MB x 5 per container.

## 12. Routine operations

| Task | Command |
|---|---|
| Status | `dcp ps` |
| Restart a service | `dcp restart api` |
| psql (owner) | `dcp exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'` |
| Rotate JWT_SECRET | edit `.env.production`, `dcp up -d api worker beat` (logs everyone out) |
| Rotate APP_DB_PASSWORD | `ALTER ROLE leadex_app PASSWORD '...'` as owner, update env, `dcp up -d api worker beat` |
| Disk usage | `docker system df`; prune old images with `docker image prune -a --filter until=720h` |
