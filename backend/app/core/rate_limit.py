"""In-process sliding-window rate limiting for authentication endpoints.

Deliberately dependency-free. With more than one API process this moves to Redis or a
Postgres table; the `RateLimiter` interface stays the same.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.exceptions import RateLimitedError


class RateLimiter:
    """Allow at most `limit` hits per key within `window_seconds`."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record a hit for `key`, raising RateLimitedError once the limit is exceeded."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self._limit:
                retry_after = int(hits[0] - cutoff) + 1
                raise RateLimitedError(
                    f"Too many attempts. Please try again in {retry_after} seconds."
                )
            hits.append(now)

    def reset(self, key: str) -> None:
        """Forget a key's hits (called after a successful login)."""
        with self._lock:
            self._hits.pop(key, None)


login_limiter = RateLimiter(limit=5, window_seconds=60)
otp_request_limiter = RateLimiter(limit=3, window_seconds=300)
