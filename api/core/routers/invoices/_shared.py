"""Shared helpers used across invoice sub-routers."""

import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from typing import List as TypingList

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_attachment_info(invoice, new_attachments):
    """Helper function to get attachment info from modern attachment system"""
    has_attachment = len(new_attachments) > 0
    attachment_filename = new_attachments[0].filename if new_attachments else None

    # Fallback to legacy fields only if no modern attachments exist
    if not has_attachment and hasattr(invoice, 'attachment_filename') and invoice.attachment_filename:
        has_attachment = True
        attachment_filename = invoice.attachment_filename

    return has_attachment, attachment_filename


class BulkDeleteRequest(BaseModel):
    invoice_ids: TypingList[int]


def make_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_to_midnight_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to naive midnight (no tzinfo) to avoid timezone shifts on clients.

    If dt is timezone-aware, its date component is used.
    If dt is naive, its date component is used.
    """
    if dt is None:
        return None
    return datetime(dt.year, dt.month, dt.day)


def normalize_to_midnight_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize to midnight UTC (tz-aware). Suitable for timestamptz columns like created_at."""
    if dt is None:
        return None
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
