"""Tests for the invoice branding settings service."""

import pytest

from core.models.models_per_tenant import Settings
from core.services.invoice_branding import (
    DEFAULT_INVOICE_BRANDING,
    INVOICE_BRANDING_KEY,
    get_invoice_branding,
    validate_invoice_branding,
)


# --- validate_invoice_branding -------------------------------------------------

def test_validate_accepts_valid_payload():
    out = validate_invoice_branding({
        "brand_color": "#1E3A8A",
        "accent_color": "#3b82f6",
        "show_logo": False,
        "footer_text": "  Thanks for your business  ",
    })
    assert out["brand_color"] == "#1e3a8a"  # lowercased
    assert out["accent_color"] == "#3b82f6"
    assert out["show_logo"] is False
    assert out["footer_text"] == "Thanks for your business"  # trimmed


def test_validate_drops_unknown_keys():
    out = validate_invoice_branding({"brand_color": "#000000", "evil": "rm -rf"})
    assert out == {"brand_color": "#000000"}


@pytest.mark.parametrize("bad", ["red", "#fff", "#1e3a8", "1e3a8a", "#1e3a8az", ""])
def test_validate_rejects_bad_hex(bad):
    with pytest.raises(ValueError):
        validate_invoice_branding({"brand_color": bad})


def test_validate_rejects_overlong_footer():
    with pytest.raises(ValueError):
        validate_invoice_branding({"footer_text": "x" * 501})


def test_validate_partial_payload_only_returns_provided_keys():
    out = validate_invoice_branding({"show_logo": True})
    assert out == {"show_logo": True}


def test_validate_rejects_non_dict():
    with pytest.raises(ValueError):
        validate_invoice_branding("nope")


# --- get_invoice_branding ------------------------------------------------------

def test_get_returns_defaults_when_unset(db_session):
    assert get_invoice_branding(db_session) == DEFAULT_INVOICE_BRANDING


def test_get_merges_stored_over_defaults(db_session):
    db_session.add(Settings(key=INVOICE_BRANDING_KEY, value={"brand_color": "#abcdef"}))
    db_session.commit()

    result = get_invoice_branding(db_session)
    assert result["brand_color"] == "#abcdef"          # overridden
    assert result["accent_color"] == DEFAULT_INVOICE_BRANDING["accent_color"]  # default kept
    assert result["show_logo"] == DEFAULT_INVOICE_BRANDING["show_logo"]


def test_get_handles_empty_value(db_session):
    db_session.add(Settings(key=INVOICE_BRANDING_KEY, value=None))
    db_session.commit()
    assert get_invoice_branding(db_session) == DEFAULT_INVOICE_BRANDING


def test_get_falls_back_for_non_hex_color(db_session):
    # Defence-in-depth: colours land in CSS contexts that HTML autoescape does
    # not protect. A non-hex value reaching the DB through any path must fall
    # back to the default rather than being rendered.
    db_session.add(Settings(key=INVOICE_BRANDING_KEY, value={
        "brand_color": "red; } body { display: none }",
        "accent_color": "#abcdef",
        "footer_text": "Acme",
    }))
    db_session.commit()

    result = get_invoice_branding(db_session)
    assert result["brand_color"] == DEFAULT_INVOICE_BRANDING["brand_color"]  # sanitized
    assert result["accent_color"] == "#abcdef"  # valid value preserved
    assert result["footer_text"] == "Acme"  # non-colour fields untouched


# --- PDF generator branding override -------------------------------------------

def test_pdf_generator_applies_brand_color():
    from reportlab.lib import colors
    from core.utils.pdf_generator import InvoicePDFGenerator

    gen = InvoicePDFGenerator(branding={"brand_color": "#AABBCC"})
    assert gen.styles["InvoiceTitle"].textColor == colors.HexColor("#aabbcc")
    assert gen.styles["CompanyName"].textColor == colors.HexColor("#aabbcc")


def test_pdf_generator_falls_back_on_invalid_brand_color():
    from reportlab.lib import colors
    from core.utils.pdf_generator import InvoicePDFGenerator

    gen = InvoicePDFGenerator(template_name="modern", branding={"brand_color": "not-a-hex"})
    # modern template title colour is darkblue
    assert gen.styles["InvoiceTitle"].textColor == colors.darkblue


def test_pdf_generator_no_branding_uses_template():
    from reportlab.lib import colors
    from core.utils.pdf_generator import InvoicePDFGenerator

    gen = InvoicePDFGenerator(template_name="classic")
    assert gen.styles["InvoiceTitle"].textColor == colors.black


@pytest.mark.parametrize("bad", [
    "http://evil.example.com/logo.png",   # remote URL — not served from local static
    "/static/../../../etc/passwd",         # path traversal
    "logos/1/x.png",                        # missing leading /static/
    "",
])
def test_resolve_logo_path_rejects_unsafe(bad):
    from core.utils.pdf_generator import InvoicePDFGenerator
    gen = InvoicePDFGenerator()
    assert gen._resolve_logo_path(bad) is None


def test_resolve_logo_path_missing_file_is_none():
    from core.utils.pdf_generator import InvoicePDFGenerator
    gen = InvoicePDFGenerator()
    assert gen._resolve_logo_path("/static/logos/999999/nope.png") is None


def test_build_items_table_accepts_orm_rows():
    # Regression: the client portal / emailed PDF pass ORM InvoiceItem rows
    # (not dicts); the table builder must tolerate both. (db=None -> the
    # currency lookup falls back, so no DB needed.)
    from types import SimpleNamespace
    from core.utils.pdf_generator import InvoicePDFGenerator

    gen = InvoicePDFGenerator()
    orm_item = SimpleNamespace(description="Widget", quantity=2, price=10.0, amount=20.0, unit_of_measure=None)
    elements = gen._build_items_table([orm_item], "USD", None, False, 0, "percentage", 0)
    assert elements  # built without raising AttributeError

    # dicts still work
    dict_item = {"description": "Gadget", "quantity": 1, "price": 5.0, "amount": 5.0}
    assert gen._build_items_table([dict_item], "USD", None, False, 0, "percentage", 0)
