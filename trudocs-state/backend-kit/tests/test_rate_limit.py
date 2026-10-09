import asyncio

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from backend.kit.rate_limit import PortalGate, client_ip, install, make_limiter


def fake_request(peer="10.0.0.9", xff=None):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return StarletteRequest({"type": "http", "headers": headers, "client": (peer, 1234), "method": "GET", "path": "/"})


# ── client_ip ────────────────────────────────────────────────────────────────

def test_xff_is_ignored_by_default_so_it_cannot_be_spoofed():
    assert client_ip(fake_request("10.0.0.9", "1.2.3.4"), trusted_hops=0) == "10.0.0.9"


def test_one_trusted_proxy_uses_the_entry_it_appended_not_the_spoofable_left_side():
    # attacker sent "6.6.6.6"; our load balancer appended the real address
    assert client_ip(fake_request("10.0.0.9", "6.6.6.6, 203.0.113.7"), trusted_hops=1) == "203.0.113.7"


def test_two_trusted_proxies():
    assert client_ip(fake_request("10.0.0.9", "6.6.6.6, 203.0.113.7, 35.1.1.1"), trusted_hops=2) == "203.0.113.7"


def test_header_shorter_than_hops_falls_back_to_peer():
    assert client_ip(fake_request("10.0.0.9", "1.2.3.4"), trusted_hops=2) == "10.0.0.9"
    assert client_ip(fake_request("10.0.0.9", None), trusted_hops=1) == "10.0.0.9"


def test_env_setting_is_read(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HOPS", "1")
    assert client_ip(fake_request("10.0.0.9", "203.0.113.7")) == "203.0.113.7"


# ── limiter ──────────────────────────────────────────────────────────────────

def make_app(limit="2/minute"):
    limiter = make_limiter()
    app = FastAPI(); install(app, limiter)

    @app.get("/ping")
    @limiter.limit(limit)
    def ping(request: Request):
        return {"ok": True}
    return app


def test_429_after_the_limit_with_json_detail_and_retry_after():
    c = TestClient(make_app("2/minute"))
    assert [c.get("/ping").status_code for _ in range(3)] == [200, 200, 429]
    r = c.get("/ping")
    assert r.json() == {"detail": "Too many requests. Please wait and try again."}
    assert r.headers["retry-after"] == "60"


def test_different_clients_get_separate_buckets_behind_a_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HOPS", "1")
    c = TestClient(make_app("1/minute"))
    assert c.get("/ping", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert c.get("/ping", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429
    assert c.get("/ping", headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 200   # someone else


def test_without_proxy_trust_everyone_behind_a_balancer_shares_one_bucket():
    """The failure TRUST_PROXY_HOPS exists to prevent — documented here so it stays visible."""
    c = TestClient(make_app("1/minute"))
    assert c.get("/ping", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert c.get("/ping", headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 429


# ── PortalGate ───────────────────────────────────────────────────────────────

async def hold(gate, req, secs, out, tag):
    try:
        async with gate.slot(req):
            await asyncio.sleep(secs)
        out[tag] = 200
    except HTTPException as e:
        out[tag] = e.status_code


def test_global_cap_queues_then_503s():
    async def main():
        gate = PortalGate("p", max_concurrent=2, per_ip=99, queue_timeout=0.2)
        out = {}
        reqs = [fake_request(f"10.0.0.{i}") for i in range(4)]
        await asyncio.gather(*[hold(gate, r, 0.6, out, i) for i, r in enumerate(reqs)])
        return gate, out
    gate, out = asyncio.run(main())
    assert sorted(out.values()) == [200, 200, 503, 503]
    assert gate.rejected_busy == 2 and gate.in_flight == 0


def test_waiting_caller_gets_in_when_a_slot_frees_within_the_timeout():
    async def main():
        gate = PortalGate("p", max_concurrent=1, per_ip=99, queue_timeout=1.0)
        out = {}
        await asyncio.gather(hold(gate, fake_request("10.0.0.1"), 0.2, out, "a"),
                             hold(gate, fake_request("10.0.0.2"), 0.1, out, "b"))
        return out
    assert asyncio.run(main()) == {"a": 200, "b": 200}


def test_per_ip_cap_stops_one_visitor_hogging_slots_but_not_others():
    async def main():
        gate = PortalGate("p", max_concurrent=10, per_ip=1, queue_timeout=0.2)
        out = {}
        same = fake_request("10.0.0.1")
        await asyncio.gather(hold(gate, same, 0.4, out, "first"),
                             hold(gate, same, 0.4, out, "second"),
                             hold(gate, fake_request("10.0.0.2"), 0.4, out, "other"))
        return gate, out
    gate, out = asyncio.run(main())
    assert out == {"first": 200, "second": 429, "other": 200}
    assert gate.rejected_ip == 1 and not gate._per_ip_count        # counters fully released


def test_slot_is_released_when_the_body_raises():
    async def main():
        gate = PortalGate("p", max_concurrent=1, per_ip=1, queue_timeout=0.2)
        with pytest.raises(RuntimeError):
            async with gate.slot(fake_request()):
                raise RuntimeError("portal blew up")
        async with gate.slot(fake_request()):               # would 503/429 if the slot leaked
            pass
        return gate
    assert asyncio.run(main()).in_flight == 0
