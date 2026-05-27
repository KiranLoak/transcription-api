"""Thread-safe token-bucket rate limiter."""

from __future__ import annotations

import os
import threading
import time

_DEFAULT_RPM = {
    "gemini": int(os.getenv("GEMINI_RPM", "15000")),
}


class RateLimiter:
    """Token-bucket rate limiter for a single (provider, model) pair."""

    def __init__(self, rpm: int) -> None:
        self._rpm = rpm
        self._interval = 60.0 / rpm
        self._tokens = float(rpm)
        self._max_tokens = float(rpm)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._max_tokens,
                    self._tokens + elapsed * (self._rpm / 60.0),
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            time.sleep(self._interval)


_limiters: dict[tuple[str, str], RateLimiter] = {}
_registry_lock = threading.Lock()


def acquire(provider: str, model: str) -> None:
    key = (provider, model)
    with _registry_lock:
        if key not in _limiters:
            rpm = _DEFAULT_RPM.get(provider, 1000)
            _limiters[key] = RateLimiter(rpm)
    _limiters[key].acquire()
