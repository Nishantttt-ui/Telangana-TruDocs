"""Fetch the 61 GHMC municipal circles from Search.aspx and save to
backend/data/ghmc_circles.json.

These circles never change — running this once bakes them into a static
file so the backend doesn't need to hit ghmc.gov.in on startup just to
populate the circle dropdown.

Usage:
  cd /Users/apple/Downloads/Telangana-TruDocs
  .venv/bin/python -m backend.scripts.scrape_ghmc_circles
"""
import json
import re
from pathlib import Path

import httpx

BASE_URL = "https://www.ghmc.gov.in"
PAGE_PATH = "/Search.aspx"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = DATA_DIR / "ghmc_circles.json"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {BASE_URL}{PAGE_PATH} ...")
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True) as client:
        html = client.get(BASE_URL + PAGE_PATH).text

    match = re.search(
        r'<select name="ctl00\$ContentPlaceHolder1\$ddlcircle"[^>]*>(.*?)</select>',
        html, re.S
    )
    if not match:
        print("ERROR: circle <select> not found on page — portal layout may have changed.")
        return

    options = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', match.group(1))
    circles = [{"value": v, "label": t.strip()} for v, t in options if v]

    if not circles:
        print("ERROR: parsed zero circles — check the regex against the live HTML.")
        return

    OUT_FILE.write_text(json.dumps(circles, ensure_ascii=False, indent=2))
    print(f"Saved {len(circles)} circles → {OUT_FILE}")
    for c in circles:
        print(f"  {c['value']:>4}  {c['label']}")


if __name__ == "__main__":
    main()
