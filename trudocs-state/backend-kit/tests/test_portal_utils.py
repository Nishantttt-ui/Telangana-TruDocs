from backend.kit.portal_utils import (content_disposition, filename_from_content_disposition, is_pdf,
                                      js_alert_messages, safe_filename, sniff_image_mime)


def test_alerts_ignore_boilerplate_and_handle_apostrophes():
    html = '''<script>alert("Thank you for clicking, but that's a demo link.")</script>
              <script>alert('Enter Valid Captcha Text');$('#x').focus();</script>'''
    assert js_alert_messages(html, ignore=("demo link",)) == ["Enter Valid Captcha Text"]
    assert len(js_alert_messages(html)) == 2
    assert js_alert_messages("<p>no scripts</p>") == []


def test_is_pdf():
    assert is_pdf(b"%PDF-1.7 ...") and not is_pdf(b"<html>") and not is_pdf(b"")


def test_sniff_image_mime_ignores_the_name():
    assert sniff_image_mime(b"\xff\xd8\xff\xe0abc") == "image/jpeg"      # a "CaptchaImage.png" that is a JPEG
    assert sniff_image_mime(b"\x89PNG\r\n\x1a\nxxxx") == "image/png"
    assert sniff_image_mime(b"GIF89a....") == "image/gif"
    assert sniff_image_mime(b"RIFF1234WEBPVP8 ") == "image/webp"
    assert sniff_image_mime(b"junk", "image/jpeg") == "image/jpeg"


def test_safe_filename_kills_path_separators():
    assert safe_filename("Receipt_253417396_05/10/2026.pdf") == "Receipt_253417396_05_10_2026.pdf"
    assert safe_filename('a:b*c?"d<e>f|g.pdf') == "a_b_c__d_e_f_g.pdf"
    assert safe_filename("..", "x.pdf") == "x.pdf" and safe_filename(None, "x.pdf") == "x.pdf"


def test_filename_from_content_disposition_variants():
    assert filename_from_content_disposition('attachment; filename=Receipt_1_05/10/2026.pdf') == "Receipt_1_05_10_2026.pdf"
    assert filename_from_content_disposition('inline; filename="a b.pdf"') == "a b.pdf"
    assert filename_from_content_disposition("attachment; filename*=UTF-8''%E0%B2%B0.pdf") == "ರ.pdf"
    assert filename_from_content_disposition(None, "d.pdf") == "d.pdf"


def test_content_disposition_is_latin1_safe_for_indic_names():
    v = content_disposition("ರಸೀದಿ 05/10.pdf")
    v.encode("latin-1")                                  # Starlette would raise on anything else
    assert "filename*=UTF-8''" in v and v.startswith("inline;")
    assert content_disposition("plain.pdf", inline=False) == 'attachment; filename="plain.pdf"'
