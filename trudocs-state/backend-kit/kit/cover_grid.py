"""
cover_grid — draw a labelled coordinate grid over a cover template so text positions
can be read off by eye instead of guessed.

    python -m backend.kit.cover_grid covers/ec.pdf                 # writes covers/ec_grid.pdf
    python -m backend.kit.cover_grid covers/ec.pdf --design 1403.2 992.4 --step 50

Open the output PDF: lines every `step` design units (bold + labelled every 100), labelled
`x=…` along the top and `top=…` down the left edge. A text field's `x` / `top` in covers.json are the numbers at
the point where the text's top-left should sit. Without --design the template's own page
size in points is the design space (recommended for new covers).
"""

import argparse
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas


def make_grid(template, out=None, design=None, step: float = 50.0, label_every: float = 0) -> Path:
    label_every = label_every or max(step, 100.0)       # label every 100 units (or every line if step > 100)
    template = Path(template)
    out = Path(out) if out else template.with_name(template.stem + "_grid.pdf")

    page = PdfReader(str(template)).pages[0]
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    dw, dh = design if design else (w, h)
    sx, sy = w / dw, h / dh

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    minor, major = Color(0.1, 0.4, 0.9, 0.25), Color(0.9, 0.1, 0.1, 0.55)
    c.setFont("Helvetica", max(6.0, 7.0 * min(sx, sy)))

    v = 0.0
    while v <= dw:
        is_major = round(v % label_every, 6) in (0.0, label_every)
        c.setStrokeColor(major if is_major else minor)
        c.setLineWidth(0.6 if is_major else 0.3)
        c.line(v * sx, 0, v * sx, h)
        if is_major:
            c.setFillColor(major)
            c.drawString(v * sx + 2, h - 10, f"x={v:g}")
        v += step

    v = 0.0
    while v <= dh:
        is_major = round(v % label_every, 6) in (0.0, label_every)
        y = h - v * sy
        c.setStrokeColor(major if is_major else minor)
        c.setLineWidth(0.6 if is_major else 0.3)
        c.line(0, y, w, y)
        if is_major:
            c.setFillColor(major)
            c.drawString(2, y + 2, f"top={v:g}")
        v += step
    c.save()
    buf.seek(0)

    page.merge_page(PdfReader(buf).pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    with open(out, "wb") as f:
        writer.write(f)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template")
    ap.add_argument("-o", "--out")
    ap.add_argument("--design", nargs=2, type=float, metavar=("W", "H"))
    ap.add_argument("--step", type=float, default=50.0)
    a = ap.parse_args()
    print("wrote", make_grid(a.template, a.out, tuple(a.design) if a.design else None, a.step))
