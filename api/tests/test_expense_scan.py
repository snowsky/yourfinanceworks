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


def test_map_extraction_grand_total_alias():
    fields = map_extraction_to_fields({"vendor": "X", "grand_total": "42.00"})
    assert fields["amount"] == 42.0
    assert fields["total_amount"] == 42.0


def test_map_extraction_non_dict_returns_empty():
    assert map_extraction_to_fields(None) == {}
    assert map_extraction_to_fields("garbage") == {}


def test_map_extraction_unparseable_amount_omitted():
    fields = map_extraction_to_fields({"vendor": "X", "amount": "not-a-number"})
    assert fields["vendor"] == "X"
    assert "amount" not in fields
    assert "total_amount" not in fields


from core.services import expense_scan
from core.services.expense_scan import ScanError, scan_receipt_bytes

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # minimal PNG-signature bytes


@pytest.mark.asyncio
async def test_scan_rejects_bad_extension():
    with pytest.raises(ScanError):
        await scan_receipt_bytes(None, "note.txt", "text/plain", b"hello")


@pytest.mark.asyncio
async def test_scan_rejects_oversize(monkeypatch):
    monkeypatch.setattr(expense_scan, "_MAX_BYTES", 10)
    with pytest.raises(ScanError):
        await scan_receipt_bytes(None, "r.png", "image/png", b"x" * 11)


@pytest.mark.asyncio
async def test_scan_unavailable_when_extractor_returns_none(monkeypatch):
    monkeypatch.setattr(expense_scan, "validate_file_magic_bytes", lambda *a, **k: None)

    async def fake_extract(path, db):
        return None  # simulates commercial AI absent / extraction failed

    monkeypatch.setattr(expense_scan, "_extract_structured", fake_extract)
    result = await scan_receipt_bytes(None, "r.png", "image/png", _PNG)
    assert result["available"] is False
    assert "reason" in result


@pytest.mark.asyncio
async def test_scan_success_maps_fields(monkeypatch):
    monkeypatch.setattr(expense_scan, "validate_file_magic_bytes", lambda *a, **k: None)
    captured = {}

    async def fake_extract(path, db):
        captured["path_existed"] = __import__("os").path.exists(path)
        return {"vendor": "Acme", "total_amount": "9.99", "currency": "USD"}

    monkeypatch.setattr(expense_scan, "_extract_structured", fake_extract)
    result = await scan_receipt_bytes(None, "r.png", "image/png", _PNG)
    assert result["available"] is True
    assert result["fields"]["vendor"] == "Acme"
    assert result["fields"]["amount"] == 9.99
    assert captured["path_existed"] is True


@pytest.mark.asyncio
async def test_scan_cleans_temp_on_extractor_error(monkeypatch):
    monkeypatch.setattr(expense_scan, "validate_file_magic_bytes", lambda *a, **k: None)
    seen = {}

    async def boom(path, db):
        seen["path"] = path
        raise RuntimeError("extractor blew up")

    monkeypatch.setattr(expense_scan, "_extract_structured", boom)
    result = await scan_receipt_bytes(None, "r.png", "image/png", _PNG)
    assert result["available"] is False
    assert not __import__("os").path.exists(seen["path"])
