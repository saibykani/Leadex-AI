# LEADEX AI: Go-Live Security Checklist

Tick every item before pointing real users or real outbound channels at production.

## Secrets and configuration
- [ ] `.env.production` generated with `generate-secrets.sh`, `chmod 600`, not in git, backed up in a vault.
- [ ] `APP_ENV=production` (set by `docker-compose.prod.yml`; confirm with `dcp config | grep APP_ENV`).
- [ ] `JWT_SECRET` >= 32 random chars; `APP_DB_PASSWORD` is not `leadex_app`; `ENCRYPTION_KEY` is a valid Fernet key and stored offline.
- [ ] Postgres, Redis, Qdrant and SeaweedFS all have non-default credentials; `/etc/leadex/s3.json` is not the repo's local file.
- [ ] `CORS_ORIGINS` is exactly `https://<DOMAIN>`.
- [ ] Third-party keys (Google, SMTP, WhatsApp, LiveKit, Stripe/Razorpay) are production keys with least privilege; webhook secrets set.

## Network
- [ ] `dcp ps` shows published ports only for nginx (80, 443). `ss -tlnp` on the host shows nothing else but SSH.
- [ ] ufw: deny incoming except 22/80/443. SSH key-only, root login disabled, fail2ban active.
- [ ] External scan (`nmap -Pn <ip>`) confirms only 22/80/443 open.
- [ ] `/docs`, `/redoc`, `/openapi.json` return 404 publicly.

## TLS and headers
- [ ] Valid Let's Encrypt certificate; HTTP redirects to HTTPS; SSL Labs grade A or better.
- [ ] Responses carry HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy (`curl -sI https://<DOMAIN>`).
- [ ] CSP checked in the browser console on the main pages (no blocked resources needed by the app).
- [ ] Rate limiting verified: rapid requests to `/api/v1/auth/*` get 429.

## Database
- [ ] API connects as `leadex_app` (`SELECT usename, count(*) FROM pg_stat_activity GROUP BY 1;`), not the owner.
- [ ] RLS enabled on tenant tables (`SELECT relname FROM pg_class WHERE relrowsecurity;`) and cross-tenant access tested.
- [ ] Exactly the intended superadmin accounts: `SELECT email FROM users WHERE is_superadmin;`

## Backups and recovery
- [ ] First nightly backup present in `backups/` and in the S3 bucket; bucket has versioning/lifecycle.
- [ ] `restore-drill.sh` run successfully and timed (meets RTO in DISASTER_RECOVERY.md).
- [ ] Volume snapshots configured for `objectdata` / `qdrantdata`.

## Operations
- [ ] Unattended security upgrades enabled on the host; Docker images pinned and a monthly update routine agreed.
- [ ] External uptime monitor on `https://<DOMAIN>/health/ready`; disk-space alert.
- [ ] Grafana admin password changed from the generated one only via vault; Grafana not exposed without login.
- [ ] Log rotation in place (json-file 10m x 5) and disk headroom > 30%.
- [ ] Deploy workflow secrets configured with a dedicated non-root deploy key, `production` environment has required reviewers.
- [ ] Incident contact list and DR runbook location known to the on-call people.

## Compliance (see ../SECURITY_AND_COMPLIANCE.md)
- [ ] Outbound messaging consent/unsubscribe flows verified in production mode (outbound is real only when `APP_ENV=production`).
- [ ] Privacy policy, DPA and data-retention settings published.
