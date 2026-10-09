"""Bulk-scrape District → Division → Mandal → Village from CCLA (Adangal/Pahani portal).

Saves backend/data/adangal_hierarchy.json — a flat list of records:
  {"district_id","district","division_id","division","mandal_id","mandal","village_id","village"}

Resumable: progress tracked in backend/data/_adangal_scrape_progress.json.

Usage:
  cd /Users/apple/Downloads/Telangana-TruDocs
  .venv/bin/python -m backend.scripts.scrape_adangal_hierarchy
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "https://ccla.telangana.gov.in"
LANDING_PATH = "/landStatus.do"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
RATE_SECONDS = 1.2  # CCLA is slower than Bhu Bharati, be conservative

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = DATA_DIR / "adangal_hierarchy.json"
PROGRESS_FILE = DATA_DIR / "_adangal_scrape_progress.json"

_OPTION_RE = re.compile(r'<option[^>]*value=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>([^<]*)')


def _find_options(html: str) -> list[dict]:
    results = []
    for m in _OPTION_RE.finditer(html):
        value = m.group(1) or m.group(2) or m.group(3) or ""
        label = re.sub(r"\s+", " ", m.group(4)).strip()
        if value and value not in ("0", ""):
            results.append({"value": value, "label": label})
    return results


def _options_from_select(html: str, select_name: str) -> list[dict]:
    m = re.search(rf'<select[^>]*name="{re.escape(select_name)}"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        return []
    return _find_options(m.group(1))


def _get(client: httpx.Client, path: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            time.sleep(RATE_SECONDS)
            resp = client.get(path, timeout=60.0)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            wait = 5 * (attempt + 1)
            print(f"  WARN: GET {path} attempt {attempt+1} failed ({exc}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"GET failed after {retries} attempts: {path}")


def _post(client: httpx.Client, path: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            time.sleep(RATE_SECONDS)
            resp = client.post(path, data={}, timeout=60.0)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            wait = 5 * (attempt + 1)
            print(f"  WARN: POST {path} attempt {attempt+1} failed ({exc}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"POST failed after {retries} attempts: {path}")


def _seed_session(client: httpx.Client) -> None:
    """Hit landing page to get a fresh JSESSIONID."""
    _get(client, LANDING_PATH)


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"done_mandals": []}


def _save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2))


def _load_existing() -> list[dict]:
    if OUT_FILE.exists():
        return json.loads(OUT_FILE.read_text())
    return []


def _save_output(records: list[dict]) -> None:
    OUT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2))


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    records = _load_existing()
    progress = _load_progress()
    done_mandals: set[str] = set(progress["done_mandals"])
    existing_keys = {(r["district_id"], r["mandal_id"], r["village_id"]) for r in records}

    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(base_url=BASE_URL, headers=headers, follow_redirects=True) as client:
        print("Fetching districts...")
        _seed_session(client)
        landing_html = _get(client, LANDING_PATH)
        districts = _options_from_select(landing_html, "userProperties(district_id)")
        if not districts:
            print("ERROR: could not find district options on landing page")
            sys.exit(1)
        print(f"Found {len(districts)} districts.")

        for di, district in enumerate(districts, 1):
            d_id, d_name = district["value"], district["label"]
            print(f"\n[{di}/{len(districts)}] District: {d_name} (id={d_id})")

            _seed_session(client)
            div_html = _post(client, f"{LANDING_PATH}?method=getDivisions&district_id={d_id}")
            divisions = _find_options(div_html)
            print(f"  {len(divisions)} divisions")

            for dvi, division in enumerate(divisions, 1):
                dv_id, dv_name = division["value"], division["label"]
                print(f"  [{dvi}/{len(divisions)}] Division: {dv_name} (id={dv_id})")

                _seed_session(client)
                mandal_html = _post(
                    client,
                    f"{LANDING_PATH}?method=getMandals&district_id={d_id}&division_id={dv_id}",
                )
                mandals = _find_options(mandal_html)
                print(f"    {len(mandals)} mandals")

                for mi, mandal in enumerate(mandals, 1):
                    m_id, m_name = mandal["value"], mandal["label"]
                    cache_key = f"{d_id}:{dv_id}:{m_id}"

                    if cache_key in done_mandals:
                        print(f"    [{mi}/{len(mandals)}] Mandal {m_name} — skipped (already done)")
                        continue

                    print(f"    [{mi}/{len(mandals)}] Mandal: {m_name} (id={m_id})", end=" ... ", flush=True)
                    _seed_session(client)
                    village_html = _post(
                        client,
                        f"{LANDING_PATH}?method=getVillages&district_id={d_id}&mandal_id={m_id}",
                    )
                    villages = _find_options(village_html)
                    print(f"{len(villages)} villages")

                    for village in villages:
                        v_id, v_name = village["value"], village["label"]
                        key = (d_id, m_id, v_id)
                        if key not in existing_keys:
                            records.append({
                                "district_id": d_id,
                                "district": d_name,
                                "division_id": dv_id,
                                "division": dv_name,
                                "mandal_id": m_id,
                                "mandal": m_name,
                                "village_id": v_id,
                                "village": v_name,
                            })
                            existing_keys.add(key)

                    done_mandals.add(cache_key)
                    progress["done_mandals"] = list(done_mandals)
                    _save_progress(progress)
                    _save_output(records)

    print(f"\nDone. {len(records)} total village records → {OUT_FILE}")
    PROGRESS_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
