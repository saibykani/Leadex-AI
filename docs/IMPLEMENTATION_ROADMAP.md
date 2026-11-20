# LEADEX AI — Implementation Roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
|0|Architecture docs, ER, API spec, matrices, cost, risks|Docs in `/docs`|
|1|Monorepo, FastAPI, Next.js, Postgres, Redis, Docker, auth, orgs, RBAC, tenant isolation, migrations|compose healthy, migrations run, tests green|
|2|Design system, app shell, dashboard on real data, CRM (leads, contacts, notes, tasks, activities), MFA|CRUD + filters + cross-tenant tests|
|3|Discovery: Places adapter (+simulated), CSV import, provenance, dedup, website audit, usage/cost tracking|search job end-to-end with provenance|
|4|Ollama, LangGraph, Qdrant RAG, agent registry, tool authorisation, logs|agent text test with citations|
|5|LiveKit voice, STT/TTS, agent builder & testing lab, OutreachGate, telephony adapter (simulated)|browser voice test; blocked call proven|
|6|Website Studio: templates, generation, preview, versions, publish/rollback|preview served from SeaweedFS (S3)|
|7|Email (Gmail/Graph/SMTP), WhatsApp Cloud API, campaigns + approvals, suppression|simulated campaign end-to-end|
|8|Marketplace, matching, referrals, commissions|settlement rules tested|
|9|Workflow builder (React Flow) + Celery/Temporal execution|example pipeline runs|
|10|Plans, billing, metering, white label|limits enforced|
|11|Security audit, performance, monitoring, backups, CI/CD, DR|runbooks + green pipeline|

## Risk register
| Risk | Impact | Mitigation |
|---|---|---|
|Outreach law violations|Severe fines|OutreachGate default-block, counsel review, kill switches|
|Google Maps terms breach|API suspension|No scraping; minimal caching; provenance & retention jobs|
|Hindi/Telugu TTS quality|Poor UX|Per-language evaluation gate before enabling|
|Local hardware too weak for voice|Latency|Configurable remote GPU / paid provider (explicit opt-in)|
|Scope size|Delivery slip|Phased delivery; each phase runnable|
|Cross-tenant leak|Trust / legal|RLS + scoped queries + automated tests|
|Cost overrun|Cash burn|Usage metering, budgets, hard limits|
