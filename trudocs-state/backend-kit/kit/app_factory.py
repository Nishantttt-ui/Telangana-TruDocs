"""
app_factory — one place that wires the cross-cutting parts, so every state's main.py is
a dozen lines and behaves the same.

    from backend.kit.app_factory import create_app
    from backend.kit.rate_limit import make_limiter
    from backend.kit.service_health import HealthBoard
    from backend.tools.bbmp_receipt.routes import make_router

    limiter = make_limiter()
    board   = HealthBoard()
    app = create_app("TruDocs <State>", limiter=limiter, board=board,
                     routers=[make_router(limiter, board)],
                     frontend_dist="frontend-v2/dist")

What it adds:
  * rate-limit install + JSON 429
  * /api/health (liveness + per-portal status + memory) and /api/ready
  * one access-log line per request (method, path, status, ms, ip, request id) — it
    deliberately logs NO query string or body: those carry application numbers, party
    names and captcha text
  * the built React app at "/" (mounted last so /api/* wins)
  * startup hooks that can be switched off with SKIP_STARTUP=1

SKIP_STARTUP matters for development and tests: anything slow or with side effects at
boot (logging in to a portal, warming sessions, loading a big index) belongs in a startup
hook, so `SKIP_STARTUP=1` gives a fast, side-effect-free app. In the Karnataka repo that
logic runs at import time and a plain `import backend.main` triggers a real Kaveri login.
"""

import asyncio
import inspect
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Iterable, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .rate_limit import client_ip, install as install_limiter

log = logging.getLogger("trudocs.access")


def _configure_logging() -> None:
    """
    Make every `trudocs.*` logger (access log, health, covers, tools) visible under uvicorn.
    Python's default is WARNING with no handler, so without this the INFO access lines —
    your only record of rate-limit hits and portal failures — silently vanish. Skipped when
    the host app already configured logging (root has handlers: pytest, gunicorn, your own).
    LOG_LEVEL env overrides the level (default INFO).
    """
    base = logging.getLogger("trudocs")
    base.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    if not base.handlers and not logging.getLogger().handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        base.addHandler(h)


def create_app(
    title: str,
    *,
    limiter=None,
    board=None,                       # HealthBoard
    gates: Iterable = (),             # PortalGate instances, shown in /api/health
    routers: Iterable = (),
    frontend_dist: Optional[str] = None,
    startup_hooks: Iterable[Callable] = (),
) -> FastAPI:
    _configure_logging()
    state = {"ready": False}
    hooks = list(startup_hooks)
    gates = list(gates)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bg = []
        if os.getenv("SKIP_STARTUP") != "1":
            for hook in hooks:
                res = hook()
                if inspect.isawaitable(res):
                    await res
            if board is not None:
                bg.append(asyncio.create_task(board.checker()))
        state["ready"] = True
        try:
            yield
        finally:
            for t in bg:
                t.cancel()

    app = FastAPI(title=title, lifespan=lifespan)

    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:           # same-origin deployment (API + built frontend together) needs no CORS at all
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    if limiter is not None:
        install_limiter(app, limiter)

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = uuid.uuid4().hex[:8]
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "same-origin")
            return response
        finally:
            if request.url.path.startswith("/api/"):
                log.info("%s %s %s %.0fms ip=%s rid=%s", request.method, request.url.path,
                         status, (time.perf_counter() - t0) * 1000, client_ip(request), rid)

    @app.get("/api/health")
    def health(request: Request):
        info = {"status": "ok", "ready": state["ready"]}
        # How the limiter sees THIS caller. Hit /api/health from your own machine after the
        # first deploy: "client_ip" must be your real public IP. If it is a Google/AWS/
        # nginx address, TRUST_PROXY_HOPS is wrong and everyone shares one rate limit.
        info["client_ip"] = client_ip(request)
        info["x_forwarded_for"] = request.headers.get("x-forwarded-for")
        if board is not None:
            info["services"] = board.status()
        if gates:
            info["gates"] = {g.name: g.stats() for g in gates}
        try:
            import psutil
            info["rss_mb"] = round(psutil.Process().memory_info().rss / 1e6)
        except Exception:
            pass
        return info

    @app.get("/api/ready")
    def ready():
        if not state["ready"]:
            return JSONResponse({"ready": False}, status_code=503)
        return {"ready": True}

    for r in routers:
        app.include_router(r)

    if frontend_dist and Path(frontend_dist).is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app
