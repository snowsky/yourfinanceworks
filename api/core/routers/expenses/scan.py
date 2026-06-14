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
