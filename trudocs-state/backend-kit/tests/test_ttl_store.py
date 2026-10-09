import threading

from backend.kit.ttl_store import TTLStore


class Clock:
    t = 0.0
    def __call__(self): return self.t


def test_pop_is_single_use():
    s = TTLStore()
    k = s.put("sess")
    assert s.pop(k) == "sess" and s.pop(k) is None


def test_get_peeks_without_consuming():
    s = TTLStore(); k = s.put(1)
    assert s.get(k) == 1 and s.get(k) == 1 and s.pop(k) == 1


def test_entries_expire():
    clk = Clock(); s = TTLStore(ttl=10, clock=clk)
    k = s.put("a"); clk.t = 9.9
    assert s.get(k) == "a"
    clk.t = 10.1
    assert s.get(k) is None and len(s) == 0


def test_cap_evicts_oldest_first():
    s = TTLStore(max_items=3)
    keys = [s.put(i) for i in range(5)]
    assert len(s) == 3
    assert s.get(keys[0]) is None and s.get(keys[1]) is None and s.get(keys[4]) == 4


def test_unknown_key_is_none():
    assert TTLStore().pop("nope") is None


def test_thread_hammering_never_raises():
    """The bug this guards: iterating a dict while another thread mutates it."""
    s = TTLStore(ttl=0.001, max_items=50); errors = []
    def work():
        try:
            for _ in range(2000):
                k = s.put(object()); s.get(k); s.pop(k); len(s)
        except Exception as e:                           # pragma: no cover
            errors.append(e)
    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors
