"""
Assemble a throwaway repo laid out exactly as SKILL.md tells people to copy it:

    <tmp>/backend/__init__.py
    <tmp>/backend/kit/...                 <- backend-kit/kit
    <tmp>/backend/tools/bbmp_receipt/...  <- backend-kit/examples/bbmp_receipt

so the tests import `backend.kit.*` the way a real state repo does, and a broken copy
instruction would fail here.
"""
import atexit
import shutil
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

KIT_ROOT = Path(__file__).resolve().parent.parent


def _assemble() -> Path:
    # Done at import time (not in a fixture): test modules import `backend.kit.*` while
    # pytest is still collecting, before any fixture would run.
    root = Path(tempfile.mkdtemp(prefix="trudocs-kit-"))
    (root / "backend").mkdir()
    (root / "backend" / "__init__.py").write_text("")
    shutil.copytree(KIT_ROOT / "kit", root / "backend" / "kit")
    tools = root / "backend" / "tools"
    tools.mkdir()
    (tools / "__init__.py").write_text("")
    shutil.copytree(KIT_ROOT / "examples" / "bbmp_receipt", tools / "bbmp_receipt")
    sys.path.insert(0, str(root))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    return root


ASSEMBLED_ROOT = _assemble()


def make_pdf(path_or_none, w: float, h: float, pages: int = 1, label: str = "page") -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    for i in range(pages):
        c.drawString(20, h - 40, f"{label} {i + 1}")
        c.showPage()
    c.save()
    data = buf.getvalue()
    if path_or_none:
        Path(path_or_none).write_bytes(data)
    return data


def text_items(pdf_bytes: bytes, page_index: int = 0):
    """
    [(text, x, y, font_size)] for the text drawn on one page, read straight from the content
    stream (Tm position + the active Tf size). pypdf's visitor_text reports a bogus matrix for
    reportlab's overlay layout, so don't use it for positions.
    """
    from pypdf.generic import ContentStream

    reader = PdfReader(BytesIO(pdf_bytes))
    page = reader.pages[page_index]
    items, size, pos = [], 0.0, (0.0, 0.0)
    for operands, op in ContentStream(page.get_contents(), reader).operations:
        if op == b"Tf":
            size = float(operands[1])
        elif op == b"Tm":
            pos = (float(operands[4]), float(operands[5]))
        elif op == b"Tj":
            raw = operands[0]
            text = raw if isinstance(raw, str) else raw.decode("latin-1")
            if text.strip():
                items.append((text.strip(), round(pos[0], 1), round(pos[1], 1), round(size, 1)))
    return items
