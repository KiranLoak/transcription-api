# Agent-First Transcription API

Production-ready async REST API wrapping the multi-stage transcription pipeline (Whisper → Chirp 3 → Gemini) for **AI agents**, with OpenAPI, MCP, llms.txt, API keys, quotas, and Docker deployment.

## Features

- Async jobs: upload file or URL → poll status → fetch `TranscriptionResult`
- Bearer API keys (SHA-256 hashed), rate limits, monthly quotas
- Agent discovery: `/openapi.json`, `/llms.txt`, `/.well-known/agent.json`, MCP tools
- Structured errors with retry hints
- Usage API: `GET /api/v1/usage`

## Quick start (Docker)

```bash
cd transcription-api
# Place GCP service account JSON as long-memory-481406-i3-a87ef482f961.json
docker compose up --build
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  
Keys UI: http://localhost:8000/keys  

### Create API key

```bash
curl -X POST http://localhost:8000/api/v1/keys/bootstrap \
  -H "Content-Type: application/json" \
  -H "X-Admin-Secret: local-dev-bootstrap" \
  -d '{"name":"my-agent"}'
```

### Transcribe (agent flow)

```bash
export API_KEY=tx_...

curl -X POST http://localhost:8000/api/v1/transcriptions/url \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"}'

# Poll status, then:
curl http://localhost:8000/api/v1/transcriptions/{job_id}/result \
  -H "Authorization: Bearer $API_KEY"
```

## Local dev (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Start Postgres and set DATABASE_URL in .env
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

## MCP server

```bash
set TRANSCRIPTION_API_URL=http://localhost:8000
set TRANSCRIPTION_API_KEY=tx_...
python -m mcp_server
```

## Pipeline CLI (unchanged)

```bash
python transcribe.py video.mp4 --json
```

## Project layout

| Path | Purpose |
|------|---------|
| `transcribe.py` | Original pipeline |
| `app/` | FastAPI service |
| `mcp_server/` | MCP tools |
| `public/` | llms.txt, well-known |
| `alembic/` | DB migrations |
| `DECISIONS.md` | Design notes |
| `PRICING.md` | Pricing logic |

## Deploy (Railway)

1. Push repo, add PostgreSQL plugin
2. Set env: `DATABASE_URL`, `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` (paste JSON or mount secret), `BASE_URL`, `SECRET_KEY`, `ADMIN_BOOTSTRAP_SECRET`
3. Deploy via Dockerfile; health check `/health`

## Evaluation checklist

- [x] Async transcription API (upload + URL)
- [x] Job polling + results
- [x] OpenAPI + examples
- [x] llms.txt + well-known
- [x] MCP server
- [x] API keys + rate limits + usage
- [x] Docker + health endpoint
- [x] DECISIONS.md + PRICING.md
