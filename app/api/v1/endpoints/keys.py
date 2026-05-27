from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key
from app.core.errors import APIError
from app.core.security import generate_api_key, hash_api_key, key_prefix
from app.core.settings import settings
from app.db.models import APIKey
from app.db.session import get_db
from app.schemas.api import APIKeyCreateRequest, APIKeyCreateResponse, APIKeyInfo

router = APIRouter(prefix="/keys", tags=["API Keys"])
optional_bearer = HTTPBearer(auto_error=False)


def _create_key_record(db: Session, body: APIKeyCreateRequest) -> tuple[APIKey, str]:
    raw = generate_api_key()
    record = APIKey(
        key_hash=hash_api_key(raw),
        key_prefix=key_prefix(raw),
        name=body.name,
        monthly_job_quota=body.monthly_job_quota or settings.DEFAULT_MONTHLY_JOB_QUOTA,
        rate_limit_rpm=body.rate_limit_rpm or settings.DEFAULT_RATE_LIMIT_RPM,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, raw


@router.post(
    "/bootstrap",
    response_model=APIKeyCreateResponse,
    summary="Bootstrap first API key (admin secret)",
)
def bootstrap_key(
    body: APIKeyCreateRequest,
    db: Session = Depends(get_db),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    if x_admin_secret != settings.ADMIN_BOOTSTRAP_SECRET:
        raise APIError("INVALID_API_KEY", "Invalid admin secret.", status_code=401)
    record, raw = _create_key_record(db, body)
    return APIKeyCreateResponse(
        id=record.id,
        api_key=raw,
        key_prefix=record.key_prefix,
        name=record.name,
        monthly_job_quota=record.monthly_job_quota,
        rate_limit_rpm=record.rate_limit_rpm,
    )


@router.post(
    "",
    response_model=APIKeyCreateResponse,
    summary="Create API key (authenticated)",
)
def create_api_key(
    body: APIKeyCreateRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
):
    record, raw = _create_key_record(db, body)
    return APIKeyCreateResponse(
        id=record.id,
        api_key=raw,
        key_prefix=record.key_prefix,
        name=record.name,
        monthly_job_quota=record.monthly_job_quota,
        rate_limit_rpm=record.rate_limit_rpm,
    )


@router.get("/me", response_model=APIKeyInfo, summary="Current API key metadata")
def get_my_key(api_key: APIKey = Depends(get_current_api_key)):
    return APIKeyInfo(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        is_active=api_key.is_active,
        monthly_job_quota=api_key.monthly_job_quota,
        jobs_used_this_month=api_key.jobs_used_this_month,
        jobs_remaining=max(0, api_key.monthly_job_quota - api_key.jobs_used_this_month),
        rate_limit_rpm=api_key.rate_limit_rpm,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[APIKeyInfo], summary="List all keys (admin)")
def list_keys(
    db: Session = Depends(get_db),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    if x_admin_secret != settings.ADMIN_BOOTSTRAP_SECRET:
        raise APIError("INVALID_API_KEY", "Invalid admin secret.", status_code=401)
    keys = db.query(APIKey).all()
    return [
        APIKeyInfo(
            id=k.id,
            key_prefix=k.key_prefix,
            name=k.name,
            is_active=k.is_active,
            monthly_job_quota=k.monthly_job_quota,
            jobs_used_this_month=k.jobs_used_this_month,
            jobs_remaining=max(0, k.monthly_job_quota - k.jobs_used_this_month),
            rate_limit_rpm=k.rate_limit_rpm,
            created_at=k.created_at,
        )
        for k in keys
    ]
