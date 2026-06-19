from core.services.invoice_render.config import InvoiceTemplateConfig
from core.services.invoice_render.view_model import assemble_view_model

CFG = InvoiceTemplateConfig(
    brand_color="#1e3a8a", accent_color="#3b82f6", footer_text="Thanks!",
    show={"logo": True, "notes": True, "custom_fields": True, "footer": True},
)

def _data(**over):
    base = dict(
        company={"name": "Acme", "logo_url": None, "address": "1 St",
                 "phone": "", "email": "a@b.co", "tax_id": ""},
        meta={"number": "INV-1", "issue_date": "2026-06-01", "due_date": "2026-06-15",
              "status": "pending", "currency": "USD", "show_discount": True},
        client={"name": "Bob", "email": "", "phone": "", "address": ""},
        items=[{"description": "Work", "quantity": 2, "unit_of_measure": "",
                "unit_price": 50.0, "amount": 100.0}],
        amount=100.0, paid_amount=30.0,
        discount={"type": "percentage", "value": 10.0},
        custom_fields={"PO": "123", "tax_amount": 5.0, "tax_rate": 5.0},
        notes="hi",
    )
    base.update(over)
    return base

def test_totals_with_percentage_discount_and_payment():
    vm = assemble_view_model(_data(), CFG)
    # subtotal 100, 10% discount = 10, total 90, paid 30, balance 60
    assert vm.totals.subtotal_raw == 100.0
    assert vm.totals.discount_amount_raw == 10.0
    assert vm.totals.total_raw == 90.0
    assert vm.totals.paid_raw == 30.0
    assert vm.totals.balance_raw == 60.0

def test_fixed_discount():
    vm = assemble_view_model(_data(discount={"type": "fixed", "value": 25.0}), CFG)
    assert vm.totals.discount_amount_raw == 25.0
    assert vm.totals.total_raw == 75.0

def test_tax_keys_split_out_of_custom_fields():
    vm = assemble_view_model(_data(), CFG)
    labels = {cf.label for cf in vm.custom_fields}
    assert "PO" in labels
    assert "tax_amount" not in labels and "tax_rate" not in labels

def test_currency_formatting_usd():
    vm = assemble_view_model(_data(), CFG)
    assert vm.totals.total == "$90.00"

def test_logo_hidden_when_config_off():
    cfg = InvoiceTemplateConfig(brand_color="#000", accent_color="#000",
        footer_text="", show={"logo": False, "notes": True, "custom_fields": True, "footer": True})
    vm = assemble_view_model(_data(company={"name": "Acme", "logo_url": "http://x/l.png",
        "address": "", "phone": "", "email": "", "tax_id": ""}), cfg)
    assert vm.company.logo_url is None  # suppressed by config
