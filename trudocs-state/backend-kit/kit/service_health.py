"""
Maintenance-mode tracker — generalised from the Karnataka backend.

Government portals go down, often for hours. Without this, every user request hits a dead
portal, waits for a timeout, and the portal-facing workers all get stuck. With it:

    N consecutive failures -> the service is marked "under maintenance" for `lockout_secs`
    -> requests get an immediate friendly 503 instead of a slow failure
    -> a background checker pings the portal and clears the flag as soon as it's back
    -> failures are NOT counted when OUR network is down (otherwise one Wi-Fi blip locks
       every tool out for 45 minutes)

    board = HealthBoard()
    board.register("bbmp", portal_name="BBMP tax portal", ping_url="https://bbmptax.karnataka.gov.in")

    board.ensure_available("bbmp")          # at the top of a route: raises 503 if locked out
    try: ...portal call...; board.success("bbmp")
    except PortalDown as e: board.failure("bbmp", e); raise

Only count failures that mean "the portal is down" (timeouts, 5xx, connection errors).
A wrong captcha or an unknown application number is the USER's error — never count it.
"""

import asyncio
import logging
import math
import socket
import time
import threading
import urllib.request
from typing import Callable, Optional

from fastapi import HTTPException

log = logging.getLogger("trudocs.health")


def internet_is_up(hosts=(("1.1.1.1", 53), ("8.8.8.8", 53)), timeout: float = 3.0) -> bool:
    for host, port in hosts:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


class ServiceHealth:
    def __init__(self, name: str, max_failures: int = 5, lockout_secs: int = 2700,
                 clock: Callable[[], float] = time.time):
        self.name = name
        self.max_failures = max_failures
        self.lockout_secs = lockout_secs
        self._clock = clock
        self.failures = 0
        self.unavailable_since = 0.0
        self._lock = threading.Lock()

    def _available_locked(self) -> bool:
        if self.unavailable_since == 0:
            return True
        if self._clock() - self.unavailable_since >= self.lockout_secs:
            self.failures = 0
            self.unavailable_since = 0.0
            log.info("%s auto-recovered after lockout", self.name)
            return True
        return False

    def is_available(self) -> bool:
        with self._lock:
            return self._available_locked()

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.max_failures and self.unavailable_since == 0:
                self.unavailable_since = self._clock()
                log.warning("%s UNAVAILABLE after %d failures", self.name, self.failures)

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.unavailable_since = 0.0

    def minutes_until_retry(self) -> int:
        with self._lock:
            return self._mins_locked()

    def _mins_locked(self) -> int:
        if self.unavailable_since == 0:
            return 0
        return max(1, math.ceil((self.lockout_secs - (self._clock() - self.unavailable_since)) / 60))

    def status(self) -> dict:
        with self._lock:
            return {"available": self._available_locked(), "failures": self.failures,
                    "mins_until_retry": self._mins_locked()}


class HealthBoard:
    def __init__(self, internet_probe: Callable[[], bool] = internet_is_up):
        self._svc: dict[str, ServiceHealth] = {}
        self._ping: dict[str, str] = {}
        self._portal: dict[str, str] = {}
        self._internet_up = internet_probe

    def register(self, name: str, portal_name: str, ping_url: str = "", **kw) -> ServiceHealth:
        self._svc[name] = ServiceHealth(name, **kw)
        self._portal[name] = portal_name
        self._ping[name] = ping_url
        return self._svc[name]

    def maintenance_message(self, name: str) -> str:
        mins = self._svc[name].minutes_until_retry()
        return f"{self._portal[name]} is currently under maintenance. Please try again in {mins} minutes."

    def ensure_available(self, name: str) -> None:
        if not self._svc[name].is_available():
            raise HTTPException(503, self.maintenance_message(name))

    def failure(self, name: str, error: Optional[BaseException] = None) -> None:
        if not self._internet_up():
            log.warning("%s failed but our internet is down - not counting: %s", name, error)
            return
        self._svc[name].record_failure()
        s = self._svc[name]
        log.warning("%s failure %d/%d: %s", name, s.failures, s.max_failures, error)

    def success(self, name: str) -> None:
        self._svc[name].record_success()

    def status(self) -> dict:
        return {n: s.status() for n, s in self._svc.items()}

    async def checker(self, interval: float = 300.0) -> None:
        """Background task: ping locked-out portals and clear them when they answer."""
        while True:
            await asyncio.sleep(interval)
            for name, svc in self._svc.items():
                if svc.unavailable_since > 0 and not svc.is_available():
                    url = self._ping.get(name)
                    if url and await asyncio.to_thread(self._internet_up) and await asyncio.to_thread(_ping, url):
                        svc.record_success()
                        log.info("%s back online - maintenance cleared", name)


def _ping(url: str, timeout: float = 8.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False
