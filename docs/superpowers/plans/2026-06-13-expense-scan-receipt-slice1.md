# Touchless AP — Slice 1 (Backend scan-receipt) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a synchronous `POST /api/v1/expenses/scan-receipt` that extracts a receipt's fields and returns them **without persisting anything**, so the web "Scan a bill" modal (slice 2) can preview-and-confirm.

**Architecture:** A pure helper `map_extraction_to_fields` maps a clean OCR `structured_data` dict to a stable field dict. A service `expense_scan.py` validates the upload (reusing the upload-receipt rules), runs extraction inline via `UnifiedOCRService`, maps the result, and cleans up the temp file — returning `{available, fields}` and degrading to `{available:false}` when the commercial AI module/extraction is unavailable. A new `expenses/scan.py` router submodule exposes the endpoint.

**Tech Stack:** FastAPI, SQLAlchemy, `commercial.ai` UnifiedOCRService (LiteLLM vision), pytest.

**Spec:** `docs/superpowers/specs/2026-06-13-touchless-ap-receipt-scan-design.md` (slice 1 only).

**Conventions (verified against the codebase):**
- Backend test: `docker compose exec -T api bash -c "cd /app && python -m pytest <path> -v"` (pytest is installed in the running api container; if a fresh container reports "No module named pytest", reinstall: `docker compose exec -T api bash -c "pip install --no-cache-dir 'pytest==9.0.3' 'pytest-asyncio==1.3.0' 'pytest-mock==3.14.1' 'pytest-cov==6.2.1'"`). Run ONLY the new test file — the full suite has pre-existing cross-file isolation failures.
- `pytest-asyncio` is installed; mark async tests with `@pytest.mark.asyncio`.
- The OCR field helpers live in `api/commercial/ai/services/ocr_service/expense_extraction.py`; its `_shared` module exports `first_key(d, keys)` and `parse_number(value)`. `CURRENCY_SYMBOL_MAP` is `from core.utils.currency`.
- `OCRResult` (from `commercial.ai.services.unified_ocr_service`) has `.success: bool`, `.structured_data: Optional[dict]`, `.error_message`.
- Magic-byte validation: `from core.utils.file_validation import validate_file_magic_bytes` (raises on mismatch).
- The expenses router is a package; submodules each define `router = APIRouter()` and are mounted in `api/core/routers/expenses/__init__.py` via `router.include_router(...)`.

---

## File Structure

- `api/commercial/ai/services/ocr_service/expense_extraction.py` (modify) — add the pure `map_extraction_to_fields` helper.
- `api/core/services/expense_scan.py` (new) — `ScanError`, `scan_receipt_bytes`, internal `_extract_structured` (the seam tests patch).
- `api/core/routers/expenses/scan.py` (new) — `POST /scan-receipt` endpoint.
- `api/core/routers/expenses/__init__.py` (modify) — mount the scan sub-router.
- `api/tests/test_expense_scan.py` (new) — unit tests for the helper and the service.

---

## Task 1: `map_extraction_to_fields` pure helper

**Files:**
- Modify: `api/commercial/ai/services/ocr_service/expense_extraction.py`
- Test: `api/tests/test_expense_scan.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_expense_scan.py`:

```python
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
    # keys with no extracted value are omitted entirely
    assert "category" not in fields
    assert "tax_amount" not in fields
    assert "payment_method" not in fields


def test_map_extraction_amount_falls_back_to_amount_key():
    # when total is missing, `amount` is used for both amount and total
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/test_expense_scan.py -v"`
Expected: FAIL — `ImportError: cannot import name 'map_extraction_to_fields'`.

- [ ] **Step 3: Add the helper**

In `api/commercial/ai/services/ocr_service/expense_extraction.py`, add this function (place it near the top, after the imports and before `apply_ocr_extraction_to_expense`):

