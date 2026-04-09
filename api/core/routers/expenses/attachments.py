"""Attachment management: upload, list, download, delete, and reprocess expense attachments."""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.routers.auth import get_current_user
from core.services.search_service import search_service
from core.utils.audit import log_audit_event
from core.utils.file_deletion import delete_file_from_storage
from core.utils.rbac import require_non_viewer
from core.utils.timezone import get_tenant_timezone_aware_datetime
from commercial.ai.services.ocr_service import queue_or_process_attachment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.heic'}
_ALLOWED_TYPES = {
    'application/pdf': '.pdf',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/heic': '.heic',
    'image/heif': '.heif',
}
_MAX_BYTES = 10 * 1024 * 1024


@router.post("/{expense_id}/upload-receipt")
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "upload receipts")
    try:
        expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == False
        ).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type not allowed. Supported: {', '.join(_ALLOWED_EXTENSIONS)}")

        if file.content_type not in _ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="File type not allowed. Supported: PDF, JPG, PNG, HEIC, HEIF")

        contents = await file.read()
        if len(contents) > _MAX_BYTES:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB")

        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=500, detail="Tenant context not available")

        original_name = file.filename or "receipt"
        base_name = os.path.basename(original_name)
        base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)

        existing_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).count()
        if existing_count >= 10:
            raise HTTPException(status_code=400, detail="Maximum of 10 attachments per expense")

        try:
            try:
                from commercial.cloud_storage.service import CloudStorageService
                from commercial.cloud_storage.config import get_cloud_storage_config

                cloud_config = get_cloud_storage_config()
                cloud_storage_service = CloudStorageService(db, cloud_config)

                storage_result = await cloud_storage_service.store_file(
                    file_content=contents,
                    tenant_id=str(tenant_id),
                    item_id=expense_id,
                    attachment_type="expenses",
                    original_filename=base_name,
                    user_id=current_user.id,
                    metadata={
                        'content_type': file.content_type,
                        'expense_id': expense_id
                    }
                )

                if not storage_result.success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to store file: {storage_result.error_message}"
                    )

                if storage_result.file_url:
                    file_path = storage_result.file_key
                    file_size = storage_result.file_size or len(contents)
                    is_cloud_stored = True
                else:
                    tenant_folder = f"tenant_{tenant_id}"
                    receipts_dir = Path("attachments") / tenant_folder / "expenses"
                    name_without_ext = os.path.splitext(base_name)[0][:100]
                    ext_from_ct = _ALLOWED_TYPES[file.content_type]
                    unique_suffix = str(uuid.uuid4())
                    filename = f"expense_{expense_id}_{name_without_ext}_{unique_suffix}{ext_from_ct}"
                    file_path = str(receipts_dir / filename)
                    file_size = len(contents)
                    is_cloud_stored = False

                logger.info(f"File stored successfully: {file_path} (cloud: {is_cloud_stored})")
            except ImportError:
                logger.info("Commercial CloudStorageService not found, falling back to local storage")
                raise Exception("Commercial module not found")

        except Exception as e:
            if "Commercial module not found" not in str(e):
                logger.error(f"Cloud storage service error: {e}")
            tenant_folder = f"tenant_{tenant_id}"
            receipts_dir = Path("attachments") / tenant_folder / "expenses"
            receipts_dir.mkdir(parents=True, exist_ok=True)

            name_without_ext = os.path.splitext(base_name)[0][:100]
            ext_from_ct = _ALLOWED_TYPES[file.content_type]
            unique_suffix = str(uuid.uuid4())
            filename = f"expense_{expense_id}_{name_without_ext}_{unique_suffix}{ext_from_ct}"
            file_path = receipts_dir / filename

            from core.utils.file_validation import validate_file_path
            validated_path = validate_file_path(str(file_path), must_exist=False)

            with open(validated_path, "wb") as buffer:
                buffer.write(contents)

            file_path = str(file_path)
            file_size = len(contents)
            is_cloud_stored = False
            logger.info(f"File stored locally as fallback: {file_path}")

        from core.models.models_per_tenant import ExpenseAttachment as EAtt
        attachment = EAtt(
            expense_id=expense_id,
            filename=file.filename,
            content_type=file.content_type,
            file_size=file_size,
            file_path=file_path,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        attachment_id = attachment.id

        try:
            expense.imported_from_attachment = True
            disable_ai = getattr(expense, "disable_ai_recognition", False)
            if not expense.manual_override and not disable_ai:
                expense.analysis_status = "queued"
            elif disable_ai:
                expense.analysis_status = "skipped"
                logger.info(f"AI recognition disabled for expense {expense_id}")
            expense.updated_at = get_tenant_timezone_aware_datetime(db)
            db.commit()
            db.refresh(expense)

            try:
                from core.models.database import get_tenant_context
                tenant_id = get_tenant_context()
            except Exception:
                tenant_id = None
            disable_ai = getattr(expense, "disable_ai_recognition", False)
            if not disable_ai:
                from core.services.license_service import LicenseService
                license_service = LicenseService(db)
                if not license_service.has_feature("ai_expense"):
                    logger.info(f"Skipping AI processing for expense {expense_id} - ai_expense feature not licensed")
                    expense.analysis_status = "skipped"
                    db.commit()
                else:
                    queue_or_process_attachment(db, tenant_id, expense_id, attachment_id, str(file_path))
            else:
                logger.info(f"Skipping AI processing for expense {expense_id} - AI recognition disabled")
        except Exception as post_commit_err:
            logger.warning(f"Non-fatal error after attachment commit for expense {expense_id}: {post_commit_err}")
            try:
                db.rollback()
            except Exception:
                pass

        return {
            "message": "Attachment uploaded successfully",
            "filename": file.filename,
            "size": file_size,
            "file_path": str(file_path),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload receipt: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload receipt")


@router.get("/{expense_id}/attachments")
async def list_expense_attachments(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.is_deleted == False
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).order_by(ExpenseAttachment.uploaded_at.desc()).all()
    return [
        {
            "id": att.id,
            "filename": att.filename,
            "content_type": att.content_type,
            "file_size": att.file_size,
            "uploaded_at": att.uploaded_at.isoformat() if att.uploaded_at else None,
            "analysis_status": att.analysis_status,
            "analysis_error": att.analysis_error,
            "analysis_result": att.analysis_result,
            "extracted_amount": att.extracted_amount,
        }
        for att in attachments
    ]


@router.post("/{expense_id}/reprocess")
async def reprocess_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Reprocess expense OCR analysis for expenses that can be reprocessed."""
    require_non_viewer(current_user, "reprocess expenses")
    try:
        expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == False
        ).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        if expense.analysis_status not in ["not_started", "pending", "queued", "failed", "cancelled", "done"]:
            raise HTTPException(status_code=400, detail=f"Cannot reprocess expense with status: {expense.analysis_status}")

        attachments = (
            db.query(ExpenseAttachment)
            .filter(ExpenseAttachment.expense_id == expense_id)
            .order_by(ExpenseAttachment.uploaded_at.desc())
            .all()
        )
        if not attachments or not any(getattr(att, "file_path", None) for att in attachments):
            raise HTTPException(status_code=400, detail="No attachments found to reprocess")

        from core.models.processing_lock import ProcessingLock

        if ProcessingLock.is_locked(db, "expense", expense_id):
            if expense.analysis_status in ["done", "failed"]:
                logger.info(f"Releasing stale lock for expense {expense_id} in terminal state '{expense.analysis_status}'")
                ProcessingLock.release_lock(db, "expense", expense_id)
                db.commit()
            else:
                lock_info = ProcessingLock.get_active_lock_info(db, "expense", expense_id)
                return {
                    "message": "Expense is already being processed",
                    "status": "already_processing",
                    "lock_info": lock_info
                }

        request_id = f"reprocess_{expense_id}_{datetime.now(timezone.utc).timestamp()}"
        if not ProcessingLock.acquire_lock(
            db, "expense", expense_id, current_user.id,
            lock_duration_minutes=30, metadata={"request_id": request_id}
        ):
            lock_info = ProcessingLock.get_active_lock_info(db, "expense", expense_id)
            return {
                "message": "Expense is already being processed by another request",
                "status": "already_processing",
                "lock_info": lock_info
            }

        try:
            from core.models.database import get_tenant_context
            tenant_id = get_tenant_context()

            from core.services.license_service import LicenseService
            license_service = LicenseService(db)
            if not license_service.has_feature("ai_expense"):
                logger.info(f"Cannot reprocess expense {expense_id} - ai_expense feature not licensed")
                expense.analysis_status = "skipped"
                db.commit()
                ProcessingLock.release_lock(db, "expense", expense_id)
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "FEATURE_NOT_LICENSED",
                        "message": "AI expense processing requires a business license. Please upgrade to access AI-powered expense analysis.",
                        "feature_id": "ai_expense",
                        "upgrade_required": True
                    }
                )

            expense.analysis_status = "queued"
            expense.analysis_error = None
            expense.manual_override = False
            expense.updated_at = get_tenant_timezone_aware_datetime(db)
            db.commit()

            for att in attachments:
                if getattr(att, "file_path", None):
                    queue_or_process_attachment(
                        db=db,
                        tenant_id=tenant_id,
                        expense_id=expense_id,
                        attachment_id=att.id,
                        file_path=str(att.file_path),
                    )

            logger.info(f"Reprocess started for expense {expense_id} with {len([a for a in attachments if getattr(a, 'file_path', None)])} attachment(s) by user {current_user.id} (request_id: {request_id})")

            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="REPROCESS_EXPENSE",
                resource_type="expense",
                resource_id=str(expense_id),
                resource_name=getattr(expense, "vendor", None),
                details={"expense_id": expense_id, "request_id": request_id}
            )

            return {"message": "Expense reprocessing started", "status": "queued", "request_id": request_id}

        except Exception as e:
            ProcessingLock.release_lock(db, "expense", expense_id)
            logger.error(f"Failed to reprocess expense {expense_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to reprocess expense")

    except HTTPException:
        raise
    except Exception as e:
        try:
            from core.models.processing_lock import ProcessingLock
            ProcessingLock.release_lock(db, "expense", expense_id)
        except Exception:
            pass
        db.rollback()
        logger.error(f"Failed to reprocess expense {expense_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess expense")


@router.delete("/{expense_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense_attachment(
    expense_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "delete attachments")

    att = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id, ExpenseAttachment.expense_id == expense_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if att.file_path:
        await delete_file_from_storage(att.file_path, current_user.tenant_id, current_user.id, db)

    db.delete(att)
    db.commit()
    return None


@router.get("/{expense_id}/attachments/{attachment_id}/download")
async def download_expense_attachment(
    expense_id: int,
    attachment_id: int,
    inline: bool = False,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    import mimetypes
    from io import BytesIO

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    logger.info(f"Downloading attachment {attachment_id} for expense {expense_id}, tenant {current_user.tenant_id}")

    att = db.query(ExpenseAttachment).filter(
        ExpenseAttachment.id == attachment_id,
        ExpenseAttachment.expense_id == expense_id
    ).first()
    if not att:
        logger.error(f"Attachment {attachment_id} not found for expense {expense_id}")
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not att.file_path:
        logger.error(f"Attachment {attachment_id} has no file_path")
        raise HTTPException(status_code=404, detail="Attachment file not found")

    logger.info(f"Attachment found: id={att.id}, file_path='{att.file_path}', filename='{att.filename}'")

    cloud_enabled = os.getenv('CLOUD_STORAGE_ENABLED', 'false').lower() == 'true'

    is_cloud_path = (
        cloud_enabled
        and not att.file_path.startswith('/')
        and not att.file_path.startswith('attachments/')
    )

    logger.info(f"Storage type: {'cloud' if is_cloud_path else 'local'} (cloud_enabled={cloud_enabled})")

    def _resolve_media_type(content_type: str | None, filename: str | None) -> str:
        if content_type and content_type not in ('application/octet-stream',):
            return content_type
        guessed, _ = mimetypes.guess_type(filename or '')
        return guessed or 'application/octet-stream'

    def _serve_local(file_path_str: str) -> StreamingResponse | None:
        try:
            from core.utils.file_validation import validate_file_path
            validated = validate_file_path(file_path_str)
            if not os.path.exists(validated):
                logger.info(f"Local file not found: {validated}")
                return None
            with open(validated, 'rb') as f:
                content = f.read()
            media_type = _resolve_media_type(att.content_type, att.filename)
            disposition = "inline" if inline else "attachment"
            logger.info(f"Serving local file: {validated} ({len(content)} bytes)")
            return StreamingResponse(
                BytesIO(content),
                media_type=media_type,
                headers={
                    "Content-Disposition": f"{disposition}; filename={att.filename}",
                    "Content-Length": str(len(content)),
                }
            )
        except Exception as e:
            logger.warning(f"Local file serve failed for '{file_path_str}': {e}")
            return None

    async def _serve_cloud(file_key: str) -> StreamingResponse | None:
        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config
            cloud_config = get_cloud_storage_config()
            svc = CloudStorageService(db, cloud_config)
            result = await svc.retrieve_file(
                file_key=file_key,
                tenant_id=str(current_user.tenant_id),
                user_id=current_user.id,
                generate_url=False,
            )
            if result.success and result.file_content:
                media_type = _resolve_media_type(att.content_type, att.filename)
                disposition = "inline" if inline else "attachment"
                logger.info(f"Serving cloud file: '{file_key}' ({len(result.file_content)} bytes)")
                return StreamingResponse(
                    BytesIO(result.file_content),
                    media_type=media_type,
                    headers={
                        "Content-Disposition": f"{disposition}; filename={att.filename}",
                        "Content-Length": str(len(result.file_content)),
                    }
                )
            logger.warning(f"Cloud retrieve returned no content for '{file_key}': {result.error_message}")
        except Exception as e:
            logger.warning(f"Cloud storage download failed for '{file_key}': {e}")
        return None

    if is_cloud_path:
        response = await _serve_cloud(att.file_path)
        if response:
            return response
        response = _serve_local(att.file_path)
        if response:
            return response
    else:
        response = _serve_local(att.file_path)
        if response:
            return response
        if cloud_enabled:
            response = await _serve_cloud(att.file_path)
            if response:
                return response

    logger.error(f"File not found in any storage: '{att.file_path}'")
    raise HTTPException(status_code=404, detail="Attachment file not found")
