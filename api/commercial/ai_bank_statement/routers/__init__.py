"""Bank statement router package.

Split from the original monolithic router.py (1,782 lines) into focused modules:
  - upload.py       — File upload: POST /upload
  - crud.py         — CRUD, recycle bin, bulk-labels, merge, file download
  - transactions.py — Transaction CRUD + cross-statement transaction links
  - processing.py   — Reprocessing and review endpoints
  - _shared.py      — Shared helpers (get_tenant_id)
"""

from fastapi import APIRouter
from . import upload, crud, transactions, processing

router = APIRouter(prefix="/statements", tags=["statements"])

# Static-path sub-routers (upload, list, bulk-labels, merge, recycle-bin, transaction links)
# must be included before dynamic /{statement_id} routes.
# All /{statement_id} params are typed as int, so FastAPI will not confuse
# string-only paths (e.g. /recycle-bin, /transactions) with numeric IDs.
router.include_router(upload.router)
router.include_router(crud.router)
router.include_router(transactions.router)
router.include_router(processing.router)

__all__ = ["router"]
