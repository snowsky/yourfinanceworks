"""Unit tests for invoice status validation on write schemas.

Write paths (create/update/restore) reject unknown statuses; the response model
stays permissive so existing rows with any historical status still serialize.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from pydantic import ValidationError

from core.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    RestoreInvoiceRequest,
    Invoice,
    INVOICE_STATUSES,
)


def test_create_accepts_known_statuses():
    for status in INVOICE_STATUSES:
        inv = InvoiceCreate(amount=100.0, client_id=1, status=status)
        assert inv.status == status


def test_create_rejects_unknown_status():
    with pytest.raises(ValidationError):
        InvoiceCreate(amount=100.0, client_id=1, status="hacked")


def test_create_defaults_to_draft():
    inv = InvoiceCreate(amount=100.0, client_id=1)
    assert inv.status == "draft"


def test_update_rejects_unknown_status():
    with pytest.raises(ValidationError):
        InvoiceUpdate(status="not_a_status")


def test_update_allows_none_status():
    # status omitted on a partial update must remain valid (no change)
    upd = InvoiceUpdate(notes="x")
    assert upd.status is None


def test_update_accepts_approval_status():
    # approval-workflow statuses must pass (they round-trip through the API)
    assert InvoiceUpdate(status="approved").status == "approved"
    assert InvoiceUpdate(status="pending_approval").status == "pending_approval"


def test_restore_rejects_unknown_status():
    with pytest.raises(ValidationError):
        RestoreInvoiceRequest(new_status="bogus")


def test_restore_accepts_known_status():
    assert RestoreInvoiceRequest(new_status="sent").new_status == "sent"


def test_response_model_is_permissive_for_legacy_statuses():
    # Critical: a stored invoice with an unexpected status must still serialize,
    # so the response schema must NOT enforce the status set.
    inv = Invoice(
        id=1,
        number="INV-1",
        amount=100.0,
        client_id=1,
        status="some_legacy_or_future_status",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )
    assert inv.status == "some_legacy_or_future_status"
