import pytest
from fastapi import HTTPException

from backend.kit.service_health import HealthBoard, ServiceHealth


class Clock:
    t = 1000.0
    def __call__(self): return self.t


def test_locks_out_after_n_failures_then_auto_recovers():
    clk = Clock(); h = ServiceHealth("x", max_failures=3, lockout_secs=600, clock=clk)
    for _ in range(2): h.record_failure()
    assert h.is_available()
    h.record_failure()
    assert not h.is_available() and h.minutes_until_retry() == 10
    clk.t += 601
    assert h.is_available() and h.failures == 0


def test_success_resets_the_counter():
    h = ServiceHealth("x", max_failures=3)
    h.record_failure(); h.record_failure(); h.record_success(); h.record_failure(); h.record_failure()
    assert h.is_available()


def test_board_blocks_with_friendly_503_and_ignores_failures_when_our_internet_is_down():
    online = {"up": True}
    board = HealthBoard(internet_probe=lambda: online["up"])
    board.register("bbmp", portal_name="BBMP tax portal", max_failures=2)
    online["up"] = False
    for _ in range(5): board.failure("bbmp")             # our network blip: must NOT lock the tool out
    board.ensure_available("bbmp")
    online["up"] = True
    board.failure("bbmp"); board.failure("bbmp")
    with pytest.raises(HTTPException) as e:
        board.ensure_available("bbmp")
    assert e.value.status_code == 503 and "BBMP tax portal is currently under maintenance" in e.value.detail
    assert board.status()["bbmp"]["available"] is False
    board.success("bbmp"); board.ensure_available("bbmp")
