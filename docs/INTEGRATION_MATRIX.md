# LEADEX AI — Integration Matrix

| Integration | Purpose | Credential(s) | Local mode | Cost model | Phase |
|---|---|---|---|---|---|
|PostgreSQL 16|primary DB|DATABASE_URL|container|free|1 ✅|
|Redis 7|cache, queues, rate limit|REDIS_URL|container|free|1 ✅|
|Qdrant|vectors / RAG|QDRANT_URL, QDRANT_API_KEY|container|free|4|
|SeaweedFS (S3-compatible; MinIO image no longer on Docker Hub)|object storage (S3 API)|S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY|container|free|3|
|Ollama|LLM + embeddings|OLLAMA_BASE_URL|host install or container|free (hardware)|4|
|Google Places API (New)|discovery|GOOGLE_PLACES_API_KEY|simulated without key|per request by SKU|3|
|Google OAuth / Gmail API|send/receive email|GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET|simulated|free within quota|7|
|Microsoft Graph|Outlook mail|MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID|simulated|free|7|
|SMTP|generic email|SMTP_HOST/PORT/USER/PASSWORD|local mail sink|varies|7|
|WhatsApp Business Platform (Cloud API)|messaging|WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, WA_APP_SECRET|simulated|per conversation/message|7|
|LiveKit|WebRTC voice|LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET|container|free self-hosted|5|
|SIP trunk (Twilio/Telnyx/Plivo/Exotel…)|PSTN calls|provider-specific|**disabled**|per minute + numbers|5|
|faster-whisper|STT|—|local|free|5|
|Kokoro / Piper|TTS|—|local|free|5|
|Stripe / Razorpay|billing|provider keys|simulated|% per transaction|10|
|Licensed data providers|discovery|per vendor|disabled|licence|3|
|OpenTelemetry / Prometheus / Grafana|observability|—|compose profile `monitoring`|free|11|

Every adapter implements: `setup`, `test_connection`, `health`, `status`
(`not_configured | simulated | connected | error`), usage reporting, error log, reconnect,
disconnect and credential rotation. Simulated mode is forced when `APP_ENV` is not `production`.
