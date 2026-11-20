# LEADEX AI — Cost Estimation (planning ranges, not guarantees)

| Stage | Monthly | Composition |
|---|---|---|
|Local dev|$0–30|All OSS in Docker; optional domain/GitHub; excludes hardware, power and paid API use|
|Small cloud pilot|$50–200|One 4–8 vCPU VM, small managed Postgres, object storage, CPU LLM or limited GPU time, few SIP minutes|
|Early commercial|$200–700|App + worker VMs, managed DB with backups, part-time GPU for voice/LLM, telephony usage|
|Growing|$700–2,500+|Multiple GPU nodes, HA DB, multi-region, monitoring, heavier telephony|

## Variable unit costs (verify current vendor pricing before budgeting)
- **Google Places API (New)** — billed per request by SKU and field mask; use minimal field masks, cache only `place_id`.
- **Telephony** — roughly $0.005–0.03/min in the US, highly variable by country; plus number rental and registration fees.
- **WhatsApp** — per conversation/message by category and country.
- **Self-hosted LLM** — GPU-hour cost; an 8B quantised model on a 24 GB GPU handles a few concurrent voice calls.

## Controls (Phase 3 & 10)
Central cost service → `usage_records(organization_id, resource, quantity, unit_cost, campaign_id, lead_id)`;
per-tenant budgets with alerts at 50/80/100 %, hard stop at 100 %, throttling, and paid fallback
**off** unless an administrator enables it.

## Local hardware guidance
- Minimum: 16 GB RAM, 4 cores — runs the stack plus a 3B LLM on CPU (voice will be slow).
- Recommended: 32 GB RAM + NVIDIA GPU ≥ 8 GB VRAM (8B Q4 LLM, faster-whisper on GPU).
- Give Docker Desktop (WSL2) at least 8 GB of memory.
