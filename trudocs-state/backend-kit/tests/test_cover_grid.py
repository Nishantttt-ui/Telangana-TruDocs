from pypdf import PdfReader

from backend.kit.cover_grid import make_grid

from conftest import make_pdf


def test_grid_keeps_page_size_and_labels_coordinates(tmp_path):
    tpl = tmp_path / "cover.pdf"; make_pdf(tpl, 842.0, 595.0, label="TEMPLATE")
    out = make_grid(tpl)
    assert out.name == "cover_grid.pdf"
    page = PdfReader(str(out)).pages[0]
    assert (float(page.mediabox.width), float(page.mediabox.height)) == (842.0, 595.0)
    txt = page.extract_text()
    assert "TEMPLATE 1" in txt and "x=100" in txt and "top=100" in txt


def test_design_space_labels_use_design_units_not_points(tmp_path):
    tpl = tmp_path / "cover.pdf"; make_pdf(tpl, 842.0, 595.0)
    out = make_grid(tpl, tmp_path / "g.pdf", design=(1403.2, 992.4), step=100)
    txt = PdfReader(str(out)).pages[0].extract_text()
    assert "x=1400" in txt and "top=900" in txt                  # beyond the 842x595 point range
