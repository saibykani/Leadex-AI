# LEADEX AI — Security & Compliance

## Security controls
| Control | Implementation | Status |
|---|---|---|
|Password hashing|Argon2id (argon2-cffi)|✅ Phase 1|
|Tokens|JWT HS256 access (15 min); opaque refresh tokens hashed (SHA-256) in `sessions`, rotated on use, revocable|✅ Phase 1|
|RBAC|permissions → roles → memberships; `require_permission` dependency|✅ Phase 1|
|Tenant isolation|`TenantContext` scoping + PostgreSQL RLS + cross-tenant tests|✅ Phase 1|
|Rate limiting|Redis fixed window on auth endpoints (in-memory fallback)|✅ Phase 1|
|Input validation / SQLi|Pydantic + SQLAlchemy bound parameters only|✅ Phase 1|
|CORS / CSRF|Bearer tokens (no auth cookies) ⇒ CSRF not applicable to API; strict CORS allow-list|✅ Phase 1|
|Security headers|nosniff, frame deny, referrer policy, HSTS in production|✅ Phase 1|
|Audit logs|append-only `audit_logs`|✅ Phase 1|
|MFA (TOTP)|pyotp|Phase 2|
|Field encryption|Fernet for integration credentials and MFA secrets|Phase 3|
|File uploads|type sniffing, size limits, AV hook, private SeaweedFS (S3) buckets|Phase 3|
|Secrets|`.env` locally (git-ignored); cloud secrets manager in production|policy ✅|

## Compliance framework (Phase 2–5)
The `compliance` module holds **jurisdiction profiles** (IN, US, UK, EU, CA, AU, default) describing,
per channel (voice, SMS, email, WhatsApp): required lawful basis, consent type, calling windows,
DNC registries (US National DNC, TRAI NCPR/DND, UK TPS/CTPS, Canada DNCL, AU DNCR), sender-ID rules,
AI-disclosure and recording-consent requirements.

`OutreachGate.check(org, lead, channel, jurisdiction)` returns `ALLOW` or `BLOCK(reasons)`; an unknown
jurisdiction or missing evidence ⇒ BLOCK. Public business contact details are **not** consent.
Global and per-tenant kill switches override everything. Outside `APP_ENV=production`, real sends are
impossible — adapters are forced into simulated mode.

Data-subject rights (access, correction, deletion, export, withdrawal) are tracked as requests with
SLAs; retention jobs purge Places-derived fields per Google terms and tenant policy.

Regulations considered: GDPR / UK GDPR, ePrivacy / PECR, CAN-SPAM, TCPA + TSR, CASL, TRAI TCCCPR 2018,
India DPDP Act 2023, WhatsApp Business policy, Google Maps Platform terms.
**This document is not legal advice; profiles must be reviewed by counsel in each launch market.**
