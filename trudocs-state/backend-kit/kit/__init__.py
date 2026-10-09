"""
TruDocs backend kit — state-agnostic building blocks.

Copy this folder to <repo>/backend/kit/ and import as `backend.kit.<module>`.
Nothing in here knows about any particular state or portal.

    portal_utils    JS-alert parsing, PDF sniffing, safe filenames / Content-Disposition
    ttl_store       bounded, thread-safe, single-use store for captcha sessions / jobs
    rate_limit      per-IP limiter (proxy-aware), 429 handler, PortalGate concurrency cap
    service_health  maintenance-mode tracker: N failures -> lockout -> auto-recover
    pdf_cover       config-driven cover page(s) prepended to a portal PDF
    cover_grid      draws a coordinate grid over a cover template (to pick text positions)
    app_factory     FastAPI app wiring: limiter, health, request log, static frontend
"""
