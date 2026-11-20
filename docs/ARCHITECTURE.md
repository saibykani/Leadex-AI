# LEADEX AI — Architecture

## 1. Context
Leadex AI is a multi-tenant SaaS for business discovery, CRM, AI voice/email/WhatsApp outreach,
website generation, a professional-services referral marketplace and workflow automation. The
platform owner's own business runs as one tenant ("internal operations" mode, flag
`organizations.is_platform_owner`) on the same codebase as subscriber tenants.

## 2. Guiding principles
1. **Tenant isolation in depth** — every tenant-owned row has `organization_id`; the API scopes every
   query through a `TenantContext` dependency, and PostgreSQL Row-Level Security (`app.current_org`
   session setting) is the second line of defence.
2. **Compliance-gated side effects** — no call, email, WhatsApp message or campaign leaves the system
   except through `compliance.OutreachGate`, which defaults to **BLOCK** when eligibility is uncertain.
   Non-production environments force all outbound adapters into `simulated` mode.
3. **Adapters, not vendors** — every external service (Places, LLM, STT, TTS, telephony, email,
   WhatsApp, payments, storage) sits behind an interface with a provider registry.
   Missing credentials ⇒ adapter reports `not_configured`; simulated adapters label every result
   `simulated=true`.
4. **Provenance everywhere** — business data is stored per field with source, collection time and
   retention rule. Google Places content is kept separate (`business_source_fields` with
   `source='google_places'`; only `place_id` cached long-term) per Maps Platform terms.
5. **Open-source first, cost-attributed** — Ollama, faster-whisper, Kokoro/Piper, Qdrant, SeaweedFS (S3). Every
   metered operation writes a `usage_records` row attributed to tenant (+ campaign/lead when known).

## 3. Logical view
```
            +------------- Nginx (TLS, rate limit) ---------------+
 Browser -->|  apps/web (Next.js)       apps/api (FastAPI /api/v1) |
            +--------------------------------+---------------------+
                                             |
   +-------------+-------------+-------------+-------------+-------------+
 PostgreSQL    Redis         Qdrant        SeaweedFS (S3)         Ollama       LiveKit
 (RLS data) (cache/queues) (RAG vectors) (files/sites) (LLM/embed)  (voice/SIP)
   ^             ^
   +-- workflow-workers (Celery; Temporal later) -- voice-workers (LiveKit Agents)
```

## 4. Backend bounded contexts (`apps/api/app/modules/`)
identity · organizations · discovery · crm · compliance · agents · voice · campaigns · websites ·
communication · marketplace · referrals · commissions · automation · billing · analytics ·
administration. Each module owns `models.py`, `schemas.py`, `service.py`, `router.py`. Modules talk
via service functions, never via each other's tables directly. Shared kernel lives in `app/core`
(config, db, security, tenancy, errors, audit, rate limiting).

## 5. Request lifecycle
1. JWT access token (15 min) + rotating opaque refresh token (stored hashed in `sessions`).
2. `get_current_user` → `TenantContext(org_id, user_id, permissions)` from the `X-Organization-Id`
   header, validated against `organization_memberships`.
3. On PostgreSQL the DB session executes `set_config('app.current_org', :org, true)` so RLS applies.
4. Permission check via `require_permission("members:write")`.
5. Mutations write `audit_logs` (append-only).
6. External actions require an `Idempotency-Key` header (table `idempotency_keys`).

## 6. AI architecture
LangGraph graphs per agent (discovery, audit, qualification, voice sales, email, website gen,
requirement, matching, follow-up, BI). Agents receive **tools** that are thin clients of backend
services — tool calls are authorised against the agent's `agent_tools` allow-list and the tenant's
permissions; side-effecting tools route through `OutreachGate`. RAG: ingestion → chunking →
embeddings (sentence-transformers / Ollama `nomic-embed-text`) → Qdrant with mandatory `org_id`
payload filter → citations returned with every answer.

## 7. Voice
LiveKit Agents worker with pluggable STT (faster-whisper), LLM (Ollama), TTS (Kokoro for EN; Piper or
other evaluated models for HI/TE — a language is enabled only after its evaluation passes).
Telephony via a LiveKit SIP trunk adapter. Global and per-tenant kill switches are checked before
dialling and periodically during a call.

## 8. Deployment profiles
- **LOCAL** — docker-compose + dev override, simulated integrations, hot reload.
- **STAGING** — separate DB/credentials, real provider sandboxes, public webhook URLs.
- **PRODUCTION** — managed Postgres with PITR, private network for data stores, HTTPS only,
  horizontal Celery workers, OpenTelemetry → Prometheus/Grafana. Data stores never get public ports.

## 9. Key decisions
| # | Decision | Reason |
|---|----------|--------|
|1|Monorepo: npm workspaces (web) + Python package (api)|Single codebase, simple on Windows|
|2|Celery first, Temporal later|Temporal adds ops cost; adopt for multi-day workflows in Phase 9|
|3|Shared-schema multitenancy + RLS|Cheapest at small scale; large tenants can be sharded later|
|4|UUID v4 PKs|Safe to expose, mergeable across regions|
|5|Argon2id via `argon2-cffi`|OWASP recommendation|
|6|LiveKit Agents over Pipecat|Native SIP + WebRTC, self-hostable|
|7|Tests run on SQLite by default, Postgres when `TEST_DATABASE_URL` is set|Fast local loop; RLS verified against Postgres|
