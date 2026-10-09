"""
pdf_cover — prepend a branded cover page to a portal PDF.

Generalised from the Karnataka `pdf_cover.py`. Same maths, but nothing is hardcoded:
which template, where the text goes, and which service uses which cover all live in a
JSON config, so each state/tool is configured, not edited.

    covers.json
    {
      "default":  { "template": "covers/default.pdf",
                    "fields": [ {"key": "name", "x": 64, "top": 560, "size": 52, "color": "#163A2E"} ] },
      "services": {
        "ec":        { "template": "covers/ec.pdf", "design": [1403.2, 992.4],
                       "fields": [ {"key": "name", "x": 64, "top": 560, "size": 52} ] },
        "rtc":       null                      <- null = this service gets NO cover
      }                                           (service missing => falls back to "default")
    }

    registry = load_registry("covers.json")
    final    = apply_cover(portal_pdf_bytes, registry, "ec", {"name": "Harsha"})

COORDINATES. Positions are in "design units" with the origin at the TOP-LEFT of the
design space (x grows right, top grows down), like CSS/Figma. `design` is the size of that
space; omit it and the template's own page size (in PDF points) is used, which is the
simplest choice for a new cover. The design space is scaled onto the real page, so a cover
laid out once works for any page size. Use cover_grid.py to read coordinates off a template.

PAGE SIZE. The template is scaled to the portal PDF's FIRST page size, so a landscape A4
EC and a portrait A4 certificate each get a cover that matches. Pages flagged /Rotate
(rare) are not handled specially.

FONTS. Standard PDF fonts (Helvetica, Times-Roman, Courier + Bold/Oblique) are Latin only;
other characters print as '?'. For Kannada, Hindi, Tamil, ... give the field a
"font_file": a .ttf that covers the script. Reportlab does not do complex-script shaping,
so verify a sample visually before promising Indic cover text.
"""

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

log = logging.getLogger("trudocs.cover")

_BASELINE = 0.85       # baseline sits this fraction of the font size below `top` (matches the Karnataka cover)
_MIN_SHRINK = 0.5      # max_width never shrinks text below half its configured size


@dataclass(frozen=True)
class TextField:
    key: str
    x: float
    top: float
    size: float = 24.0
    color: str = "#000000"
    font: str = "Helvetica"
    font_file: Optional[str] = None      # absolute path after load_registry resolves it
    align: str = "left"                  # left | center | right  (x is the anchor)
    max_width: Optional[float] = None    # design units; text shrinks to fit


@dataclass(frozen=True)
class CoverSpec:
    template: Path
    design_w: float
    design_h: float
    fields: tuple = field(default_factory=tuple)


class CoverRegistry:
    def __init__(self, default: Optional[CoverSpec], services: dict):
        self.default = default
        self.services = services

    def resolve(self, service: str) -> Optional[CoverSpec]:
        """Service-specific cover if configured (None there = explicitly no cover), else default."""
        if service in self.services:
            return self.services[service]
        return self.default


# ── config loading ───────────────────────────────────────────────────────────

def _page_size(path: Path) -> tuple[float, float]:
    box = PdfReader(str(path)).pages[0].mediabox
    return float(box.width), float(box.height)


def _parse_spec(raw: dict, base: Path) -> CoverSpec:
    template = (base / raw["template"]).resolve()
    if not template.is_file():
        raise FileNotFoundError(f"cover template not found: {template}")
    if raw.get("design"):
        dw, dh = (float(v) for v in raw["design"])
    else:
        dw, dh = _page_size(template)
    fields = []
    for f in raw.get("fields", []):
        ff = f.get("font_file")
        fields.append(TextField(
            key=f["key"], x=float(f["x"]), top=float(f["top"]),
            size=float(f.get("size", 24)), color=f.get("color", "#000000"),
            font=f.get("font", "Helvetica"),
            font_file=str((base / ff).resolve()) if ff else None,
            align=f.get("align", "left"), max_width=f.get("max_width"),
        ))
    return CoverSpec(template=template, design_w=dw, design_h=dh, fields=tuple(fields))


