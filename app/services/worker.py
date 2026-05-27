"""Background transcription worker."""

from __future__ import annotations

import logging
import pathlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from app.core.errors import error_body
from app.core.settings import settings
from app.db.models import JobStatus, TranscriptionJob, UsageRecord
from app.db.session import SessionLocal
from config import usage_tracker

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=settings.WORKER_POOL_SIZE)


def _classify_pipeline_error(exc: Exception) -> dict:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "quota" in msg:
        code = "UPSTREAM_GEMINI_ERROR" if "gemini" in msg or "vertex" in msg else "UPSTREAM_CHIRP3_ERROR"
        return error_body(
            code,
            str(exc),
            retryable=True,
            suggested_action="Retry with exponential backoff.",
        )["error"]
    if "speech" in msg or "chirp" in msg or "diar" in msg:
        return error_body(
            "UPSTREAM_CHIRP3_ERROR",
            str(exc),
            retryable=True,
            suggested_action="Verify audio is valid; retry.",
        )["error"]
    if "gemini" in msg or "vertex" in msg or "json" in msg:
        return error_body(
            "UPSTREAM_GEMINI_ERROR",
            str(exc),
            retryable=True,
            suggested_action="Retry; pipeline may fall back to Pro model.",
        )["error"]
    return error_body(
        "PIPELINE_ERROR",
        str(exc),
        retryable=True,
        suggested_action="Retry once; contact support if persistent.",
    )["error"]


def _notify_webhook(job: TranscriptionJob) -> None:
    if not job.webhook_url:
        return
    payload = {
        "job_id": str(job.id),
        "status": job.status,
        "error": job.error,
    }
    if job.status == JobStatus.COMPLETED.value and job.result:
        payload["result"] = job.result
    try:
        httpx.post(str(job.webhook_url), json=payload, timeout=15.0)
    except Exception as exc:
        logger.warning("Webhook failed for job %s: %s", job.id, exc)


def _run_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        db.close()
        return

    job.status = JobStatus.PROCESSING.value
    db.commit()

    usage_tracker.reset()
    try:
        from transcribe import transcribe

        if job.file_path:
            result = transcribe(input_path=job.file_path)
        elif job.input_url:
            result = transcribe(url=job.input_url)
        else:
            raise ValueError("Job has no input source")

        summary = usage_tracker.summary()
        job.result = result
        job.status = JobStatus.COMPLETED.value
        job.pipeline_cost_usd = summary.get("total_cost_usd", settings.COST_PER_JOB_USD)
        job.completed_at = datetime.now(timezone.utc)

        record = UsageRecord(
            api_key_id=job.api_key_id,
            job_id=job.id,
            provider="pipeline",
            model="whisper+chirp3+gemini",
            cost_usd=job.pipeline_cost_usd or settings.COST_PER_JOB_USD,
            billed_units=1.0,
        )
        db.add(record)

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        job.status = JobStatus.FAILED.value
        job.error = _classify_pipeline_error(exc)
        job.completed_at = datetime.now(timezone.utc)
    finally:
        db.commit()
        _notify_webhook(job)
        if job.file_path:
            p = pathlib.Path(job.file_path)
            if p.exists() and str(p).startswith(settings.UPLOAD_DIR):
                try:
                    p.unlink()
                except OSError:
                    pass
        db.close()


def enqueue_job(job_id: uuid.UUID) -> None:
    _executor.submit(_run_job, job_id)
