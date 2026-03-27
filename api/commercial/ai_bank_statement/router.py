"""Bank statement router — delegates to the routers/ package.

Split from a 1,782-line monolith into focused modules:
  routers/upload.py       — POST /upload
  routers/crud.py         — CRUD, recycle bin, bulk-labels, merge, file download
  routers/transactions.py — Transaction CRUD + cross-statement transaction links
  routers/processing.py   — Reprocessing and review endpoints
"""

from .routers import router

__all__ = ["router"]
