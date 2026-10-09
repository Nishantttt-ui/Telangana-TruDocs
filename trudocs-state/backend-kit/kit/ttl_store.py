"""
TTLStore — bounded, thread-safe, single-use in-memory store.

Use for anything short-lived that a later request must find again:
  * a captcha session (portal cookie jar + hidden form fields + the captcha image)
  * a background job's status/result

Properties that matter in production:
  * entries expire (ttl) so abandoned captchas don't pile up
  * hard cap (max_items) — oldest evicted first — so a flood can't exhaust memory
  * pop() is single-use: a captcha is consumed by the attempt, win or lose
  * thread-safe (FastAPI runs `def` routes in a threadpool)

LIMIT: this lives in one process. With >1 worker or >1 instance, the request that
creates an entry and the request that consumes it can land on different processes.
See SKILL.md §11 for the two fixes (sticky routing, or a serialisable value + Redis).
"""

import secrets
import threading
import time
from collections import OrderedDict
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")


class TTLStore(Generic[T]):
    def __init__(self, ttl: float = 600.0, max_items: int = 500,
                 clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl
        self.max_items = max_items
        self._clock = clock
        self._items: "OrderedDict[str, tuple[float, T]]" = OrderedDict()
        self._lock = threading.Lock()

    def _purge_locked(self) -> None:
        cutoff = self._clock() - self.ttl
        while self._items:
            key, (created, _) = next(iter(self._items.items()))
            if created >= cutoff:
                break
            self._items.pop(key)

    def put(self, value: T) -> str:
        key = secrets.token_urlsafe(16)
        with self._lock:
            self._purge_locked()
            self._items[key] = (self._clock(), value)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)
        return key

    def get(self, key: str) -> Optional[T]:
        """Peek without consuming."""
        with self._lock:
            self._purge_locked()
            hit = self._items.get(key)
            return hit[1] if hit else None

    def pop(self, key: str) -> Optional[T]:
        """Take and remove (single use). None if unknown or expired."""
        with self._lock:
            self._purge_locked()
            hit = self._items.pop(key, None)
            return hit[1] if hit else None

    def __len__(self) -> int:
        with self._lock:
            self._purge_locked()
            return len(self._items)
