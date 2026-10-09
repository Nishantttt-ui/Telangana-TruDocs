"""
Abuse protection that every tool needs, in three independent layers:

  1. Per-IP request rate    -> `limiter` (slowapi) + @limiter.limit("10/minute") on routes
  2. Per-IP in-flight cap   -> PortalGate(per_ip=...)   (one visitor can't hog every slot)
  3. Global portal cap      -> PortalGate(max_concurrent=...)  (protects the government
                               portal AND our own workers; excess gets a clean 503)

Why all three: a per-minute limit alone doesn't stop 10 slow requests from tying up
10 workers, and nothing per-IP stops 500 different IPs from hammering one portal.

CLIENT IP — the usual silent failure. Behind a load balancer (Cloud Run, nginx, ALB)
every request's socket peer is the balancer, so a naive limiter sees ONE client and
throttles everybody together. Behind a proxy you must read X-Forwarded-For — but only
the entry your own proxy appended; the left side is attacker-controlled.
    TRUST_PROXY_HOPS=0  (default) use the socket peer. Safe, but wrong behind a proxy.
    TRUST_PROXY_HOPS=1  one trusted proxy in front: use the last X-Forwarded-For entry.
Verify the right number after first deploy by logging the header (SKILL.md §11).

MULTI-INSTANCE — the default limiter store is in-memory, per process: with 4 instances
the effective limit is 4x. Set RATE_LIMIT_STORAGE=redis://host:6379 to share counters.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

TOO_MANY = "Too many requests. Please wait and try again."


def client_ip(request: Request, trusted_hops: Optional[int] = None) -> str:
    hops = int(os.getenv("TRUST_PROXY_HOPS", "0")) if trusted_hops is None else trusted_hops
    peer = request.client.host if request.client else "unknown"
    if hops > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
        # Header shorter than the configured hop count = misconfiguration or direct hit;
        # don't trust it.
    return peer


def make_limiter(default_limits: Optional[list[str]] = None) -> Limiter:
    return Limiter(
        key_func=client_ip,
        storage_uri=os.getenv("RATE_LIMIT_STORAGE", "memory://"),
        default_limits=default_limits or [],
    )


def install(app, limiter: Limiter) -> None:
    """Attach the limiter and a JSON 429 the frontend's friendly-error layer understands."""
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _too_many(request, exc):
        return JSONResponse({"detail": TOO_MANY}, status_code=429, headers={"Retry-After": "60"})


class PortalGate:
    """
    Bounded concurrency to one upstream portal.

        gate = PortalGate("bbmp", max_concurrent=6, per_ip=2)

        @router.post("/api/bbmp/receipt")
        async def receipt(request: Request, ...):
            async with gate.slot(request):
                return await asyncio.to_thread(blocking_portal_call, ...)

    Use it around the part that talks to the portal, not around cheap validation.
    Waiting callers queue for up to `queue_timeout` seconds, then get 503 — better a
    quick "busy, retry" than a request that hangs until the browser gives up.
    """

    def __init__(self, name: str, max_concurrent: int = 6, per_ip: int = 2,
                 queue_timeout: float = 5.0, busy_message: Optional[str] = None):
        self.name = name
        self.max_concurrent = max_concurrent
        self.per_ip = per_ip
        self.queue_timeout = queue_timeout
        self.busy_message = busy_message or "The records service is busy. Please try again shortly."
        self._sem: Optional[asyncio.Semaphore] = None     # created lazily inside the running loop
        self._per_ip_count: dict[str, int] = {}
        self.in_flight = 0
        self.rejected_busy = 0
        self.rejected_ip = 0

    def _semaphore(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.max_concurrent)
        return self._sem

    @asynccontextmanager
    async def slot(self, request: Request):
        ip = client_ip(request)
        if self._per_ip_count.get(ip, 0) >= self.per_ip:
            self.rejected_ip += 1
            raise HTTPException(429, TOO_MANY, headers={"Retry-After": "10"})
        self._per_ip_count[ip] = self._per_ip_count.get(ip, 0) + 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(self._semaphore().acquire(), self.queue_timeout)
                acquired = True
            except asyncio.TimeoutError:
                self.rejected_busy += 1
                raise HTTPException(503, self.busy_message, headers={"Retry-After": "10"})
            self.in_flight += 1
            yield
        finally:
            if acquired:
                self.in_flight -= 1
                self._semaphore().release()
            left = self._per_ip_count.get(ip, 1) - 1
            if left <= 0:
                self._per_ip_count.pop(ip, None)
            else:
                self._per_ip_count[ip] = left

    def stats(self) -> dict:
        return {"in_flight": self.in_flight, "max_concurrent": self.max_concurrent,
                "rejected_busy": self.rejected_busy, "rejected_ip": self.rejected_ip}
