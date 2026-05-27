# Pricing model

## Upstream cost (per short video ~30s)

| Stage | Service | Approx. cost |
|-------|---------|--------------|
| Language detection | Whisper tiny (local) | $0.00 |
| Diarization | Chirp 3 | ~$0.008 |
| Transcription | Gemini 2.5 Flash | ~$0.01–0.02 |
| Fallback | Gemini 2.5 Pro | ~$0.05–0.08 |

**Total upstream:** ~$0.02–0.08 per video.

## Competitor reference

| Provider | Model |
|----------|--------|
| Deepgram | ~$0.0043/min (Nova) |
| AssemblyAI | ~$0.00025/s core + diarization add-ons |
| Google STT Chirp | ~$0.016/min |

## Our public pricing

| Tier | Price | Included |
|------|-------|----------|
| Default | **$0.05 / job** | 500 jobs/month, 30 RPM |
| High volume | Custom | Higher quota, negotiated RPM |

We bill **per completed job** (1 billed unit), not per minute, to keep agent integration simple. Actual pipeline cost is tracked in `pipeline_cost_usd` on each job.

## Sustainability

At $0.05/job with ~$0.04 average upstream cost → ~20% gross margin before infra. Pro fallbacks reduce margin; rate limits protect Gemini (~15k RPM) and Chirp quotas.

## Programmatic usage

`GET /api/v1/usage` returns `jobs_remaining`, `total_billed_usd`, and `estimated_cost_per_job_usd`.
