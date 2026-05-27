#!/usr/bin/env python3
"""Generate Python SDK from OpenAPI spec."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sdk" / "generated"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = ROOT / "openapi.snapshot.json"
    if not spec.exists():
        import httpx
        r = httpx.get("http://localhost:8000/openapi.json", timeout=10)
        r.raise_for_status()
        spec.write_text(r.text, encoding="utf-8")
    cmd = [
        sys.executable, "-m", "openapi_python_client", "generate",
        "--path", str(spec),
        "--output-path", str(OUT),
        "--meta", "none",
    ]
    subprocess.check_call(cmd)
    print(f"Client written to {OUT}")


if __name__ == "__main__":
    main()
