"""CRUD, recycle-bin, bulk-labels, merge, and file-download endpoints for bank statements."""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from core.models.database import get_db, get_master_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_non_viewer
from core.utils.file_validation import validate_file_path
from core.utils.file_deletion import delete_file_from_storage
from core.models.models_per_tenant import BankStatement, BankStatementTransaction
from core.services.search_service import search_service
from core.schemas.bank_statement import (
    PaginatedBankStatements,
    PaginatedDeletedBankStatements,
    RecycleBinStatementResponse,
    RestoreStatementRequest,
)
from core.utils.audit import log_audit_event
from core.utils.timezone import get_tenant_timezone_aware_datetime
from ._shared import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=PaginatedBankStatements)
async def list_statements(
    skip: int = 0,
    limit: int = 100,
    label: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "list statements")
    tenant_id = get_tenant_id()

    query = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == False)
    )

    # Apply creator filter if provided
    if created_by_user_id is not None:
        query = query.filter(BankStatement.created_by_user_id == created_by_user_id)

    # Apply status filter if provided
    if status:
        query = query.filter(BankStatement.status == status)

    # Apply label filter if provided
    if label:
        import sqlalchemy as sa

        query = query.filter(
            sa.cast(BankStatement.labels, sa.String).ilike(f"%{label}%")
        )

    # Apply search filter if provided
    if search:
        import sqlalchemy as sa

        # Search in original_filename, stored_filename, and bank_name
        query = query.filter(
            sa.or_(
                BankStatement.original_filename.ilike(f"%{search}%"),
                BankStatement.stored_filename.ilike(f"%{search}%"),
                BankStatement.bank_name.ilike(f"%{search}%")
            )
        )

    total_count = query.count()
    rows = (
        query.order_by(BankStatement.created_at.desc()).offset(skip).limit(limit).all()
    )

    # Fetch user details from master DB to handle cross-database attribution
    user_ids = {s.created_by_user_id for s in rows if s.created_by_user_id}
    user_map = {}
    if user_ids:
        try:
             users = master_db.query(MasterUser).filter(MasterUser.id.in_(user_ids)).all()
             user_map = {u.id: u for u in users}
        except Exception as e:
             logger.warning(f"Failed to fetch users from master DB: {e}")

    statements = []
    for s in rows:
        # Resolve creator, falling back to master DB lookups
        creator = s.created_by
        if not creator and s.created_by_user_id and s.created_by_user_id in user_map:
             creator = user_map[s.created_by_user_id]

        # Calculate username and email
        created_by_username = None
        created_by_email = None

        if creator:
             created_by_email = creator.email
             name_parts = []
             if creator.first_name:
                 name_parts.append(creator.first_name)
             if creator.last_name:
                 name_parts.append(creator.last_name)

             if name_parts:
                 created_by_username = " ".join(name_parts)
             else:
                 created_by_username = creator.email

        statements.append(
            {
                "id": s.id,
                "original_filename": s.original_filename,
                "stored_filename": s.stored_filename,
                "file_path": s.file_path,
                "status": s.status,
                "extracted_count": s.extracted_count,
                "extraction_method": getattr(s, "extraction_method", None),
                "analysis_error": getattr(s, "analysis_error", None),
                "analysis_updated_at": (
                    s.analysis_updated_at.isoformat()
                    if getattr(s, "analysis_updated_at", None)
                    else None
                ),
                "labels": getattr(s, "labels", None),
                "notes": getattr(s, "notes", None),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "created_by_user_id": s.created_by_user_id,
                "created_by_username": created_by_username,
                "created_by_email": created_by_email,
                "card_type": getattr(s, "card_type", "debit"),
                "bank_name": getattr(s, "bank_name", None),
                "review_status": getattr(s, "review_status", "not_started"),
                "review_result": getattr(s, "review_result", None),
                "reviewed_at": (
                    s.reviewed_at.isoformat()
                    if getattr(s, "reviewed_at", None)
                    else None
                ),
            }
        )

    return {"success": True, "statements": statements, "total": total_count}


