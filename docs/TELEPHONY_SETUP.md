# Telephony setup (Twilio)

LEADEX places real outbound AI phone calls through Twilio. The conversation runs on Twilio's built-in speech
recognition and text-to-speech (TwiML `<Gather input="speech">` + `<Say>`). Your own LLM (Ollama) writes the agent's
replies. A LiveKit/SIP adapter can be added later behind the same `TelephonyAdapter` interface
(`apps/api/app/modules/voice/telephony.py`).

## When a call is really dialled

`POST /api/v1/calls` runs all of its existing checks first: Idempotency-Key, kill switches, published agent, language
evaluation, the compliance gate (consent, suppression, calling window, jurisdiction) and billing limits. If every check
passes, the call is **really dialled** only when one of these is true:

| Environment | Real dial when |
|---|---|
| `APP_ENV=production` | always (subject to all checks) |
| any other `APP_ENV` | `ALLOW_TEST_CALLS=true` **and** the lead's number (normalised to E.164 using the lead's country) is listed in `TEST_CALL_ALLOWLIST` |

Every other allowed call is **simulated**: nobody is contacted. If a real dial was intended but Twilio isn't set up,
the call is recorded with status `not_configured` and one of these reasons: `telephony_not_configured` or
`telephony_needs_public_url`. Twilio REST errors are saved word for word on the call (`error_message`) and shown on
`/calls/<id>`.

The **Telephony** card on `/calls` shows the current state: `not_configured`, `needs_public_url`, `simulated`,
`test_allowlist` or `live`.

## Step by step (local test on your own phone)

1. **Create a Twilio account.** A free trial works: <https://www.twilio.com/try-twilio>.
2. **Verify your own phone number.** Go to Console → Phone Numbers → Manage → *Verified Caller IDs*. A trial account
   can **only** call verified numbers. Calling any other number fails with Twilio error 21219 ("unverified"), and
   LEADEX shows that error on the call page.
3. **Get a Twilio number.** The trial includes one free number. Use it as `TWILIO_FROM_NUMBER` in E.164 format, for
   example `+1XXXXXXXXXX`. Trial calls start with a short Twilio trial message, and the person must press a key
   before LEADEX's TwiML runs.
4. **Expose the API over public HTTPS.** Twilio has to reach the webhooks. Run one of these:
   - Cloudflare quick tunnel (no account needed): `cloudflared tunnel --url http://localhost:8010`
     It prints a URL like `https://random-words.trycloudflare.com`.
   - ngrok: `ngrok http 8010`, which prints an `https://….ngrok-free.app` URL.

   Use the port your API actually listens on (8010 here). The URL changes every time a quick tunnel restarts, so
   update `.env` each time.
5. **Configure `.env`** in the repository root, then restart the API:
   ```env
   PUBLIC_WEBHOOK_BASE_URL=https://random-words.trycloudflare.com   # no trailing path
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_FROM_NUMBER=+1XXXXXXXXXX
   ALLOW_TEST_CALLS=true
   TEST_CALL_ALLOWLIST=+91XXXXXXXXXX          # your verified number, E.164, comma-separated
   # optional
   TWILIO_ESCALATION_NUMBER=+91YYYYYYYYYY     # "talk to a human" is transferred here
   OLLAMA_BASE_URL=http://localhost:11434     # the LLM that writes the agent's replies
   ```
   Credentials can also be set per organization under Integrations → **twilio**, with the credentials
   `account_sid`, `auth_token`, `from_number` and optionally `escalation_number`. Organization credentials override
   the env values. The webhook signature is checked with the auth token of the organization that owns the call.
6. **Prepare the lead.** Set the phone number to your verified number and the country (for example `IN`). Record a
   consent reference and a *voice* consent record, and move the lead to `approved_for_outreach`. The call must also
   fall inside the calling window for that jurisdiction.
7. **Publish an agent.** The compliance disclosure must say it is an AI and name the business. If it doesn't,
   LEADEX adds "This is an AI assistant calling on behalf of <organization>".
