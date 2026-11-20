# LEADEX AI

LEADEX AI is a multi-tenant lead discovery, qualification and outreach platform (B2B sales intelligence with AI-assisted research, voice and messaging). This repository is the monorepo; it is currently at **Phase 1** (identity, tenancy, RBAC and platform foundations).

## Repository layout

```
apps/api/            FastAPI service (SQLAlchemy, Alembic migrations in apps/api/alembic, tests in apps/api/tests)
apps/web/            Next.js 15 + Tailwind frontend
database/seeds/      Notes on seed data (RBAC is seeded by migration)
docs/                Architecture, API, database, security, roadmap, cost and integration docs
infrastructure/      nginx reverse proxy config and helper scripts (setup, migrate, backup, restore)
.github/workflows/   CI (api: ruff + pytest on SQLite and Postgres; web: typecheck + build)
docker-compose.yml       Base stack: postgres, redis, qdrant, objectstore (SeaweedFS S3), api, web, ollama (profile "ai")
docker-compose.dev.yml   Dev override: binds data stores to 127.0.0.1, hot reload for api
```

## Prerequisites

- Docker Desktop (or Docker Engine) with Compose v2
- Python 3.12
- Node.js 22 + npm
- Git (Git Bash on Windows works for the `.sh` scripts)

## Quickstart

`infrastructure/scripts/setup.ps1` / `setup.sh` do the `.env`, venv and dependency steps for you.

### Windows PowerShell

```powershell
# 1. Environment file + JWT secret
Copy-Item .env.example .env
python -c "import secrets;print(secrets.token_urlsafe(48))"   # paste into .env as JWT_SECRET=...

# 2. Start the stack (dev override exposes postgres/redis/etc. on 127.0.0.1)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. API venv + migrations (the api container also migrates on start)
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head

# 4. Tests - default SQLite
pytest

# 4b. Tests against Postgres
docker compose exec -T postgres createdb -U leadex leadex_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://leadex_app:leadex_app@localhost:5433/leadex_test"
$env:TEST_MIGRATION_DATABASE_URL = "postgresql+psycopg://leadex:leadex@localhost:5433/leadex_test"
pytest
Remove-Item Env:TEST_DATABASE_URL, Env:TEST_MIGRATION_DATABASE_URL

# 5. Web dev server
cd ..\web
npm install
npm run dev
```

### bash (Linux / macOS / Git Bash)

```bash
cp .env.example .env
secret=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=$secret|" .env && rm .env.bak

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

cd apps/api
python -m venv .venv && source .venv/bin/activate   # Git Bash: source .venv/Scripts/activate
pip install -r requirements-dev.txt
alembic upgrade head

pytest                                               # SQLite (default)
docker compose exec -T postgres createdb -U leadex leadex_test
TEST_MIGRATION_DATABASE_URL=postgresql+psycopg://leadex:leadex@localhost:5433/leadex_test TEST_DATABASE_URL=postgresql+psycopg://leadex_app:leadex_app@localhost:5433/leadex_test pytest

cd ../web && npm install && npm run dev
```

Endpoints: web http://localhost:3000, API http://localhost:8000 (readiness at `/health/ready`), S3 endpoint http://localhost:8333. Add `--profile ai` to also start Ollama.

## Scripts

| Script | Purpose |
|---|---|
| `infrastructure/scripts/setup.ps1` / `setup.sh` | Create `.env` with a random `JWT_SECRET` if missing, api venv + dev deps, web deps |
| `infrastructure/scripts/migrate.ps1` / `migrate.sh` | `alembic upgrade head` in `apps/api` |
| `infrastructure/scripts/backup.ps1` / `backup.sh` | `pg_dump` from the postgres container into `./backups/` (timestamped) |
| `infrastructure/scripts/restore.sh` | Restore a dump into the postgres container |
| `infrastructure/nginx/nginx.conf` | Reverse proxy: `/api`, `/health` -> api:8000, `/` -> web:3000 |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API specification](docs/API_SPECIFICATION.md)
- [Database design](docs/DATABASE_DESIGN.md)
- [Security and compliance](docs/SECURITY_AND_COMPLIANCE.md)
- [Implementation roadmap](docs/IMPLEMENTATION_ROADMAP.md)
- [Integration matrix](docs/INTEGRATION_MATRIX.md)
- [Cost estimation](docs/COST_ESTIMATION.md)
- [Seed data](database/seeds/README.md)

### Guides

- [Go-live checklist](docs/GO_LIVE_CHECKLIST.md): every key, account and step needed for production
- [User guide](docs/USER_GUIDE.md): how to use the app (for non-technical users)
- [API guide](docs/API_GUIDE.md): authentication, errors, webhooks; live reference at `/docs` and `/openapi.json`
- [Deployment](docs/deployment/DEPLOYMENT.md), [monitoring](docs/deployment/MONITORING.md), [disaster recovery](docs/deployment/DISASTER_RECOVERY.md)

## Status: Phase 1

**Works now**
- FastAPI service: JWT auth, tenants/users, role-based access control (roles and permissions seeded by migration 0001)
- Postgres row-level security policies (migration 0002) — written, **not yet verified against a live Postgres**
- Health endpoints; test suite passes on SQLite (14 passed, RLS test skipped); Postgres run pending
- Next.js web app foundation (login, register, dashboard, organization settings) — production build passes
- Docker Compose stack, CI workflow, nginx config, setup/migrate/backup/restore scripts — written, not yet executed
- MFA, CRM UI and the compliance gate are not implemented yet (Phase 2+)

**Not built yet** (see the [roadmap](docs/IMPLEMENTATION_ROADMAP.md))
- Lead discovery and AI research/embeddings (Phases 3-4; qdrant, objectstore and ollama are provisioned but unused)
- Voice calling (Phase 5), email/WhatsApp outreach (Phase 7), billing (Phase 10)
- Outbound integrations are simulated unless `APP_ENV=production` and the provider is configured
- No demo/fake business data is seeded
- Production deployment (TLS, secrets management, nginx in compose) is not wired up

## Production deployment

See [docs/deployment/DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md) (single-server Docker Compose with `docker-compose.prod.yml`, TLS via Let's Encrypt, backups, monitoring), [DISASTER_RECOVERY.md](docs/deployment/DISASTER_RECOVERY.md) and the go-live [SECURITY_CHECKLIST.md](docs/deployment/SECURITY_CHECKLIST.md).
