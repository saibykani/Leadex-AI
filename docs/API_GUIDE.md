# LEADEX AI: API Guide

For developers integrating with the LEADEX AI backend (FastAPI). This guide covers the conventions; the **live, always-current reference** is generated from the code:

- Interactive docs (Swagger UI): `https://<your-domain>/docs`
- Machine-readable schema: `https://<your-domain>/openapi.json`

Locally (default compose ports) that is `http://localhost:8010/docs`. If a reverse proxy only forwards `/api` and `/health` to the API, reach `/docs` directly on the API port. `docs/API_SPECIFICATION.md` is the original design document and may differ from what is implemented; trust `/openapi.json`.

## Base URL

All application endpoints live under `/api/v1`, for example `POST /api/v1/auth/login`. Health checks are outside that prefix: `GET /health` and `GET /health/ready`. `/metrics` requires `Authorization: Bearer <METRICS_TOKEN>` in production.

## Authentication

1. **Log in**

   ```
   POST /api/v1/auth/login
   {"email": "you@example.com", "password": "...", "otp_code": "123456"}
   ```

   `otp_code` is only needed if the user enabled two-factor authentication; without it the API returns `401` with code `mfa_required`. Response:

   ```json
   {"access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900}
   ```

   Access tokens are short-lived JWTs (default 15 minutes). Send them as `Authorization: Bearer <access_token>`.

2. **Refresh** with `POST /api/v1/auth/refresh`. Refresh tokens last 14 days by default and rotate: each refresh returns a new one and the old one stops working.
   - **Browsers**: the refresh token is stored in an httpOnly cookie named `lx_refresh` (path `/api/v1/auth`, `SameSite=Lax`, `Secure` in production). The cookie is only honoured when the request also carries the header `X-Requested-With: leadex` (CSRF protection).
   - **API clients**: send the token in the JSON body: `{"refresh_token": "..."}`. No special header is needed.

3. **Log out** with `POST /api/v1/auth/logout` (same cookie or body rules); it returns `204` and revokes that session.

Other auth endpoints: `POST /api/v1/auth/register` (creates a user and a first organization) and `GET /api/v1/auth/me` (the user, their organizations, roles and permissions).

## Choosing the organization (multi-tenancy)

Most business endpoints are tenant-scoped. Send `X-Organization-Id: <organization uuid>` on every such request (get the ids from `GET /api/v1/auth/me`). Without it the API returns `400` with code `tenant_required`. Your role in that organization determines which permissions apply, and data from other organizations is isolated at the database level (row-level security).

## Idempotency

Where a request can cost money or contact a person, send an `Idempotency-Key` header (any unique string up to 128 characters, such as a UUID). Repeating a request with the same key will not repeat the action. It is **required** for placing a call (the voice call endpoint) and for the campaign endpoint that checks it (a missing key returns `400` `idempotency_key_required`). It is accepted on some workflow and marketplace actions. See `/docs` for which operations list the header.

## Errors

Every error uses one JSON shape:

```json
{"error": {"code": "invalid_credentials", "message": "Invalid email or password", "details": null}}
```

- `code` is a stable machine-readable string (for example `rate_limited`, `tenant_required`, `idempotency_key_required`, `invalid_refresh_token`, `validation_error`); framework errors use `http_error`.
- `message` is human-readable.
- `details` is usually `null`. For validation errors (HTTP 422, code `validation_error`) it is a list of `{"loc": [...], "msg": "..."}`.

## Rate limits

The built-in rate limiter protects the **auth endpoints** (`register`, `login`, `refresh`): by default **20 requests per minute per client IP per endpoint** (`AUTH_RATE_LIMIT_PER_MINUTE`). Exceeding it returns HTTP `429` with code `rate_limited`. It uses Redis when configured, otherwise a per-process counter. Other endpoints have no general request-rate limit in the code, but billing plans and budgets (for example call or discovery limits) can refuse actions with an error. Put your reverse proxy or a gateway in front for broader limits.

## Pagination

List endpoints that return many rows use `page` (starting at 1) and `page_size` (default 25, maximum 200) query parameters and return an object with the items and paging information (for example `GET /api/v1/leads?page=2&page_size=50`). Parameters differ by endpoint (filters, search `q`, sort), so check the endpoint in `/docs`.

## Webhooks (inbound, called by providers)

These endpoints are public (no bearer token) and instead verify a signature or secret. Register them in each provider's dashboard using your public base URL.

| Provider | Endpoint | Verification |
|---|---|---|
| Stripe | `POST /api/v1/billing/webhooks/stripe` | `Stripe-Signature` header, secret `STRIPE_WEBHOOK_SECRET` |
| Razorpay | `POST /api/v1/billing/webhooks/razorpay` | `X-Razorpay-Signature` header, secret `RAZORPAY_WEBHOOK_SECRET` |
| Twilio voice | `POST /api/v1/telephony/twilio/voice/{call_id}`, `/turn/{call_id}`, `/status/{call_id}` | Created per call from `PUBLIC_WEBHOOK_BASE_URL`; you do not configure these by hand (see [TELEPHONY_SETUP.md](TELEPHONY_SETUP.md)) |
| Email replies | `POST /api/v1/webhooks/email/inbound` | Header `X-Leadex-Webhook-Secret` must equal `EMAIL_WEBHOOK_SECRET` (returns 503 if unset) |
| Email events (bounces etc.) | `POST /api/v1/webhooks/email/events` | Same secret header |
| WhatsApp | `GET` (verification handshake using `WA_VERIFY_TOKEN`) and `POST /api/v1/webhooks/whatsapp` | `X-Hub-Signature-256`, secret `WA_APP_SECRET` |

Workflows can also expose a per-workflow webhook secret (`POST /api/v1/.../{workflow_id}/webhook-secret`; see `/docs`).

Return `2xx` quickly from your own receivers and make handlers idempotent; providers retry.

## Quick example

```bash
BASE=https://your-domain
TOKEN=$(curl -s $BASE/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
ORG=$(curl -s $BASE/api/v1/auth/me -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print(json.load(sys.stdin)['memberships'][0]['organization']['id'])")
curl -s "$BASE/api/v1/leads?page=1&page_size=25" -H "Authorization: Bearer $TOKEN" -H "X-Organization-Id: $ORG"
```

The `memberships` field name in the example is taken from the `/auth/me` response model; confirm it in `/docs` if your version differs.