8. **Start the call** from the lead or the pipeline. On `/calls/<id>`, the status, transcript and outcome update
   every 3 seconds while the call is active.

## What happens on a call

| Webhook (public, signature-validated) | Purpose |
|---|---|
| `POST /api/v1/telephony/twilio/voice/{call_id}` | First turn: the AI disclosure and greeting, then `<Gather input="speech">` (`en-IN` for Indian leads, otherwise `en-US`; `hi-IN`/`te-IN` for Hindi/Telugu agents) |
| `POST /api/v1/telephony/twilio/turn/{call_id}` | Each thing the caller says is added to the transcript. Opt-out phrases ("stop", "don't call", "not interested", "remove me") trigger a polite goodbye, add a suppression record, withdraw consent, add a DO NOT CONTACT note and hang up. "Human"/"person" transfers the call to `TWILIO_ESCALATION_NUMBER`, or takes a callback message if none is set. Anything else goes to the agent orchestrator with the conversation history, with replies capped at 2 sentences and an 8 s LLM budget. If the LLM fails or times out, the agent says a safe fallback and offers a callback. A price that doesn't appear in the agent's knowledge or business info is replaced with "a specialist will confirm pricing". The call ends at `TELEPHONY_MAX_TURNS` (default 12) or at the agent's `max_call_seconds`. |
| `POST /api/v1/telephony/twilio/status/{call_id}` | Status updates (`completed`, `busy`, `no_answer`, `failed`, `canceled`). The first terminal event records billing usage `voice_minutes` (whole minutes, rounded up) plus the cost if Twilio sends `Price`. On `completed`, it runs outcome extraction (budget with evidence, timeline, interest, next step) and writes it to the lead and the call summary. Duplicate callbacks are ignored. |

Every webhook rejects a missing or invalid `X-Twilio-Signature` with **403**. The signature is computed over
`PUBLIC_WEBHOOK_BASE_URL` + path + the sorted POST params, so `PUBLIC_WEBHOOK_BASE_URL` must exactly match the URL
Twilio calls. The tenant is resolved from the call session id by the `telephony_call_org` SECURITY DEFINER function
(migration 0015), and all further work runs under row-level security for that tenant only.

Recording stays **off** unless the call request includes `record=true` and a recording consent reference.

## India notes (read before calling real prospects)

- Commercial or promotional calls to Indian numbers are regulated by TRAI (TCCCPR 2018). You need DLT registration as
  a telemarketer or principal entity and approved headers, you must respect the NCPR/DND preferences, and you need the
  person's consent. Calling from an unregistered or international number for commercial purposes can be blocked and
  penalised. Get legal advice before you use this for real.
- Twilio cannot provide Indian local caller IDs for outbound calls to most customers. Calls to India usually show an
  international number, and answer rates are lower.
- Per-minute cost depends on the destination and number type. Calls to Indian mobiles from a US Twilio number cost
  noticeably more than US-to-US calls. Check <https://www.twilio.com/voice/pricing>. Trial credit is limited.
- A trial account can call **verified numbers only**. Upgrade the account before calling anyone else, and only after
  you have the compliance basis described above.

## Troubleshooting

- Card shows **Needs public URL**: `PUBLIC_WEBHOOK_BASE_URL` is empty or doesn't start with `https://`.
- Call is `failed` with `Twilio error 21219`: the number isn't verified in your trial account.
- Call connects but says "an application error has occurred": Twilio couldn't reach the webhook. Check that the
  tunnel is running and points at the API port. If every request returns 403, `PUBLIC_WEBHOOK_BASE_URL` doesn't match
  the tunnel URL or the auth token is wrong.
- Agent always uses the fallback line: Ollama isn't reachable (`OLLAMA_BASE_URL`) or takes longer than 8 s. Use a
  smaller model or set `TELEPHONY_LLM_BUDGET_S`. Keep it under Twilio's 15 s webhook timeout.
- Race condition: the call row is committed when `POST /calls` returns. Twilio fetches the voice webhook only after
  the callee answers, which is normally several seconds later.
