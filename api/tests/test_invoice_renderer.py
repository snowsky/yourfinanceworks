from core.services.invoice_render.config import InvoiceTemplateConfig
from core.services.invoice_render.view_model import assemble_view_model
from core.services.invoice_render.renderer import render_invoice_html
from tests.test_invoice_view_model import _data, CFG


def test_html_contains_core_fields():
    html = render_invoice_html(assemble_view_model(_data(), CFG), CFG)
    assert "INV-1" in html and "Acme" in html and "Bob" in html
    assert "$90.00" in html  # total


def test_html_hides_notes_when_toggled_off():
    cfg = InvoiceTemplateConfig(brand_color="#000", accent_color="#000", footer_text="",
        show={"logo": True, "notes": False, "custom_fields": True, "footer": True})
    html = render_invoice_html(assemble_view_model(_data(notes="SECRET"), cfg), cfg)
    assert "SECRET" not in html


def test_html_hides_discount_when_invoice_flag_off():
    html = render_invoice_html(assemble_view_model(_data(meta={**_data()["meta"], "show_discount": False}), CFG), CFG)
    assert "Discount" not in html


def test_render_pdf_returns_valid_pdf_bytes():
    from core.services.invoice_render.renderer import render_invoice_pdf
    pdf = render_invoice_pdf(assemble_view_model(_data(), CFG), CFG)
    assert isinstance(pdf, bytes) and pdf[:5] == b"%PDF-" and len(pdf) > 1000
