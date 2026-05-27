#!/usr/bin/env python3
"""CLI to bootstrap an API key."""

from __future__ import annotations

import argparse
import os
import sys

import httpx

DEFAULT_URL = os.getenv("TRANSCRIPTION_API_URL", "http://localhost:8000")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create transcription API key")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--admin-secret", default=os.getenv("ADMIN_BOOTSTRAP_SECRET", "local-dev-bootstrap"))
    parser.add_argument("--name", default="cli-key")
    args = parser.parse_args()

    r = httpx.post(
        f"{args.url.rstrip('/')}/api/v1/keys/bootstrap",
        json={"name": args.name},
        headers={"X-Admin-Secret": args.admin_secret},
        timeout=30.0,
    )
    if r.status_code >= 400:
        print(r.text, file=sys.stderr)
        sys.exit(1)
    data = r.json()
    print("API key (save now):", data["api_key"])
    print("Prefix:", data["key_prefix"])


if __name__ == "__main__":
    main()
