from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
import shutil
import uuid
import logging
from core.utils.file_validation import validate_file_path
from core.utils.file_deletion import delete_file_from_storage

from core.models.database import get_db
from sqlalchemy.orm import Session
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_non_viewer
from core.utils.feature_gate import require_feature
from core.services.statement_service import extract_transactions_from_pdf_paths
from core.models.models_per_tenant import BankStatement, BankStatementTransaction
from core.schemas.bank_statement import BankStatementResponse, DeletedBankStatement, RecycleBinStatementResponse, RestoreStatementRequest
from datetime import datetime, timezone
from fastapi.responses import FileResponse
from core.services.ocr_service import publish_bank_statement_task
from core.utils.audit import log_audit_event
from sqlalchemy.orm import joinedload
from core.services.attribution_service import AttributionService


router = APIRouter(prefix="/statements", tags=["statements"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def upload_statements(
    files: List[UploadFile] = File(..., description="Up to 12 PDF or CSV statements"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Accept up to 12 PDF/CSV files, create one Statement per file, enqueue processing, and return created statements."""
    require_non_viewer(current_user, "upload statements")

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if len(files) > 12:
        raise HTTPException(status_code=400, detail="Maximum of 12 files are allowed")

    allowed_types = {"application/pdf", "text/csv", "application/vnd.ms-excel"}

    # Save to tenant-scoped folder
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    tenant_folder = f"tenant_{tenant_id}"
    base_dir = Path("attachments") / tenant_folder / "bank_statements"
    base_dir.mkdir(parents=True, exist_ok=True)

    created: List[Dict[str, Any]] = []

    try:
        for f in files:
            if f.content_type not in allowed_types:
                raise HTTPException(status_code=400, detail="Only PDF or CSV files are supported")
            contents = await f.read()
            if len(contents) > 20 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Each file must be <= 20 MB")
            await f.seek(0)

            name = (f.filename or "statement.pdf").strip()
            name = os.path.basename(name)
            name = "".join(ch for ch in name if ch.isalnum() or ch in (".", "_", "-"))
            stem, _ext = os.path.splitext(name)
            unique = uuid.uuid4().hex
            ext = (_ext.lower() if _ext else ".pdf")
            if ext not in (".pdf", ".csv"):
                # Normalize unknown extensions to .pdf for storage but keep original filename for display
                ext = ".pdf"
            stored_filename = f"bs_{stem[:100]}_{unique}{ext}"
            out_path = base_dir / stored_filename
            with open(out_path, "wb") as out:
                shutil.copyfileobj(f.file, out)

            # Upload to cloud storage
            cloud_file_url = None
            try:
                try:
                    from commercial.cloud_storage.service import CloudStorageService
                    from commercial.cloud_storage.config import get_cloud_storage_config
                    
                    cloud_config = get_cloud_storage_config()
                    cloud_storage_service = CloudStorageService(db, cloud_config)
                    
                    # Upload file to cloud storage
                    storage_result = await cloud_storage_service.store_file(
                        file_content=contents,
                        tenant_id=str(tenant_id),
                        item_id=0,  # Will be updated after statement is created
                        attachment_type="bank_statements",
                        original_filename=name,
                        user_id=current_user.id,
                        metadata={
                            "original_filename": name,
                            "stored_filename": stored_filename,
                            "uploaded_at": datetime.utcnow().isoformat(),
                            "file_size": len(contents),
                            "document_type": "bank_statement",
                            "upload_method": "internal_api"
                        }
                    )
                    
                    if storage_result.success:
                        cloud_file_url = storage_result.file_url
                        logger.info(f"Bank statement uploaded to cloud storage: {cloud_file_url}")
                    else:
                        logger.warning(f"Cloud storage upload failed, using local file: {storage_result.error}")
                except ImportError:
                    logger.info("Commercial CloudStorageService not found, using local file only")
            except Exception as e:
                logger.error(f"Cloud storage upload failed: {e}")

            # Create statement in processing state and enqueue OCR task
            statement = BankStatement(
                tenant_id=tenant_id,
                original_filename=name,
                stored_filename=stored_filename,
                file_path=str(out_path),
                status="processing",
                extracted_count=0,
                created_by_user_id=current_user.id,  # User attribution
            )
            db.add(statement)
            db.flush()
            # Force async-only: always enqueue, no sync fallback
            try:
                topic_name = os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr")
                logger.info(f"Enqueue bank statement id={statement.id} topic={topic_name}")
                ok = publish_bank_statement_task({
                    "tenant_id": tenant_id,
                    "statement_id": statement.id,
                    "file_path": str(out_path),
                    "ts": datetime.utcnow().isoformat(),
                })
                if not ok:
                    logger.warning(
                        f"Bank enqueue failed servers={os.getenv('KAFKA_BOOTSTRAP_SERVERS')} topic={topic_name}"
                    )
                    raise RuntimeError("Failed to enqueue bank statement task")
                else:
                    logger.info(f"Bank enqueue success id={statement.id} topic={topic_name}")
            except Exception as e:
                # Keep as processing so UI reflects pending state; worker retry/ops will handle later
                pass
            finally:
                # Persist statement in processing state so it appears immediately
                db.commit()
                db.refresh(statement)

            created.append({
                "id": statement.id,
                "original_filename": statement.original_filename,
                "stored_filename": statement.stored_filename,
                "file_path": statement.file_path,
                "status": statement.status,
                "extracted_count": statement.extracted_count,
                "created_at": statement.created_at.isoformat() if statement.created_at else None,
            })

        return {"success": True, "statements": created}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process bank statements: {e}")
    finally:
        # No cleanup: keep uploads under attachments for audit/debug
        pass


@router.get("/", response_model=Dict[str, Any])
@router.get("", response_model=Dict[str, Any])
async def list_statements(
    created_by_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "list statements")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    query = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == False)
    )

    # Apply creator filter if provided
    if created_by_user_id is not None:
        query = query.filter(BankStatement.created_by_user_id == created_by_user_id)

    rows = query.order_by(BankStatement.created_at.desc()).all()
    return {
        "success": True,
        "statements": [
            {
                "id": s.id,
                "original_filename": s.original_filename,
                "stored_filename": s.stored_filename,
                "file_path": s.file_path,
                "status": s.status,
                "extracted_count": s.extracted_count,
                "labels": getattr(s, 'labels', None),
                "notes": getattr(s, 'notes', None),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "created_by_user_id": s.created_by_user_id,
                "created_by_username": s.created_by.email if s.created_by else None,
                "created_by_email": s.created_by.email if s.created_by else None,
            }
            for s in rows
        ],
    }



# Recycle Bin Endpoints (must come before /{statement_id} route)

@router.get("/recycle-bin", response_model=List[DeletedBankStatement])
async def get_deleted_statements(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get all deleted statements in the recycle bin"""
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    try:
        deleted_statements = db.query(BankStatement).filter(
            BankStatement.tenant_id == tenant_id,
            BankStatement.is_deleted == True
        ).offset(skip).limit(limit).all()

        result = []
        for statement in deleted_statements:
            # Get deleted by user information
            deleted_by_username = None
            if statement.deleted_by_user:
                if statement.deleted_by_user.first_name and statement.deleted_by_user.last_name:
                    deleted_by_username = f"{statement.deleted_by_user.first_name} {statement.deleted_by_user.last_name}"
                elif statement.deleted_by_user.first_name:
                    deleted_by_username = statement.deleted_by_user.first_name
                else:
                    deleted_by_username = statement.deleted_by_user.email

            # Get created by user information
            created_by_username = None
            created_by_email = None
            if statement.created_by:
                if statement.created_by.first_name and statement.created_by.last_name:
                    created_by_username = f"{statement.created_by.first_name} {statement.created_by.last_name}"
                elif statement.created_by.first_name:
                    created_by_username = statement.created_by.first_name
                else:
                    created_by_username = statement.created_by.email
                created_by_email = statement.created_by.email

            statement_dict = {
                "id": statement.id,
                "original_filename": statement.original_filename,
                "stored_filename": statement.stored_filename,
                "file_path": statement.file_path,
                "status": statement.status,
                "extracted_count": statement.extracted_count,
                "notes": statement.notes,
                "labels": statement.labels,
                "created_at": statement.created_at,
                "updated_at": statement.updated_at,
                "is_deleted": statement.is_deleted,
                "deleted_at": statement.deleted_at,
                "deleted_by": statement.deleted_by,
                "deleted_by_username": deleted_by_username,
                "created_by_user_id": statement.created_by_user_id,
                "created_by_username": created_by_username,
                "created_by_email": created_by_email
            }
            result.append(statement_dict)

        return result

    except Exception as e:
        logger.error(f"Error getting deleted statements: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deleted statements: {str(e)}"
        )

@router.post("/recycle-bin/empty", response_model=dict)
async def empty_statement_recycle_bin(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Empty the entire statement recycle bin (admin only)"""
    try:
        # Only admins can empty the recycle bin
        if current_user.role != 'admin':
            raise HTTPException(
                status_code=403,
                detail="Only admins can empty the recycle bin"
            )

        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    # Get all deleted statements
    deleted_statements = db.query(BankStatement).filter(
        BankStatement.tenant_id == tenant_id,
        BankStatement.is_deleted == True
    ).all()
    count = len(deleted_statements)

    if count == 0:
        return {"message": "Recycle bin is already empty", "deleted_count": 0}

    # Delete all attachment files from storage before deleting statements
    try:
        from core.models.models_per_tenant import BankStatementAttachment
        for statement in deleted_statements:
            # Delete main statement file if exists
            if statement.file_path:
                try:
                    await delete_file_from_storage(statement.file_path, tenant_id, current_user.id, db)
                except Exception as e:
                    logger.warning(f"Failed to delete statement file {statement.file_path}: {e}")

            # Delete attachments
            attachments = db.query(BankStatementAttachment).filter(
                BankStatementAttachment.statement_id == statement.id
            ).all()
            for att in attachments:
                if att.file_path:
                    try:
                        await delete_file_from_storage(att.file_path, tenant_id, current_user.id, db)
                    except Exception as e:
                        logger.warning(f"Failed to delete attachment file {att.file_path}: {e}")

        if deleted_statements:
            logger.info(f"Deleted attachment files for {len(deleted_statements)} statement(s) during recycle bin empty")
    except Exception as e:
        logger.warning(f"Failed to delete attachment files during statement recycle bin empty: {e}")

    # Delete all statements in recycle bin
    for statement in deleted_statements:
        db.delete(statement)

    db.commit()

    # Audit log for empty recycle bin
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="Empty Statement Recycle Bin",
        resource_type="statement",
        resource_id=None,
        resource_name=None,
        details={"message": f"Statement recycle bin emptied, {count} statements permanently deleted."},
        status="success"
    )

    return {
        "message": f"Statement recycle bin emptied successfully. {count} statements permanently deleted.",
        "deleted_count": count
    }


@router.get("/{statement_id}", response_model=Dict[str, Any])
async def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "view statement")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == False)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    txns = (
        db.query(BankStatementTransaction)
        .filter(BankStatementTransaction.statement_id == s.id)
        .order_by(BankStatementTransaction.date.asc(), BankStatementTransaction.id.asc())
        .all()
    )
    return {
        "success": True,
        "statement": {
            "id": s.id,
            "original_filename": s.original_filename,
            "stored_filename": s.stored_filename,
            "file_path": s.file_path,
            "status": s.status,
            "extracted_count": s.extracted_count,
            "labels": getattr(s, 'labels', None),
            "notes": getattr(s, 'notes', None),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "created_by_user_id": s.created_by_user_id,
            "created_by_username": s.created_by.email if s.created_by else None,
            "created_by_email": s.created_by.email if s.created_by else None,
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "description": t.description,
                    "amount": t.amount,
                    "transaction_type": t.transaction_type,
                    "balance": t.balance,
                    "category": t.category,
                    "invoice_id": getattr(t, 'invoice_id', None),
                    "expense_id": getattr(t, 'expense_id', None),
                }
                for t in txns
            ],
        },
    }


@router.post("/{statement_id}/reprocess", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def reprocess_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Requeue or inline-process a bank statement again.
    Prevents duplicate reprocess requests that would send multiple Kafka messages.
    """
    require_non_viewer(current_user, "reprocess bank statement")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    # Import ProcessingLock model
    from core.models.processing_lock import ProcessingLock

    # Check if statement is already being processed
    if ProcessingLock.is_locked(db, "bank_statement", statement_id):
        lock_info = ProcessingLock.get_active_lock_info(db, "bank_statement", statement_id)
        return {
            "success": True,
            "message": "Statement is already being processed",
            "status": "already_processing",
            "lock_info": lock_info
        }

    # Acquire processing lock
    request_id = f"reprocess_statement_{statement_id}_{datetime.utcnow().timestamp()}"
    if not ProcessingLock.acquire_lock(
        db, "bank_statement", statement_id, current_user.id,
        lock_duration_minutes=30, metadata={"request_id": request_id}
    ):
        # Lock was acquired by someone else between check and acquire
        lock_info = ProcessingLock.get_active_lock_info(db, "bank_statement", statement_id)
        return {
            "success": True,
            "message": "Statement is already being processed by another request",
            "status": "already_processing",
            "lock_info": lock_info
        }

    try:
        # Mark as processing again
        try:
            s.status = "processing"
            db.commit()
        except Exception:
            db.rollback()

        # Publish Kafka task
        ok = publish_bank_statement_task({
            "tenant_id": tenant_id,
            "statement_id": statement_id,
            "file_path": s.file_path,
            "ts": datetime.utcnow().isoformat(),
        })
        if not ok:
            # Release lock on failure
            ProcessingLock.release_lock(db, "bank_statement", statement_id)
            raise HTTPException(status_code=500, detail="Failed to enqueue reprocess task")

        logger.info(f"Reprocess started for bank statement {statement_id} by user {current_user.id} (request_id: {request_id})")
        return {"success": True, "message": "Reprocessing started", "request_id": request_id}

    except Exception as e:
        # Release lock on failure
        try:
            ProcessingLock.release_lock(db, "bank_statement", statement_id)
        except:
            pass
        logger.error(f"Failed to reprocess bank statement {statement_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess statement")


@router.put("/{statement_id}", response_model=Dict[str, Any])
async def update_statement_meta(
    statement_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Update metadata for a bank statement: notes and label."""
    require_non_viewer(current_user, "edit bank statement")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    try:
        # Capture previous state for audit
        prev_notes = getattr(s, "notes", None)
        prev_labels = list(getattr(s, "labels", []) or [])
        if "notes" in payload:
            s.notes = payload.get("notes")
        if "labels" in payload:
            v = payload.get("labels")
            if v in (None, ""):
                s.labels = None
            elif not isinstance(v, list):
                raise HTTPException(status_code=400, detail="labels must be an array of strings")
            else:
                cleaned: list[str] = []
                for item in v:
                    if not isinstance(item, str):
                        continue
                    text = item.strip()
                    if not text:
                        continue
                    if text not in cleaned:
                        cleaned.append(text)
                    if len(cleaned) >= 10:
                        break
                s.labels = cleaned
        db.commit()
        db.refresh(s)
        # Audit log the meta update (best-effort; ignore failures)
        try:
            changed: Dict[str, Any] = {}
            if "notes" in payload and prev_notes != s.notes:
                changed["notes"] = {"before": prev_notes, "after": s.notes}
            if "labels" in payload and (prev_labels or []) != (getattr(s, "labels", []) or []):
                changed["labels"] = {"before": prev_labels, "after": getattr(s, "labels", []) or []}
            if changed:
                log_audit_event(
                    db=db,
                    user_id=current_user.id,
                    user_email=current_user.email,
                    action="UPDATE",
                    resource_type="bank_statement_meta",
                    resource_id=str(s.id),
                    resource_name=s.original_filename,
                    details={"statement_id": s.id, **changed},
                )
        except Exception:
            pass
        return {
            "success": True,
            "statement": {
                "id": s.id,
                "original_filename": s.original_filename,
                "stored_filename": s.stored_filename,
                "file_path": s.file_path,
                "status": s.status,
                "extracted_count": s.extracted_count,
                "labels": getattr(s, 'labels', None),
                "notes": getattr(s, 'notes', None),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "created_by_user_id": s.created_by_user_id,
                "created_by_username": s.created_by.email if s.created_by else None,
                "created_by_email": s.created_by.email if s.created_by else None,
            },
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update statement: {e}")


@router.put("/{statement_id}/transactions", response_model=Dict[str, Any])
async def replace_statement_transactions(
    statement_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "edit bank statement")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    items = payload.get("transactions", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="transactions must be an array")

    try:
        # Snapshot previous transactions for audit summary
        prev_rows = (
            db.query(BankStatementTransaction)
            .filter(BankStatementTransaction.statement_id == s.id)
            .order_by(BankStatementTransaction.date.asc(), BankStatementTransaction.id.asc())
            .all()
        )
        prev_count = len(prev_rows)
        prev_ids = [getattr(r, "id", None) for r in prev_rows if getattr(r, "id", None) is not None]
        # Replace transactions: simple strategy but preserve invoice links if provided
        db.query(BankStatementTransaction).filter(BankStatementTransaction.statement_id == s.id).delete()

        count = 0
        for t in items:
            try:
                dt = datetime.fromisoformat(t.get("date", "")).date()
            except Exception:
                dt = datetime.utcnow().date()
            new_txn = BankStatementTransaction(
                statement_id=s.id,
                date=dt,
                description=t.get("description", ""),
                amount=float(t.get("amount", 0)),
                transaction_type=(t.get("transaction_type") if t.get("transaction_type") in ("debit", "credit") else ("debit" if float(t.get("amount", 0)) < 0 else "credit")),
                balance=(float(t["balance"]) if t.get("balance") not in (None, "") else None),
                category=t.get("category") or None,
            )
            inv_id = t.get("invoice_id")
            try:
                new_txn.invoice_id = int(inv_id) if inv_id not in (None, "") else None
            except Exception:
                new_txn.invoice_id = None
            exp_id = t.get("expense_id")
            try:
                new_txn.expense_id = int(exp_id) if exp_id not in (None, "") else None
            except Exception:
                new_txn.expense_id = None
            db.add(new_txn)
            count += 1

        s.extracted_count = count
        db.commit()
        # Audit log the replace operation (best-effort; ignore failures)
        try:
            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="UPDATE",
                resource_type="bank_statement_transactions",
                resource_id=str(s.id),
                resource_name=s.original_filename,
                details={
                    "statement_id": s.id,
                    "previous_count": prev_count,
                    "new_count": count,
                    "removed_ids": prev_ids[:200],  # cap size
                },
            )
        except Exception:
            pass
        return {"success": True, "updated_count": count}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update transactions: {e}")


@router.get("/{statement_id}/file")
async def download_statement_file(
    statement_id: int,
    inline: bool = False,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return the original uploaded PDF for a bank statement.
    If inline=true, set Content-Disposition to inline; otherwise as attachment.
    """
    require_non_viewer(current_user, "download bank statement file")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")
    if not s.file_path:
        raise HTTPException(status_code=404, detail="File not found")

    # Validate file path
    try:
        safe_path = validate_file_path(s.file_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid file path")
    
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Infer content type based on extension
    _name = s.original_filename or "statement.pdf"
    _ext = os.path.splitext(_name)[1].lower()
    media_type = "application/pdf" if _ext != ".csv" else "text/csv"

    headers = None
    if inline:
        headers = {"Content-Disposition": f"inline; filename=\"{_name}\""}
        return FileResponse(path=safe_path, media_type=media_type, headers=headers)
    # Attachment with filename
    return FileResponse(path=safe_path, media_type=media_type, filename=_name)


@router.post("/{statement_id}/restore", response_model=RecycleBinStatementResponse)
async def restore_statement(
    statement_id: int,
    restore_request: RestoreStatementRequest = RestoreStatementRequest(),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Restore a statement from the recycle bin"""
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    # Find the deleted statement
    statement = db.query(BankStatement).filter(
        BankStatement.id == statement_id,
        BankStatement.tenant_id == tenant_id,
        BankStatement.is_deleted == True
    ).first()

    if not statement:
        raise HTTPException(
            status_code=404,
            detail="Deleted statement not found"
        )

    # Restore the statement
    statement.is_deleted = False
    statement.deleted_at = None
    statement.deleted_by = None
    statement.status = restore_request.new_status  # Set the new status
    statement.updated_at = datetime.now(timezone.utc)

    db.commit()

    # Audit log for restore
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="Restore",
        resource_type="statement",
        resource_id=str(statement_id),
        resource_name=f"Statement {statement_id}",
        details={"message": "Statement restored from recycle bin"},
        status="success"
    )

    return RecycleBinStatementResponse(
        message="Statement restored successfully",
        statement_id=statement_id,
        action="restored"
    )

@router.delete("/{statement_id}/permanent", response_model=RecycleBinStatementResponse)
async def permanently_delete_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Permanently delete a statement from the recycle bin"""
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    # Find the deleted statement
    statement = db.query(BankStatement).filter(
        BankStatement.id == statement_id,
        BankStatement.tenant_id == tenant_id,
        BankStatement.is_deleted == True
    ).first()

    if not statement:
        raise HTTPException(
            status_code=404,
            detail="Deleted statement not found"
        )

    # Delete attachment files from storage
    try:
        from core.models.models_per_tenant import BankStatementAttachment
        # Delete main statement file if exists
        if statement.file_path:
            try:
                await delete_file_from_storage(statement.file_path, tenant_id, current_user.id, db)
            except Exception as e:
                logger.warning(f"Failed to delete statement file {statement.file_path}: {e}")

        # Delete attachments
        attachments = db.query(BankStatementAttachment).filter(
            BankStatementAttachment.statement_id == statement_id
        ).all()
        for att in attachments:
            if att.file_path:
                try:
                    await delete_file_from_storage(att.file_path, tenant_id, current_user.id, db)
                except Exception as e:
                    logger.warning(f"Failed to delete attachment file {att.file_path}: {e}")

        if attachments or statement.file_path:
            logger.info(f"Deleted attachment files for statement {statement_id}")
    except Exception as e:
        logger.warning(f"Failed to delete attachment files for statement {statement_id}: {e}")

    # Permanently delete the statement
    db.delete(statement)
    db.commit()

    # Audit log for permanent delete
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="Permanent Delete",
        resource_type="statement",
        resource_id=str(statement_id),
        resource_name=f"Statement {statement_id}",
        details={"message": "Statement permanently deleted"},
        status="success"
    )

    return RecycleBinStatementResponse(
        message="Statement permanently deleted",
        statement_id=statement_id,
        action="permanently_deleted"
    )


@router.delete("/{statement_id}", response_model=RecycleBinStatementResponse)
async def delete_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Move a statement to the recycle bin (soft delete)"""
    require_non_viewer(current_user, "delete statement")
    try:
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
    except Exception:
        tenant_id = None
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Tenant context required")

    # First check if statement exists (regardless of deletion status)
    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    # If statement is already deleted, return success
    if s.is_deleted:
        return RecycleBinStatementResponse(
            message="Statement is already in recycle bin",
            statement_id=statement_id,
            action="already_in_recycle_bin"
        )

    # Check if this statement was created from batch processing
    from core.models.models_per_tenant import BatchFileProcessing
    batch_file = db.query(BatchFileProcessing).filter(
        BatchFileProcessing.created_statement_id == statement_id
    ).first()

    if batch_file and batch_file.job_id:
        # Get the batch job to find export destination
        from core.models.models_per_tenant import BatchProcessingJob, ExportDestinationConfig
        batch_job = db.query(BatchProcessingJob).filter(
            BatchProcessingJob.job_id == batch_file.job_id
        ).first()

        # Get S3 config from export destination or use default
        bucket_name = None
        aws_credentials = None
        if batch_job and batch_job.export_destination_config_id:
            export_dest = db.query(ExportDestinationConfig).filter(
                ExportDestinationConfig.id == batch_job.export_destination_config_id
            ).first()
            if export_dest and export_dest.config:
                bucket_name = export_dest.config.get('bucket_name')
                # Get AWS credentials from export destination
                aws_credentials = {
                    'access_key': export_dest.config.get('access_key_id'),
                    'secret_key': export_dest.config.get('secret_access_key'),
                    'region': export_dest.config.get('region')
                }

        # Delete entire batch job folder from S3
        job_folder_prefix = f"exported/{batch_file.job_id}/"
        logger.info(f"Deleting batch job folder from S3: {job_folder_prefix} (bucket: {bucket_name}) for statement {statement_id}")

        try:
            try:
                from commercial.cloud_storage.service import CloudStorageService
                storage_service = CloudStorageService(db)
                
                # Delete all files in the job folder
                tenant_id_str = str(tenant_id)
                result = await storage_service.delete_folder(job_folder_prefix, tenant_id_str, bucket_name, aws_credentials)
                if result:
                    logger.info(f"Successfully deleted batch job folder: {job_folder_prefix}")
                else:
                    logger.warning(f"Failed to delete batch job folder: {job_folder_prefix}")
            except ImportError:
                logger.info("Commercial CloudStorageService not found, skipping batch job folder deletion")
        except Exception as e:
            logger.error(f"Exception deleting batch job folder {job_folder_prefix}: {e}", exc_info=True)

    # Soft delete the statement (don't delete files yet - they'll be deleted when permanently deleted)
    s.is_deleted = True
    s.deleted_at = datetime.now(timezone.utc)
    s.deleted_by = current_user.id
    s.updated_at = datetime.now(timezone.utc)

    db.commit()

    # Audit log for soft delete
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="Soft Delete",
        resource_type="statement",
        resource_id=str(statement_id),
        resource_name=f"Statement {statement_id}",
        details={"message": "Statement moved to recycle bin"},
        status="success"
    )

    return RecycleBinStatementResponse(
        message="Statement moved to recycle bin successfully",
        statement_id=statement_id,
        action="moved_to_recycle"
    )
