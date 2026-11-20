# LEADEX AI: Disaster Recovery

## Targets

| Metric | Target | How it is met |
|---|---|---|
| **RPO** (max data loss) | **24 h** default; **<= 1 h** if hourly backups are enabled | Nightly `pg_dump` (`BACKUP_SCHEDULE`), off-server copy in S3. Set `BACKUP_SCHEDULE=0 * * * *` for 1 h. For RPO of minutes, add WAL archiving (pgBackRest / WAL-G); not included. |
| **RTO** (time to restore service) | **4 h** to a new server; **1 h** for a DB restore on the same server | Scripted rebuild (DEPLOYMENT.md sections 2-6) plus `restore-prod.sh`. Validate with the monthly drill. |

These are targets for a single-server deployment. Tighten them only together with infrastructure changes
(managed Postgres with PITR, standby server).

## What must exist off-server

1. Database dumps + globals + checksums (`BACKUP_S3_BUCKET`, ideally with versioning / object lock).
2. `.env.production` and `/etc/leadex/s3.json` in a password manager or secrets vault. **Without
   `ENCRYPTION_KEY` the encrypted columns in a restored DB are unreadable.**
3. Snapshots of the `objectdata` (uploaded files) and `qdrantdata` (vectors; re-indexable from Postgres if the app
   supports it) volumes, e.g. provider disk snapshots, daily.
4. The git repository (release tags).

## Scenarios

### A. Bad migration / data corruption, server healthy
1. `dcp stop api worker beat web`
2. Pick the last good dump in `backups/` (the pre-deploy backup from `deploy.sh` is usually right).
3. `infrastructure/scripts/restore-prod.sh backups/<file>.dump`
4. `infrastructure/scripts/deploy.sh <last-good-ref>`; verify `/health/ready`, log in, spot-check data.

### B. Server lost
1. Provision a new server (DEPLOYMENT.md sections 2-4), restore `.env.production` and `s3.json` from the vault.
2. `aws [--endpoint-url ...] s3 cp s3://<bucket>/<prefix>/<latest>.dump backups/` (and the globals + sha256 files).
3. `dcp up -d postgres redis qdrant objectstore`, then `infrastructure/scripts/restore-prod.sh backups/<file>.dump --yes`.
4. Restore the `objectdata`/`qdrantdata` volume snapshots if available.
5. `infrastructure/scripts/deploy.sh <release-tag>`, point DNS at the new IP (low TTL helps), run `init-letsencrypt.sh`.
6. Verify, then announce recovery and the data-loss window (time of last backup).

### C. Secret compromise
Rotate the affected secret (DEPLOYMENT.md section 12). `JWT_SECRET` rotation invalidates all sessions.
`ENCRYPTION_KEY` rotation requires re-encrypting stored data with the app's key-rotation procedure (do not just
replace the key). Review access logs (`dcp logs nginx`) and the audit log in the app.

### D. TLS certificate expired
`dcp run --rm certbot renew --webroot -w /var/www/certbot && dcp exec nginx nginx -s reload`. Check that port 80
is reachable for the ACME challenge.

## Restore drill (monthly)

```bash
infrastructure/scripts/restore-drill.sh            # newest local dump -> scratch DB -> checks -> drop
```

Also quarterly: download a dump **from S3** onto a different machine and restore it there. Record each drill:

| Date | Dump used | Source (local/S3) | Restore time | Checks OK | Operator |
|---|---|---|---|---|---|
| | | | | | |
