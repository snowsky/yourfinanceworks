"""Expense router package.

Split from the original monolithic expenses.py (2,795 lines) into focused modules:
  - crud.py        — Core CRUD, bulk ops (create/delete/labels), potential-duplicates
  - recycle_bin.py — Recycle bin: list deleted, empty, restore, permanently delete
  - attachments.py — Upload, list, download, delete, and reprocess expense attachments
  - reviews.py     — Review workflow: accept, reject, trigger, cancel
  - analytics.py   — Summary, trends, and category analytics
  - _shared.py     — Shared helpers and Pydantic request models
"""

from fastapi import APIRouter
from . import analytics, attachments, crud, recycle_bin, reviews

router = APIRouter(prefix="/expenses", tags=["expenses"])

# Static paths (analytics, recycle-bin, bulk-*, potential-duplicates) are registered
# before dynamic /{expense_id} paths via sub-router ordering below.
router.include_router(analytics.router)
router.include_router(crud.router)
router.include_router(recycle_bin.router)
router.include_router(attachments.router)
router.include_router(reviews.router)

__all__ = ["router"]
