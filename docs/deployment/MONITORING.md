# Monitoring, alerts and load testing

Everything here is free and self-hostable.

## 1. Metrics (built in)
- `GET /metrics` on the API, in Prometheus format: requests per route and status, latency histograms, 5xx counts, uptime.
- Production: set `METRICS_TOKEN` in `.env`. Without it, `/metrics` is disabled. Scrapers must send `Authorization: Bearer <token>`.
- Scrape config and alert rules: `infrastructure/monitoring/prometheus.yml` and `alerts.yml`.
  The alerts cover: API down, error rate above 2 %, p95 latency above 1.5 s, and voice-agent replies slower than 4 s.

## 2. Error tracking (optional)
- Self-host **GlitchTip** (free, works with Sentry clients) or use any Sentry-compatible service.
- Set `SENTRY_DSN` in `.env`. Personal data is not sent (`send_default_pii=False`).

## 3. Uptime checks
- Run **Uptime Kuma** (free): `docker run -d -p 3001:3001 louislam/uptime-kuma:1`.
- Monitor `https://<api-domain>/health/ready` (checks DB + Redis) and `https://<web-domain>/`.
- Send notifications to email, Telegram, Slack or WhatsApp from Uptime Kuma's settings.

## 4. Load testing
```
cd apps/api
pip install -r requirements-dev.txt
LOADTEST_EMAIL=loadtest@yourco.com LOADTEST_PASSWORD=... locust -f tests/load/locustfile.py --host https://staging-api.yourco.com
```
Open http://localhost:8089 and ramp up users. Record p95 latency and failure rate in the go-live checklist.
Run it only against staging with a test account.

## 5. Logs
`docker compose logs -f api worker` locally. In production, ship container logs to Loki/Grafana (free) or your host's log service.
