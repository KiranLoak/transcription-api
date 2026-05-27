from __future__ import annotations

from unittest.mock import patch


def _bootstrap(client):
    r = client.post(
        "/api/v1/keys/bootstrap",
        json={"name": "test"},
        headers={"X-Admin-Secret": "test-admin"},
    )
    assert r.status_code == 200
    return r.json()["api_key"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()


def test_bootstrap_and_usage(client):
    key = _bootstrap(client)
    r = client.get("/api/v1/usage", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    body = r.json()
    assert body["monthly_job_quota"] >= 1
    assert "jobs_remaining" in body


def test_submit_url_job(client):
    key = _bootstrap(client)
    with patch("app.services.worker.enqueue_job"):
        r = client.post(
            "/api/v1/transcriptions/url",
            json={"url": "https://example.com/video.mp4"},
            headers={"Authorization": f"Bearer {key}"},
        )
    assert r.status_code == 202
    assert "job_id" in r.json()


def test_invalid_key(client):
    r = client.get("/api/v1/usage", headers={"Authorization": "Bearer tx_invalid"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_API_KEY"


def test_llms_txt(client):
    r = client.get("/llms.txt")
    assert r.status_code == 200
    assert "Transcription API" in r.text


def test_well_known(client):
    r = client.get("/.well-known/agent.json")
    assert r.status_code == 200
    assert r.json()["openapi"] == "/openapi.json"
