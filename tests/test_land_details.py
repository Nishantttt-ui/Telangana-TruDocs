"""Land Details Search (Pattadar) checks — survey search and the new passbook search.
No network: the portal is never called, and the fixtures use synthetic data only
(never a real person's details).

Run from the repo root:  python -m pytest tests
"""
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.errors import BAD_INPUT, CAPTCHA_FAILED, NOT_FOUND, PORTAL_DOWN, PortalError
from backend.routers import pattadar_passbook as router_mod
from backend.scrapers.pattadar_passbook import client

# The portal returns each field as <strong>Label</strong><br>Value. Synthetic values.
RESULT_HTML = """<!DOCTYPE html><html><body>
<div class="col"><strong>District</strong><br> Rangareddy </div>
<div class="col"><strong>Pattadar / Authorised Person Name</strong><br> TEST OWNER </div>
<div class="col"><strong>Khata Number</strong><br> 337 </div>
<div class="col"><strong>Land Status</strong><br> Not Prohibited </div>
<div class="col"><strong>Total Extent (Ac. Gts)</strong><br> 1.20 </div>
</body></html>"""

NO_RECORD_HTML = "<html><body><h3>No Record Found</h3></body></html>"
ERROR_HTML = "<html><body>Something went wrong... Click Here to go to home page</body></html>"


def _raises(user_message, fn, *args, **kwargs):
    with pytest.raises(PortalError) as info:
        fn(*args, **kwargs)
    assert info.value.user_message == user_message


def test_parses_the_field_list():
    r = client._parse_result(RESULT_HTML)
    assert r["found"] is True
    assert r["raw_fields"]["Land Status"] == "Not Prohibited"
    assert r["raw_fields"]["Pattadar / Authorised Person Name"] == "TEST OWNER"
    assert "District" in r["raw_fields"]


def test_no_record_and_error_pages():
    _raises(NOT_FOUND, client._parse_result, NO_RECORD_HTML)
    _raises(PORTAL_DOWN, client._parse_result, ERROR_HTML)


def test_passbook_inputs_checked_before_the_portal():
    _raises(BAD_INPUT, client.fetch_pattadar_by_passbook, passbook_no="", aadhaar_last4="1234")
    _raises(BAD_INPUT, client.fetch_pattadar_by_passbook, passbook_no="123", aadhaar_last4="12")      # not 4 digits
    _raises(BAD_INPUT, client.fetch_pattadar_by_passbook, passbook_no="123", aadhaar_last4="12ab")    # not digits
    _raises(BAD_INPUT, client.fetch_pattadar_by_passbook, passbook_no="has space", aadhaar_last4="1234")
    _raises(BAD_INPUT, client.fetch_pattadar_by_passbook, passbook_no="X" * 13, aadhaar_last4="1234")  # too long


def test_passbook_request_uses_ppb_mode_and_hides_aadhaar(monkeypatch):
    captured = {}

    def fake_search(_client, build_request, _max):
        captured["url"], captured["body"] = build_request("ENC_CAPTCHA")
        return {"source": "pattadar_passbook", "sections": [], "raw_fields": {"Land Status": "ok"}, "found": True}

    monkeypatch.setattr(client, "_search_with_captcha", fake_search)
    monkeypatch.setattr(client, "_get", lambda *a, **k: None)
    client.fetch_pattadar_by_passbook(passbook_no="PPB123", aadhaar_last4="1234")
    assert captured["url"]["flagval"] == "ppb"
    assert captured["url"]["ppbType"] == client._PPB_TYPE_AADHAAR
    assert captured["url"]["ppbno"] == "PPB123"
    # the raw Aadhaar digits are encrypted, never sent in the clear
    assert captured["url"]["adhrfour"] != "1234"
    assert "1234" not in captured["body"].values()


def test_passbook_empty_reply_is_no_record(monkeypatch):
    monkeypatch.setattr(client, "_get", lambda *a, **k: None)
    monkeypatch.setattr(client, "_search_with_captcha",
                        lambda *a: {"source": "pattadar_passbook", "sections": [], "raw_fields": {}, "found": False})
    _raises(NOT_FOUND, client.fetch_pattadar_by_passbook, passbook_no="PPB123", aadhaar_last4="1234")


def test_captcha_loop_retries_then_gives_up(monkeypatch):
    # Every attempt returns the portal's generic error page -> CAPTCHA_FAILED after N tries.
    attempts = []

    class Reply:
        def __init__(self, text, content=b"img"):
            self.text, self.content = text, content
        def raise_for_status(self):
            pass

    class FakeClient:
        def post(self, path, *a, **k):
            if "checkcaptcha" in path:
                return Reply("true")
            attempts.append(1)
            return Reply("Something went wrong... go to home page")

    monkeypatch.setattr(client, "_get", lambda c, p: Reply("", b"imgbytes"))
    monkeypatch.setattr(client, "solve_captcha", lambda b: "ABCDE")
    monkeypatch.setattr(client._throttle, "wait", lambda: None)
    _raises(CAPTCHA_FAILED, client._search_with_captcha, FakeClient(), lambda cap: ({}, {}), 3)
    assert len(attempts) == 3


def _app():
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


@pytest.mark.parametrize("message, status", [
    (NOT_FOUND, 404), (BAD_INPUT, 400), (CAPTCHA_FAILED, 503), (PORTAL_DOWN, 502),
])
def test_routes_map_errors(monkeypatch, message, status):
    def fail(**_):
        raise PortalError(message)

    monkeypatch.setattr(client, "fetch_pattadar_by_survey", fail)
    monkeypatch.setattr(client, "fetch_pattadar_by_passbook", fail)
    c = _app()
    r1 = c.post("/api/pattadar/search", json={"district_id": "5", "mandal_id": "83", "village_id": "507004", "survey_no": "1", "khata_id": "1"})
    r2 = c.post("/api/pattadar/search-by-passbook", json={"passbook_no": "PPB123", "aadhaar_last4": "1234"})
    assert r1.status_code == status and r1.json()["detail"] == message
    assert r2.status_code == status and r2.json()["detail"] == message


def test_identical_searches_at_once_hit_the_portal_once(monkeypatch):
    calls = []

    def slow(_client, _build, _max):
        calls.append(1)
        time.sleep(0.2)
        return {"source": "pattadar_passbook", "sections": [], "raw_fields": {"Land Status": "ok"}, "found": True}

    monkeypatch.setattr(client, "_get", lambda *a, **k: None)
    monkeypatch.setattr(client, "_search_with_captcha", slow)
    args = dict(district_id="5", mandal_id="83", village_id="507004", survey_no="1/2A", khata_id="337")
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: client.fetch_pattadar_by_survey(**args), range(8)))
    assert len(calls) == 1
    assert all(r["found"] and r == results[0] for r in results)
