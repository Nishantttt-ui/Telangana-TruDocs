"""Adangal Extract (Pahani) — ccla.telangana.gov.in, Java/Struts 1.x.

Confirmed live (2026-09-29) by reading the actual page source and JS:
- District/Division/Mandal/Village cascade is server-rendered for District,
  then AJAX (`landStatus.do?method=getDivisions|getMandals|getVillages`) for
  the rest.
- The "captcha" is not an image at all — the answer is rendered in plain text
  in a <span id="showCaptcha"> and duplicated into a hidden field
  (`hidden_captcha`). No OCR is needed: just read the value and echo it back
  as `captcha_input`. This was verified directly against the live page source,
  not assumed.
- The actual search is a plain HTML form POST (`document.forms['landStatus'].submit()`
  after setting the hidden `method` field), not an AJAX call — so submitting
  requires replaying that full form post, not calling a JSON endpoint.
"""
import re

import httpx

from backend.core.errors import BAD_INPUT, NOT_FOUND, PORTAL_DOWN, PORTAL_TIMEOUT, PortalError
from backend.core.rate_limit import RateLimiter

BASE_URL = "https://ccla.telangana.gov.in"
LANDING_PATH = "/landStatus.do"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

_throttle = RateLimiter(min_interval_seconds=1.0)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT},
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


def _post(client: httpx.Client, path: str, data: dict) -> httpx.Response:
    try:
        _throttle.wait()
        resp = client.post(path, data=data)
        resp.raise_for_status()
        return resp
    except httpx.TimeoutException as exc:
        raise PortalError(PORTAL_TIMEOUT, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise PortalError(PORTAL_DOWN, str(exc)) from exc


# Some of these endpoints render `<option value=32>` with NO quotes around the
# value (confirmed live on getDivisions/getMandals/getVillages) — the pattern
# below matches both quoted and unquoted attribute values.
_OPTION_RE = re.compile(r'<option[^>]*value=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))[^>]*>([^<]*)')


def _find_options(html: str) -> list:
    results = []
    for m in _OPTION_RE.finditer(html):
        value = m.group(1) or m.group(2) or m.group(3) or ""
        label = re.sub(r"\s+", " ", m.group(4)).strip()
        if value and value != "0":
            results.append({"value": value, "label": label})
    return results


def _options(html: str, select_name: str) -> list:
    m = re.search(rf'<select[^>]*name="{re.escape(select_name)}"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        return []
    return _find_options(m.group(1))


def fetch_districts() -> list:
    with _client() as client:
        html = _get(client, LANDING_PATH).text
    return _options(html, "userProperties(district_id)")


def fetch_divisions(district_id: str) -> list:
    # Confirmed live: params travel as a query string, not a POST body — the
    # site's own JS builds `landStatus.do?method=getDivisions&district_id=...`.
    with _client() as client:
        _get(client, LANDING_PATH)  # seed session cookie
        resp = _post(client, f"{LANDING_PATH}?method=getDivisions&district_id={district_id}", {})
    return _parse_ajax_options(resp.text)


def fetch_mandals(district_id: str, division_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _post(
            client,
            f"{LANDING_PATH}?method=getMandals&district_id={district_id}&division_id={division_id}",
            {},
        )
    return _parse_ajax_options(resp.text)


def fetch_villages(district_id: str, mandal_id: str) -> list:
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _post(
            client,
            f"{LANDING_PATH}?method=getVillages&district_id={district_id}&mandal_id={mandal_id}",
            {},
        )
    return _parse_ajax_options(resp.text)


def _parse_ajax_options(text: str) -> list:
    # These endpoints return a raw <option> fragment, not a full page.
    return _find_options(text)


def fetch_survey_options(village_id: str, option: str = "surveyNo") -> list:
    """`option` is "surveyNo", "khataNo", or "pattadarNo" — matches the
    portal's own toggle. Confirmed live: this endpoint (the currently-active
    JS, not the older commented-out version still present in the page source)
    takes all three fields in the POST body, with no query string."""
    with _client() as client:
        _get(client, LANDING_PATH)
        resp = _post(
            client,
            LANDING_PATH,
            {"method": "getOptions", "village_id": village_id, "optionval1": option},
        )
    if resp.text.strip() == "NODATA":
        return []
    return _parse_ajax_options(resp.text)


def fetch_adangal(
    *,
    district_id: str,
    division_id: str,
    mandal_id: str,
    village_id: str,
    survey_or_khata_value: str,
    option: str = "surveyNo",
) -> dict:
    if not all([district_id, division_id, mandal_id, village_id, survey_or_khata_value]):
        raise PortalError(BAD_INPUT, "district, division, mandal, village and survey/khata number are all required")
    if option not in ("surveyNo", "khataNo"):
        raise PortalError(BAD_INPUT, "option must be surveyNo or khataNo")

    with _client() as client:
        _get(client, LANDING_PATH)  # seed JSESSIONID

        # Confirmed live: the captcha value embedded in the initial page load is
        # NOT what the server validates the final submit against — only an
        # explicit refreshCaptcha call actually sets the session-bound expected
        # value (the page-load one caused a server-side "mismatch" rejection in
        # testing). Always fetch a fresh one this way immediately before submit.
        refresh_resp = _post(
            client, f"{LANDING_PATH}?method=refreshCaptcha", {"captchaType": "ror"}
        )
        captcha_value = refresh_resp.text.strip()
        if not captcha_value:
            raise PortalError(PORTAL_DOWN, "could not obtain a fresh captcha value")

        # The real form action includes a jsessionid-bearing path
        # (`/landStatus.done;jsessionid=...`); httpx's cookie jar already
        # tracks JSESSIONID from the Set-Cookie header, so posting back to the
        # plain landStatus.do with that cookie attached is equivalent and
        # avoids depending on regex-extracting the exact rewritten URL.
        payload = {
            "method": "getLandDetails",
            "userProperties(district_id)": district_id,
            "userProperties(division_id)": division_id,
            "userProperties(mandal_id)": mandal_id,
            "userProperties(village_id)": village_id,
            "userProperties(option1)": option,
            "userProperties(khata_survey_pattadar)": survey_or_khata_value,
            "userProperties(h_option1)": option,
            "userProperties(h_khata_survey_pattadar)": survey_or_khata_value,
            "hidden_captcha": captcha_value,
            "userProperties(captcha_input)": captcha_value,
        }
        resp = _post(client, LANDING_PATH, payload)

    return _parse_result(resp.text)


def _parse_result(html: str) -> dict:
    lower = html.lower()
    if "no record" in lower or "no data" in lower:
        raise PortalError(NOT_FOUND, "portal reported no record")
    if "captcha" in lower and ("doesnot match" in lower or "does not match" in lower or "invalid" in lower):
        raise PortalError("Search failed due to a security-check mismatch. Please try again.", "captcha mismatch on replay")

    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.S)
    return {
        "source": "adangal_pahani",
        "found": bool(tables),
        "raw_tables_html": tables[:3],
    }
