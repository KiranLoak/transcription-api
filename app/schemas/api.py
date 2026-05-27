"""API request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from schemas import TranscriptionResult


class JobSubmitUrlRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description="Public HTTP(S) URL to a video or audio file (max ~100MB).",
        examples=["https://storage.googleapis.com/demo/sample.mp4"],
    )
    webhook_url: HttpUrl | None = Field(
        default=None,
        description="Optional callback URL POSTed when the job completes or fails.",
    )
    model: str | None = Field(
        default=None,
        description="Force Gemini model (skips diarization when set).",
        examples=["gemini-2.5-pro"],
    )


class JobSubmitResponse(BaseModel):
    job_id: uuid.UUID
    status: Literal["pending"] = "pending"
    status_url: str = Field(..., description="Poll this URL until status is completed.")
    message: str = "Job accepted. Poll status_url every 2-5 seconds."


class JobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: Literal["pending", "processing", "completed", "failed"]
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: dict[str, Any] | None = None
    result_url: str | None = Field(
        default=None,
        description="Present when status=completed; fetch full TranscriptionResult.",
    )


class JobResultResponse(BaseModel):
    job_id: uuid.UUID
    status: Literal["completed"]
    result: TranscriptionResult
    pipeline_cost_usd: float | None = None


class APIKeyCreateRequest(BaseModel):
    name: str = Field(default="agent-key", max_length=255)
    monthly_job_quota: int | None = Field(default=None, ge=1, le=100000)
    rate_limit_rpm: int | None = Field(default=None, ge=1, le=1000)


class APIKeyCreateResponse(BaseModel):
    id: uuid.UUID
    api_key: str = Field(..., description="Shown once. Store securely.")
    key_prefix: str
    name: str
    monthly_job_quota: int
    rate_limit_rpm: int


class APIKeyInfo(BaseModel):
    id: uuid.UUID
    key_prefix: str
    name: str
    is_active: bool
    monthly_job_quota: int
    jobs_used_this_month: int
    jobs_remaining: int
    rate_limit_rpm: int
    created_at: datetime


class UsageResponse(BaseModel):
    period_start: datetime
    jobs_submitted: int
    jobs_completed: int
    jobs_failed: int
    monthly_job_quota: int
    jobs_remaining: int
    total_billed_usd: float
    estimated_cost_per_job_usd: float
