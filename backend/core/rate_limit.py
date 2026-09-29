"""Per-host request throttle.

Enforces a minimum gap between successive requests to the same government
portal, shared across all callers in this process, so concurrent users can't
collectively hammer a portal that has no rate limit of its own.
"""
import threading
import time


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self.min_interval_seconds = min_interval_seconds
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def wait(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        with self._lock:
            gap = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
            if gap > 0:
                time.sleep(gap)
            self._last_request_at = time.monotonic()