@router.post("/bulk-labels")
async def bulk_labels(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Bulk add or remove labels from bank statements"""
    require_non_viewer(current_user, "bulk update statements")

    ids = payload.get("ids", [])
    action = payload.get("action")  # "add" or "remove"
    label = payload.get("label", "").strip()

    if not ids or action not in ["add", "remove"] or label == "":
        raise HTTPException(status_code=400, detail="Invalid request payload")

    try:
        tenant_id = get_tenant_id()

        statements = (
            db.query(BankStatement)
            .filter(BankStatement.id.in_(ids), BankStatement.tenant_id == tenant_id)
            .all()
        )

        for s in statements:
            current_labels = list(s.labels or [])
            if action == "add":
                if label not in current_labels:
                    current_labels.append(label)
            elif action == "remove":
                if label in current_labels:
                    current_labels.remove(label)

            s.labels = current_labels
            s.updated_at = get_tenant_timezone_aware_datetime(db)

        db.commit()
        return {"success": True, "count": len(statements)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk_labels for statements: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update labels")


@router.post("/merge")
async def merge_statements(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Merge multiple bank statements into one (originals are kept)"""
    require_non_viewer(current_user, "merge statements")

    ids = payload.get("ids", [])
    if not isinstance(ids, list) or len(ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least two statement IDs are required for merging",
        )

    try:
        tenant_id = get_tenant_id()

        # Fetch statements and verify they belong to the tenant and are not deleted
        statements = (
            db.query(BankStatement)
            .filter(
                BankStatement.id.in_(ids),
                BankStatement.tenant_id == tenant_id,
                BankStatement.is_deleted == False,
            )
            .all()
        )

        if len(statements) != len(ids):
            raise HTTPException(
                status_code=404,
                detail="One or more statements not found or already deleted",
            )

        # Ensure no merged statements are being merged again
        for s in statements:
            if s.status == "merged":
                raise HTTPException(
                    status_code=400,
                    detail=f"Statement #{s.id} is already a merged statement and cannot be merged again",
                )

        now = datetime.now(timezone.utc)

        # Create new merged statement
        merged_filename = f"Merged Statement ({now.strftime('%Y-%m-%d %H:%M')})"
        unique_id = uuid.uuid4().hex
        stored_filename = f"merged_{unique_id}.txt"
        file_path = f"merged_statements/{stored_filename}"  # Placeholder path

        merged_statement = BankStatement(
            tenant_id=tenant_id,
            original_filename=merged_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            status="merged",
            extracted_count=0,
            created_by_user_id=current_user.id,
            notes=f"Merged from statement IDs: {', '.join(map(str, sorted(ids)))}",
            created_at=now,
            updated_at=now,
        )
        db.add(merged_statement)
        db.flush()  # Get merged_statement.id

        total_txns = 0
        # Copy transactions from each statement
        for s in statements:
            txns = (
                db.query(BankStatementTransaction)
                .filter(BankStatementTransaction.statement_id == s.id)
                .all()
            )
            for t in txns:
                new_txn = BankStatementTransaction(
                    statement_id=merged_statement.id,
                    date=t.date,
                    description=t.description,
                    amount=t.amount,
                    transaction_type=t.transaction_type,
                    balance=t.balance,
                    category=t.category,
                    invoice_id=t.invoice_id,
                    expense_id=t.expense_id,
                )
                db.add(new_txn)
                total_txns += 1

            # Original statements are kept in the list

        merged_statement.extracted_count = total_txns

        db.commit()

        # Audit log
        try:
            log_audit_event(
                db=db,
                user_id=current_user.id,
                user_email=current_user.email,
                action="MERGE",
                resource_type="bank_statement",
                resource_id=str(merged_statement.id),
                resource_name=merged_filename,
                details={"merged_from_ids": ids, "transaction_count": total_txns},
            )
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Successfully merged {len(ids)} statements",
            "id": merged_statement.id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error merging statements: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to merge statements: {str(e)}"
        )


