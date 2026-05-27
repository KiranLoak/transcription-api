"""FastAPI dependencies."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.rate_limit import check_rate_limit
from app.core.security import hash_api_key
from app.core.settings import settings
from app.db.models import APIKey
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def _maybe_reset_quota(key: APIKey) -> None:
    now = datetime.now(timezone.utc)
    reset_at = key.quota_reset_at
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    if now.month != reset_at.month or now.year != reset_at.year:
        key.jobs_used_this_month = 0
        key.quota_reset_at = now


def get_current_api_key(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> APIKey:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(
            "INVALID_API_KEY",
            "Missing Bearer token. Use Authorization: Bearer tx_...",
            status_code=401,
            suggested_action="Create an API key via POST /api/v1/keys or the /keys web form.",
        )
    raw = credentials.credentials
    key_hash = hash_api_key(raw)
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash, APIKey.is_active.is_(True)).first()
    if not api_key:
        raise APIError(
            "INVALID_API_KEY",
            "API key not found or inactive.",
            status_code=401,
            suggested_action="Generate a new API key.",
        )
    _maybe_reset_quota(api_key)
    if api_key.jobs_used_this_month >= api_key.monthly_job_quota:
        raise APIError(
            "QUOTA_EXCEEDED",
            f"Monthly quota of {api_key.monthly_job_quota} jobs exceeded.",
            status_code=429,
            retryable=False,
            suggested_action="Wait for monthly reset or request a higher quota.",
        )
    if not check_rate_limit(str(api_key.id), api_key.rate_limit_rpm):
        raise APIError(
            "RATE_LIMIT_EXCEEDED",
            "Rate limit exceeded for this API key or globally.",
            status_code=429,
            retryable=True,
            suggested_action="Backoff and retry after 60 seconds.",
        )
    return api_key
