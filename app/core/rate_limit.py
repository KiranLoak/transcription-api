"""Per-key and global API rate limiting."""

from __future__ import annotations

import threading
import time

from app.core.settings import settings


class TokenBucket:
    def __init__(self, rpm: int):
        self._rpm = max(rpm, 1)
        self._tokens = float(rpm)
        self._max = float(rpm)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    @property
    def rpm(self) -> int:
        return int(self._rpm)

    def try_acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._max, self._tokens + elapsed * (self._rpm / 60.0))
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


_global_bucket = TokenBucket(settings.GLOBAL_RATE_LIMIT_RPM)
_key_buckets: dict[str, TokenBucket] = {}
_buckets_lock = threading.Lock()


def configure_key_bucket(key_id: str, rpm: int) -> None:
    with _buckets_lock:
        _key_buckets[key_id] = TokenBucket(rpm)


def check_rate_limit(key_id: str, rpm: int | None = None) -> bool:
    if not _global_bucket.try_acquire():
        return False
    with _buckets_lock:
        if key_id not in _key_buckets:
            _key_buckets[key_id] = TokenBucket(rpm or settings.DEFAULT_RATE_LIMIT_RPM)
        elif rpm is not None and _key_buckets[key_id].rpm != rpm:
            # Rare: only update if key’s configured RPM changes.
            _key_buckets[key_id] = TokenBucket(rpm)

        bucket = _key_buckets[key_id]
    return bucket.try_acquire()
