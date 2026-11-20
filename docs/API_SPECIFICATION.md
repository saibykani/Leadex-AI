# LEADEX AI — API Specification (v1)

Base: `/api/v1`. Live OpenAPI (authoritative): `http://localhost:8000/docs`.

## Conventions
- Auth: `Authorization: Bearer <access_token>`; tenant: `X-Organization-Id: <uuid>`.
- Pagination: `?page=1&page_size=25` → `{items, total, page, page_size}`.
- Errors: `{"error": {"code": "string", "message": "string", "details": ...}}` with proper HTTP status.
- Idempotency: `Idempotency-Key` header **required** on endpoints causing external side effects
  (calls, messages, payments, referrals, campaign start).

## Implemented (Phase 1)
| Method | Path | Auth / permission |
|---|---|---|
|GET|/health|public liveness|
|GET|/health/ready|public; checks DB (and Redis if configured)|
|POST|/api/v1/auth/register|public; creates user + organization (Owner role); rate limited|
|POST|/api/v1/auth/login|public; rate limited|
|POST|/api/v1/auth/refresh|refresh token; rotates it|
|POST|/api/v1/auth/logout|revokes refresh session|
|GET|/api/v1/auth/me|bearer|
|GET|/api/v1/organizations|bearer; only orgs the user belongs to|
|POST|/api/v1/organizations|bearer; caller becomes Owner|
|GET|/api/v1/organizations/{id}|membership required|
|GET|/api/v1/organizations/{id}/members|`members:read`|
|POST|/api/v1/organizations/{id}/members|`members:write`|
|GET|/api/v1/roles|bearer + tenant|
|GET|/api/v1/audit-logs|`audit:read`, tenant scoped|

## Planned
- Discovery (3): `POST /discovery/search`, `GET /discovery/jobs/{id}`, `GET /businesses`, `GET /businesses/{id}`, `POST /businesses/{id}/audit`
- CRM (2): `GET|POST /leads`, `GET|PATCH /leads/{id}`, `/leads/{id}/notes|tasks|activities`, `POST /leads/import`
- Agents (4–5): `GET|POST /agents`, `POST /agents/{id}/test`, `/agents/{id}/versions`
- Calls (5): `POST /calls` (idempotent, OutreachGate), `GET /calls`, `GET /calls/{id}`
- Websites (6): `POST /websites/generate`, `GET /websites`, `POST /websites/{id}/publish`, `POST /websites/{id}/rollback`
- Campaigns (7): `POST /campaigns`, `POST /campaigns/{id}/approve`, `POST /campaigns/{id}/start`
- Marketplace (8): `POST /requirements`, `GET /providers`, `POST /referrals`, `GET /commissions`
- Workflows (9): `POST /workflows`, `POST /workflows/{id}/execute`
- Billing (10): `GET /billing/subscription`, `GET /billing/usage`
- Admin: `/admin/organizations`, `/admin/kill-switches`