def load_registry(config_path) -> CoverRegistry:
    """Load covers.json. Relative paths inside it are relative to the JSON file."""
    config_path = Path(config_path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    default = _parse_spec(raw["default"], base) if raw.get("default") else None
    services = {name: (None if spec is None else _parse_spec(spec, base))
                for name, spec in (raw.get("services") or {}).items()}
    return CoverRegistry(default, services)


# ── rendering ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=32)
def _template_bytes(path: str, mtime: float) -> bytes:
    return Path(path).read_bytes()


def _register_font(font_file: str) -> str:
    name = "ttf:" + Path(font_file).stem
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, font_file))
    return name


def _build_overlay(page_w: float, page_h: float, spec: CoverSpec, values: dict) -> Optional[BytesIO]:
    sx, sy = page_w / spec.design_w, page_h / spec.design_h
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    drew = False
    for f in spec.fields:
        text = values.get(f.key)
        if text is None or str(text) == "":
            continue                         # a missing value must not break the download
        text = str(text)
        if f.font_file:
            font = _register_font(f.font_file)
        else:
            font = f.font
            safe = text.encode("cp1252", "replace").decode("cp1252")
            if safe != text:
                log.warning("cover field %r has characters outside Latin-1; they print as '?'. "
                            "Give the field a font_file for that script.", f.key)
            text = safe
        size = f.size * sy
        if f.max_width:
            limit = f.max_width * sx
            floor = size * _MIN_SHRINK
            while size > floor and pdfmetrics.stringWidth(text, font, size) > limit:
                size *= 0.95
            size = max(size, floor)
        width = pdfmetrics.stringWidth(text, font, size)
        x = f.x * sx
        if f.align == "center":
            x -= width / 2
        elif f.align == "right":
            x -= width
        y = page_h - (f.top + f.size * _BASELINE) * sy
        c.setFillColor(HexColor(f.color))
        c.setFont(font, size)
        c.drawString(x, y, text)
        drew = True
    c.save()
    buf.seek(0)
    return buf if drew else None


def add_cover_page(pdf_bytes: bytes, spec: CoverSpec, values: dict) -> bytes:
    """Scale the template to the PDF's page size, overlay `values`, prepend. Bytes in, bytes out."""
    body = PdfReader(BytesIO(pdf_bytes))
    box = body.pages[0].mediabox
    target_w, target_h = float(box.width), float(box.height)

    path = str(spec.template)
    cover = PdfReader(BytesIO(_template_bytes(path, Path(path).stat().st_mtime))).pages[0]
    cover_w, cover_h = float(cover.mediabox.width), float(cover.mediabox.height)

    sx, sy = target_w / cover_w, target_h / cover_h
    if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
        cover.add_transformation(Transformation().scale(sx, sy))
        cover.mediabox.lower_left = (0, 0)
        cover.mediabox.upper_right = (target_w, target_h)

    overlay = _build_overlay(target_w, target_h, spec, values)
    if overlay is not None:
        cover.merge_page(PdfReader(overlay).pages[0])

    writer = PdfWriter()
    writer.add_page(cover)
    for page in body.pages:
        writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def apply_cover(pdf_bytes: bytes, registry: CoverRegistry, service: str, values: dict) -> bytes:
    """Resolve the cover for `service`; return the PDF unchanged if it has none."""
    spec = registry.resolve(service)
    if spec is None:
        return pdf_bytes
    return add_cover_page(pdf_bytes, spec, values)


# ── preview from the command line ────────────────────────────────────────────
#   python -m backend.kit.pdf_cover covers.json ec sample.pdf out.pdf name="Harsha B"

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 5:
        print('Usage: python -m backend.kit.pdf_cover covers.json <service> <input.pdf> <output.pdf> key="value" ...')
        sys.exit(1)
    cfg, service, src, dst, *pairs = sys.argv[1:]
    vals = dict(p.split("=", 1) for p in pairs)
    reg = load_registry(cfg)
    if reg.resolve(service) is None:
        print(f"service {service!r} resolves to NO cover")
    Path(dst).write_bytes(apply_cover(Path(src).read_bytes(), reg, service, vals))
    print("wrote", dst)
