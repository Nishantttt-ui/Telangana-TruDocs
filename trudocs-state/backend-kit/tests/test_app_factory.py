import logging

import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient

from backend.kit.app_factory import create_app
from backend.kit.rate_limit import PortalGate, make_limiter
from backend.kit.service_health import HealthBoard


def router_with_ping(limiter=None, limit="100/minute"):
    r = APIRouter()
    if limiter:
        @r.get("/api/ping")
        @limiter.limit(limit)
        def ping(request: Request):
            return {"ok": True}
    else:
        @r.get("/api/ping")
        def ping():
            return {"ok": True}
    return r


def test_health_ready_headers_and_how_the_limiter_sees_the_caller():
    board = HealthBoard(); board.register("bbmp", portal_name="BBMP tax portal")
    gate = PortalGate("bbmp")
    app = create_app("t", board=board, gates=[gate], routers=[router_with_ping()])
    with TestClient(app) as c:
        h = c.get("/api/health", headers={"X-Forwarded-For": "1.2.3.4"})
        body = h.json()
        assert h.status_code == 200 and body["status"] == "ok" and body["ready"] is True
        assert body["services"]["bbmp"]["available"] is True
        assert body["gates"]["bbmp"]["max_concurrent"] == gate.max_concurrent
        assert body["client_ip"] == "testclient" and body["x_forwarded_for"] == "1.2.3.4"
        assert h.headers["x-content-type-options"] == "nosniff" and len(h.headers["x-request-id"]) == 8
        assert c.get("/api/ready").json() == {"ready": True}


def test_startup_hooks_run_unless_skip_startup(monkeypatch):
    calls = []
    async def a(): calls.append("async")
    def s(): calls.append("sync")

    monkeypatch.delenv("SKIP_STARTUP", raising=False)
    with TestClient(create_app("t", startup_hooks=[s, a])):
        pass
    assert calls == ["sync", "async"]

    calls.clear(); monkeypatch.setenv("SKIP_STARTUP", "1")
    with TestClient(create_app("t", startup_hooks=[s, a])) as c:
        assert calls == []                                   # nothing slow / side-effecting at boot
        assert c.get("/api/ready").status_code == 200        # but the app is usable immediately


def test_not_ready_until_startup_finishes(monkeypatch):
    monkeypatch.delenv("SKIP_STARTUP", raising=False)
    app = create_app("t")
    c = TestClient(app)                                      # no `with`: lifespan has not run
    assert c.get("/api/ready").status_code == 503


def test_access_log_never_contains_query_strings_or_bodies(caplog):
    app = create_app("t", routers=[router_with_ping()])
    caplog.set_level(logging.INFO, logger="trudocs.access")
    with TestClient(app) as c:
        c.get("/api/ping?application_no=1500082907&captcha=63255")
    line = " ".join(r.getMessage() for r in caplog.records)
    assert "/api/ping" in line and "200" in line and "rid=" in line
    assert "1500082907" not in line and "63255" not in line and "?" not in line


def test_429_is_json_and_installed_by_the_factory():
    limiter = make_limiter()
    app = create_app("t", limiter=limiter, routers=[router_with_ping(limiter, "1/minute")])
    with TestClient(app) as c:
        assert c.get("/api/ping").status_code == 200
        r = c.get("/api/ping")
        assert r.status_code == 429 and "Too many requests" in r.json()["detail"]


def test_cors_is_off_unless_configured(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with TestClient(create_app("t", routers=[router_with_ping()])) as c:
        r = c.get("/api/ping", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example")
    with TestClient(create_app("t", routers=[router_with_ping()])) as c:
        ok = c.get("/api/ping", headers={"Origin": "https://app.example"})
        assert ok.headers["access-control-allow-origin"] == "https://app.example"
        bad = c.get("/api/ping", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in bad.headers


def test_frontend_is_served_at_root_and_api_still_wins(tmp_path):
    (tmp_path / "index.html").write_text("<html>SPA</html>")
    app = create_app("t", routers=[router_with_ping()], frontend_dist=str(tmp_path))
    with TestClient(app) as c:
        assert "SPA" in c.get("/").text
        assert c.get("/api/ping").json() == {"ok": True}
        assert c.get("/api/health").status_code == 200


def test_missing_frontend_dist_is_not_fatal(tmp_path):
    app = create_app("t", frontend_dist=str(tmp_path / "nope"))
    with TestClient(app) as c:
        assert c.get("/api/ready").status_code == 200
