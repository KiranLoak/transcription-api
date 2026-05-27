"""Structured API errors for agents."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        suggested_action: str = "",
        docs_url: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.suggested_action = suggested_action
        self.docs_url = docs_url or f"/docs/errors#{code}"
        self.details = details or {}
        super().__init__(message)


def error_body(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    suggested_action: str = "",
    docs_url: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "suggested_action": suggested_action,
            "docs_url": docs_url or f"/docs/errors#{code}",
            **({"details": details} if details else {}),
        }
    }


def api_error_response(exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            exc.code,
            exc.message,
            retryable=exc.retryable,
            suggested_action=exc.suggested_action,
            docs_url=exc.docs_url,
            details=exc.details or None,
        ),
    )


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    return api_error_response(exc)


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            "HTTP_ERROR",
            str(exc.detail),
            retryable=exc.status_code >= 500,
            suggested_action="Review request parameters and retry if appropriate.",
        ),
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body(
            "VALIDATION_ERROR",
            "Request validation failed.",
            retryable=False,
            suggested_action="Fix request body or query parameters per OpenAPI schema.",
            details={"issues": exc.errors()},
        ),
    )


# Catalog for /docs/errors
ERROR_CATALOG: list[dict[str, str]] = [
    {
        "code": "INVALID_API_KEY",
        "description": "Missing or invalid Bearer API key.",
        "suggested_action": "Create a key at POST /api/v1/keys or /keys UI.",
    },
    {
        "code": "RATE_LIMIT_EXCEEDED",
        "description": "Per-key or global rate limit hit.",
        "suggested_action": "Wait and retry with exponential backoff.",
    },
    {
        "code": "QUOTA_EXCEEDED",
        "description": "Monthly job quota exhausted.",
        "suggested_action": "Upgrade plan or wait until quota resets.",
    },
    {
        "code": "FILE_TOO_LARGE",
        "description": "Upload exceeds 100MB limit.",
        "suggested_action": "Compress media or use a shorter clip.",
    },
    {
        "code": "JOB_NOT_FOUND",
        "description": "Unknown job id or wrong API key.",
        "suggested_action": "Verify job_id from submit response.",
    },
    {
        "code": "UPSTREAM_GEMINI_ERROR",
        "description": "Gemini/Vertex AI failure.",
        "suggested_action": "Retry; use retryable flag on response.",
    },
    {
        "code": "UPSTREAM_CHIRP3_ERROR",
        "description": "Google Speech Chirp 3 failure.",
        "suggested_action": "Retry; check audio format.",
    },
    {
        "code": "PIPELINE_ERROR",
        "description": "Internal transcription pipeline error.",
        "suggested_action": "Retry once; contact support if persistent.",
    },
]
