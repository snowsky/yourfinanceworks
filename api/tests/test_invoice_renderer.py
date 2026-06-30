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


def test_html_applies_font_class():
    cfg = InvoiceTemplateConfig(font_family="serif")
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "font-serif" in html


def test_html_applies_logo_placement_and_size_classes():
    cfg = InvoiceTemplateConfig(logo_placement="right", logo_size="large")
    data = _data(company={"name": "Acme", "logo_url": "http://x/l.png", "address": "",
                          "phone": "", "email": "", "tax_id": ""})
    html = render_invoice_html(assemble_view_model(data, cfg), cfg)
    assert "logo-right" in html and "logo-large" in html


def test_css_defines_font_and_logo_classes():
    cfg = InvoiceTemplateConfig()
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert ".font-serif" in html and ".logo-large" in html  # CSS rules inlined in <style>


def test_inlined_css_is_not_html_escaped():
    # Autoescape must NOT mangle the <style> block: quotes and '>' combinators
    # have to reach the browser/WeasyPrint raw, or font-family declarations and
    # child selectors are invalid and silently dropped.
    cfg = InvoiceTemplateConfig()
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert 'font-family: "DejaVu Sans Mono"' in html   # raw quotes, not &#34;
    assert "&#34;" not in html and "&gt;" not in html


def test_default_order_renders_all_sections_in_order():
    html = render_invoice_html(assemble_view_model(_data(notes="HELLO"), CFG), CFG)
    # billto before items before totals
    assert html.index('class="billto"') < html.index('class="items"') < html.index('class="totals"')


def test_section_order_reorders_body():
    cfg = InvoiceTemplateConfig(section_order=["notes", "totals", "items", "custom", "billto"])
    html = render_invoice_html(assemble_view_model(_data(notes="HELLO"), cfg), cfg)
    assert html.index('class="notes"') < html.index('class="totals"') < html.index('class="billto"')


def test_section_order_independent_of_visibility():
    cfg = InvoiceTemplateConfig(
        section_order=["notes", "billto", "items", "totals", "custom"],
        show={"logo": True, "notes": False, "custom_fields": True, "footer": True},
    )
    html = render_invoice_html(assemble_view_model(_data(notes="SECRET"), cfg), cfg)
    assert "SECRET" not in html  # notes still hidden despite being first in order
    assert html.index('class="billto"') < html.index('class="items"')


_ITEM_HRS = [{"description": "Work", "quantity": 10, "unit_of_measure": "hrs",
              "unit_price": 50.0, "amount": 500.0}]


def test_default_columns_render_qty_and_price():
    cfg = InvoiceTemplateConfig()
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "<th>Qty</th>" in html
    assert "<th>Price</th>" in html


def test_hiding_unit_price_column_drops_price_header_and_cells():
    cfg = InvoiceTemplateConfig(columns={"quantity": True, "unit_price": False, "unit_of_measure": False})
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "<th>Price</th>" not in html
    assert "<th>Qty</th>" in html
    assert "<th>Amount</th>" in html  # always-on


def test_hiding_quantity_column_drops_qty_and_suppresses_uom():
    cfg = InvoiceTemplateConfig(columns={"quantity": False, "unit_price": True, "unit_of_measure": True})
    html = render_invoice_html(assemble_view_model(_data(items=_ITEM_HRS), cfg), cfg)
    assert "<th>Qty</th>" not in html
    assert "hrs" not in html  # UoM has no cell when Qty is hidden


def test_uom_merges_into_qty_cell_when_enabled():
    cfg = InvoiceTemplateConfig(columns={"quantity": True, "unit_price": True, "unit_of_measure": True})
    html = render_invoice_html(assemble_view_model(_data(items=_ITEM_HRS), cfg), cfg)
    assert "10 hrs" in html


def test_uom_absent_renders_bare_quantity():
    # default _data() item has unit_of_measure="" and quantity=2
    cfg = InvoiceTemplateConfig(columns={"quantity": True, "unit_price": True, "unit_of_measure": True})
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "<td>2</td>" in html  # bare quantity, no trailing UoM


def test_custom_fields_layout_emits_class():
    list_cfg = InvoiceTemplateConfig(custom_fields_layout="list")
    grid_cfg = InvoiceTemplateConfig(custom_fields_layout="grid")
    list_html = render_invoice_html(assemble_view_model(_data(custom_fields={"PO": "123"}), list_cfg), list_cfg)
    grid_html = render_invoice_html(assemble_view_model(_data(custom_fields={"PO": "123"}), grid_cfg), grid_cfg)
    assert 'class="custom custom-list"' in list_html
    assert 'class="custom custom-grid"' in grid_html
