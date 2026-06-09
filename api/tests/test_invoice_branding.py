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
