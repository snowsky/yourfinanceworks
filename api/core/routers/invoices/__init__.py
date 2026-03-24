"""Invoice router package.

Split from the original monolithic invoices.py (3,640 lines) into focused modules:
  - crud.py        — Core CRUD, recycle bin, bulk ops, stats, calculate-discount, ai-status
  - history.py     — Invoice history endpoints
  - pdf_email.py   — PDF generation and email stub
  - attachments.py — Legacy and new attachment system
  - reviews.py     — Review / approval endpoints
  - _shared.py     — Shared helpers (get_attachment_info, BulkDeleteRequest, date normalizers)
"""

from fastapi import APIRouter
from . import crud, history, pdf_email, attachments, reviews, email_references

router = APIRouter(prefix="/invoices", tags=["invoices"])

# Route ordering: static paths in crud must be registered before /{invoice_id} dynamic paths.
# crud.py preserves the original ordering: POST /, GET /, static paths, then /{invoice_id}.
router.include_router(crud.router)
router.include_router(history.router)
router.include_router(pdf_email.router)
router.include_router(attachments.router)
router.include_router(reviews.router)
router.include_router(email_references.router)

__all__ = ["router"]
