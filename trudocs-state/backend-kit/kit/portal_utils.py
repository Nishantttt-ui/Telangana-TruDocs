"""
Small helpers every portal scraper ends up needing. Each one exists because a real
portal broke without it.
"""

import re
from html import unescape
from urllib.parse import quote, unquote

# alert('...') / alert("...") with the matching quote — handles apostrophes inside "..."
_ALERT = re.compile(r"""alert\(\s*(['"])(.*?)\1\s*\)""", re.S)


def js_alert_messages(html: str, ignore: tuple[str, ...] = ()) -> list[str]:
    """
    Messages passed to JS alert('...') in an HTML page.

    ASP.NET WebForms portals report validation errors this way inside an HTTP 200
    page (e.g. alert('Enter Valid Captcha Text')), and often ship a boilerplate
    alert on EVERY page — pass its text in `ignore` (case-insensitive substring).
    """
    out = []
    for _, msg in _ALERT.findall(html or ""):
        msg = unescape(msg).strip()
        if msg and not any(i.lower() in msg.lower() for i in ignore):
            out.append(msg)
    return out


def is_pdf(data: bytes) -> bool:
    """True if the bytes start like a PDF. Check this — portals return 200 + HTML on errors."""
    return bool(data) and data[:5] == b"%PDF-"


def sniff_image_mime(data: bytes, default: str = "application/octet-stream") -> str:
    """Real image type from magic bytes. Don't trust the URL ('CaptchaImage.png' can be a JPEG)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return default


_BAD_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_filename(name: str | None, default: str = "download.pdf") -> str:
    """
    Make a portal-supplied filename safe to write to disk and to echo in a header.
    One portal sent 'Receipt_253417396_05/10/2026.pdf' — slashes became folders.
    """
    name = _BAD_FILENAME_CHARS.sub("_", name or "").strip(" .")
    return name or default


def filename_from_content_disposition(header: str | None, default: str = "download.pdf") -> str:
    """Pull the filename out of a Content-Disposition header (handles filename*=UTF-8''...)."""
    if not header:
        return default
    m = re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", header, re.I)
    if m:
        return safe_filename(unquote(m.group(1).strip()), default)
    m = re.search(r'filename\s*=\s*"([^"]*)"', header, re.I) or re.search(r"filename\s*=\s*([^;]+)", header, re.I)
    return safe_filename(m.group(1).strip() if m else None, default)


def content_disposition(filename: str, inline: bool = True) -> str:
    """
    Content-Disposition value that is safe for non-ASCII names (Indic party names!).
    Starlette encodes headers as latin-1 and raises on anything else, so emit an ASCII
    fallback plus the RFC 5987 filename* form.
    """
    filename = safe_filename(filename)
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace("?", "_").replace('"', "_")
    kind = "inline" if inline else "attachment"
    if ascii_name == filename:
        return f'{kind}; filename="{ascii_name}"'
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
