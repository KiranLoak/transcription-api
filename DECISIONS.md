# Architecture decisions

## Async job pattern (polling + optional webhooks)

Transcription takes 10–60s. We return **HTTP 202** with `job_id` immediately and process in a **thread pool** (Whisper/PyTorch are not asyncio-friendly). Agents poll `GET /transcriptions/{id}` every 2–5s, then fetch `/result`. Optional `webhook_url` POSTs completion payload.

**Why not SSE/long-poll?** Polling is simplest for stateless agents, works through proxies, and maps cleanly to MCP tools. Webhooks cover push-based workflows.

## Agent discoverability

- **OpenAPI** at `/openapi.json` with Bearer security and rich endpoint descriptions
- **llms.txt** at `/llms.txt` (emerging convention for LLM crawlers)
- **/.well-known/agent.json** and **ai-plugin.json** for capability discovery
- **MCP server** (`python -m mcp_server`) exposes the same operations as tools
- **Structured errors** with `code`, `retryable`, `suggested_action`, `docs_url`

## Auth & quotas

- API keys: `tx_` prefix, stored as **SHA-256** hash only
- Bootstrap via `X-Admin-Secret` or authenticated key creation
- Per-key **token-bucket** RPM + global RPM cap
- Monthly **job quota** per key with calendar reset

## Pricing (see PRICING.md)

Bill ~$0.05/job (margin over $0.02–0.08 upstream). Usage endpoint exposes quota and spend.

## Database

PostgreSQL + SQLAlchemy 2 + Alembic. Jobs, keys, usage_records tables.

## Deployment

Docker + docker-compose (Postgres + API). Railway via `railway.json` and Dockerfile healthcheck. Image includes ffmpeg and CPU PyTorch.

## SDK

`openapi-python-client` generation script; httpx examples in `sdk/README.md`.
