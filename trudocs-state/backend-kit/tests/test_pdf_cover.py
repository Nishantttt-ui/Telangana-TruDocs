import json
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from backend.kit.pdf_cover import add_cover_page, apply_cover, load_registry

from conftest import make_pdf, text_items

A4_L = (842.0, 595.0)
A4_P = (595.0, 842.0)


@pytest.fixture
def covers_dir(tmp_path):
    d = tmp_path / "covers"; d.mkdir()
    make_pdf(d / "default.pdf", *A4_L, label="DEFAULT COVER")
    make_pdf(d / "ec.pdf", *A4_P, label="EC COVER")
    return d


def write_cfg(covers_dir, services=None, default=True):
    cfg = {"services": services or {}}
    if default:
        cfg["default"] = {"template": "covers/default.pdf",
                          "fields": [{"key": "name", "x": 100, "top": 200, "size": 20}]}
    p = covers_dir.parent / "covers.json"
    p.write_text(json.dumps(cfg)); return p


def test_resolution_service_specific_then_default_then_explicit_none(covers_dir):
    reg = load_registry(write_cfg(covers_dir, {
        "ec": {"template": "covers/ec.pdf", "fields": []},
        "rtc": None,
    }))
    assert reg.resolve("ec").template.name == "ec.pdf"
    assert reg.resolve("bhunaksha").template.name == "default.pdf"      # not configured -> default
    assert reg.resolve("rtc") is None                                   # explicit "no cover"


def test_no_default_and_unconfigured_service_means_no_cover(covers_dir):
    reg = load_registry(write_cfg(covers_dir, default=False))
    assert reg.resolve("anything") is None
    body = make_pdf(None, *A4_L)
    assert apply_cover(body, reg, "anything", {"name": "x"}) == body    # untouched, byte for byte


def test_missing_template_fails_loudly_at_load_time(covers_dir):
    p = covers_dir.parent / "covers.json"
    p.write_text(json.dumps({"default": {"template": "covers/nope.pdf", "fields": []}}))
    with pytest.raises(FileNotFoundError):
        load_registry(p)


def test_cover_is_prepended_and_body_pages_survive(covers_dir):
    reg = load_registry(write_cfg(covers_dir))
    body = make_pdf(None, *A4_L, pages=3, label="BODY")
    out = apply_cover(body, reg, "ec", {"name": "Harsha"})
    r = PdfReader(BytesIO(out))
    assert len(r.pages) == 4
    assert "BODY 1" in r.pages[1].extract_text() and "BODY 3" in r.pages[3].extract_text()


def test_text_lands_at_the_configured_position(covers_dir):
    reg = load_registry(write_cfg(covers_dir))
    out = apply_cover(make_pdf(None, *A4_L), reg, "x", {"name": "Harsha"})
    items = {t: (x, y, s) for t, x, y, s in text_items(out)}
    x, y, size = items["Harsha"]
    # origin top-left: baseline = page_h - (top + size*0.85)
    assert (x, size) == (100.0, 20.0)
    assert y == pytest.approx(595 - (200 + 20 * 0.85), abs=0.2)


def test_cover_and_text_scale_to_the_portal_pdfs_page_size(covers_dir):
    reg = load_registry(write_cfg(covers_dir))
    out = apply_cover(make_pdf(None, 1684.0, 1190.0), reg, "x", {"name": "Harsha"})   # a 2x page
    box = PdfReader(BytesIO(out)).pages[0].mediabox
    assert (float(box.width), float(box.height)) == (1684.0, 1190.0)
    items = {t: (x, y, s) for t, x, y, s in text_items(out)}
    x, y, size = items["Harsha"]
    assert (x, size) == (200.0, 40.0)


def test_portrait_template_is_fitted_to_a_landscape_body(covers_dir):
    reg = load_registry(write_cfg(covers_dir, {"ec": {"template": "covers/ec.pdf", "fields": []}}))
    out = apply_cover(make_pdf(None, *A4_L), reg, "ec", {})
    box = PdfReader(BytesIO(out)).pages[0].mediabox
    assert (float(box.width), float(box.height)) == A4_L


def test_missing_or_empty_values_do_not_break_the_download(covers_dir):
    reg = load_registry(write_cfg(covers_dir))
    for vals in ({}, {"name": ""}, {"name": None}, {"other": "x"}):
        out = apply_cover(make_pdf(None, *A4_L), reg, "x", vals)
        assert len(PdfReader(BytesIO(out)).pages) == 2
        assert all(t not in ("x",) for t, *_ in text_items(out))


def spec_with(covers_dir, field):
    p = covers_dir.parent / "c.json"
    p.write_text(json.dumps({"default": {"template": "covers/default.pdf", "fields": [field]}}))
    return load_registry(p).default


def test_max_width_shrinks_long_text_but_not_below_half(covers_dir):
    spec = spec_with(covers_dir, {"key": "n", "x": 50, "top": 100, "size": 40, "max_width": 200})
    out = add_cover_page(make_pdf(None, *A4_L), spec, {"n": "A Very Long Party Name Indeed Yes"})
    size = [s for t, x, y, s in text_items(out) if t.startswith("A Very")][0]
    assert 20.0 <= size < 40.0
    short = add_cover_page(make_pdf(None, *A4_L), spec, {"n": "Ram"})
    assert [s for t, x, y, s in text_items(short) if t == "Ram"][0] == 40.0       # short text untouched


def test_center_alignment_anchors_on_x(covers_dir):
    spec = spec_with(covers_dir, {"key": "n", "x": 400, "top": 100, "size": 30, "align": "center"})
    out = add_cover_page(make_pdf(None, *A4_L), spec, {"n": "Centered"})
    x = [x for t, x, y, s in text_items(out) if t == "Centered"][0]
    assert x == pytest.approx(400 - pdfmetrics.stringWidth("Centered", "Helvetica", 30) / 2, abs=0.3)


def test_characters_outside_latin1_print_as_question_marks_not_a_crash(covers_dir):
    spec = spec_with(covers_dir, {"key": "n", "x": 50, "top": 100, "size": 30})
    out = add_cover_page(make_pdf(None, *A4_L), spec, {"n": "ರಾಮ Ram"})
    assert any("Ram" in t for t, *_ in text_items(out))


def test_font_file_registers_a_ttf(covers_dir):
    import reportlab
    vera = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    if not vera.exists():
        pytest.skip("reportlab's bundled Vera.ttf not present")
    spec = spec_with(covers_dir, {"key": "n", "x": 50, "top": 100, "size": 30, "font_file": str(vera)})
    out = add_cover_page(make_pdf(None, *A4_L), spec, {"n": "TrueType"})
    assert any(t == "TrueType" for t, *_ in text_items(out))
