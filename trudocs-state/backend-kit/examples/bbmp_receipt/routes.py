"""
Worked example: a captcha-session tool built on the kit.   (application no -> captcha -> PDF)

This is the pattern for ANY portal where the user must type a captcha:

    POST /api/bbmp/captcha   {application_no}                  -> {session_id, years, captcha_b64, captcha_mime}
    POST /api/bbmp/receipt   {session_id, assessment_year,     -> application/pdf
                              captcha}

Why two calls: the portal's captcha is bound to the cookie session that was issued with it,
so the session that fetched the image must be the one that submits the answer. The backend
keeps that session (single-use, 10-minute TTL) between the calls; the browser only holds an
opaque session_id.

Where each kit piece is used:
    TTLStore        the captcha sessions (bounded, expiring, single-use)
    PortalGate      caps concurrent portal calls (global + per IP); the captcha-age wait
                    happens OUTSIDE the gate so a waiting request doesn't hold a portal slot
    HealthBoard     portal 5xx / timeouts count toward maintenance mode; a wrong captcha or
                    unknown number is the user's error and never counts
    apply_cover     optional: only when covers are configured for this service
    portal_utils    Content-Disposition that survives non-ASCII filenames

Copy to backend/tools/<tool>/routes.py next to scraper.py.
"""

import asyncio
import base64
import logging
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from backend.kit.pdf_cover import apply_cover
from backend.kit.portal_utils import content_disposition, sniff_image_mime
from backend.kit.rate_limit import PortalGate
from backend.kit.ttl_store import TTLStore

from . import scraper

log = logging.getLogger("trudocs.bbmp_receipt")

SERVICE = "bbmp_receipt"
PORTAL_DOWN = "BBMP tax portal is not responding. Please try again shortly."


class CaptchaRequest(BaseModel):
    application_no: str


class ReceiptRequest(BaseModel):
    session_id: str
    assessment_year: str
    captcha: str


def make_router(limiter, board=None, covers=None, gate: PortalGate | None = None) -> APIRouter:
    """
    limiter  kit.rate_limit.make_limiter()
    board    optional kit HealthBoard (registers/uses SERVICE)
    covers   optional kit CoverRegistry; the PDF is returned unchanged if it has no cover for SERVICE
    gate     optional PortalGate override (tests / tuning)
    """
    router = APIRouter()
    sessions: TTLStore = TTLStore(ttl=600, max_items=200)
    gate = gate or PortalGate(SERVICE, max_concurrent=6, per_ip=2)
    router.gate = gate            # so create_app(gates=[router.gate]) can show it in /api/health
    router.sessions = sessions

    def portal_failed(exc: BaseException):
        if board is not None:
            board.failure(SERVICE, exc)
        log.warning("portal failure: %r", exc)
        return HTTPException(502, PORTAL_DOWN)

    @router.post("/api/bbmp/captcha")
    @limiter.limit("10/minute")
    async def bbmp_captcha(request: Request, req: CaptchaRequest):
        app_no = req.application_no.strip()
        if not re.fullmatch(r"\d{10}", app_no):
            raise HTTPException(400, "Application number must be 10 digits.")
        if board is not None:
            board.ensure_available(SERVICE)
        async with gate.slot(request):
            try:
                sess = await asyncio.to_thread(scraper.start_session, app_no)
            except scraper.PortalUnavailable as e:
                raise portal_failed(e)
            except scraper.BbmpError as e:               # e.g. number not found: the user's input
                raise HTTPException(400, str(e))
            except Exception as e:                       # timeouts, DNS, TLS: the portal/network
                raise portal_failed(e)
        if board is not None:
            board.success(SERVICE)
        return {
            "session_id": sessions.put(sess),
            "years": sess.years,
            "captcha_b64": base64.b64encode(sess.captcha_img).decode(),
            "captcha_mime": sniff_image_mime(sess.captcha_img, sess.captcha_mime),
        }

    @router.post("/api/bbmp/receipt")
    @limiter.limit("10/minute")
    async def bbmp_receipt(request: Request, req: ReceiptRequest):
        if not req.captcha.strip():
            raise HTTPException(400, "Please enter the captcha.")       # before pop: don't burn the session
        sess = sessions.pop(req.session_id)              # single-use: win or lose, it's consumed
        if sess is None:
            raise HTTPException(410, "Captcha expired. Please try again.")
        if board is not None:
            board.ensure_available(SERVICE)

        # The portal rejects a correct captcha that arrives too soon after it was shown.
        # Wait it out here, async and outside the gate: sleeping costs no thread and no slot.
        wait = scraper.hold_remaining(sess)
        if wait > 0:
            await asyncio.sleep(wait)

        async with gate.slot(request):
            try:
                pdf, filename = await asyncio.to_thread(
                    scraper.download_receipt, sess, req.assessment_year, req.captcha, 60, False)
            except scraper.CaptchaError as e:            # wrong captcha: user error, not a portal failure
                raise HTTPException(422, str(e))
            except scraper.PortalUnavailable as e:
                raise portal_failed(e)
            except scraper.BbmpError as e:
                raise HTTPException(400, str(e))
            except Exception as e:
                raise portal_failed(e)
        if board is not None:
            board.success(SERVICE)

        if covers is not None:
            pdf = apply_cover(pdf, covers, SERVICE, {"application_no": sess.application_no})
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": content_disposition(filename, inline=True)})

    return router
