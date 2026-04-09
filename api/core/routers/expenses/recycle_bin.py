"""Recycle bin endpoints: list deleted, empty, restore, and permanently delete expenses."""

import logging
import traceback

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Expense, ExpenseAttachment
from core.routers.auth import get_current_user
from core.schemas.expense import PaginatedDeletedExpenses, RecycleBinExpenseResponse, RestoreExpenseRequest
from core.utils.audit import log_audit_event
from core.utils.file_deletion import delete_file_from_storage
from core.utils.timezone import get_tenant_timezone_aware_datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/recycle-bin", response_model=PaginatedDeletedExpenses)
async def get_deleted_expenses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get all deleted expenses in the recycle bin"""
    try:
        query = db.query(Expense).filter(
            Expense.is_deleted == True
        )

        total_count = query.count()

        deleted_expenses = query.offset(skip).limit(limit).all()

        result = []
        for expense in deleted_expenses:
            deleted_by_username = None
            if expense.deleted_by_user:
                if expense.deleted_by_user.first_name and expense.deleted_by_user.last_name:
                    deleted_by_username = f"{expense.deleted_by_user.first_name} {expense.deleted_by_user.last_name}"
                elif expense.deleted_by_user.first_name:
                    deleted_by_username = expense.deleted_by_user.first_name
                else:
                    deleted_by_username = expense.deleted_by_user.email

            expense_dict = {
                "id": expense.id,
                "amount": expense.amount,
                "currency": expense.currency,
                "expense_date": expense.expense_date,
                "category": expense.category,
                "vendor": expense.vendor,
                "status": expense.status,
                "notes": expense.notes,
                "user_id": expense.user_id,
                "created_at": expense.created_at,
                "updated_at": expense.updated_at,
                "is_deleted": expense.is_deleted,
                "deleted_at": expense.deleted_at,
                "deleted_by": expense.deleted_by,
                "deleted_by_username": deleted_by_username,
                "created_by_user_id": expense.created_by_user_id,
                "created_by_username": expense.created_by_username,
                "created_by_email": expense.created_by_email
            }
            result.append(expense_dict)

        return {
            "items": result,
            "total": total_count
        }
    except Exception as e:
        logger.error(f"Error getting deleted expenses: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deleted expenses: {str(e)}"
        )


@router.post("/recycle-bin/empty", response_model=dict)
async def empty_expense_recycle_bin(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Empty the entire expense recycle bin (admin only)"""
    try:
        if current_user.role != 'admin':
            raise HTTPException(
                status_code=403,
                detail="Only admins can empty the recycle bin"
            )

        count = db.query(Expense).filter(Expense.is_deleted == True).count()

        if count == 0:
            return {"message": "Recycle bin is already empty", "deleted_count": 0}

        def delete_expenses_background(tenant_id: int, user_id: int, user_email: str, count: int):
            """Background task to delete all expenses in recycle bin"""
            from core.models.database import set_tenant_context
            from core.services.tenant_database_manager import tenant_db_manager

            set_tenant_context(tenant_id)

            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db_task = SessionLocal_tenant()
            try:
                deleted_expenses = db_task.query(Expense).filter(Expense.is_deleted == True).all()

                try:
                    import asyncio

                    async def delete_files():
                        for expense in deleted_expenses:
                            if expense.receipt_path:
                                try:
                                    await delete_file_from_storage(expense.receipt_path, tenant_id, user_id, db_task)
                                except Exception as e:
                                    logger.warning(f"Failed to delete receipt file {expense.receipt_path}: {e}")

                            attachments = db_task.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).all()
                            for att in attachments:
                                if att.file_path:
                                    try:
                                        await delete_file_from_storage(att.file_path, tenant_id, user_id, db_task)
                                    except Exception as e:
                                        logger.warning(f"Failed to delete attachment file {att.file_path}: {e}")

                        if deleted_expenses:
                            logger.info(f"Deleted attachment files for {len(deleted_expenses)} expense(s) during recycle bin empty")

                    asyncio.run(delete_files())

                except Exception as e:
                    logger.warning(f"Failed to delete attachment files during expense recycle bin empty: {e}")

                for expense in deleted_expenses:
                    db_task.delete(expense)

                db_task.commit()

                log_audit_event(
                    db=db_task,
                    user_id=user_id,
                    user_email=user_email,
                    action="Empty Expense Recycle Bin",
                    resource_type="expense",
                    resource_id=None,
                    resource_name=None,
                    details={"message": f"Expense recycle bin emptied, {count} expenses permanently deleted."},
                    status="success"
                )

                logger.info(f"Successfully emptied expense recycle bin: {count} expenses deleted")

            except Exception as e:
                db_task.rollback()
                logger.error(f"Error in background task emptying expense recycle bin: {str(e)}")
            finally:
                db_task.close()

        background_tasks.add_task(
            delete_expenses_background,
            current_user.tenant_id,
            current_user.id,
            current_user.email,
            count
        )

        return {
            "message": f"Deletion of {count} expense(s) has been initiated. You will be notified when complete.",
            "deleted_count": count,
            "status": "processing"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error emptying expense recycle bin: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to empty expense recycle bin: {str(e)}"
        )


@router.post("/{expense_id}/restore", response_model=RecycleBinExpenseResponse)
async def restore_expense(
    expense_id: int,
    restore_request: RestoreExpenseRequest = RestoreExpenseRequest(),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Restore an expense from the recycle bin"""
    try:
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == True
        ).first()

        if not db_expense:
            raise HTTPException(
                status_code=404,
                detail="Deleted expense not found"
            )

        db_expense.is_deleted = False
        db_expense.deleted_at = None
        db_expense.deleted_by = None
        db_expense.status = restore_request.new_status
        db_expense.updated_at = get_tenant_timezone_aware_datetime(db)

        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="Restore",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details={"message": "Expense restored from recycle bin"},
            status="success"
        )

        return RecycleBinExpenseResponse(
            message="Expense restored successfully",
            expense_id=expense_id,
            action="restored"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring expense {expense_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore expense: {str(e)}"
        )


@router.delete("/{expense_id}/permanent", response_model=RecycleBinExpenseResponse)
async def permanently_delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Permanently delete an expense from the recycle bin"""
    try:
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == True
        ).first()

        if not db_expense:
            raise HTTPException(
                status_code=404,
                detail="Deleted expense not found"
            )

        try:
            if db_expense.receipt_path:
                try:
                    await delete_file_from_storage(db_expense.receipt_path, current_user.tenant_id, current_user.id, db)
                except Exception as e:
                    logger.warning(f"Failed to delete receipt file {db_expense.receipt_path}: {e}")

            attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).all()
            for att in attachments:
                if att.file_path:
                    try:
                        await delete_file_from_storage(att.file_path, current_user.tenant_id, current_user.id, db)
                    except Exception as e:
                        logger.warning(f"Failed to delete attachment file {att.file_path}: {e}")

            if attachments or db_expense.receipt_path:
                logger.info(f"Deleted attachment files for expense {expense_id}")
        except Exception as e:
            logger.warning(f"Failed to delete attachment files for expense {expense_id}: {e}")

        db.delete(db_expense)
        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="Permanent Delete",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details={"message": "Expense permanently deleted"},
            status="success"
        )

        return RecycleBinExpenseResponse(
            message="Expense permanently deleted",
            expense_id=expense_id,
            action="permanently_deleted"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error permanently deleting expense {expense_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to permanently delete expense: {str(e)}"
        )
