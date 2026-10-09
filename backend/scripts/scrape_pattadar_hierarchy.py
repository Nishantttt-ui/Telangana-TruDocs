"""Bulk-scrape District → Mandal → Village from Bhu Bharati (Pattadar Passbook portal).

Saves backend/data/pattadar_hierarchy.json — a flat list of records:
  {"district_id","district","mandal_id","mandal","village_id","village"}

Resumable: progress is tracked in backend/data/_pattadar_scrape_progress.json.
If the script dies mid-run, re-run it and it picks up where it left off.

Usage:
  cd /Users/apple/Downloads/Telangana-TruDocs
  .venv/bin/python -m backend.scripts.scrape_pattadar_hierarchy
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "https://bhubharati.telangana.gov.in"
LANDING_PATH = "/knowLandStatus"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
RATE_SECONDS = 0.8  # conservative — government server

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = DATA_DIR / "pattadar_hierarchy.json"
PROGRESS_FILE = DATA_DIR / "_pattadar_scrape_progress.json"

_OPTION_RE = re.compile(r'<option[^>]*value=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>([^<]*)')


def _find_options(html: str) -> list[dict]:
    results = []
    for m in _OPTION_RE.finditer(html):
        value = m.group(1) or m.group(2) or m.group(3) or ""
        label = re.sub(r"\s+", " ", m.group(4)).strip()
        if value and value not in ("0", ""):
            results.append({"value": value, "label": label})
    return results


def _get(client: httpx.Client, path: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            time.sleep(RATE_SECONDS)
            resp = client.get(path, timeout=60.0)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            wait = 5 * (attempt + 1)
            print(f"  WARN: {path} attempt {attempt+1} failed ({exc}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"failed after {retries} attempts: {path}")


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

    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL + LANDING_PATH,
    }

    with httpx.Client(base_url=BASE_URL, headers=headers, follow_redirects=True) as client:
        print("Fetching districts...")
        landing_html = _get(client, LANDING_PATH)
        m = re.search(r'id="districtID"[^>]*>(.*?)</select>', landing_html, re.S)
        if not m:
            print("ERROR: could not find district select on landing page")
            sys.exit(1)
        districts = _find_options(m.group(1))
        print(f"Found {len(districts)} districts.")

        for di, district in enumerate(districts, 1):
            d_id, d_name = district["value"], district["label"]
            print(f"\n[{di}/{len(districts)}] District: {d_name} (id={d_id})")

            mandal_html = _get(client, f"/getMandalFromDivisionCitizenPortal?district={d_id}")
            mandals = _find_options(mandal_html)
            print(f"  {len(mandals)} mandals")

            for mi, mandal in enumerate(mandals, 1):
                m_id, m_name = mandal["value"], mandal["label"]

                if m_id in done_mandals:
                    print(f"  [{mi}/{len(mandals)}] Mandal {m_name} — skipped (already done)")
                    continue

                print(f"  [{mi}/{len(mandals)}] Mandal: {m_name} (id={m_id})", end=" ... ", flush=True)
                village_html = _get(client, f"/getVillageFromMandalCitizenPortal?mandalId={m_id}")
                villages = _find_options(village_html)
                print(f"{len(villages)} villages")

                for village in villages:
                    v_id, v_name = village["value"], village["label"]
                    key = (d_id, m_id, v_id)
                    if key not in existing_keys:
                        records.append({
                            "district_id": d_id,
                            "district": d_name,
                            "mandal_id": m_id,
                            "mandal": m_name,
                            "village_id": v_id,
                            "village": v_name,
                        })
                        existing_keys.add(key)

                done_mandals.add(m_id)
                progress["done_mandals"] = list(done_mandals)
                _save_progress(progress)
                _save_output(records)

    print(f"\nDone. {len(records)} total village records → {OUT_FILE}")
    PROGRESS_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
