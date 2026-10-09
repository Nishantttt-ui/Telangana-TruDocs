---
name: trudocs-state
description: Playbook for building TruDocs for a new Indian state, or adding a tool/portal to one. Gives the exact React frontend shell, a tested FastAPI backend kit (rate limiting, concurrency gates, PDF covers, captcha sessions, maintenance mode, Docker), and the rules for scaling and deploying. Use when starting a state's TruDocs repo, wiring a government portal (land records, EC, Bhunaksha, tax receipts, ...), adding or changing a PDF cover, choosing HTTP vs Playwright vs Selenium for a portal, or hardening/deploying a tool. Always begins with intake questions (PDF covers first) before any code is written.
---

# TruDocs state playbook

TruDocs fetches official documents from government portals and presents them in one consistent product. Every state differs in **portals, requests, payloads and covers**; everything else is shared. This skill carries the shared part so it never has to be re-explained:

| In this folder | What it is |
|---|---|
| `SKILL.md` | This playbook — rules, decisions, checklists. Read it fully before starting. |
| `frontend-shell/` | The real frontend (React + Vite), copied as-is from the Karnataka product. Every state ships the same UI. |
| `backend-kit/kit/` | State-agnostic backend modules, **tested** (57 tests): rate limiting, concurrency gates, TTL store, maintenance mode, PDF covers, app wiring. |
| `backend-kit/examples/bbmp_receipt/` | A complete worked tool (captcha session → PDF) built on the kit. Copy its shape for every new tool. |
| `backend-kit/Dockerfile.http`, `Dockerfile.playwright`, `.dockerignore`, `requirements.base.txt`, `main.example.py`, `covers.example.json` | Build/deploy templates, verified by building and running them. |
| `sync.sh` | Maintainers only: refreshes `frontend-shell/` and the example scraper from the live Karnataka repo. |

---

## 0. Intake — ask BEFORE writing any code

Ask these in **one message** and wait for the answers. Do not start a tool, a PDF path, or a Dockerfile until 1 is answered. (Use `AskUserQuestion` if available, otherwise plain text.)

**1. PDF covers — ALWAYS ask, every time this skill is used.**

> "Will you give me cover PDFs, or should we use the default one? I need:
> (a) the **default cover PDF** — used by any tool without its own;
> (b) a **service-specific cover PDF** for each tool that needs a different one (EC, land records, Bhunaksha, … — each differs);
> (c) or tell me **'no cover'** for a tool that should return the portal PDF untouched.
> For each cover: what text goes on it (party name, property number, survey number, …) and a sample value."

Then, per cover: run `cover_grid` on the template to read positions (§8), write `covers.json`, render a sample, and **show the user the sample page** before moving on. Never invent a cover design. If the user says "use the default" but hasn't supplied the file, ask for it.

**2. Tools and portals.** For each tool: portal URL; what the user types; what comes back (PDF directly / a list then a PDF / HTML). Ask for the browser's **"Copy as cURL" for every request in order** (and the form payload). Don't guess requests from the portal's HTML alone.

**3. Hosting and scale.** Where it deploys (Cloud Run / VM / Kubernetes), expected daily users and peak concurrency, whether Redis is available, which languages the cover text needs (Indic scripts need a font file, §8).

**4. Technology per tool — do NOT pick yet.** Run the analysis in §3, present the findings and a recommendation with the trade-offs, and **wait for the user to choose**.

Out of scope for this skill: accounts/logins and anything about solving captchas (see rule 1).

---

## 1. Hard rules

