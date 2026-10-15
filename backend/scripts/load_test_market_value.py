"""Fire N market-value searches at the same moment at a running server and report
how each one did. Uses real villages from the pre-scraped list, so it also hits
the live government portal (politely: the client throttles its own requests).

Usage (server running, e.g. on :8000):
  .venv/bin/python -m backend.scripts.load_test_market_value --base http://localhost:8000 -n 10
  .venv/bin/python -m backend.scripts.load_test_market_value -n 10 --same   # 10 identical searches
"""
import argparse
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "market_value_hierarchy.json"


def search(base: str, village: dict) -> tuple:
    body = json.dumps({k: village[k] for k in ("district_id", "mandal_id", "mandal", "village_id", "village")}).encode()
    req = urllib.request.Request(f"{base}/api/market-value/search", data=body, headers={"content-type": "application/json"})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, time.monotonic() - t, f"{len(json.load(r)['rows'])} rates"
    except urllib.error.HTTPError as e:
        return e.code, time.monotonic() - t, json.load(e).get("detail", "")
    except Exception as e:  # connection refused, timeout: the server itself failed
        return 0, time.monotonic() - t, repr(e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("-n", type=int, default=10, help="requests fired at the same moment")
    ap.add_argument("--same", action="store_true", help="all requests for the same village")
    ap.add_argument("--seed", type=int, default=10)
    a = ap.parse_args()

    villages = json.loads(DATA.read_text(encoding="utf-8"))
    rng = random.Random(a.seed)
    picks = [rng.choice(villages)] * a.n if a.same else rng.sample(villages, a.n)
    start = threading.Barrier(a.n)  # release every request together

    def fire(v):
        start.wait()
        return v, search(a.base.rstrip("/"), v)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=a.n) as pool:
        results = list(pool.map(fire, picks))
    wall = time.monotonic() - t0

    for v, (status, secs, note) in sorted(results, key=lambda x: x[1][1]):
        print(f"{status or 'ERR':>3}  {secs:5.1f}s  {v['village'][:24]:24} {v['district'][:20]:20} {note}")
    ok = [s for _, (st, s, _) in results if st in (200, 404)]  # 404 = no rates published: a valid answer
    times = [s for _, (_, s, _) in results]
    print(f"\n{len(ok)}/{a.n} answered (200 or 404) | slowest {max(times):.1f}s | median {statistics.median(times):.1f}s | wall {wall:.1f}s")


if __name__ == "__main__":
    main()
