"""Quota accounting."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import APIKey, JobStatus, TranscriptionJob, UsageRecord


def increment_job_quota(db: Session, api_key: APIKey) -> None:
    api_key.jobs_used_this_month += 1
    db.add(api_key)
    db.commit()


def get_usage_summary(db: Session, api_key: APIKey) -> dict:
    jobs = db.query(TranscriptionJob).filter(TranscriptionJob.api_key_id == api_key.id)
    completed = jobs.filter(TranscriptionJob.status == JobStatus.COMPLETED.value).count()
    failed = jobs.filter(TranscriptionJob.status == JobStatus.FAILED.value).count()
    total = jobs.count()
    billed = (
        db.query(UsageRecord)
        .filter(UsageRecord.api_key_id == api_key.id)
        .with_entities(UsageRecord.cost_usd)
        .all()
    )
    total_usd = sum(r[0] for r in billed) if billed else 0.0
    return {
        "period_start": api_key.quota_reset_at,
        "jobs_submitted": total,
        "jobs_completed": completed,
        "jobs_failed": failed,
        "monthly_job_quota": api_key.monthly_job_quota,
        "jobs_remaining": max(0, api_key.monthly_job_quota - api_key.jobs_used_this_month),
        "total_billed_usd": round(total_usd, 4),
    }