1. **Captchas are typed by the end user. Always.** No OCR, no vision/LLM model, no third-party solver, no "temporary", "fallback" or flag-gated solver — not here and not in any state. If a captcha blocks a flow, tell the user; don't engineer around it. The shared pieces are only the plumbing for a human to answer it (§7).
2. **Everything that talks to a portal is rate-limited, concurrency-gated and health-tracked** (§10). No exceptions for "internal" tools.
3. **Never log personal data or secrets**: application numbers, party names, survey numbers, captcha text. The kit's access log records method, path, status, time, IP and request id only — no query strings, no bodies.
4. **Users see friendly messages, never upstream detail.** Backend `detail` text for 400/410/422 is shown to the user as-is, so it must be user-ready. 5xx collapses to one generic line in the frontend.
5. **Copy the frontend shell; don't reinvent it.** Only the edit points in §9 change.
6. **Importing the app must not have side effects.** Anything slow or external at boot goes in a startup hook that `SKIP_STARTUP=1` disables. (In Karnataka, `import backend.main` triggers a real portal login. Don't copy that.)
7. **A fake portal proves our code; only the real portal proves the integration.** Test against fakes, then have a human do one real run per tool.
8. **Preserve each file's line endings.** Karnataka's `rtc_routes.py` is CRLF; a naive rewrite flips the whole file and ruins the diff. Check with `file <path>` before editing.

---

## 2. What a state repo looks like

```
<state-repo>/
├── backend/
│   ├── __init__.py
│   ├── main.py                  ← main.example.py (a dozen lines)
│   ├── kit/                     ← backend-kit/kit        (do not edit per state)
│   └── tools/
│       └── <tool>/              ← one folder per portal tool
│           ├── scraper.py       ← pure portal logic, no FastAPI
│           ├── routes.py        ← make_router(limiter, board, covers)
│           └── (tests live in <repo>/tests/)
├── frontend-v2/                 ← frontend-shell/  (+ the state's views)
├── covers/                      ← covers.json + the PDFs the user supplied
├── requirements.txt             ← backend-kit/requirements.base.txt (+ playwright if chosen)
├── Dockerfile                   ← Dockerfile.http or Dockerfile.playwright
└── .dockerignore
```

```
Browser ──► React shell ──► /api/<tool>/…  ──► FastAPI (kit: limiter · gate · health · access log)
                                                  │
                                    scraper.py ◄──┘──► government portal
                                                  │
                                         PDF bytes ──► pdf_cover (default | per-service | none) ──► response
```

Install into a new state repo (from the repo root; `SKILL=.claude/skills/trudocs-state`):

```bash
mkdir -p backend/tools covers && touch backend/__init__.py backend/tools/__init__.py
cp -R $SKILL/backend-kit/kit backend/kit
cp -R $SKILL/frontend-shell frontend-v2
cp $SKILL/backend-kit/main.example.py backend/main.py
cp $SKILL/backend-kit/requirements.base.txt requirements.txt
cp $SKILL/backend-kit/Dockerfile.http Dockerfile && cp $SKILL/backend-kit/.dockerignore .
cp $SKILL/backend-kit/covers.example.json covers/covers.json     # then fill in from intake §0.1
# start a tool from the worked example:
cp -R $SKILL/backend-kit/examples/bbmp_receipt backend/tools/<tool>
```

---

## 3. Choose the technology per tool (analyse → recommend → user chooses)

Don't default to a browser, and don't default to HTTP either. Analyse each portal, present what you found, recommend one approach with reasons, list the alternatives with costs, **then wait for the user's choice.**

### 3.1 Analysis checklist (cheapest first)

1. **Capture the real flow.** DevTools → Network → *Preserve log* → do the whole flow once → *Copy as cURL* for each request, in order. Note cookies set and hidden form fields.
2. **Replay it with HTTP.** First `httpx`; if the portal answers differently, retry with `curl_cffi` (`impersonate="chrome124"`). If only `curl_cffi` works, the portal checks the TLS fingerprint — HTTP is still fine.
3. **Where is the data?** Server-rendered HTML (parse with BeautifulSoup) · JSON from XHR · a PDF binary · or built by JavaScript in the page (needs a browser or reimplementation).
4. **State and tokens.** ASP.NET `__VIEWSTATE` / `__EVENTVALIDATION` / CSRF fields are replayable (parse and echo them). A hash/signature computed by page JS (e.g. an md5) can usually be reimplemented in Python. Obfuscated or WASM-computed tokens → browser.
5. **The postback sequence.** WebForms dependent dropdowns are POSTs with `__EVENTTARGET`. Replay the **same sequence the browser sends** — on BBMP, the year dropdown stays empty (and any year is rejected) until the application-number postback has run.
6. **Anti-bot.** Cloudflare/Akamai challenge pages, JS challenges, headless detection. These are the real reason to need a browser.
7. **The output.** Portal serves a PDF · we print a page to PDF · we render our own HTML to PDF (Karnataka's RTC does this with Playwright).
8. **Timing rules.** Minimum captcha age, session lifetime, one-active-session limits. (§7.)

### 3.2 What each option costs — measured

Measured on this repo's BBMP form page, MacBook Pro M1 Pro, Python 3.14, median of 5 requests. Indicative, not a benchmark: a Linux container will differ, but the ratios are what matter.

| | Latency per request | Process memory | Notes |
|---|---|---|---|
| `httpx` | ~127 ms | +35 MB (the whole client, not per request) | Plain HTTP client |
| `curl_cffi` (Chrome TLS fingerprint) | ~100 ms | +42 MB (the whole client, not per request) | Same API shape; use when the fingerprint matters |
| Playwright / Chromium | launch ~1.8 s, first page ~0.9 s, warm page ~0.5 s | **~494 MB with 1 page open, ~1,044 MB with 4 pages** (≈ 0.3 GB for the browser + ≈ 0.18 GB per extra page) | Real browser; **~2 GB more image**; needs RAM-bounded concurrency |

Roughly **5–9× the latency** per request, and a browser *process* costs ~0.3–0.5 GB before it fetches anything, versus a ~40 MB HTTP client that serves any number of concurrent requests. A browser tool therefore needs a hard concurrency cap (a `PortalGate`, §6) and much more RAM per instance. A design that launches a **new browser per request** pays the full ~0.5 GB each time — reuse one browser and open pages/contexts.

### 3.3 Options

| Option | Choose it when | Avoid it when |
|---|---|---|
| **Plain HTTP** (`httpx`/`requests`, or `curl_cffi`) | Steps 2–5 of the checklist succeed. **The default recommendation.** | The data only exists after JS runs, or an anti-bot wall blocks non-browsers. |
| **Playwright** (async API, one browser per process, a context per request) | JS must execute; a token can't be reproduced; an anti-bot wall requires a real browser; you must print HTML to PDF. | Plain HTTP works — you'd pay ~10× memory for nothing. |
| **Selenium** | Only to keep an existing script that already works. | New work: slower, synchronous, heavier than Playwright with no advantage. |
| **Hybrid** — browser once to mint a short-lived token/cookie, HTTP for the volume | A portal needs a browser only at the front door. | The token expires faster than a browser round-trip is worth. |

For reference, in the Karnataka product: Akarband uses `requests`; E-Khata `httpx`; E-Swathu `httpx`+`bs4`; BBMP receipt `curl_cffi`+`bs4`; Kaveri's API calls `curl_cffi`; RTC and Mutation use Playwright; Selenium is used in one legacy flow only.

### 3.4 Present it like this, then stop and ask

| Tool | Portal | Data lives in | State/tokens | Anti-bot | Captcha | Recommended | Why | Cost/risk | Alternative |
|---|---|---|---|---|---|---|---|---|---|

End with: *"Which approach do you want for each tool?"* Do not write scraper code before the answer.

---

## 4. API contract (what the frontend shell expects)

Keep to this and the shell works unchanged.

| Situation | Status | Body |
|---|---|---|
| Success, document | 200 | `application/pdf` + `Content-Disposition` (use `kit.portal_utils.content_disposition` — safe for non-ASCII names) |
| Success, JSON | 200 | tool-specific JSON |
| Bad input (format, unknown number, empty captcha) | 400 | `{"detail": "<user-ready sentence>"}` |
| Wrong captcha | **422** | `{"detail": "Enter Valid Captcha Text"}` (the portal's own wording is fine) |
| Captcha/session expired or already used | **410** | `{"detail": "Captcha expired. Please try again."}` |
| Not found | 404 | `{"detail": "No records found …"}` |
| Rate limited | **429** | `{"detail": "Too many requests. Please wait and try again."}` + `Retry-After` |
| Portal down / error | **502** | `{"detail": "<Portal> is not responding. Please try again shortly."}` |
| Portal in maintenance mode / our gate is full | **503** | `{"detail": "<Portal> is currently under maintenance. Please try again in N minutes."}` or "busy" |

- Paths: `/api/<tool>/<action>`. Long jobs: `POST /api/<tool>/start → {job_id}`, `GET …/jobs/{id}/status`, `GET …/jobs/{id}/download-pdf`.
- A wrong captcha or an unknown number is **the user's error**: never count it toward maintenance mode. Portal 5xx and timeouts are the portal's: count those.
- Frontend behaviour: `friendlyMessage()` in `api.js` shows the backend's text for 404/429 and a generic line for 5xx. Tools with user-actionable messages (like BBMP) read `detail` themselves — copy `throwBBMP` for that.

---

## 5. Backend kit

All modules are state-agnostic and covered by tests in `backend-kit/tests/` (they assemble the exact layout from §2, so the copy instructions are tested too).

| Module | Purpose | Key API |
|---|---|---|
| `portal_utils` | Things every scraper needs | `js_alert_messages(html, ignore=…)` · `is_pdf(bytes)` · `sniff_image_mime(bytes)` · `safe_filename()` · `content_disposition(name)` |
| `ttl_store` | Bounded, thread-safe, **single-use** store for captcha sessions / jobs | `TTLStore(ttl, max_items)` → `put()` `get()` `pop()` |
| `rate_limit` | Per-IP limiter (proxy-aware), JSON 429, and `PortalGate` (global + per-IP concurrency cap) | `make_limiter()` · `install(app, limiter)` · `PortalGate(name, max_concurrent, per_ip).slot(request)` |
| `service_health` | Maintenance mode: N failures → lockout → auto-recover; ignores failures when *our* network is down | `HealthBoard().register(…)` · `ensure_available()` · `failure()` / `success()` |
| `pdf_cover` | Config-driven cover(s) prepended to a portal PDF | `load_registry(json)` · `apply_cover(pdf, registry, service, values)` |
| `cover_grid` | Draws a labelled coordinate grid on a template to read text positions | `python -m backend.kit.cover_grid covers/x.pdf` |
| `app_factory` | Wires limiter, `/api/health`, `/api/ready`, access log, static frontend, startup hooks | `create_app(title, limiter=, board=, gates=, routers=, frontend_dist=)` |

### A tool is two files

- **`scraper.py`** — pure portal logic. No FastAPI. Returns bytes/dicts. Conventions:
  - One error base class for *user* errors; a subclass `PortalUnavailable` for HTTP ≥ 500 / timeouts (so the route can tell them apart); a `CaptchaError` for the portal's "wrong captcha" reply.
  - A timeout on **every** network call. Never retry silently in a loop.
  - Check `is_pdf()` before returning bytes — portals return HTTP 200 with an HTML error page.
  - Debug prints that include user data behind an env flag (`BBMP_DEBUG=1`), off by default.
- **`routes.py`** — `make_router(limiter, board, covers)` returning an `APIRouter`. Conventions:
  - Validate input with a regex **before** touching the portal.
  - `async def`; wrap blocking portal calls in `asyncio.to_thread`; put them inside `async with gate.slot(request)`.
  - **Never `time.sleep` in a route** (§11). Wait with `await asyncio.sleep`.
  - Map errors per §4; call `board.failure()` only for portal-side failures.

`main.example.py` shows the whole `main.py`. `examples/bbmp_receipt/routes.py` shows every convention above in one place — start from it.

---

## 6. Rate limiting and abuse protection

Three independent layers, because each one alone has a hole:

| Layer | Stops | Tool | Starting value |
|---|---|---|---|
| Per-IP request rate | One client spamming | `@limiter.limit("10/minute")` on every portal-facing route | captcha/session 10/min · fetch/receipt 10/min · lookups 40/min |
| Per-IP in-flight cap | One client tying up all slots with slow requests | `PortalGate(per_ip=2)` | 2 |
| Global portal cap | Many clients hammering the portal (and our workers) | `PortalGate(max_concurrent=6, queue_timeout=5)` | 6 for HTTP tools · 1–2 for Playwright tools |

Also: a single-use captcha session is itself a throttle (one portal fetch per human answer); validate payload shape; cap response sizes; set upstream timeouts.

### Client IP — the usual silent failure

Behind any load balancer (Cloud Run, nginx, ALB) the socket peer is the balancer, so a naive limiter sees **one** client and throttles everyone together. Reading `X-Forwarded-For` fixes that, but only the entry your **own** proxy appended can be trusted — the left side is attacker-controlled.

- `TRUST_PROXY_HOPS=0` (default): use the socket peer. Safe, wrong behind a balancer.
- `TRUST_PROXY_HOPS=1`: one trusted proxy → use the **last** `X-Forwarded-For` entry. Tested, including the spoofing case.
- After first deploy, `GET /api/health` and read `client_ip`: it must be **your real public IP**. If it's a Google/AWS/nginx address, the hop count is wrong.
- **Do not** start uvicorn with `--forwarded-allow-ips='*'`. In uvicorn's source, `*` makes it trust the **leftmost** (client-supplied) entry for `request.client`. The kit reads the header itself; leave uvicorn's default.

### Multiple instances

The default limiter store is per-process: N instances means an N× effective limit. Set `RATE_LIMIT_STORAGE=redis://host:6379` to share counters (and `pip install redis`).

---

## 7. Captcha: the user types it

Pattern for any portal whose form has a captcha. Reference implementation: `examples/bbmp_receipt/` + `frontend-shell/src/views/BBMPReceipt/` + `CaptchaField.jsx`.

```
1. user enters the identifier  ──►  POST /api/<tool>/captcha {id}
2. backend opens a PORTAL SESSION (cookie jar + hidden form fields), fetches the captcha image
   with that same session, stores the session (TTLStore, single-use, ~10 min),
   returns {session_id, captcha_b64, captcha_mime, …}           ← image bytes, never solved
3. user reads the image, types it  ──►  POST /api/<tool>/receipt {session_id, captcha, …}
4. backend pops the session (single-use: win or lose, it is consumed), submits the form on
   the SAME session  ──►  PDF, or 422 wrong captcha  ──►  frontend auto-loads a fresh captcha
```

Why two calls: the portal binds the captcha to the cookie session that was issued it.

Rules learned on real portals:

- **One image per session, fetched once.** Re-requesting the captcha URL returns a *different* image and invalidates the previous one. Anything that fetches it twice makes a correct answer fail.
- **Minimum captcha age.** BBMP rejects a *correct* captcha that arrives too soon after it was rendered (observed: 3 s rejected, 10 s accepted; CLI typed fast also rejected). The scraper exposes `hold_remaining(sess)`; the route waits with `await asyncio.sleep(...)` — **outside** the `PortalGate` so the wait holds no portal slot. This was observed on BBMP; verify on each new portal and set `MIN_CAPTCHA_AGE` to what it needs (start at 0, find the threshold).
- **Validate before consuming.** An empty captcha must 400 *before* `pop()`; don't burn the session.
- **Don't trust the image URL's extension.** BBMP serves a JPEG from `…Image.axd`. Sniff the bytes (`sniff_image_mime`).
- **Errors come as JS `alert('…')` in an HTTP 200 page** on ASP.NET WebForms portals. Parse with `js_alert_messages(html, ignore=(boilerplate,))`; a generic "Oops.. Error on page" screen means the session died.
- **Never write the captcha to disk.** Not in the app, not in CLIs (the BBMP CLI opens a temp file and deletes it).

### Frontend: `CaptchaField.jsx`

Shows the image and a refresh button, focuses the box when a new image arrives **and when the box becomes usable again**, calls `onComplete(text)` the moment `length` characters are typed, and locks everything while `busy`. The parent owns the value and decides what completion does (submit). Locking inputs while loading/fetching is mandatory for every tool (§9).

---

## 8. PDF output and covers

### Configuration, not code

`covers/covers.json` (see `covers.example.json`):

```json
{
  "default":  { "template": "covers/default_cover.pdf",
                "fields": [ {"key": "name", "x": 64, "top": 560, "size": 52, "color": "#163A2E", "max_width": 1100} ] },
  "services": {
    "ec":  { "template": "covers/ec_cover.pdf", "design": [1403.2, 992.4], "fields": [ … ] },
    "rtc": null
  }
}
```

- **Resolution:** a service's own cover → else `default` → else none. `"rtc": null` means *explicitly no cover* for that service.
- **Coordinates** are "design units" from the **top-left** of the design space (x → right, top ↓), like CSS/Figma. `design` omitted = the template's own page size in points (simplest for a new cover). The design space is scaled onto the real page, so a cover laid out once fits any page size. The cover template is also scaled to the portal PDF's **first page size**, so a portrait certificate and a landscape EC each get a matching cover.
- **Field options:** `size`, `color`, `font`, `font_file`, `align` (`left|center|right`, with `x` as the anchor), `max_width` (text shrinks to fit, never below half size).
- A missing/empty value skips that field; it never breaks the download.

### Procedure for every new cover

1. Get the template from the user (§0.1).
2. `python -m backend.kit.cover_grid covers/<file>.pdf` → open `<file>_grid.pdf` and read `x`/`top` where each text's top-left should sit.
3. Write the config, render a sample: `python -m backend.kit.pdf_cover covers/covers.json <service> sample.pdf out.pdf name="Sample Name"`.
4. Open `out.pdf` (the Read tool can view PDFs) and **show the user the page**. Adjust until they approve.
5. Check a long value (a 40-character name) and a short one.

### Fonts and scripts

Standard PDF fonts are Latin-only — other characters print as `?` (the kit logs a warning). For Kannada, Hindi, Tamil, Bengali and so on, give the field a `font_file` (a `.ttf` covering the script). ReportLab does no complex-script shaping, so **render and visually check a real name** before promising Indic cover text.

### Rules

- Covers are applied on the **backend**, after `is_pdf()` passes. The frontend only displays the result.
- Karnataka's cover builder was verified against this one: same page count, page size and text position (x 64, y 388.2, size 52) on the real EC cover.
- Decide with the user what happens if cover generation fails: the kit raises (loud, safer for a branded deliverable). Falling back to the plain portal PDF is a one-line `try/except` if they prefer.
- Pages with a `/Rotate` flag aren't specially handled.
- Filenames: always `content_disposition()` — a non-ASCII name in a raw header crashes Starlette.

---

## 9. Frontend shell

`frontend-shell/` is the Karnataka frontend verbatim (it builds as-is: `npm ci && npm run build`). Copy it, then change **only** these places:

| File | Change |
|---|---|
| `index.html` | `<title>`, `<meta description>` |
| `src/App.jsx` | `SECTION_IDS`, `SHEET_TITLES`, `EXPLORE_CARDS`, the imports + `renderSheetContent()` switch + the `<section>` list (one block per tool, each preceded by `<div className="tool-sep" />`), and the hero text/badges/stats ("Bangalore's only…", "Kaveri Verified", "2,928 Villages"…). |
| `src/components/layout/AppHeader.jsx`, `DrawerMenu.jsx` | the `*_ITEMS` arrays and the group titles ("Kaveri (EC)", "Bhoomi", "BBMP / Panchayat"), and the "Kaveri Online" status label. |
| `src/components/common/LoaderModal.jsx` | `TIPS` and the default `title` (mention the state's portal). |
| `src/utils/api.js` | **Keep the helper block at the top** (`fetchWithTimeout`, `friendlyMessage`, `makeFriendlyError`, `throwFriendly`). Delete the Karnataka tool functions below it and add the state's. |
| `src/views/` | Delete the Karnataka views you don't need. Keep `BBMPReceipt/` (captcha→PDF), `EKhata/` (search→list→PDF job) and `KarnatakaEC/` (form→PDF) as **reference** until your own views exist. |
| `public/PropertyType.json` | Kaveri-specific — delete or replace. |
| `public/` brand files | `TruEstate full gold.png`, fonts and icon CSS stay. |

`Sidebar.jsx` and `MobileHeader.jsx` are not imported anywhere (legacy) — ignore or delete.

### Adding a tool

1. `src/views/<Tool>/<Tool>View.jsx` (+ `use<Tool>.js` if the logic is non-trivial).
2. API functions in `api.js`, reusing `throwFriendly` / `makeFriendlyError`.
3. Register it in `App.jsx` (mobile **and** desktop paths), `AppHeader.jsx` and `DrawerMenu.jsx`.
4. **Header width:** the top bar is wide-screen only. From the measured tab widths, 7 tabs need a viewport of about 1160 px and 8 tabs about 1280 px (an estimate, not tested at every width). More tools than that → group them, shorten labels, or move the long tail into the drawer.

### Result patterns (pick one per tool)

| Pattern | Flow | Reference view |
|---|---|---|
| **A. Direct PDF** | form → one request → PDF | `KarnatakaEC` |
| **B. List then PDF** | search → results table → "View" → PDF | `EKhata` |
| **C. Job polling** | `POST start` → poll `status` every 1 s → fetch PDF | `EKhata`, `Mutation` |
| **D. Captcha session** | identifier → captcha → type → PDF | `BBMPReceipt` |

All show the document with `<PDFViewer blob filename />` (pdf.js canvases + a download button) and status with `<StatusMessage kind message />`.

### Conventions that every view follows

- **Lock inputs while loading or fetching** (`disabled={busy}`), so values can't change under an in-flight request. When a lookup fails, unlock **and refocus** the first field.
- **Auto-load when input is complete** (e.g. 10 digits → load the captcha) with a short debounce; ignore replies for stale requests (a request-id ref).
- **Don't set `maxLength` on numeric inputs** you also sanitise: it truncates pasted "1500 082 907" before your `onChange` can strip spaces. Sanitise in `onChange`.
- **Effects must be StrictMode-safe.** React dev mode runs effects twice; any async render into a shared container needs a cancel flag (`PDFViewer` has one — without it a 1-page PDF showed 2 pages under `npm run dev`).
- Abort in-flight fetches on unmount/cancel (`AbortController`), show a cancellable `LoaderModal` for long calls.
- 429/503/502 are expected states, not exceptions: show the message, keep the form usable.

### Run it without any backend side effects

```bash
SKIP_STARTUP=1 uvicorn backend.main:app --port 8000      # backend, no portal logins/warm-ups
cd frontend-v2 && npm run dev                            # http://localhost:5173 (Vite proxies /api → :8000)
```

---

## 10. Scaling and deployment

### Capacity model

Concurrent requests in flight ≈ **requests per second × seconds each takes** (Little's law). A tool with a 10 s captcha wait and a 2 s portal call holds each request ~12 s: at 5 req/s that's ~60 in flight. What matters is **what each in-flight request occupies**:

| Waiting inside… | Occupies | Cost at 60 in flight |
|---|---|---|
| `await asyncio.sleep` / `await` network | an event-loop task | ~nothing |
| `time.sleep` or a blocking call in a `def` route | a **threadpool thread** (FastAPI default: 40) | the whole pool; every other sync route queues |
| `asyncio.to_thread(...)` call | a worker thread, only for the call's duration | fine if short and gated |
| a Playwright page in a shared browser | ~0.2 GB RAM (+ ~0.3 GB for the browser itself) | ~12 GB — must be capped; a browser *per request* would be ~30 GB |

**Measured on this repo** (fake portal, 60 submits waiting out the captcha-age at once, then probing another tool's sync route):

| Design | Other tool's route latency while 60 waited |
|---|---|
| `time.sleep` inside a threaded route (the first BBMP version) | **1,539 ms** (the 40-thread pool was exhausted) |
| `await asyncio.sleep` + `to_thread` for the portal call (current) | **12 ms** |

This is guarded by `test_the_captcha_age_wait_does_not_block_other_routes`. **Never `time.sleep` in a route.**

### Order of scaling

1. **One instance, one worker, done properly** — async routes, `to_thread` for blocking calls, a `PortalGate` per portal, bounded executors for browsers.
2. **More instances** — needs the state below to stop being per-process.
3. **Never more uvicorn worker processes inside one container** unless the state is shared. `WEB_CONCURRENCY=1` in the Dockerfiles for that reason.

### State that is per-process (and what breaks)

`TTLStore` captcha sessions/jobs, the default rate-limit counters, `HealthBoard` failure counts. With two instances the captcha request and the receipt request can land on different ones → "Captcha expired". Options:

- **Sticky routing** (Cloud Run `--session-affinity`, nginx `ip_hash`/cookie). Simplest; best-effort; required when the session holds a live object that can't be serialised (a Playwright page).
- **Serialise and share** — for HTTP flows like BBMP the session is just `cookies + hidden form fields + captcha bytes`: store that JSON in Redis under the session id and rebuild a client on whichever instance gets the next request. Rate-limit counters: `RATE_LIMIT_STORAGE=redis://…`.
- Job results/PDFs that outlive a request → object storage or Redis with a TTL, not instance memory.

### Docker

| | `Dockerfile.http` | `Dockerfile.playwright` |
|---|---|---|
| Base | `python:3.11-slim` + a Node stage that builds the frontend | same + `playwright install --with-deps chromium` |
| Measured size | **378 MB** | **2.37 GB** |
| Use | HTTP-only tools (the default) | only if §3 chose a real browser |

- The frontend is built in a Node stage, so `dist/` never has to be committed (Karnataka commits `frontend-v2/dist`, so a source change isn't live until someone rebuilds and commits it — don't copy that).
- Runs as a non-root user, has a `HEALTHCHECK` on `/api/ready`, installs one browser at most.
- **Karnataka's image is heavy for a reason you don't share:** its `requirements.txt` carries `torch`, `onnxruntime`, `opencv`, `easyocr`, `ddddocr`, `selenium` and Google AI libraries (this Mac's venv: **1.5 GB**, `torch` alone 443 MB) for captcha OCR and a Selenium login. The kit's `requirements.base.txt` is **92 MB** installed (with pytest). Don't import the Karnataka requirements.
- Playwright in containers: it launches Chromium without the sandbox by default, so no extra flag is needed (verified: Chromium starts as the non-root user in the image; `--no-sandbox` is a Selenium/Puppeteer concern). Keep **one browser per process** and open pages/contexts from it, cap concurrent pages, and size the instance's memory for the cap (≈ 0.3 GB + 0.2 GB × pages).
- Build and smoke-test locally: `docker build -f Dockerfile.http -t trudocs-<state> . && docker run --rm -p 8080:8080 -e SKIP_STARTUP=1 trudocs-<state>`, then `curl localhost:8080/api/health`.

### Cloud Run notes (if that's the target)

`gcloud run deploy` flags that matter: `--concurrency` (HTTP/async tools: tens per instance; Playwright tools: 1–2), `--min-instances 1` (avoid cold starts), `--max-instances` (protects the portal), `--memory` (512Mi for HTTP, 2Gi+ for Playwright), `--timeout` ≥ 120, `--session-affinity` if state is in-process, `--no-cpu-throttling` if you rely on the background `HealthBoard.checker()` (CPU is otherwise throttled between requests). Set `TRUST_PROXY_HOPS=1` and **verify at `/api/health`**.

### Watch it

The access log (`trudocs.access`) prints `METHOD /path status ms ip rid` for every `/api/*` call. Alert on rising 429 (abuse or a too-low limit), 502/503 (portal trouble or maintenance mode), and `rejected_busy` in `/api/health → gates`. `LOG_LEVEL` controls verbosity.

---

## 11. Testing

```bash
# kit tests — run from the skill folder (they assemble the §2 layout in a temp dir themselves)
python -m venv .venv && .venv/bin/pip install -r $SKILL/backend-kit/requirements.base.txt pytest
cd $SKILL/backend-kit && ../../../../.venv/bin/python -m pytest      # 57 tests, ~5 s, no network
```
Your own tool tests live in the state repo (`tests/`) and import `backend.kit.*` directly.

- Test a new tool the way `tests/test_bbmp_example.py` does: monkeypatch the scraper's `start_session`/`download_receipt` with a fake portal; assert single-use sessions, user-error vs portal-error mapping, maintenance mode, cover hook, 429, and that waiting doesn't block other routes.
- Then **one real run per tool by a human**, typing the captcha. Fakes can't tell you the portal changed.
- Frontend: drive the view with Playwright against the Vite dev server, mocking `/api/<tool>/*` with held responses — that lets you assert the disabled/locked states mid-request and the focus handling.
- Never import the app entrypoint in tests unless `SKIP_STARTUP=1` is set.

---

## 12. Gotchas (each one cost real time)

- **A correct captcha can still fail** — minimum age (§7), a second image fetch invalidating the first, or a dead session. Log (without the captcha text) the session id and age to tell which.
- **Portal filenames contain slashes** (`Receipt_…_05/10/2026.pdf`). `safe_filename()` everywhere a name touches disk or a header.
- **HTTP 200 with an HTML error page.** Always `is_pdf()`; parse `alert()` messages.
- **Dependent dropdowns are postbacks**, not static options. Replay the browser's sequence.
- **`maxLength` on pasted numeric fields** truncates before you can sanitise (§9).
- **React StrictMode double effects** duplicate async DOM work; use cancel flags.
- **Focus on a disabled input is a silent no-op** — refocus when the input becomes enabled again (`CaptchaField` does).
- **A browser's `localhost` view hides proxy problems.** Only the deployed `/api/health` shows whether the client IP is right.
- **Logging config.** Under uvicorn, `trudocs.*` INFO logs vanish unless something sets up logging; `create_app` does.
- **CRLF files** — check `file` before scripted edits and re-check the diff is additive.
- **VS Code yellow squiggles on imports** mean the wrong interpreter is selected, not missing packages (*Python: Select Interpreter* → the venv).
- **If `docker build` is slow,** you copied `node_modules` or `dist` into the context — check `.dockerignore`.

---

## 13. Definition of done (per tool)

- [ ] §0 intake answered: cover(s) supplied or "no cover" recorded; technology chosen by the user after §3.
- [ ] Scraper is pure, has timeouts everywhere, separates user errors / captcha errors / `PortalUnavailable`, checks `is_pdf()`, logs no personal data.
- [ ] Routes: input validated before the portal; `@limiter.limit` on every portal-facing route; calls inside `PortalGate`; `HealthBoard` registered and fed only portal-side failures; no `time.sleep`.
- [ ] Captcha (if any): user-typed, single-use session, fetched once, min-age wait async and outside the gate, validated before consumption, nothing written to disk.
- [ ] Cover: positions read with `cover_grid`, sample rendered **and shown to the user**, long/short values checked, non-Latin text checked if relevant.
- [ ] Frontend: view registered on mobile and desktop and in header + drawer; inputs lock while busy; friendly errors; `PDFViewer`; passes under `npm run dev` (StrictMode) and `npm run build`.
- [ ] Tests: fake-portal tests green; kit tests green; one real run by a human.
- [ ] Docker image builds, runs as non-root, `/api/ready` healthy, `/api/health` shows the correct `client_ip` behind the real balancer.
- [ ] No captcha solver anywhere.
