# Telangana TruDocs

Real-estate document search for Telangana. Python (FastAPI) backend, React+Vite frontend.

## Status (v0, first working slice)

Working end-to-end against the live government portals:
- **GHMC Mutation Status** — fully working.
- **GHMC Property Tax Search** — fully working (circle is a required field on the portal, not optional).
- **Adangal Extract (Pahani)** — location cascade (District → Division → Mandal → Village → Survey/Khata options) is fully working live. Final search submission is wired to the confirmed request shape but has not yet returned a verified real result — see `backend/scrapers/adangal/client.py` and `backend/routers/adangal.py` for notes.

Not yet built: Pattadar Passbook (its known URL currently 404s on the live portal — needs re-verification), Bhu Bharati EC (no confirmed working URL found yet), TG-IGRS Encumbrance Certificate (confirmed to require citizen login + OTP — blocked on that decision).

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
