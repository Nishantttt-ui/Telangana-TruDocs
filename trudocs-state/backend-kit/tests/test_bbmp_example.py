"""
The worked example end to end, with the portal faked. Proves the properties the playbook
promises: single-use sessions, user errors vs portal failures, maintenance mode, the cover
hook, per-IP / global caps, and — the scaling one — that the captcha-age wait does NOT
block other routes.
"""
import asyncio
import base64
import threading
import time
from io import BytesIO

import httpx
import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.kit.app_factory import create_app
from backend.kit.pdf_cover import load_registry
from backend.kit.rate_limit import PortalGate, make_limiter
from backend.kit.service_health import HealthBoard
from backend.tools.bbmp_receipt import routes, scraper

from conftest import make_pdf

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 64


class FakeSess:
    def __init__(self, app_no="1500082907"):
        self.application_no = app_no
        self.years = ["2025-2026", "2024-2025"]
        self.captcha_img = JPEG
        self.captcha_mime = "image/png"          # the portal lies about the type; the route must sniff
        self.created = time.time()


@pytest.fixture
def fake_portal(monkeypatch):
    state = {"start_delay": 0.0, "mode": "ok", "downloads": 0, "lock": threading.Lock()}

    def start_session(app_no, timeout=30):
        time.sleep(state["start_delay"])
        if state["mode"] == "down":
            raise scraper.PortalUnavailable("Form page HTTP 503")
        if app_no == "0000000000":
            raise scraper.BbmpError("Application number not found. Please check it and try again.")
        return FakeSess(app_no)

    def download_receipt(sess, year, captcha, timeout=60, hold=True):
        assert hold is False, "the route must wait asynchronously, never sleep in a worker thread"
        with state["lock"]:
            state["downloads"] += 1
        time.sleep(0.05)
        if state["mode"] == "down":
            raise scraper.PortalUnavailable("Receipt POST HTTP 502")
        if captcha == "00000":
            raise scraper.CaptchaError("Enter Valid Captcha Text")
        return make_pdf(None, 842.0, 595.0, pages=2, label="RECEIPT"), "Receipt_1_05_10_2026.pdf"

    monkeypatch.setattr(scraper, "start_session", start_session)
    monkeypatch.setattr(scraper, "download_receipt", download_receipt)
    monkeypatch.setattr(scraper, "MIN_CAPTCHA_AGE", 0)
    return state


def build(limiter=None, board=None, covers=None, gate=None):
    limiter = limiter or make_limiter()
    board = board or HealthBoard(internet_probe=lambda: True)
    board.register(routes.SERVICE, portal_name="BBMP tax portal", max_failures=2)
    router = routes.make_router(limiter, board, covers, gate)

    probe = APIRouter()                                    # another tool's SYNC route (needs a pool thread)
    @probe.get("/api/probe")
    def probe_route():
        return {"ok": True}

    app = create_app("t", limiter=limiter, board=board, gates=[router.gate], routers=[router, probe])
    return app, router, board


def captcha(c, app_no="1500082907"):
    return c.post("/api/bbmp/captcha", json={"application_no": app_no})


def receipt(c, sid, captcha_text="12345", year="2025-2026"):
    return c.post("/api/bbmp/receipt", json={"session_id": sid, "assessment_year": year, "captcha": captcha_text})


def test_full_flow_and_session_is_single_use(fake_portal):
    app, router, _ = build()
    with TestClient(app) as c:
        r = captcha(c)
        j = r.json()
        assert r.status_code == 200 and j["years"][0] == "2025-2026"
        assert j["captcha_mime"] == "image/jpeg"                            # sniffed, not the portal's claim
        assert base64.b64decode(j["captcha_b64"]) == JPEG

        ok = receipt(c, j["session_id"])
        assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf"
        assert ok.headers["content-disposition"] == 'inline; filename="Receipt_1_05_10_2026.pdf"'
        assert len(PdfReader(BytesIO(ok.content)).pages) == 2

        again = receipt(c, j["session_id"])
        assert again.status_code == 410 and "expired" in again.json()["detail"].lower()
        assert len(router.sessions) == 0


def test_input_validation_never_reaches_the_portal(fake_portal):
    app, router, _ = build()
    with TestClient(app) as c:
        assert captcha(c, "12ab").status_code == 400
        assert captcha(c, "123456789").status_code == 400
        sid = captcha(c).json()["session_id"]
        assert receipt(c, sid, "   ").status_code == 400
        assert len(router.sessions) == 1                       # an empty submit must NOT burn the captcha
        assert receipt(c, sid, "12345").status_code == 200
        assert receipt(c, "not-a-session").status_code == 410


