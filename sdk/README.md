# Python SDK

## Auto-generated client

1. Start the API locally.
2. Run:

```bash
python scripts/generate_client.py
```

3. Use the generated package in `sdk/generated/`.

## Manual example (httpx)

```python
import time
import httpx

API = "http://localhost:8000"
KEY = "tx_your_key_here"
headers = {"Authorization": f"Bearer {KEY}"}

# Submit
r = httpx.post(
    f"{API}/api/v1/transcriptions/url",
    json={"url": "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"},
    headers=headers,
)
r.raise_for_status()
job_id = r.json()["job_id"]

# Poll
while True:
    s = httpx.get(f"{API}/api/v1/transcriptions/{job_id}", headers=headers).json()
    if s["status"] in ("completed", "failed"):
        break
    time.sleep(3)

# Result
result = httpx.get(f"{API}/api/v1/transcriptions/{job_id}/result", headers=headers).json()
print(result["result"]["text"])
```
