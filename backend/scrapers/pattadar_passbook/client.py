"""Pattadar Passbook (Land Details Search) — bhubharati.telangana.gov.in,
Java/Spring Boot ("Dharani" backend family).

Two real things found by reading this page's actual JS (confirmed against a
real captured browser session's request/response pair, not guessed):

1. District/Mandal/Village cascade uses plain GET endpoints that return raw
   <option> fragments — but Mandal/Village need query params, not a request
   body (`getMandalFromDivisionCitizenPortal?district=..`,
   `getVillageFromMandalCitizenPortal?mandalId=..`).

2. The final search (`getPublicDataInfo`) requires two fields —
   `searchData` (the survey number) and `captcha` (the solved captcha text)
   — to be AES-128-CBC encrypted client-side before being sent, using a
   HARDCODED key+IV found in plain sight in their own `js/aes.js`:
     key = base64("u/Gu5posvwDsXUnV5Zaq4g==")
     iv  = base64("5D9r9ZVzEYYgha93/aUK2w==")
   PKCS7 padding, UTF-8 plaintext, output is base64(ciphertext) (no salt/IV
   prepended). Verified byte-for-byte against a real captured
   plaintext/ciphertext pair from the live site before relying on this.
"""
import random
import re

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

from backend.core.captcha import solve as solve_captcha
from backend.core.errors import BAD_INPUT, CAPTCHA_FAILED, NOT_FOUND, PORTAL_DOWN, PORTAL_TIMEOUT, PortalError
from backend.core.rate_limit import RateLimiter

BASE_URL = "https://bhubharati.telangana.gov.in"
LANDING_PATH = "/knowLandStatus"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

_throttle = RateLimiter(min_interval_seconds=0.5)

_AES_KEY = base64.b64decode("u/Gu5posvwDsXUnV5Zaq4g==")
_AES_IV = base64.b64decode("5D9r9ZVzEYYgha93/aUK2w==")


def _enc(plaintext: str) -> str:
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    return base64.b64encode(cipher.encrypt(padded)).decode("ascii")


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest", "Referer": BASE_URL + LANDING_PATH},
        timeout=20.0,
        follow_redirects=True,
    )