def test_wrong_captcha_is_a_user_error_and_never_counts_toward_maintenance(fake_portal):
    app, router, board = build()
    with TestClient(app) as c:
        for _ in range(5):
            sid = captcha(c).json()["session_id"]
            r = receipt(c, sid, "00000")
            assert r.status_code == 422 and r.json()["detail"] == "Enter Valid Captcha Text"
        assert captcha(c, "0000000000").status_code == 400      # unknown number: also the user's input
        assert board.status()[routes.SERVICE]["available"] is True and board.status()[routes.SERVICE]["failures"] == 0


def test_portal_failures_502_then_maintenance_503(fake_portal):
    limiter = make_limiter()
    app, router, board = build(limiter=limiter)
    with TestClient(app) as c:
        fake_portal["mode"] = "down"
        r1, r2 = captcha(c), captcha(c)
        assert (r1.status_code, r2.status_code) == (502, 502)
        assert "not responding" in r1.json()["detail"]
        r3 = captcha(c)                                          # 2 failures reached -> maintenance mode
        assert r3.status_code == 503 and "under maintenance" in r3.json()["detail"]
        assert fake_portal["downloads"] == 0
        fake_portal["mode"] = "ok"
        board.success(routes.SERVICE)                            # what the background checker does
        assert captcha(c).status_code == 200


def test_cover_is_applied_when_configured_for_the_service(fake_portal, tmp_path):
    import json
    make_pdf(tmp_path / "cover.pdf", 842.0, 595.0, label="COVER")
    (tmp_path / "covers.json").write_text(json.dumps({"services": {
        routes.SERVICE: {"template": "cover.pdf", "fields": [{"key": "application_no", "x": 50, "top": 50, "size": 20}]}}}))
    app, _, _ = build(covers=load_registry(tmp_path / "covers.json"))
    with TestClient(app) as c:
        out = receipt(c, captcha(c).json()["session_id"])
        r = PdfReader(BytesIO(out.content))
        assert len(r.pages) == 3                                # cover + 2 receipt pages
        assert "COVER" in r.pages[0].extract_text() and "1500082907" in r.pages[0].extract_text()


def test_rate_limit_applies_per_route(fake_portal):
    app, _, _ = build()
    with TestClient(app) as c:
        codes = [captcha(c).status_code for _ in range(12)]
        assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


def test_per_ip_gate_blocks_a_visitor_opening_many_portal_sessions_at_once(fake_portal):
    fake_portal["start_delay"] = 0.4
    gate = PortalGate("bbmp_receipt", max_concurrent=10, per_ip=1, queue_timeout=0.2)
    app, _, _ = build(gate=gate)

    async def main():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=30) as c:
            rs = await asyncio.gather(*[c.post("/api/bbmp/captcha", json={"application_no": "1500082907"}) for _ in range(3)])
            return sorted(r.status_code for r in rs)
    assert asyncio.run(main()) == [200, 429, 429]


def test_the_captcha_age_wait_does_not_block_other_routes(fake_portal, monkeypatch):
    """
    60 fast typists wait out MIN_CAPTCHA_AGE at the same moment (more than FastAPI's 40-thread
    pool). Another tool's sync route must still answer instantly — the wait is an async sleep,
    not a thread parked in time.sleep().
    """
    monkeypatch.setattr(scraper, "MIN_CAPTCHA_AGE", 1.5)
    gate = PortalGate("bbmp_receipt", max_concurrent=100, per_ip=1000, queue_timeout=5)
    limiter = make_limiter()
    limiter.enabled = False                                      # this test is about threads, not limits
    app, router, _ = build(limiter=limiter, gate=gate)

    async def main():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=30) as c:
            sids = [(await c.post("/api/bbmp/captcha", json={"application_no": "1500082907"})).json()["session_id"]
                    for _ in range(60)]
            t0 = time.perf_counter()
            held = [asyncio.create_task(c.post("/api/bbmp/receipt", json={
                "session_id": s, "assessment_year": "2025-2026", "captcha": "12345"})) for s in sids]
            await asyncio.sleep(0.4)                             # everyone is inside the wait now
            t1 = time.perf_counter()
            probe = await c.get("/api/probe")
            probe_ms = (time.perf_counter() - t1) * 1000
            results = await asyncio.gather(*held)
            return probe.status_code, probe_ms, [r.status_code for r in results], time.perf_counter() - t0

    status, probe_ms, codes, total = asyncio.run(main())
    assert status == 200 and probe_ms < 250, f"other route took {probe_ms:.0f} ms while 60 submits waited"
    assert codes == [200] * 60
    assert total < 4.0                                            # waits overlapped; they did not queue up serially
