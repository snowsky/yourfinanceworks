"""Tests for validate_file_magic_bytes content-type spoofing protection."""

import pytest
from fastapi import HTTPException

from core.utils.file_validation import validate_file_magic_bytes

# Minimal valid magic-byte prefixes for each supported type.
PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
HEIC_BYTES = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
HTML_PAYLOAD = b"<html><script>alert(1)</script></html>"


@pytest.mark.unit
@pytest.mark.parametrize(
    "content,content_type",
    [
        (PDF_BYTES, "application/pdf"),
        (JPEG_BYTES, "image/jpeg"),
        (PNG_BYTES, "image/png"),
        (HEIC_BYTES, "image/heic"),
        (HEIC_BYTES, "image/heif"),
        (b"id,amount\n1,10\n", "text/csv"),
    ],
)
def test_valid_content_passes(content, content_type):
    # Should not raise for content matching the declared type.
    validate_file_magic_bytes(content, content_type)


@pytest.mark.unit
@pytest.mark.parametrize(
    "content_type",
    ["application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif"],
)
def test_html_payload_spoofing_declared_type_is_rejected(content_type):
    # An HTML/script payload uploaded under a safe declared type must be rejected
    # (this is the stored-XSS vector the check defends against).
    with pytest.raises(HTTPException) as exc:
        validate_file_magic_bytes(HTML_PAYLOAD, content_type)
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_truncated_heic_is_rejected():
    with pytest.raises(HTTPException):
        validate_file_magic_bytes(b"\x00\x00", "image/heic")


@pytest.mark.unit
def test_unknown_content_type_is_not_inspected():
    # Types without a registered signature are passed through unchanged
    # (no false positives for legitimately unsupported types).
    validate_file_magic_bytes(b"anything at all", "application/octet-stream")
