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
        logger.info(
            "Receipt scan extraction did not succeed: %s",
            getattr(ocr_result, "error_message", None),
        )
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
        raise ScanError(
            f"File type not allowed. Supported: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )
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
