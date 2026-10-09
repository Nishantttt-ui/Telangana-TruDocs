"""
backend/tools/bbmp_receipt/scraper.py — Download a BBMP property-tax receipt PDF (Receipt Print form).

Portal: https://bbmptax.karnataka.gov.in/forms/PrintForms.aspx?rptype=3

The page is a classic ASP.NET WebForms form. Clicking "submit" POSTs the form
and the server answers with the PDF itself (Content-Disposition: attachment),
so no HTML scraping of the result is needed — only the form round-trip:

    1. GET  PrintForms.aspx?rptype=3
           -> ASP.NET_SessionId cookie + hidden fields (__VIEWSTATE, __EVENTVALIDATION, ...)
    2. POST PrintForms.aspx?rptype=3  with __EVENTTARGET=txtApp
           (the browser fires this when you tab out of the Application No. box)
           -> page re-rendered with the Assessment Year dropdown filled in,
              fresh __VIEWSTATE / __EVENTVALIDATION, and the captcha image URL
    3. GET  CaptchaImage.axd?guid=...
    4. POST PrintForms.aspx?rptype=3  with year + captcha + submit
           -> application/pdf

Submits are held until the captcha is MIN_CAPTCHA_AGE seconds old (see below).

Step 2 is required: until it runs, the year dropdown is empty and the server's
__EVENTVALIDATION rejects any year. Everything shares one cookie session, and the
captcha belongs to that session.

This module deliberately does NOT solve the captcha: the caller shows the image
to a person and passes what they typed to download_receipt().

Usage:
    from backend.tools.bbmp_receipt.scraper import start_session, download_receipt

    sess = start_session("1500082907")
    print(sess.years)                                      # ["2025-2026", "2024-2025", ...]
    sess.captcha_img                                       # JPEG bytes — show to the user
    pdf_bytes, filename = download_receipt(sess, "2025-2026", "68336")

HTTP routes (/api/bbmp/*) are in backend/tools/bbmp_receipt/routes.py.

Standalone: python -m backend.tools.bbmp_receipt.scraper 1500082907 2025-2026
"""

import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests


BBMP_BASE = "https://bbmptax.karnataka.gov.in"
FORM_URL  = f"{BBMP_BASE}/forms/PrintForms.aspx?rptype=3"

# The portal answers "Enter Valid Captcha Text" to a CORRECT captcha that arrives too
# soon after it was rendered (observed: 3 s rejected, 10 s accepted). Submits are held
# until the captcha is this many seconds old. Seconds.
MIN_CAPTCHA_AGE = 10

# Set BBMP_DEBUG=1 to also print the typed captcha and portal reply. Off by default:
# those lines are personal data / secrets and must not sit in production logs.
DEBUG = os.getenv("BBMP_DEBUG") == "1"

# ASP.NET control names (ContentPlaceHolder nesting is fixed by the master page)
_P          = "ctl00$ctl00$ContentPlaceHolder1$"
F_SEARCH    = _P + "txtSearchQuery"
F_LANG      = _P + "ddlLanguages"
F_APP       = _P + "ContentPlaceHolder1$txtApp"
F_YEAR      = _P + "ContentPlaceHolder1$ddlAsses"
F_CAPTCHA   = _P + "ContentPlaceHolder1$txtCaptcha"
F_SUBMIT    = _P + "ContentPlaceHolder1$Button1"
F_CSRF      = _P + "ContentPlaceHolder1$Hdn_CSRF"
F_IP        = _P + "lblIp"


class BbmpError(RuntimeError):
    """Portal rejected the request (message is the portal's own text if found)."""


class PortalUnavailable(BbmpError):
    """The portal itself failed (HTTP 5xx). Not the user's fault: show 'try again shortly',
    and count it toward maintenance mode — unlike a wrong captcha or unknown number."""


class CaptchaError(BbmpError):
    """Captcha text was wrong or the captcha session expired — fetch a new one."""


