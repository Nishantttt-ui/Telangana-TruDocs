# Telangana TruDocs

Real-estate document search for Telangana. Python (FastAPI) backend, React+Vite frontend.

## Status (v0, first working slice)

Working end-to-end against the live government portals:
- **GHMC Mutation Status** — fully working.
- **GHMC Property Tax Search** — fully working (circle is a required field on the portal, not optional).
- **Adangal Extract (Pahani)** — fully working, including the final search submit. (Note: survey/khata number dropdowns come back empty for most villages tried so far — that appears to be sparse data on the portal's side, not a bug on ours; the search itself correctly returns "No RoR-1B Details Found" for a number with no record, confirmed live.)
- **Land Details Search (Bhu Bharati, agri land status)** — fully working, no login or OTP (Bhu Bharati `/knowLandStatus`). Two public search modes: by village + survey/khata number, or by passbook number + the last 4 digits of the owner's Aadhaar. The portal captcha is solved with ddddocr (`backend/core/captcha.py`), retried up to 8 times. Shows the portal's full 16-field record, including Land Status. Identical searches arriving together share one portal flow (single-flight); nothing is cached at rest, and the Aadhaar digits and captcha text are never logged.

Not yet built: Bhu Bharati EC (no confirmed working URL found yet), TG-IGRS Encumbrance Certificate (confirmed to require citizen login + OTP — blocked on that decision).

## Run locally

Backend:
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload
```

Frontend (separate terminal, dev mode with hot reload, proxies /api to :8000):
```
cd frontend
npm install
npm run dev
```

Or build the frontend once and let the backend serve it as one process:
```
cd frontend && npm run build && cd ..
.venv/bin/uvicorn backend.main:app
```

Tests (parsers, validation, error mapping and single-flight — no network, synthetic data):
```
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests
```

Load test (server running): fires N survey searches at the same moment at the live portal
(each solves the captcha; identical searches share one flow):
```
.venv/bin/python -m backend.scripts.load_test_land_details --base http://localhost:8000 -n 10
.venv/bin/python -m backend.scripts.load_test_land_details --base http://localhost:8000 -n 10 --same
```
