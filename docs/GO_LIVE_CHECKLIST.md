# LEADEX AI: Go-Live Checklist

One page listing every key, account and decision needed to run LEADEX AI for real customers. Companion docs:
[DEPLOYMENT.md](deployment/DEPLOYMENT.md) (how to deploy), [DISASTER_RECOVERY.md](deployment/DISASTER_RECOVERY.md),
[MONITORING.md](deployment/MONITORING.md), [TELEPHONY_SETUP.md](TELEPHONY_SETUP.md).

**Cost column:** "free" means the software or account costs nothing. "free tier" means the provider has a free allowance
with limits. "paid" means you will be billed; we do not quote prices because they change. Always check the linked
provider pricing page before committing.

**Important:** outside `APP_ENV=production`, every outbound call, SMS, email and WhatsApp message is **simulated**. Nothing
real is sent until `APP_ENV=production` and the relevant provider is configured.

For a production deploy, values go in `.env.production` (see `.env.production.example`), not `.env`. Anything not listed
in `.env.production.example` is still read from the environment, but see "Known gaps" at the bottom.

## 1. Core secrets and URLs (all required)

| Variable | What it is | Where to get it | Required | Cost |
|---|---|---|---|---|
| `APP_ENV` | Set to `production` (compose does this for you in `docker-compose.prod.yml`) | You set it | Required | free |
| `DOMAIN` | Your public domain, used by nginx, TLS and CORS | Domain registrar | Required | paid (domain), see registrar |
| `LETSENCRYPT_EMAIL` | Contact email for TLS certificates | Your email | Required | free |
| `JWT_SECRET` | Signs login tokens. Must be 32+ chars; app refuses to start otherwise | `infrastructure/scripts/generate-secrets.sh` or `python -c "import secrets;print(secrets.token_urlsafe(48))"` | Required | free |
| `ENCRYPTION_KEY` | Fernet key that encrypts stored secrets. **Losing it makes encrypted data unrecoverable, even from backups** | Same script, or `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` | Required | free |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database owner (used for migrations) | You choose; use a strong password | Required | free |
| `APP_DB_PASSWORD` | Password of the restricted runtime database role. Must not be the default | You choose | Required | free |
| `REDIS_PASSWORD` | Redis password | You choose | Required | free |
| `QDRANT_API_KEY` | Vector database key (knowledge search) | You choose | Required | free |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Credentials for the built-in SeaweedFS file store | You choose; also put them in the `s3.json` file referenced by `SEAWEEDFS_S3_CONFIG` | Required | free |
| `SEAWEEDFS_S3_CONFIG` | Host path of the production `s3.json` (outside the repo) | See DEPLOYMENT.md | Required | free |
| `PUBLIC_API_URL` | Public base URL of the API (webhook and tracking links), e.g. `https://yourdomain` | Your domain | Required | free |
| `WEB_APP_URL` | Public base URL of the web app (links in emails) | Your domain | Required | free |
| `CORS_ORIGINS` | Allowed browser origins. The prod compose sets it to `https://$DOMAIN` | Automatic | Automatic | free |
| `IMAGE_PREFIX`, `IMAGE_TAG`, `API_WORKERS`, `TZ` | Image names/tag, API worker count, timezone | You choose | Optional | free |
| `CELERY_ENABLED` | Background jobs on Celery workers (defaults to true in compose) | Leave on | Optional | free |

## 2. Telephony and voice (needed for real AI phone calls)

| Variable | What it is | Where to get it | Required | Cost |
|---|---|---|---|---|
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio account credentials. Can instead be entered per organization in the app under Integrations (per-org values win) | https://console.twilio.com | Required for real calls | free trial, then paid: https://www.twilio.com/en-us/pricing |
| `TWILIO_FROM_NUMBER` | Your Twilio caller number in E.164 format. For India you need a number that is allowed for outbound telemarketing (see DLT below) | Twilio console | Required for real calls | paid, see Twilio pricing |
| `PUBLIC_WEBHOOK_BASE_URL` | Public HTTPS URL Twilio calls back to. Empty means no real calls. In production this is the same as `PUBLIC_API_URL` | Your domain | Required for real calls | free |
| `TWILIO_ESCALATION_NUMBER` | Number dialled when a caller asks for a human | Your team phone | Optional | call charges apply |
| `TWILIO_MACHINE_DETECTION` | Answering-machine detection (`true`/`false`) | You choose | Optional | may add Twilio charges, see Twilio pricing |
| `TWILIO_VOICE_EN_IN`, `TWILIO_VOICE_HI_IN` | Female Indian voice for English and Hindi calls (default `Polly.Aditi`; neural voices such as `Polly.Kajal-Neural` sound more natural) | Twilio voice list | Optional | neural voices may cost extra, see Twilio pricing |
| `SIP_PROVIDER` | `twilio`, `telnyx`, `plivo` or `exotel`. Empty disables calling | You choose | Required for calling | n/a |
| `VOICE_KILL_SWITCH` | `true` blocks every call globally (emergency stop) | You choose | Optional | free |
| `ALLOW_TEST_CALLS`, `TEST_CALL_ALLOWLIST` | Non-production only: really dial the listed numbers. Keep off in production | You choose | Optional | n/a |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | LiveKit realtime audio. Present in the config; leave empty unless you have set up LiveKit (the Twilio path does not need it) | https://cloud.livekit.io or self-host | Optional | free tier / paid, see https://livekit.io/pricing |