@dataclass
class BbmpSession:
    """One form load: cookies + hidden fields + the captcha issued with them."""
    http:           cffi_requests.Session
    application_no: str
    years:          list       # assessment years the portal offers for this application
    fields:         dict       # every <input name=...> on the page, as echoed back on POST
    captcha_img:    bytes      # raw image bytes
    captcha_mime:   str = "image/jpeg"
    created:     float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(extra: dict | None = None) -> dict:
    h = {
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         FORM_URL,
    }
    h.update(extra or {})
    return h


def _form_fields(soup: BeautifulSoup) -> dict:
    """All named inputs on the page (hidden state + empty text boxes)."""
    fields = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if name and inp.get("type") not in ("submit", "button", "image"):
            fields[name] = inp.get("value") or ""
    return fields


def _portal_message(html: str) -> str:
    """The portal reports problems as JS alert('...') — pull the real one out."""
    for msg in re.findall(r"alert\(\s*['\"](.+?)['\"]\s*\)", html, re.S):
        if "demo link" not in msg:          # boilerplate alert present on every page
            return msg.strip()
    return ""


def _http_error(what: str, resp) -> BbmpError:
    if resp.status_code >= 500:
        return PortalUnavailable(f"{what} HTTP {resp.status_code}")
    return BbmpError(f"{what} HTTP {resp.status_code}")


def _filename(resp) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    name = m.group(1).strip() if m else "bbmp_receipt.pdf"
    return re.sub(r'[\\/:*?"<>|]', "_", name)     # portal sends "Receipt_…_05/10/2026.pdf"


# ---------------------------------------------------------------------------
# Main functions
# ---------------------------------------------------------------------------

def _parse_form(html: str):
    """-> (soup, hidden/text fields, assessment-year options)."""
    soup   = BeautifulSoup(html, "html.parser")
    fields = _form_fields(soup)
    sel    = soup.find("select", {"name": F_YEAR})
    years  = [o["value"] for o in sel.find_all("option") if o.get("value")] if sel else []
    return soup, fields, years


def start_session(application_no: str, timeout: int = 30) -> BbmpSession:
    """
    Load the form, enter the application number (which fills the year dropdown),
    and fetch the captcha image issued with that page.

    Raises BbmpError if the portal knows no assessment years for the number.
    """
    application_no = application_no.strip()
    http = cffi_requests.Session(impersonate="chrome124")

    page = http.get(FORM_URL, headers=_headers({"Referer": BBMP_BASE + "/"}), timeout=timeout)
    if page.status_code != 200:
        raise _http_error("Form page", page)

    _, fields, _ = _parse_form(page.text)
    if "__VIEWSTATE" not in fields or F_CSRF not in fields:
        raise BbmpError("Form page layout changed — __VIEWSTATE / Hdn_CSRF not found")

    # Same postback the browser fires when the Application No. box loses focus
    fields.update({"__EVENTTARGET": F_APP, F_APP: application_no, F_LANG: "en-us"})
    page = http.post(
        FORM_URL, data=fields,
        headers=_headers({"Origin": BBMP_BASE}),
        timeout=timeout,
    )
    if page.status_code != 200:
        raise _http_error("Application-no postback", page)

    soup, fields, years = _parse_form(page.text)
    if not years:
        raise BbmpError("Application number not found. Please check it and try again.")

    img = soup.find("img", src=re.compile(r"CaptchaImage\.axd", re.I))
    if not img:
        raise BbmpError("Captcha image not found on form page")

    cap = http.get(urljoin(FORM_URL, img["src"]), headers=_headers(), timeout=timeout)
    if cap.status_code != 200 or not cap.content:
        raise _http_error("Captcha image", cap)

    print(f"[bbmp] Session ready — years {years}, captcha {len(cap.content)} bytes")
    return BbmpSession(
        http=http, application_no=application_no, years=years,
        fields=fields, captcha_img=cap.content,
        captcha_mime=cap.headers.get("content-type", "image/jpeg").split(";")[0],
    )