```python
def map_extraction_to_fields(extracted: Any) -> Dict[str, Any]:
    """Map a clean OCR ``structured_data`` dict to a stable expense-field dict.

    Used by the synchronous scan-receipt path. Only the success path is handled
    (the input is the parsed ``structured_data`` from ``UnifiedOCRService``), so no
    raw-text fallback parsing is needed here. Keys with no extracted value are omitted
    so callers can distinguish "not found" from an empty value. Mirrors the field reads
    in ``apply_ocr_extraction_to_expense``.
    """
    if not isinstance(extracted, dict):
        return {}

    fields: Dict[str, Any] = {}

    vendor = first_key(extracted, ["vendor", "merchant", "vendor_name", "supplier"])
    if isinstance(vendor, str) and vendor.strip():
        fields["vendor"] = vendor.strip()

    total = parse_number(first_key(extracted, ["total_amount", "total", "amount"]))
    amount = parse_number(first_key(extracted, ["amount", "total_amount", "total"]))
    primary = total if total is not None else amount
    if primary is not None:
        fields["amount"] = primary
        fields["total_amount"] = primary

    currency = first_key(extracted, ["currency", "currency_code"])
    if isinstance(currency, str) and currency.strip():
        cur = currency.strip()
        fields["currency"] = CURRENCY_SYMBOL_MAP.get(cur, cur.upper())

    date_val = first_key(extracted, ["date", "expense_date", "transaction_date", "invoice_date"])
    if isinstance(date_val, str) and date_val.strip():
        fields["expense_date"] = date_val.strip()

    category = first_key(extracted, ["category"])
    if isinstance(category, str) and category.strip():
        fields["category"] = category.strip()

    tax = parse_number(first_key(extracted, ["tax_amount", "tax"]))
    if tax is not None:
        fields["tax_amount"] = tax

    payment = first_key(extracted, ["payment_method", "payment"])
    if isinstance(payment, str) and payment.strip():
        fields["payment_method"] = payment.strip()

    reference = first_key(extracted, ["reference_number", "reference", "invoice_number"])
    if isinstance(reference, str) and reference.strip():
        fields["reference_number"] = reference.strip()

    notes = first_key(extracted, ["notes", "description"])
    if isinstance(notes, str) and notes.strip():
        fields["notes"] = notes.strip()

    return fields
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/test_expense_scan.py -v"`
Expected: PASS — 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add api/commercial/ai/services/ocr_service/expense_extraction.py api/tests/test_expense_scan.py
git commit -m "feat(expenses): map_extraction_to_fields helper for sync receipt scan"
```

---

## Task 2: `expense_scan` service

**Files:**
- Create: `api/core/services/expense_scan.py`
- Test: `api/tests/test_expense_scan.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_expense_scan.py`:

```python
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
    # temp file existed during extraction and is cleaned up afterward
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
    # an extractor *exception* degrades to unavailable, not a 500
    assert result["available"] is False
    # temp file removed even though the extractor raised
    assert not __import__("os").path.exists(seen["path"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/test_expense_scan.py -k scan -v"`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.services.expense_scan'`.

- [ ] **Step 3: Write the service**

Create `api/core/services/expense_scan.py`:

```python
"""Synchronous receipt scan: extract fields from an uploaded receipt without persisting.

Validates the upload (mirroring the upload-receipt rules), runs OCR inline via the
commercial UnifiedOCRService, maps the result to stable expense fields, and always
cleans up the temp file. Degrades to ``{"available": False}`` when the commercial AI
module or the extraction is unavailable — it never raises for "AI off".
"""

import logging
import os
import tempfile
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.utils.file_validation import validate_file_magic_bytes
from commercial.ai.services.ocr_service.expense_extraction import map_extraction_to_fields

logger = logging.getLogger(__name__)

# Mirror the upload-receipt allowlist (api/core/routers/expenses/attachments.py).
_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
_ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
_MAX_BYTES = 10 * 1024 * 1024


class ScanError(Exception):
    """Raised for client-side validation failures (→ HTTP 400)."""


async def _extract_structured(temp_path: str, db: Optional[Session]) -> Optional[Dict[str, Any]]:
    """Run OCR on a file path, returning the structured_data dict or None.

    Returns None (never raises) when the commercial OCR module is unavailable or the
    extraction does not succeed. This is the seam tests patch.
    """
    try:
        from commercial.ai.services.unified_ocr_service import (
            UnifiedOCRService,
            DocumentType,
            OCRConfig,
        )
        from commercial.ai.services.ocr_service._shared import _get_ai_config_from_env

        ocr_config = OCRConfig(
            ai_config=_get_ai_config_from_env(),
            enable_ai_vision=True,
            enable_fallback_parsing=True,
            timeout_seconds=300,
            max_retries=3,
        )
        ocr_service = UnifiedOCRService(ocr_config)
        ocr_result = await ocr_service.extract_structured_data(
            temp_path, DocumentType.EXPENSE_RECEIPT, db_session=db
        )
        if ocr_result.success and ocr_result.structured_data:
            return ocr_result.structured_data
        logger.info("Receipt scan extraction did not succeed: %s",
                    getattr(ocr_result, "error_message", None))
        return None
    except ImportError as e:
        logger.warning("Commercial OCR unavailable for receipt scan: %s", e)
        return None


async def scan_receipt_bytes(
    db: Optional[Session],
    filename: Optional[str],
    content_type: Optional[str],
    contents: bytes,
) -> Dict[str, Any]:
    """Validate, extract, and map a receipt — without persisting anything."""
    if not filename:
        raise ScanError("Filename is required")
    ext = os.path.splitext(filename.lower())[1]
    if ext not in _ALLOWED_EXTENSIONS:
        raise ScanError(f"File type not allowed. Supported: {', '.join(sorted(_ALLOWED_EXTENSIONS))}")
    if content_type not in _ALLOWED_TYPES:
        raise ScanError("File type not allowed. Supported: PDF, JPG, PNG, HEIC, HEIF")
    if len(contents) > _MAX_BYTES:
        raise ScanError("File too large. Maximum size is 10 MB")

    # Anti-spoof: the bytes must match the declared content type.
    validate_file_magic_bytes(contents, content_type)

    temp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(contents)
            temp_path = tmp.name

        try:
            extracted = await _extract_structured(temp_path, db)
        except Exception as e:  # an extractor crash must degrade, not 500
            logger.warning("Receipt scan extraction raised: %s", e)
            extracted = None

        if not extracted:
            return {"available": False, "reason": "Could not read the receipt automatically"}
        return {"available": True, "fields": map_extraction_to_fields(extracted)}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Failed to remove temp scan file %s", temp_path)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/test_expense_scan.py -v"`
Expected: PASS — all 10 tests (5 helper + 5 service).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/expense_scan.py api/tests/test_expense_scan.py
git commit -m "feat(expenses): expense_scan service (validate, extract, map, cleanup)"
```

---

## Task 3: `scan-receipt` endpoint

**Files:**
- Create: `api/core/routers/expenses/scan.py`
- Modify: `api/core/routers/expenses/__init__.py`

- [ ] **Step 1: Write the endpoint**

Create `api/core/routers/expenses/scan.py`:

```python
"""Synchronous receipt scan endpoint: extract fields without creating an expense."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.services.expense_scan import ScanError, scan_receipt_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scan-receipt")
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "scan receipts")
    contents = await file.read()
    try:
        return await scan_receipt_bytes(db, file.filename, file.content_type, contents)
    except ScanError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 2: Mount the sub-router**

In `api/core/routers/expenses/__init__.py`:

Change the import line:
```python
from . import analytics, attachments, crud, export, merge, recycle_bin, reviews, voice
```
to:
```python
from . import analytics, attachments, crud, export, merge, recycle_bin, reviews, scan, voice
```

And add, immediately after `router.include_router(voice.router)` (keep `scan` among the
static paths, before the dynamic `/{expense_id}` routes in `attachments`/`crud`):
```python
router.include_router(scan.router)
```

- [ ] **Step 3: Verify the route is registered and imports cleanly**

Run: `docker compose exec -T api bash -c "cd /app && python -c \"from core.routers.expenses import router; print('/expenses/scan-receipt' in [r.path for r in router.routes])\""`
Expected: `True`.

- [ ] **Step 4: Commit**

```bash
git add api/core/routers/expenses/scan.py api/core/routers/expenses/__init__.py
git commit -m "feat(expenses): POST /expenses/scan-receipt endpoint"
```

---

## Task 4: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole new test file**

Run: `docker compose exec -T api bash -c "cd /app && python -m pytest tests/test_expense_scan.py -v"`
Expected: PASS — 10 tests.

- [ ] **Step 2: Confirm the expenses router still assembles and exposes the route**

Run: `docker compose exec -T api bash -c "cd /app && python -c \"from core.routers.expenses import router; print(sorted({r.path for r in router.routes if 'scan' in r.path}))\""`
Expected: `['/expenses/scan-receipt']`.

- [ ] **Step 3: No commit** — verification only. If anything fails, fix in the relevant task's file and re-run.

---

## Self-Review (completed by plan author)

**Spec coverage (slice 1):**
- Pure `map_extraction_to_fields` helper → Task 1 (+ note: does not refactor `apply`, per spec follow-up).
- `expense_scan.py` service with validation (ext/type/magic/size), temp file, inline extraction, mapping, cleanup, graceful degradation → Task 2.
- `ScanError` → 400; no DB write → Task 2 + Task 3.
- `POST /expenses/scan-receipt`, `require_non_viewer` → Task 3.
- Tests (mapping, graceful degrade, validation, temp cleanup; extraction mocked) → Tasks 1–2.

**Placeholder scan:** none — every code step is complete.

**Type consistency:** the service returns `{"available": bool, "fields"|"reason"}`; the helper returns the field dict consumed under `"fields"`. `_extract_structured` (the patched seam) returns `Optional[dict]`; `scan_receipt_bytes` treats falsy/None as unavailable. `ScanError` raised in the service, caught in the router. The `_MAX_BYTES`/`validate_file_magic_bytes`/`_extract_structured` names are patched in tests exactly as defined in the module.