@router.get("/recycle-bin", response_model=PaginatedDeletedBankStatements)
async def get_deleted_statements(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get all deleted statements in the recycle bin"""
    tenant_id = get_tenant_id()

    try:
        query = db.query(BankStatement).filter(
            BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == True
        )

        total_count = query.count()

        deleted_statements = query.offset(skip).limit(limit).all()

        result = []
        for statement in deleted_statements:
            # Get deleted by user information
            deleted_by_username = None
            if statement.deleted_by_user:
                if (
                    statement.deleted_by_user.first_name
                    and statement.deleted_by_user.last_name
                ):
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
                "created_by_email": created_by_email,
            }
            result.append(statement_dict)

        return {
            "items": result,
            "total": total_count
        }

    except Exception as e:
        logger.error(f"Error getting deleted statements: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get deleted statements: {str(e)}"
        )


@router.post("/recycle-bin/empty", response_model=dict)
async def empty_statement_recycle_bin(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Empty the entire statement recycle bin (admin only)"""
    try:
        # Only admins can empty the recycle bin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403, detail="Only admins can empty the recycle bin"
            )

        tenant_id = get_tenant_id()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Tenant context required")

    # Get count of deleted statements
    count = (
        db.query(BankStatement)
        .filter(BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == True)
        .count()
    )

    if count == 0:
        return {"message": "Recycle bin is already empty", "deleted_count": 0}

    # Define the background task function
    async def delete_statements_background(tenant_id: int, user_id: int, user_email: str, count: int):
        """Background task to delete all statements in recycle bin"""
        from core.models.database import set_tenant_context
        from core.services.tenant_database_manager import tenant_db_manager

        # Set tenant context for this background task
        set_tenant_context(tenant_id)

        # Get tenant-specific session
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
        db_task = SessionLocal_tenant()

        try:
            # Get all deleted statements
            deleted_statements = (
                db_task.query(BankStatement)
                .filter(BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == True)
                .all()
            )

            # Delete all attachment files from storage before deleting statements
            try:
                from core.models.models_per_tenant import BankStatementAttachment
                import asyncio

                async def delete_files():
                    # Import CloudStorageService locally to avoid circular imports or if missing
                    cloud_storage_service = None
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        cloud_config = get_cloud_storage_config()
                        cloud_storage_service = CloudStorageService(db_task, cloud_config)
                    except ImportError:
                        pass
                    except Exception as e:
                        logger.warning(f"Failed to initialize CloudStorageService for deletion: {e}")

                    for statement in deleted_statements:
                        # 1. Try to delete local file (using existing utility)
                        if statement.file_path:
                            try:
                                await delete_file_from_storage(
                                    statement.file_path, tenant_id, user_id, db_task
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to delete local statement file {statement.file_path}: {e}"
                                )

                        # 2. Try to delete from Cloud Storage if configured
                        # Use the deterministic key strategy: tenant_{id}/bank_statements/{stored_filename}
                        if cloud_storage_service and statement.stored_filename:
                            try:
                                from core.interfaces.storage_provider import StorageProvider
                                cloud_key = f"tenant_{tenant_id}/bank_statements/{statement.stored_filename}"
                                # Only attempt deletion on cloud providers to avoid "File not found" warnings from local provider
                                # because local provider expects "attachments/..." prefix while cloud key is "tenant_..."
                                await cloud_storage_service.delete_file(
                                    cloud_key,
                                    str(tenant_id),
                                    user_id,
                                    files_providers=[
                                        StorageProvider.AWS_S3,
                                        StorageProvider.AZURE_BLOB,
                                        StorageProvider.GCP_STORAGE
                                    ]
                                )
                            except Exception as e:
                                logger.warning(f"Failed to delete cloud file {cloud_key}: {e}")

                        # Delete attachments
                        attachments = (
                            db_task.query(BankStatementAttachment)
                            .filter(BankStatementAttachment.statement_id == statement.id)
                            .all()
                        )
                        for att in attachments:
                            if att.file_path:
                                try:
                                    await delete_file_from_storage(
                                        att.file_path, tenant_id, user_id, db_task
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to delete attachment file {att.file_path}: {e}"
                                    )

                # Run async file deletion
                await delete_files()

                if deleted_statements:
                    logger.info(
                        f"Deleted attachment files for {len(deleted_statements)} statement(s) during recycle bin empty"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to delete attachment files during statement recycle bin empty: {e}"
                )

            # Delete all statements in recycle bin
            for statement in deleted_statements:
                db_task.delete(statement)

            db_task.commit()

            # Audit log for empty recycle bin
            log_audit_event(
                db=db_task,
                user_id=user_id,
                user_email=user_email,
                action="Empty Statement Recycle Bin",
                resource_type="statement",
                resource_id=None,
                resource_name=None,
                details={
                    "message": f"Statement recycle bin emptied, {count} statements permanently deleted."
                },
                status="success",
            )

            logger.info(f"Successfully emptied statement recycle bin: {count} statements deleted")

        except Exception as e:
            db_task.rollback()
            logger.error(f"Error in background task emptying statement recycle bin: {str(e)}")
        finally:
            db_task.close()

    # Add the deletion task to background tasks
    background_tasks.add_task(
        delete_statements_background,
        tenant_id,
        current_user.id,
        current_user.email,
        count
    )

    return {
        "message": f"Deletion of {count} statement(s) has been initiated. You will be notified when complete.",
        "deleted_count": count,
        "status": "processing"
    }


