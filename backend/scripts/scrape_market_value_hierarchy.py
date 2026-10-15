"""Bulk-scrape District → Mandal → Village from the IGRS Market Value search.

Saves backend/data/market_value_hierarchy.json — a flat list of records:
  {"district_id","district","mandal_id","mandal","village_id","village"}

Hyderabad (16_1) is skipped: it has no mandals/villages on this portal; its
localities are searched live instead (see scrapers/market_value/client.py).

Resumable: progress tracked in backend/data/_market_value_scrape_progress.json.
The client's own throttle keeps it to one request per second.

Usage:
  .venv/bin/python -m backend.scripts.scrape_market_value_hierarchy
"""
import json
import time
from pathlib import Path

from backend.core.errors import PortalError
from backend.scrapers.market_value import client as mv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = DATA_DIR / "market_value_hierarchy.json"
PROGRESS_FILE = DATA_DIR / "_market_value_scrape_progress.json"


def _retry(fn, *args, retries: int = 3):
    for attempt in range(retries):
        try:
            return fn(*args)
        except PortalError as exc:
            wait = 5 * (attempt + 1)
            print(f"  WARN: {fn.__name__}{args} attempt {attempt + 1} failed ({exc.detail}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"{fn.__name__}{args} failed after {retries} attempts")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    records = json.loads(OUT_FILE.read_text(encoding="utf-8")) if OUT_FILE.exists() else []
    done = set(json.loads(PROGRESS_FILE.read_text())) if PROGRESS_FILE.exists() else set()
    seen = {(r["district_id"], r["mandal_id"], r["village_id"]) for r in records}

    districts = [d for d in _retry(mv.fetch_districts) if d["value"] != mv.HYDERABAD]
    print(f"Found {len(districts)} districts (Hyderabad skipped).")

    for di, district in enumerate(districts, 1):
        d_id, d_name = district["value"], district["label"]
        mandals = _retry(mv.fetch_mandals, d_id)
        print(f"\n[{di}/{len(districts)}] {d_name} (id={d_id}): {len(mandals)} mandals")

        for mandal in mandals:
            m_id, m_name = mandal["value"], mandal["label"]
            key = f"{d_id}:{m_id}"
            if key in done:
                continue

            villages = _retry(mv.fetch_villages, d_id, m_id)
            print(f"  {m_name}: {len(villages)} villages")
            for village in villages:
                if (d_id, m_id, village["value"]) not in seen:
                    records.append({
                        "district_id": d_id,
                        "district": d_name,
                        "mandal_id": m_id,
                        "mandal": m_name,
                        "village_id": village["value"],
                        "village": village["label"],
                    })
                    seen.add((d_id, m_id, village["value"]))

            done.add(key)
            PROGRESS_FILE.write_text(json.dumps(sorted(done)))
            OUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {len(records)} total village records → {OUT_FILE}")
    PROGRESS_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