Twilio webhook endpoints (the app builds these from `PUBLIC_WEBHOOK_BASE_URL`; you normally do not paste them anywhere):
`/api/v1/telephony/twilio/voice/{call_id}`, `/turn/{call_id}`, `/status/{call_id}`. Follow [TELEPHONY_SETUP.md](TELEPHONY_SETUP.md).

### Fast LLM for live calls (strongly recommended)

A phone call needs replies in about 1-2 seconds. CPU-only Ollama can take far longer, so use a hosted OpenAI-compatible model.

| Variable | Value | Cost |
|---|---|---|
| `FAST_LLM_BASE_URL` | e.g. `https://api.groq.com/openai/v1` | free tier (rate-limited): https://console.groq.com/keys, pricing https://groq.com/pricing |
| `FAST_LLM_API_KEY` | Key from that provider | as above |
| `FAST_LLM_MODEL` | e.g. `llama-3.1-8b-instant` (check the provider's current model list) | as above |

## 3. AI models (non-call features: agents' text chat, email and website copy, knowledge search)

| Variable | What it is | Required | Cost |
|---|---|---|---|
| `OLLAMA_BASE_URL` | Ollama server (self-hosted models). Start the bundled one with `docker compose --profile ai up -d`, or point at another host | Optional (without it AI text features fall back or are simulated) | free (your own hardware) |
| `OLLAMA_MODEL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL` | Models for copy polish, agents and embeddings (examples in `.env.example`) | Optional | free |
| `AI_HTTP_TIMEOUT_S` | Timeout for model calls (seconds) | Optional | free |

## 4. Discovery (finding businesses)

| Variable | What it is | Where to get it | Required | Cost |
|---|---|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Google Places lookups. Empty means the adapter reports "not configured" and CSV import is the main source | Google Cloud console, enable Places API | Optional | paid with a monthly free allowance, see https://developers.google.com/maps/billing-and-pricing/pricing |
| `GOOGLE_PLACES_UNIT_COST` | USD per request, used for usage costing and budget stops. Set it from Google's current pricing | You set it | Optional | n/a |
| `DISCOVERY_DAILY_REQUEST_BUDGET` | Max billable provider requests per organization per day (default 100) | You choose | Optional | n/a |
| `GOOGLE_PLACES_RETENTION_DAYS` | Provider fields are purged after this many days (default 30, per Google terms) | You choose | Optional | n/a |
| `DISCOVERY_HTTP_TIMEOUT`, `WEBSITE_AUDIT_MAX_RETRIES` | Timeouts and retry cap | You choose | Optional | n/a |

## 5. Email (SMTP, mailbox connections, inbound events)

| Variable | What it is | Where to get it | Required | Cost |
|---|---|---|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | Mail server for password-reset emails, team invites and verification emails | Any SMTP provider (your email host, Brevo, Amazon SES, Mailgun, etc.) | Required for password reset and invites | many providers have a free tier, see your provider's pricing |
| `SMTP_FROM` | Sender address, e.g. `no-reply@yourdomain` | Your domain (set up SPF, DKIM and DMARC for it) | Required | free |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | "Connect Gmail" OAuth app | Google Cloud console, OAuth consent screen | Optional | free to create (Google verification may be needed for public use) |
| `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID` | "Connect Outlook" OAuth app | Microsoft Entra (Azure) app registration | Optional | free to register |
| `EMAIL_WEBHOOK_SECRET` | Shared secret for inbound replies and bounces. Your email provider must send header `X-Leadex-Webhook-Secret`. Endpoints: `/api/v1/webhooks/email/inbound` and `/api/v1/webhooks/email/events` | You choose | Required if you want reply and bounce tracking (without it these endpoints return 503) | free |

## 6. WhatsApp (Meta Cloud API)

| Variable | What it is | Where to get it | Required | Cost |
|---|---|---|---|---|
| `WA_ACCESS_TOKEN` | Permanent access token | Meta for Developers, WhatsApp Business | Optional (WhatsApp is simulated without it) | Meta charges per conversation, see https://developers.facebook.com/docs/whatsapp/pricing |
| `WA_PHONE_NUMBER_ID` | Sending phone number ID | Meta WhatsApp manager | Optional | as above |
| `WA_APP_SECRET` | Verifies `X-Hub-Signature-256` on incoming webhooks | Meta app settings | Required if WhatsApp is on | free |
| `WA_VERIFY_TOKEN` | Token you invent; Meta echoes it when you register the webhook | You choose | Required if WhatsApp is on | free |

Webhook URL to register in Meta: `https://<DOMAIN>/api/v1/webhooks/whatsapp`.

## 7. Billing

| Variable | What it is | Where to get it | Required | Cost |
|---|---|---|---|---|
| `PAYMENT_PROVIDER` | Listed in `.env.example` but **not read anywhere in the API code**. A provider becomes available once its keys below are set; otherwise only the "Simulated" provider (no money moves) works | n/a | Not needed | n/a |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe API key and webhook signing secret | https://dashboard.stripe.com (Developers) | If using Stripe | no monthly fee; per-transaction fees, see https://stripe.com/pricing |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Razorpay keys and webhook secret | https://dashboard.razorpay.com | If using Razorpay | per-transaction fees, see https://razorpay.com/pricing |

Register webhooks in the provider dashboard:
- Stripe: `https://<DOMAIN>/api/v1/billing/webhooks/stripe` (signature header `Stripe-Signature`)
- Razorpay: `https://<DOMAIN>/api/v1/billing/webhooks/razorpay` (signature header `X-Razorpay-Signature`)

## 8. Safety, compliance and monitoring settings

| Variable | What it is | Required | Cost |
|---|---|---|---|
| `CLAMAV_HOST` | Set to `clamav` after `docker compose --profile scan up -d`. Scans uploaded files for viruses. `CLAMAV_PORT` defaults to 3310 | Required in production (uploads are refused without a scanner unless `CLAMAV_REQUIRED` is set otherwise) | free (self-hosted, needs extra RAM) |
| `CLAMAV_REQUIRED` | Leave empty: default is "required" in production | Optional | free |
| `DNC_ENFORCE` | Leave empty: default is "on" in production (calls are blocked until a registry was imported) | Optional | free |
| `DNC_API_URL`, `DNC_API_KEY` | Optional registry API. The app calls `GET ?country=IN&phone=+91...` and expects `{"listed": true|false}` | Optional | depends on registry provider |
| `DNC_MAX_AGE_DAYS` | An imported registry file older than this is "stale" (default 31) | Optional | free |
| `METRICS_TOKEN` | Bearer token that lets Prometheus read `/metrics`. Required in production to expose metrics | Required if you use monitoring | free |
| `SENTRY_DSN` | Error tracking. Self-hosted GlitchTip is free | Optional | free tier / paid, see https://sentry.io/pricing |
| `GRAFANA_ADMIN_PASSWORD` | Grafana login (monitoring profile) | Required with `--profile monitoring` | free |
| `BACKUP_HOST_DIR`, `BACKUP_SCHEDULE`, `BACKUP_RETENTION_DAYS` | Nightly database backups on the server | Required | free |
| `BACKUP_S3_BUCKET`, `BACKUP_S3_ENDPOINT`, `BACKUP_S3_PREFIX`, `BACKUP_S3_REGION`, `BACKUP_S3_ACCESS_KEY`, `BACKUP_S3_SECRET_KEY` | Off-server copy of backups in any S3-compatible bucket | Strongly recommended | paid or free tier, see your storage provider |

## 9. Non-key steps (people, paperwork, servers)

- **Domain and DNS.** Buy a domain. Create an `A` record for `DOMAIN` pointing to the server's public IP. For email also add SPF, DKIM and DMARC records at your email provider.
- **HTTPS.** The prod compose runs nginx plus certbot (Let's Encrypt). Ports 80 and 443 must be open to the internet for certificate issue and renewal. Confirm renewal works and the certificate is not near expiry (see DISASTER_RECOVERY.md, scenario D).
- **Server size and Docker memory.** The prod compose sets limits of roughly: Postgres 2 GB, API 2 GB, Redis 512 MB, Qdrant 1 GB, SeaweedFS 1 GB, plus web, worker, beat and nginx. Plan for at least about 8 GB RAM for the base stack; add more for ClamAV (a few GB), Ollama models, and the monitoring profile. On Docker Desktop or WSL raise the memory allowance accordingly. These are our estimates from the compose limits, not a benchmark: load test before launch.
- **India telemarketing: TRAI and DLT.** Calling or messaging Indian numbers for commercial purposes requires registration as a telemarketer/principal entity on a telecom operator's DLT platform, approved headers and templates, and scrubbing against the NCPR (National Customer Preference Register). Rules change; confirm with your telecom provider and a lawyer. Twilio also has its own regulatory requirements for Indian numbers, see their docs.
- **DNC registries.** Subscribe to the registries for each country you call (India NCPR via your DLT registration; US DNC, UK TPS, Canada DNCL, Australia DNCR where relevant). Download the scrub file and import it in the app under **Compliance, DNC registry**. Re-import before it goes stale (default 31 days).
- **Consent capture.** Record consent (who, channel, when, evidence) under Compliance or on each lead. Only message people you have a lawful basis to contact. The app blocks suppressed or opted-out contacts.
- **Legal review.** The `/privacy`, `/terms` and `/cookies` pages are templates. Have a lawyer review and edit them for your company, countries and data practices before launch. Nothing in this repository is a certification of legal compliance.
- **Real prices.** Sign in as the platform owner and open **/sales** to set your real plan prices, tagline, bullets and demo-booking availability. Do not launch with placeholder prices.
- **Monitoring.** Set `METRICS_TOKEN`, start the monitoring profile if you want Grafana, and add an external uptime check on `https://<DOMAIN>/health/ready` (see MONITORING.md; no alerting is configured by default).
- **Backups and recovery.** Turn on nightly backups plus an off-server copy and run a restore drill (DISASTER_RECOVERY.md). Store `ENCRYPTION_KEY`, `POSTGRES_PASSWORD` and `APP_DB_PASSWORD` in a password manager.
- **First platform owner.** Create the first account through the web UI (see DEPLOYMENT.md) and enable two-factor authentication in Settings, Security.

## 10. Launch day sequence

1. Server ready, DNS pointing at it, ports 80/443 open.
2. Generate secrets, fill `.env.production`, store the secrets safely.
3. Create the SeaweedFS `s3.json`, validate config, start the stack per DEPLOYMENT.md (`docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml up -d`).
4. Start ClamAV: `docker compose --profile scan up -d`, set `CLAMAV_HOST=clamav`, restart the API.
5. Register your account, turn on 2FA, set real prices at `/sales`.
6. Configure SMTP; test a password-reset email.
7. Add Twilio credentials, `PUBLIC_WEBHOOK_BASE_URL`, the fast LLM settings; import your DNC file.
8. Add Stripe or Razorpay keys and register both webhook URLs.
9. Enable backups and the off-server copy; run one manual backup and a restore test.
10. Have the legal pages reviewed, then announce.

## 11. Verification list

- [ ] `https://<DOMAIN>/health` and `/health/ready` return OK; HTTPS certificate valid.
- [ ] Sign up, log out, log in; password-reset email arrives; invite email arrives.
- [ ] `/docs` loads (API explorer) and a login via the API works.
- [ ] Settings, Security: 2FA enrol and sign-in works.
- [ ] Upload a file: it is accepted; (optionally) test with the EICAR test string and confirm it is refused.
- [ ] Compliance, DNC registry shows your country as imported and fresh.
- [ ] **Test call to your own phone** (Calls page, telephony card): you hear the AI disclosure, the agent answers within a couple of seconds, and the call appears in Call history as real (not "simulated").
- [ ] Rate the test call Good or Bad and confirm it saves.
- [ ] **Test payment** with the provider's test mode first, then a small real one; confirm the webhook arrives and the invoice or plan updates. Refund the real test.
- [ ] `/metrics` returns 401 without the token and data with it.
- [ ] A backup file exists off-server and a restore drill succeeded.
- [ ] `/privacy`, `/terms`, `/cookies` show your reviewed text.

## Known gaps in the repository configuration

These are variables the code reads that are **not forwarded to the API container by the `x-api-env` block in `docker-compose.yml`** (so setting them in `.env` alone has no effect in Docker until the compose file passes them through): `SMTP_STARTTLS`, `SMTP_USERNAME` (legacy), `DISCOVERY_DAILY_REQUEST_BUDGET`, `GOOGLE_PLACES_RETENTION_DAYS`, `GOOGLE_PLACES_UNIT_COST`, `DISCOVERY_HTTP_TIMEOUT`, `WEBSITE_AUDIT_MAX_RETRIES`, `VOICE_KILL_SWITCH`, `CLAMAV_PORT`, `TWILIO_VOICE_DEFAULT`, `OLLAMA_URL` (legacy), `AUTH_RATE_LIMIT_PER_MINUTE`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`. Also `PAYMENT_PROVIDER` appears in `.env.example` but nothing in `apps/api/app` reads it. `.env.production.example` does not list most integration variables (Twilio, SMTP, billing, etc.); add them to `.env.production` yourself using `.env.example` as the reference. Variables marked "read by code" here were found by searching `apps/api/app`; the compose files were not changed.