@router.get("/{statement_id}", response_model=Dict[str, Any])
async def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "view statement")
    tenant_id = get_tenant_id()

    from core.services import transaction_link_service
    from core.models.models_per_tenant import BankStatementTransaction

    s = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.created_by))
        .filter(
            BankStatement.id == statement_id,
            BankStatement.tenant_id == tenant_id,
            BankStatement.is_deleted == False,
        )
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Statement not found")

    txns = (
        db.query(BankStatementTransaction)
        .filter(BankStatementTransaction.statement_id == s.id)
        .order_by(
            BankStatementTransaction.date.asc(), BankStatementTransaction.id.asc()
        )
        .all()
    )

    txn_ids = [t.id for t in txns]
    links_by_txn_id = transaction_link_service.enrich_transactions_with_links(db, txn_ids)

    return {
        "success": True,
        "statement": {
            "id": s.id,
            "original_filename": s.original_filename,
            "stored_filename": s.stored_filename,
            "file_path": s.file_path,
            "status": s.status,
            "extracted_count": s.extracted_count,
            "extraction_method": getattr(s, "extraction_method", None),
            "analysis_error": getattr(s, "analysis_error", None),
            "analysis_updated_at": (
                s.analysis_updated_at.isoformat()
                if getattr(s, "analysis_updated_at", None)
                else None
            ),
            "labels": getattr(s, "labels", None),
            "notes": getattr(s, "notes", None),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "created_by_user_id": s.created_by_user_id,
            "created_by_username": s.created_by.email if s.created_by else None,
            "created_by_email": s.created_by.email if s.created_by else None,
            "card_type": getattr(s, "card_type", "debit"),
            "bank_name": getattr(s, "bank_name", None),
            "is_possible_receipt": getattr(s, "is_possible_receipt", False),
            "review_status": getattr(s, "review_status", "not_started"),
            "review_result": getattr(s, "review_result", None),
            "reviewed_at": (
                s.reviewed_at.isoformat()
                if getattr(s, "reviewed_at", None)
                else None
            ),
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "description": t.description,
                    "amount": t.amount,
                    "transaction_type": t.transaction_type,
                    "balance": t.balance,
                    "category": t.category,
                    "notes": getattr(t, "notes", None),
                    "invoice_id": getattr(t, "invoice_id", None),
                    "expense_id": getattr(t, "expense_id", None),
                    "linked_transfer": links_by_txn_id.get(t.id),
                }
                for t in txns
            ],
        },
    }


