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
from functools import lru_cache

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


def _client(timeout: float = 45.0) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest", "Referer": BASE_URL + LANDING_PATH},
        timeout=timeout,
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


# Districts/Mandals/Villages are government administrative boundaries — they
# don't change while this process is running, and are shared across every
# user. Caching them turns "every dropdown click re-hits the government
# server" into "the first click anyone makes populates it for everyone after,
# instantly" — the real fix for the cascade feeling slow, since each live
# call is a full round-trip to a Java/Spring server on the other side of
# India. Survey/khata numbers are also cached per (village[, survey]) since
# those are likewise static once published, just far more numerous.


@lru_cache(maxsize=1)
def fetch_districts() -> list:
    with _client() as client:
        html = _get(client, LANDING_PATH).text
    m = re.search(r'id="districtID"[^>]*>(.*?)</select>', html, re.S)
    return _find_options(m.group(1)) if m else []


@lru_cache(maxsize=64)
def fetch_mandals(district_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getMandalFromDivisionCitizenPortal?district={district_id}")
    return _find_options(resp.text)


@lru_cache(maxsize=1024)
def fetch_villages(mandal_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getVillageFromMandalCitizenPortal?mandalId={mandal_id}")
    return _find_options(resp.text)


@lru_cache(maxsize=4096)
def fetch_survey_options(village_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _get(client, f"/getSurveyCitizen?villId={village_id}&flag=survey")
    return _find_options(resp.text)


@lru_cache(maxsize=8192)
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

            encrypted_captcha = _enc(captcha_text)

            # Confirmed from captured browser session: the site calls
            # /checkcaptchaforViewRorandPahani with the encrypted captcha as
            # a URL query param (Content-Length: 0, empty body) before the
            # main submit. This "commits" the captcha to the server session —
            # skipping it causes the subsequent getPublicDataInfo to return
            # the generic error page even when the captcha would otherwise
            # be correct. Failures here (network errors, unexpected response)
            # fall through to retry; they are not treated as hard errors
            # because the pre-check does not itself return the land data.
            try:
                _throttle.wait()
                check_resp = client.post(
                    "/checkcaptchaforViewRorandPahani",
                    params={"captcha": encrypted_captcha},
                    content=b"",
                )
                check_resp.raise_for_status()
                check_body = check_resp.text.strip().lower()
                if check_body in ("false", "0", "fail", "invalid"):
                    last_detail = f"captcha pre-check rejected captcha guess {captcha_text!r}"
                    continue
            except (httpx.TimeoutException, httpx.HTTPError):
                pass  # if pre-check is unavailable, still attempt the main submit

            # Confirmed from captured browser session: district and mandal
            # travel as URL query-string params on getPublicDataInfo (NOT in
            # the POST body). The body carries villageId/searchData/captcha
            # etc. The server reads location context from the query string
            # and search params from the body.
            url_params = {
                "district": district_id,
                "mandal": mandal_id,
                "divi": "",
            }
            data = {
                "villageId": village_id,
                "flagToSearch": "surveynumber",
                "searchData": _enc(survey_no),
                "flagval": "district",
                "khataNoIdselect": khata_id,
                "ReqType": "Citizen",
                "captcha": encrypted_captcha,
            }
            try:
                _throttle.wait()
                resp = client.post("/getPublicDataInfo", params=url_params, data=data)
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
