# Telangana TruDocs

Real-estate document search for Telangana. Python (FastAPI) backend, React+Vite frontend.

## Status (v0, first working slice)

Working end-to-end against the live government portals:
- **GHMC Mutation Status** — fully working.
- **GHMC Property Tax Search** — fully working (circle is a required field on the portal, not optional).
- **Adangal Extract (Pahani)** — fully working, including the final search submit. (Note: survey/khata number dropdowns come back empty for most villages tried so far — that appears to be sparse data on the portal's side, not a bug on ours; the search itself correctly returns "No RoR-1B Details Found" for a number with no record, confirmed live.)

- **Survey Map** — fully working, no login, captcha or OTP. Pick a village and survey number to see its boundary on a satellite photo, with neighbouring survey numbers, corner GPS points (P1, P2, …), area in acres/guntas and an "Open in Google Maps" link. Boundaries come from TGRAC's public ArcGIS server (the village maps behind tgrac.telangana.gov.in/digitallandsurvey/lis): the "30 cm" copy first, and Bhunaksha's older "2.5 m" copy for the ~1 village in 4 the 30 cm copy lacks (the page says when a result is from the older map, which can be 20–50 m off). The server takes 13–60 s to find a village's parcels, so each village is fetched once and cached (public map data), and at most 2 look-ups are sent to it at a time. The village list is `backend/data/survey_map_villages.json`, rebuilt with `python -m backend.scripts.scrape_survey_map_villages`. Satellite imagery is Esri World Imagery, loaded by the browser; check Esri's terms (or swap the provider in `SATELLITE_EXPORT` in `App.jsx`) before commercial use.

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

## Tests

```
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
```

Survey Map load check (server running): `.venv/bin/python -m backend.scripts.load_test_survey_map --base http://localhost:8000 -n 10` fires 10 look-ups for different random villages at once; add `--same` for 10 identical ones.