def hold_remaining(sess: BbmpSession) -> float:
    """Seconds still to wait before this session's captcha is old enough to submit."""
    return max(0.0, MIN_CAPTCHA_AGE - (time.time() - sess.created))


def download_receipt(
    sess: BbmpSession,
    assessment_year: str,
    captcha: str,
    timeout: int = 60,
    hold: bool = True,
) -> tuple[bytes, str]:
    """
    Submit the form and return (pdf_bytes, filename).

    Args:
        sess:            from start_session() — the captcha shown to the user belongs to it
        assessment_year: one of sess.years, e.g. "2025-2026"
        captcha:         what the user read off sess.captcha_img
        hold:            sleep out the MIN_CAPTCHA_AGE wait here (fine for scripts/CLI).
                         An async server passes False and awaits hold_remaining() itself,
                         so the wait doesn't occupy a worker thread.

    Raises:
        CaptchaError: wrong captcha or expired session —
                      call start_session() again for a fresh captcha
        BbmpError:    anything else (year not offered, HTTP error, ...)
    """
    assessment_year = assessment_year.strip()
    if assessment_year not in sess.years:
        raise BbmpError(f"Assessment year {assessment_year} is not available for this application.")

    data = dict(sess.fields)
    data.update({
        F_SEARCH:  "",
        F_LANG:    "en-us",
        F_APP:     sess.application_no,
        F_YEAR:    assessment_year,
        F_CAPTCHA: captcha.strip(),
        F_SUBMIT:  "submit",
        F_IP:      "",
    })

    wait = hold_remaining(sess)
    if hold and wait > 0:
        time.sleep(wait)
    if DEBUG:
        print(f"[bbmp] submit app={sess.application_no} year={assessment_year} "
              f"captcha={captcha.strip()!r} captcha_age={time.time() - sess.created:.0f}s")
    resp = sess.http.post(
        FORM_URL,
        data=data,
        headers=_headers({
            "Origin":         BBMP_BASE,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        }),
        timeout=timeout,
    )

    if resp.content[:4] == b"%PDF":
        name = _filename(resp)
        print(f"[bbmp] {name} — {len(resp.content) / 1024:.0f} KB PDF ✓")
        return resp.content, name

    # Not a PDF. A wrong captcha re-renders the form with alert('Enter Valid Captcha Text');
    # a dead session gets a generic "Oops.. Error on page" screen instead.
    if resp.status_code != 200:
        raise _http_error("Receipt POST", resp)
    msg = _portal_message(resp.text)
    if DEBUG:
        print(f"[bbmp] portal said: {msg or '(no alert)'!r}")
    if "captcha" in msg.lower() or "Oops.. Error on page" in resp.text:
        raise CaptchaError(msg or "Portal rejected the submit — session expired")
    raise BbmpError(msg or "Portal returned no PDF and no message")


# ---------------------------------------------------------------------------
# Standalone: python -m backend.tools.bbmp_receipt.scraper <application_no> [assessment_year]
# Opens the captcha in your image viewer (temp file, deleted right after), asks you
# to type it, and writes only the receipt PDF to the current directory.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m backend.tools.bbmp_receipt.scraper <application_no> [assessment_year]")
        sys.exit(1)

    app_no = sys.argv[1]

    sess = start_session(app_no)
    year = sys.argv[2] if len(sys.argv) > 2 else sess.years[0]

    # Show the captcha in the OS image viewer from the temp dir, and delete it as
    # soon as it's been read — nothing is left behind in the repo.
    import os, subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(sess.captcha_img)
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", tmp.name])
        elif sys.platform.startswith("win"):
            os.startfile(tmp.name)
        else:
            subprocess.run(["xdg-open", tmp.name])
        text = input("Captcha text: ").strip()
    finally:
        os.unlink(tmp.name)

    pdf_bytes, name = download_receipt(sess, year, text)

    with open(name, "wb") as f:
        f.write(pdf_bytes)
    print(f"\nDone → {name}")