@router.put("/{statement_id}", response_model=Dict[str, Any])
async def update_statement_meta(
    statement_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Update metadata for a bank statement: notes and label."""
    require_non_viewer(current_user, "edit bank statement")
    tenant_id = get_tenant_id()

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
        prev_bank_name = getattr(s, "bank_name", None)
        prev_labels = list(getattr(s, "labels", []) or [])
        
        logger.info(f"Updating metadata for statement {statement_id} (Tenant: {tenant_id}, User: {current_user.email}) with payload: {payload}")
        
        if "notes" in payload:
            s.notes = payload.get("notes")
        if "bank_name" in payload:
            new_bank_name = payload.get("bank_name")
            if new_bank_name is None:
                logger.info(f"Setting bank_name to None for statement {statement_id}. User: {current_user.email}")
            s.bank_name = new_bank_name
        if "labels" in payload:
            v = payload.get("labels")
            if v in (None, ""):
                s.labels = None
            elif not isinstance(v, list):
                raise HTTPException(
                    status_code=400, detail="labels must be an array of strings"
                )
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

        # Index for search
        try:
            search_service.index_bank_statement(s)
        except Exception as index_error:
            logger.warning(f"Failed to index bank statement {s.id} for search: {index_error}")

        # Audit log the meta update (best-effort; ignore failures)
        try:
            changed: Dict[str, Any] = {}
            if "notes" in payload and prev_notes != s.notes:
                changed["notes"] = {"before": prev_notes, "after": s.notes}
            if "bank_name" in payload and prev_bank_name != s.bank_name:
                changed["bank_name"] = {"before": prev_bank_name, "after": s.bank_name}
            if "labels" in payload and (prev_labels or []) != (
                getattr(s, "labels", []) or []
            ):
                changed["labels"] = {
                    "before": prev_labels,
                    "after": getattr(s, "labels", []) or [],
                }
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
                "labels": getattr(s, "labels", None),
                "notes": getattr(s, "notes", None),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "created_by_user_id": s.created_by_user_id,
                "created_by_username": s.created_by.email if s.created_by else None,
                "created_by_email": s.created_by.email if s.created_by else None,
                "bank_name": getattr(s, "bank_name", None),
            },
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update statement: {e}")


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
    tenant_id = get_tenant_id()

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
        headers = {"Content-Disposition": f'inline; filename="{_name}"'}
        return FileResponse(path=safe_path, media_type=media_type, headers=headers)
    # Attachment with filename
    return FileResponse(path=safe_path, media_type=media_type, filename=_name)


@router.post("/{statement_id}/restore", response_model=RecycleBinStatementResponse)
async def restore_statement(
    statement_id: int,
    restore_request: RestoreStatementRequest = RestoreStatementRequest(),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Restore a statement from the recycle bin"""
    tenant_id = get_tenant_id()

    # Find the deleted statement
    statement = (
        db.query(BankStatement)
        .filter(
            BankStatement.id == statement_id,
            BankStatement.tenant_id == tenant_id,
            BankStatement.is_deleted == True,
        )
        .first()
    )

    if not statement:
        raise HTTPException(status_code=404, detail="Deleted statement not found")

    # Restore the statement
    statement.is_deleted = False
    statement.deleted_at = None
    statement.deleted_by = None
    statement.status = restore_request.new_status  # Set the new status
    statement.updated_at = get_tenant_timezone_aware_datetime(db)

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
        status="success",
    )

    return RecycleBinStatementResponse(
        message="Statement restored successfully",
        statement_id=statement_id,
        action="restored",
    )


