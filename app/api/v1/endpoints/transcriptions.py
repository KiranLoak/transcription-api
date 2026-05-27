from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key
from app.core.errors import APIError
from app.core.settings import settings
from app.db.models import APIKey, TranscriptionJob
from app.db.session import get_db
from app.schemas.api import JobSubmitResponse, JobSubmitUrlRequest, JobStatusResponse, JobResultResponse
from app.services.quota import increment_job_quota
from app.services.worker import enqueue_job
from schemas import TranscriptionResult

router = APIRouter(prefix="/transcriptions", tags=["Transcriptions"])


def _job_status_url(job_id: uuid.UUID) -> str:
    return f"{settings.BASE_URL}{settings.API_V1_STR}/transcriptions/{job_id}"


def _result_url(job_id: uuid.UUID) -> str:
    return f"{settings.BASE_URL}{settings.API_V1_STR}/transcriptions/{job_id}/result"


@router.post(
    "",
    response_model=JobSubmitResponse,
    status_code=202,
    summary="Submit transcription job (file upload)",
    description=(
        "Upload a video or audio file (max 100MB). Returns immediately with a job_id. "
        "Poll GET /transcriptions/{job_id} every 2-5 seconds until status is completed or failed."
    ),
)
async def submit_file(
    file: UploadFile = File(..., description="Video or audio file, max 100MB"),
    webhook_url: str | None = Form(default=None),
    model: str | None = Form(default=None),
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
):
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise APIError(
            "FILE_TOO_LARGE",
            f"File exceeds {settings.MAX_UPLOAD_BYTES // (1024*1024)}MB limit.",
            status_code=413,
            suggested_action="Compress or trim the media file.",
        )
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    dest = upload_dir / f"{uuid.uuid4()}{suffix}"
    dest.write_bytes(content)

    job = TranscriptionJob(
        file_path=str(dest),
        original_filename=file.filename,
        webhook_url=webhook_url,
        api_key_id=api_key.id,
    )
    db.add(job)
    increment_job_quota(db, api_key)
    db.commit()
    db.refresh(job)
    enqueue_job(job.id)
    return JobSubmitResponse(
        job_id=job.id,
        status_url=_job_status_url(job.id),
    )


@router.post(
    "/url",
    response_model=JobSubmitResponse,
    status_code=202,
    summary="Submit transcription job (URL)",
    description="Submit a public media URL. Same async polling flow as file upload.",
)
async def submit_url(
    body: JobSubmitUrlRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
):
    job = TranscriptionJob(
        input_url=str(body.url),
        webhook_url=str(body.webhook_url) if body.webhook_url else None,
        api_key_id=api_key.id,
    )
    db.add(job)
    increment_job_quota(db, api_key)
    db.commit()
    db.refresh(job)
    enqueue_job(job.id)
    return JobSubmitResponse(
        job_id=job.id,
        status_url=_job_status_url(job.id),
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get transcription job status",
)
def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
):
    job = (
        db.query(TranscriptionJob)
        .filter(TranscriptionJob.id == job_id, TranscriptionJob.api_key_id == api_key.id)
        .first()
    )
    if not job:
        raise APIError(
            "JOB_NOT_FOUND",
            f"Job {job_id} not found.",
            status_code=404,
            suggested_action="Use job_id from the 202 submit response.",
        )
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        error=job.error,
        result_url=_result_url(job.id) if job.status == "completed" else None,
    )


@router.get(
    "/{job_id}/result",
    response_model=JobResultResponse,
    summary="Get completed transcription result",
)
def get_job_result(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
):
    job = (
        db.query(TranscriptionJob)
        .filter(TranscriptionJob.id == job_id, TranscriptionJob.api_key_id == api_key.id)
        .first()
    )
    if not job:
        raise APIError("JOB_NOT_FOUND", f"Job {job_id} not found.", status_code=404)
    if job.status == "failed":
        raise APIError(
            "PIPELINE_ERROR",
            job.error.get("message", "Transcription failed") if job.error else "Transcription failed",
            status_code=422,
            retryable=job.error.get("retryable", True) if job.error else True,
            suggested_action=job.error.get("suggested_action", "Retry submission.") if job.error else "",
            details=job.error,
        )
    if job.status != "completed" or not job.result:
        raise APIError(
            "JOB_NOT_READY",
            f"Job status is '{job.status}'. Poll status endpoint until completed.",
            status_code=409,
            retryable=True,
            suggested_action="Poll GET /transcriptions/{job_id} every 2-5s.",
        )
    return JobResultResponse(
        job_id=job.id,
        status="completed",
        result=TranscriptionResult.model_validate(job.result),
        pipeline_cost_usd=job.pipeline_cost_usd,
    )
