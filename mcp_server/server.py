"""MCP server exposing transcription API tools for AI agents."""

from __future__ import annotations

import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("TRANSCRIPTION_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("TRANSCRIPTION_API_KEY", "")

mcp = FastMCP(
    "transcription-api",
    instructions=(
        "Tools for the Agent-First Transcription API. Submit media, poll until complete, "
        "fetch structured diarized transcript. Set TRANSCRIPTION_API_URL and TRANSCRIPTION_API_KEY."
    ),
)


def _headers() -> dict[str, str]:
    if not API_KEY:
        raise ValueError("Set TRANSCRIPTION_API_KEY environment variable")
    return {"Authorization": f"Bearer {API_KEY}"}


@mcp.tool()
async def check_api_health() -> dict:
    """Verify the transcription API is alive before submitting work."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/health", timeout=10.0)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def submit_transcription_url(url: str, webhook_url: str | None = None) -> dict:
    """Submit a public video/audio URL for async transcription. Returns job_id and status_url."""
    async with httpx.AsyncClient() as client:
        body: dict = {"url": url}
        if webhook_url:
            body["webhook_url"] = webhook_url
        r = await client.post(
            f"{API_BASE}/api/v1/transcriptions/url",
            json=body,
            headers=_headers(),
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_transcription_status(job_id: str) -> dict:
    """Poll transcription job status. Stop when status is completed or failed."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_BASE}/api/v1/transcriptions/{job_id}",
            headers=_headers(),
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_transcription_result(job_id: str) -> dict:
    """Fetch full TranscriptionResult JSON when job status is completed."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_BASE}/api/v1/transcriptions/{job_id}/result",
            headers=_headers(),
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def transcribe_url_and_wait(
    url: str,
    poll_interval_seconds: float = 3.0,
    max_wait_seconds: float = 300.0,
) -> dict:
    """Submit URL, poll until done, return full result (convenience for agents)."""
    submitted = await submit_transcription_url(url)
    job_id = submitted["job_id"]
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        status = await get_transcription_status(job_id)
        if status["status"] == "completed":
            return await get_transcription_result(job_id)
        if status["status"] == "failed":
            return {"error": status.get("error"), "job_id": job_id, "status": "failed"}
        time.sleep(poll_interval_seconds)
    return {"error": "timeout", "job_id": job_id, "message": "Exceeded max_wait_seconds"}


@mcp.tool()
async def get_api_usage() -> dict:
    """Query monthly quota, jobs used, and billed USD for the API key."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{API_BASE}/api/v1/usage",
            headers=_headers(),
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


def main() -> None:
    mcp.run()
