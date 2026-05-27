from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import SessionLocal

router = APIRouter(tags=["System"])


@router.get("/health", summary="Liveness probe")
@router.get("/status", summary="Alias for liveness probe")
def health_check():
    """Agents should call this before submitting work."""
    checks = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "database": False,
        "gcp_configured": bool(settings.GCP_PROJECT_ID and os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
    }
    try:
        db: Session = SessionLocal()
        db.execute(text("SELECT 1"))
        checks["database"] = True
        db.close()
    except Exception:
        checks["database"] = False

    healthy = checks["ffmpeg"] and checks["database"]
    return {
        "status": "healthy" if healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "docs": f"{settings.BASE_URL}/docs",
        "openapi": f"{settings.BASE_URL}/openapi.json",
    }
