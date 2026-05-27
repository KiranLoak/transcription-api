from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key
from app.core.settings import settings
from app.db.models import APIKey
from app.db.session import get_db
from app.schemas.api import UsageResponse
from app.services.quota import get_usage_summary

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get(
    "",
    response_model=UsageResponse,
    summary="Query usage and remaining quota",
    description="Programmatic usage for agents — jobs submitted, costs, remaining monthly quota.",
)
def get_usage(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
):
    summary = get_usage_summary(db, api_key)
    return UsageResponse(
        **summary,
        estimated_cost_per_job_usd=settings.COST_PER_JOB_USD,
    )