@router.delete("/{statement_id}/permanent", response_model=RecycleBinStatementResponse)
async def permanently_delete_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Permanently delete a statement from the recycle bin"""
    tenant_id = get_tenant_id()

    # Find the deleted statement
    statement = (
        db.query(BankStatement)
        .filter(
            BankStatement.id == statement_id,
            BankStatement.tenant_id == tenant_id,
            BankStatement.is_deleted == True,
        )
        .first()
    )

    if not statement:
        raise HTTPException(status_code=404, detail="Deleted statement not found")

    # Delete attachment files from storage
    try:
        from core.models.models_per_tenant import BankStatementAttachment

        # Delete main statement file if exists
        if statement.file_path:
            try:
                await delete_file_from_storage(
                    statement.file_path, tenant_id, current_user.id, db
                )
            except Exception as e:
                logger.warning(
                    f"Failed to delete statement file {statement.file_path}: {e}"
                )

        # Delete attachments
        attachments = (
            db.query(BankStatementAttachment)
            .filter(BankStatementAttachment.statement_id == statement_id)
            .all()
        )
        for att in attachments:
            if att.file_path:
                try:
                    await delete_file_from_storage(
                        att.file_path, tenant_id, current_user.id, db
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to delete attachment file {att.file_path}: {e}"
                    )

        if attachments or statement.file_path:
            logger.info(f"Deleted attachment files for statement {statement_id}")
    except Exception as e:
        logger.warning(
            f"Failed to delete attachment files for statement {statement_id}: {e}"
        )

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
        status="success",
    )

    return RecycleBinStatementResponse(
        message="Statement permanently deleted",
        statement_id=statement_id,
        action="permanently_deleted",
    )


@router.delete("/{statement_id}", response_model=RecycleBinStatementResponse)
async def delete_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Move a statement to the recycle bin (soft delete)"""
    require_non_viewer(current_user, "delete statement")
    tenant_id = get_tenant_id()

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
            action="already_in_recycle_bin",
        )

    # Check if this statement was created from batch processing
    from core.models.models_per_tenant import BatchFileProcessing

    batch_file = (
        db.query(BatchFileProcessing)
        .filter(BatchFileProcessing.created_statement_id == statement_id)
        .first()
    )

    if batch_file and batch_file.job_id:
        # Get the batch job to find export destination
        from core.models.models_per_tenant import (
            BatchProcessingJob,
            ExportDestinationConfig,
        )

        batch_job = (
            db.query(BatchProcessingJob)
            .filter(BatchProcessingJob.job_id == batch_file.job_id)
            .first()
        )

        # Get S3 config from export destination or use default
        bucket_name = None
        aws_credentials = None
        if batch_job and batch_job.export_destination_config_id:
            export_dest = (
                db.query(ExportDestinationConfig)
                .filter(
                    ExportDestinationConfig.id == batch_job.export_destination_config_id
                )
                .first()
            )
            if export_dest and export_dest.config:
                bucket_name = export_dest.config.get("bucket_name")
                # Get AWS credentials from export destination
                aws_credentials = {
                    "access_key": export_dest.config.get("access_key_id"),
                    "secret_key": export_dest.config.get("secret_access_key"),
                    "region": export_dest.config.get("region"),
                }

        # Delete entire batch job folder from S3
        job_folder_prefix = f"exported/{batch_file.job_id}/"
        logger.info(
            f"Deleting batch job folder from S3: {job_folder_prefix} (bucket: {bucket_name}) for statement {statement_id}"
        )

        try:
            try:
                from commercial.cloud_storage.service import CloudStorageService

                storage_service = CloudStorageService(db)

                # Delete all files in the job folder
                tenant_id_str = str(tenant_id)
                result = await storage_service.delete_folder(
                    job_folder_prefix, tenant_id_str, bucket_name, aws_credentials
                )
                if result:
                    logger.info(
                        f"Successfully deleted batch job folder: {job_folder_prefix}"
                    )
                else:
                    logger.warning(
                        f"Failed to delete batch job folder: {job_folder_prefix}"
                    )
            except ImportError:
                logger.info(
                    "Commercial CloudStorageService not found, skipping batch job folder deletion"
                )
        except Exception as e:
            logger.error(
                f"Exception deleting batch job folder {job_folder_prefix}: {e}",
                exc_info=True,
            )

    # Soft delete the statement (don't delete files yet - they'll be deleted when permanently deleted)
    s.is_deleted = True
    s.deleted_at = get_tenant_timezone_aware_datetime(db)
    s.deleted_by = current_user.id
    s.updated_at = get_tenant_timezone_aware_datetime(db)

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
        status="success",
    )

    return RecycleBinStatementResponse(
        message="Statement moved to recycle bin successfully",
        statement_id=statement_id,
        action="moved_to_recycle",
    )
