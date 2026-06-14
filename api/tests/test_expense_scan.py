"""Tests for the synchronous receipt-scan service (touchless AP slice 1)."""

import pytest

from commercial.ai.services.ocr_service.expense_extraction import map_extraction_to_fields


def test_map_extraction_full():
    fields = map_extraction_to_fields({
        "vendor": "Acme Coffee",
        "total_amount": "12.50",
        "currency": "$",
        "date": "2026-06-10",
        "category": "Meals",
        "tax_amount": "1.10",
        "payment_method": "Visa",
        "reference_number": "R-99",
        "notes": "Team coffee",
    })
    assert fields["vendor"] == "Acme Coffee"
    assert fields["amount"] == 12.5
    assert fields["total_amount"] == 12.5
    assert fields["currency"] == "USD"          # symbol mapped to code
    assert fields["expense_date"] == "2026-06-10"
    assert fields["category"] == "Meals"
    assert fields["tax_amount"] == 1.1
    assert fields["payment_method"] == "Visa"
    assert fields["reference_number"] == "R-99"
    assert fields["notes"] == "Team coffee"


def test_map_extraction_omits_absent_keys():
    fields = map_extraction_to_fields({"vendor": "Solo", "amount": 5})
    assert fields["vendor"] == "Solo"
    assert fields["amount"] == 5.0
    assert "category" not in fields
    assert "tax_amount" not in fields
    assert "payment_method" not in fields


def test_map_extraction_amount_falls_back_to_amount_key():
    fields = map_extraction_to_fields({"amount": "7.00"})
    assert fields["amount"] == 7.0
    assert fields["total_amount"] == 7.0


def test_map_extraction_non_dict_returns_empty():
    assert map_extraction_to_fields(None) == {}
    assert map_extraction_to_fields("garbage") == {}


def test_map_extraction_unparseable_amount_omitted():
    fields = map_extraction_to_fields({"vendor": "X", "amount": "not-a-number"})
    assert fields["vendor"] == "X"
    assert "amount" not in fields
    assert "total_amount" not in fields