def _get(client: httpx.Client, path: str) -> httpx.Response:
    try:
        _throttle.wait()
        resp = client.get(path)
        resp.raise_for_status()
        return resp
    except httpx.TimeoutException as exc:
        raise PortalError(PORTAL_TIMEOUT, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise PortalError(PORTAL_DOWN, str(exc)) from exc


_OPTION_RE = re.compile(r'<option[^>]*value=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>([^<]*)')


def _find_options(html: str) -> list:
    results = []
    for m in _OPTION_RE.finditer(html):
        value = m.group(1) or m.group(2) or m.group(3) or ""
        label = re.sub(r"\s+", " ", m.group(4)).strip()
        if value and value != "0":
            results.append({"value": value, "label": label})
    return results


def fetch_districts() -> list:
    with _client() as client:
        html = _get(client, LANDING_PATH).text
    m = re.search(r'id="districtID"[^>]*>(.*?)</select>', html, re.S)
    return _find_options(m.group(1)) if m else []


def fetch_mandals(district_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getMandalFromDivisionCitizenPortal?district={district_id}")
    return _find_options(resp.text)


def fetch_villages(mandal_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getVillageFromMandalCitizenPortal?mandalId={mandal_id}")
    return _find_options(resp.text)


def fetch_survey_options(village_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getSurveyCitizen?villId={village_id}&flag=survey")
    return _find_options(resp.text)


def fetch_khata_options(village_id: str, survey_no: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getKhataNoCitizen?villId={village_id}&flag=khatanos&surveyNo={survey_no}")
    return _find_options(resp.text)


def fetch_pattadar_by_survey(
    *, district_id: str, mandal_id: str, village_id: str, survey_no: str, khata_id: str, max_attempts: int = 8
) -> dict:
    # Confirmed live: this portal's grid/mesh-noise captcha style measures
    # ~50% single-shot accuracy with ddddocr (manually verified against 6 real
    # samples) — a harder OCR class than Adangal's plaintext-in-HTML
    # "captcha". 8 attempts at ~50% each gives ~99.6% odds of at least one
    # success, which is the cheaper fix before reaching for a heavier
    # OCR tier (e.g. a vision-model fallback).
    if not all([district_id, mandal_id, village_id, survey_no, khata_id]):
        raise PortalError(BAD_INPUT, "district, mandal, village, survey number and khata number are all required")

    with _client() as client:
        _get(client, LANDING_PATH)  # seed JSESSIONID/setAuth cookies

        last_detail = ""
        for _ in range(max_attempts):
            rand = random.random()
            captcha_resp = _get(client, f"/captchaforViewRorandPahani?rand_number={rand}")
            # Confirmed live: every captcha sample observed on this portal is
            # uppercase-only (digits + uppercase letters) — ddddocr's general
            # model sometimes guesses a correct letter in the wrong case
            # (e.g. "1bEK9" for an actual "1BEK9"), which silently fails the
            # server-side match. Force uppercase rather than trust the raw
            # OCR case.
            captcha_text = solve_captcha(captcha_resp.content).upper()
            if not captcha_text:
                last_detail = "ocr produced empty result"
                continue

            # Confirmed live: this MUST be a POST with these fields as a form
            # body, not a GET with a query string — sending it as GET (even
            # with a 100%-verified-correct captcha, confirmed by manually
            # reading a captcha image myself to rule out OCR error) still
            # produced the same generic error page every time. POST is what
            # the real site's own jQuery call does (`Content-Type:
            # application/x-www-form-urlencoded`, confirmed from a captured
            # browser request), and district/mandal/divi are NOT part of the
            # body in that capture — only query items like `flagval` carry
            # the location context the server needs.
            data = {
                "villageId": village_id,
                "flagToSearch": "surveynumber",
                "searchData": _enc(survey_no),
                "flagval": "district",
                "khataNoIdselect": khata_id,
                "ReqType": "Citizen",
                "captcha": _enc(captcha_text),
            }
            try:
                _throttle.wait()
                resp = client.post("/getPublicDataInfo", data=data)
                resp.raise_for_status()
            except httpx.TimeoutException as exc:
                raise PortalError(PORTAL_TIMEOUT, str(exc)) from exc
            except httpx.HTTPError as exc:
                raise PortalError(PORTAL_DOWN, str(exc)) from exc

            lower = resp.text.lower()
            # Confirmed live: a wrong captcha does NOT produce a specific
            # "captcha incorrect" message — it produces this same generic
            # Spring/JSP error page ("Something went wrong... Click Here to
            # go to home page") that the app shows for any server-side
            # exception. Since every other field here is already known-valid,
            # treat this page as a captcha-retry signal, not a hard failure.
            if "something went wrong" in lower or 'id="txtlogout"' in lower:
                last_detail = f"portal error page (likely wrong captcha guess {captcha_text!r})"
                continue

            return _parse_result(resp.text)

    raise PortalError(CAPTCHA_FAILED, last_detail or "captcha retries exhausted")


_FIELD_RE = re.compile(r"<strong>([^<]+)</strong>\s*<br>\s*([^<]*)", re.S)
_SECTION_RE = re.compile(r'<h4 class="heading-details">([^<]+)</h4>')


def _parse_result(html: str) -> dict:
    lower = html.lower()
    if "no record" in lower or "no data found" in lower:
        raise PortalError(NOT_FOUND, "portal reported no record")
    if "something went wrong" in lower:
        raise PortalError(PORTAL_DOWN, "portal returned its generic error page")

    fields = {
        label.strip(): re.sub(r"\s+", " ", value).strip()
        for label, value in _FIELD_RE.findall(html)
    }
    sections = _SECTION_RE.findall(html)

    return {
        "source": "pattadar_passbook",
        "sections": sections,
        "raw_fields": fields,
        "found": bool(fields),
    }
