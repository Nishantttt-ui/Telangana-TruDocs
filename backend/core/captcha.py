"""Captcha OCR via ddddocr — lazy-loaded, thread-safe singleton engine.

Only Pattadar Passbook needs this (Adangal's "captcha" turns out to be a
server-rendered plaintext string, not an image — see adangal/client.py).
"""
import base64
import threading

_engine = None
_init_lock = threading.Lock()
_infer_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _init_lock:
            if _engine is None:
                import ddddocr
                _engine = ddddocr.DdddOcr(show_ad=False)
    return _engine


def solve(image_bytes: bytes) -> str:
    """Best-effort captcha guess from raw image bytes. '' on failure."""
    try:
        with _infer_lock:
            text = _get_engine().classification(image_bytes)
        return "".join(ch for ch in text if ch.isalnum())
    except Exception:
        return ""
