from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timezone, timedelta
import logging
import math
import os
import re
from pathlib import Path
import uuid
from collections import defaultdict
import sqlalchemy as sa
import traceback

from core.models.database import get_db, get_master_db
from core.models.models_per_tenant import Expense, ExpenseAttachment, User, Invoice, BankStatementTransaction
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.schemas.expense import ExpenseCreate, ExpenseUpdate, Expense as ExpenseSchema, DeletedExpense, RecycleBinExpenseResponse, RestoreExpenseRequest, ExpenseListResponse, PaginatedDeletedExpenses
from core.services.currency_service import CurrencyService
from core.services.search_service import search_service
from core.utils.rbac import require_non_viewer
from core.utils.audit import log_audit_event
from core.utils.file_deletion import delete_file_from_storage
from commercial.ai.services.ocr_service import queue_or_process_attachment, cancel_ocr_tasks_for_expense
from core.constants.error_codes import EXPENSE_LINKED_TO_INVOICE
from core.constants.expense_status import ExpenseStatus
from core.utils.timezone import get_tenant_timezone_aware_datetime
from core.services.review_service import ReviewService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Ensure logs are visible under uvicorn
uvicorn_logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _apply_creator_fallback(expenses: list, master_db: Session) -> None:
    """
    Populate _creator_display_name on expenses whose created_by_username is None
    (tenant DB decryption failed) by falling back to the master DB where user
    names are stored as plain text.
    """
    needs = [ex for ex in expenses if ex.created_by_username is None and ex.created_by_user_id]
    if not needs:
        return
    user_ids = list({ex.created_by_user_id for ex in needs})
    master_users = {
        mu.id: mu
        for mu in master_db.query(MasterUser).filter(MasterUser.id.in_(user_ids)).all()
    }
    for ex in needs:
        mu = master_users.get(ex.created_by_user_id)
        if mu:
            if mu.first_name and mu.last_name:
                ex.__dict__['_creator_display_name'] = f"{mu.first_name} {mu.last_name}"
            elif mu.first_name:
                ex.__dict__['_creator_display_name'] = mu.first_name
            elif mu.email:
                ex.__dict__['_creator_display_name'] = mu.email


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """Validate if a status transition is allowed"""
    try:
        current = ExpenseStatus(current_status)
        new = ExpenseStatus(new_status)
        return current.can_transition_to(new)
    except ValueError:
        return False


def check_expense_modification_allowed(expense: Expense) -> None:
    """Check if an expense can be modified based on its current status"""
    if expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot modify expense with status '{expense.status}'. Expense is in approval workflow."
        )


@router.get("/", response_model=ExpenseListResponse)
async def list_expenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    label: Optional[str] = None,
    invoice_id: Optional[int] = None,
    unlinked_only: bool = False,
    exclude_status: Optional[str] = None,
    search: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    include_total: bool = False,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        # Build the base query with all filters
        # Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
        logger.info(f"list_expenses: current_user.id={current_user.id}, tenant_id={current_user.tenant_id}, search={search}, include_total={include_total}")
        from sqlalchemy.orm import joinedload
        query = db.query(Expense).options(joinedload(Expense.created_by)).filter(Expense.is_deleted == False)
        base_count = query.count()
        logger.info(f"list_expenses: current_user.id={current_user.id}, tenant_id={current_user.tenant_id}, search={search}")
        if category and category != "all":
            query = query.filter(Expense.category == category)
        if label:
            # Match legacy single label or within labels array
            try:
                query = query.filter(
                    (Expense.label.ilike(f"%{label}%")) |
                    (sa.cast(Expense.labels, sa.String).ilike(f"%{label}%"))
                )
            except Exception:
                query = query.filter(Expense.label == label)
        if invoice_id is not None:
            query = query.filter(Expense.invoice_id == invoice_id)
        if unlinked_only:
            query = query.filter(Expense.invoice_id.is_(None))
        if exclude_status:
            query = query.filter(Expense.status != exclude_status)
        if created_by_user_id is not None:
            query = query.filter(Expense.created_by_user_id == created_by_user_id)
        # For search: two-phase approach to avoid full-table memory loads.
        # Phase 1: DB-level match on non-encrypted fields (fast path).
        # Phase 2: Stream remaining rows with yield_per to check encrypted fields.
        if search:
            logger.info(f"list_expenses: applying search filter with term={search}")
            search_lower = search.lower()

            # Phase 1: match category / label / labels at DB level
            db_matched_ids: set = set(
                row[0]
                for row in query.with_entities(Expense.id).filter(
                    sa.or_(
                        sa.func.lower(Expense.category).contains(search_lower),
                        Expense.label.ilike(f"%{search_lower}%"),
                        sa.cast(Expense.labels, sa.String).ilike(f"%{search_lower}%"),
                    )
                ).all()
            )

            # Phase 2: stream remaining expenses to search encrypted vendor/notes
            remaining_query = query.with_entities(Expense.id, Expense.vendor, Expense.notes)
            if db_matched_ids:
                remaining_query = remaining_query.filter(Expense.id.notin_(db_matched_ids))
            encrypted_matched_ids: set = set()
            for row in remaining_query.yield_per(500):
                if (
                    (row.vendor and search_lower in row.vendor.lower()) or
                    (row.notes and search_lower in row.notes.lower())
                ):
                    encrypted_matched_ids.add(row.id)

            all_matched_ids = db_matched_ids | encrypted_matched_ids
            total_count = len(all_matched_ids)
            logger.info(f"list_expenses: total_count (after search filter)={total_count}")

            if all_matched_ids:
                expenses = (
                    query.filter(Expense.id.in_(all_matched_ids))
                    .order_by(Expense.id.desc())
                    .offset(skip)
                    .limit(limit)
                    .all()
                )
            else:
                expenses = []
        else:
            # Count total expenses with all filters applied
            total_count = query.count()
            logger.info(f"list_expenses: total_count (after all filters)={total_count}")

            # If skip is beyond available data, return empty results
            if skip >= total_count and total_count > 0:
                logger.info(f"Pagination beyond available data: skip={skip} >= total={total_count}, returning empty results")
                expenses = []
            else:
                expenses = query.order_by(Expense.id.desc()).offset(skip).limit(limit).all()

        # Log pagination info for debugging
        logger.info(f"Expenses query: total_count={total_count}, skip={skip}, limit={limit}, returned={len(expenses)}, exclude_status={exclude_status}")

        # Add attachment count for preview (single batched query instead of N+1)
        try:
            if expenses:
                expense_ids = [ex.id for ex in expenses]
                attachment_counts = dict(
                    db.query(ExpenseAttachment.expense_id, sa.func.count(ExpenseAttachment.id))
                    .filter(ExpenseAttachment.expense_id.in_(expense_ids))
                    .group_by(ExpenseAttachment.expense_id)
                    .all()
                )
                for ex in expenses:
                    ex.attachments_count = attachment_counts.get(ex.id, 0)
        except Exception as e:
            logger.warning(f"Failed to get attachment count for expenses: {e}")

        # Fallback: when tenant DB decryption fails, use master DB for creator name
        _apply_creator_fallback(expenses, master_db)

        # Attach statement_transaction_id via reverse lookup (batch)
        try:
            if expenses:
                expense_ids = [ex.id for ex in expenses]
                txn_map: dict[int, int] = dict(
                    db.query(BankStatementTransaction.expense_id, BankStatementTransaction.id)
                    .filter(BankStatementTransaction.expense_id.in_(expense_ids))
                    .all()
                )
                for ex in expenses:
                    ex.__dict__['statement_transaction_id'] = txn_map.get(ex.id)
        except Exception as e:
            logger.warning(f"Failed to get statement_transaction_id for expenses: {e}")

        # Always return the structured response format
        return {
            "success": True,
            "expenses": [ExpenseSchema.model_validate(ex) for ex in expenses],
            "total": total_count
        }
    except Exception as e:
        logger.error(f"Failed to list expenses: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expenses")


@router.get("/{expense_id:int}", response_model=ExpenseSchema)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    uvicorn_logger.info(f"Fetching expense {expense_id} for tenant {current_user.tenant_id}")

    from sqlalchemy.orm import joinedload
    expense = db.query(Expense).options(joinedload(Expense.created_by)).filter(
        Expense.id == expense_id,
        Expense.is_deleted == False
    ).first()

    if not expense:
        uvicorn_logger.warning(f"Expense {expense_id} not found for tenant {current_user.tenant_id}")
        raise HTTPException(status_code=404, detail="Expense not found")

    uvicorn_logger.info(f"Successfully retrieved expense {expense_id}")

    try:
        expense.attachments_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).count()
    except Exception as e:
        logger.warning(f"Failed to get attachment count for expense {expense_id}: {e}")

    # Ensure creator info is populated even if relationship loading fails
    if not expense.created_by and expense.created_by_user_id:
        try:
            creator = db.query(User).filter(User.id == expense.created_by_user_id).first()
            if creator:
                expense.created_by = creator
        except Exception as e:
            logger.warning(f"Failed to load creator for expense {expense_id}: {e}")

    # Fallback: when tenant DB decryption fails, use master DB for creator name
    _apply_creator_fallback([expense], master_db)

    # Attach statement_transaction_id via reverse lookup
    try:
        txn = db.query(BankStatementTransaction.id).filter(
            BankStatementTransaction.expense_id == expense_id
        ).first()
        expense.__dict__['statement_transaction_id'] = txn[0] if txn else None
    except Exception as e:
        logger.warning(f"Failed to get statement_transaction_id for expense {expense_id}: {e}")

    return expense


@router.post("/", response_model=ExpenseSchema)
async def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "create expenses")

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        currency_service = CurrencyService(db)
        currency_code = expense.currency or "USD"
        if not currency_service.validate_currency_code(currency_code):
            raise HTTPException(status_code=400, detail=f"Invalid currency code: {currency_code}")

        # Convert date to datetime for DB
        expense_dt = expense.expense_date
        if isinstance(expense_dt, date):
            expense_dt = datetime.combine(expense_dt, datetime.min.time()).replace(tzinfo=timezone.utc)

        tax_amount = expense.tax_amount
        total_amount = expense.total_amount
        if expense.amount is not None:
            if expense.amount is not None:
                if tax_amount is None and expense.tax_rate is not None:
                    tax_amount = float(expense.amount) * float(expense.tax_rate) / 100.0
                if total_amount is None:
                    total_amount = float(expense.amount) + float(tax_amount or 0)

        # Validate invoice exists if provided
        if expense.invoice_id is not None:
            inv = db.query(Invoice).filter(Invoice.id == expense.invoice_id).first()
            if not inv:
                raise HTTPException(status_code=400, detail=f"Invoice {expense.invoice_id} not found")
            uvicorn_logger.info(f"Creating expense linked to invoice_id={expense.invoice_id}")

        # Normalize labels: enforce max 10, unique, trimmed, non-empty
        input_labels = getattr(expense, "labels", None) or ([] if not getattr(expense, "label", None) else [getattr(expense, "label")])
        if input_labels:
            norm = []
            seen = set()
            for s in input_labels:
                if not isinstance(s, str):
                    continue
                v = s.strip()
                if not v or v in seen:
                    continue
                norm.append(v)
                seen.add(v)
                if len(norm) >= 10:
                    break
            input_labels = norm
        else:
            input_labels = None

        # Handle inventory purchase fields
        is_inventory_purchase = bool(getattr(expense, "is_inventory_purchase", False))
        inventory_items = getattr(expense, "inventory_items", None)

        # Handle inventory consumption fields
        is_inventory_consumption = bool(getattr(expense, "is_inventory_consumption", False))
        consumption_items = getattr(expense, "consumption_items", None)

        # Validate inventory purchase data if provided
        if is_inventory_purchase:
            if not inventory_items or len(inventory_items) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Inventory purchase must include at least one item"
                )

            # Validate each inventory item
            from core.services.inventory_service import InventoryService
            inventory_service = InventoryService(db)

            for item_data in inventory_items:
                item_id = item_data.get('item_id')
                quantity = item_data.get('quantity', 0)

                if not item_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Each inventory item must have an item_id"
                    )

                # Verify item exists
                inventory_item = inventory_service.get_item(item_id)
                if not inventory_item:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Inventory item {item_id} not found"
                    )

                if quantity <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Quantity must be greater than 0 for item {inventory_item.name}"
                    )

        # Validate inventory consumption data if provided
        if is_inventory_consumption:
            if not consumption_items or len(consumption_items) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Inventory consumption must include at least one item"
                )

            # Validate each consumption item
            from core.services.inventory_service import InventoryService
            inventory_service = InventoryService(db)

            for item_data in consumption_items:
                item_id = item_data.get('item_id')
                quantity = item_data.get('quantity', 0)

                if not item_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Each consumption item must have an item_id"
                    )

                # Verify item exists
                inventory_item = inventory_service.get_item(item_id)
                if not inventory_item:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Inventory item {item_id} not found"
                    )

                if quantity <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Quantity must be greater than 0 for item {inventory_item.name}"
                    )

                # Check if there's enough stock
                if inventory_item.track_stock and inventory_item.current_stock < quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient stock for {inventory_item.name}. Available: {inventory_item.current_stock}, Requested: {quantity}"
                    )

        db_expense = Expense(
            amount=float(expense.amount) if expense.amount is not None else None,
            currency=currency_code,
            expense_date=expense_dt,
            category=expense.category,
            vendor=expense.vendor,
            label=getattr(expense, "label", None),
            labels=input_labels,
            tax_rate=float(expense.tax_rate) if expense.tax_rate is not None else None,
            tax_amount=float(tax_amount) if tax_amount is not None else None,
            total_amount=float(total_amount) if total_amount is not None else None,
            payment_method=expense.payment_method,
            reference_number=expense.reference_number,
            status=expense.status or ExpenseStatus.RECORDED.value,
            notes=expense.notes,
            user_id=current_user.id,
            invoice_id=expense.invoice_id,
            is_inventory_purchase=is_inventory_purchase,
            inventory_items=inventory_items,
            is_inventory_consumption=is_inventory_consumption,
            consumption_items=consumption_items,
            imported_from_attachment=bool(getattr(expense, "imported_from_attachment", False)),
            analysis_status=getattr(expense, "analysis_status", "not_started"),
            analysis_result=getattr(expense, "analysis_result", None),
            analysis_error=getattr(expense, "analysis_error", None),
            manual_override=bool(getattr(expense, "manual_override", False)),
            receipt_timestamp=getattr(expense, "receipt_timestamp", None),
            receipt_time_extracted=bool(getattr(expense, "receipt_time_extracted", False)),
            created_by_user_id=current_user.id,  # User attribution
            created_at=get_tenant_timezone_aware_datetime(db),
            updated_at=get_tenant_timezone_aware_datetime(db),
        )
        db.add(db_expense)
        db.flush()  # Ensure ID is generated
        expense_id = db_expense.id
        uvicorn_logger.info(f"Expense flushed with ID: {expense_id}")

        db.commit()
        uvicorn_logger.info(f"Expense committed with ID: {expense_id}")

        # After commit, query the expense fresh from the database to ensure we have the latest state
        # This is critical for multi-session environments
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not db_expense:
            uvicorn_logger.error(f"CRITICAL: Expense {expense_id} not found after commit!")
            raise HTTPException(status_code=500, detail=f"Expense was created but cannot be retrieved (ID: {expense_id})")

        uvicorn_logger.info(f"Successfully created and verified expense with ID: {db_expense.id}")

        # Process inventory stock movements for inventory purchases
        if is_inventory_purchase and inventory_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_purchase(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for inventory purchase expense {db_expense.id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process stock movements for expense {db_expense.id}: {e}")
                # Don't fail the expense creation, but log the error
                # The expense is already created, stock movements can be processed later if needed

        # Process inventory stock movements for inventory consumption
        if is_inventory_consumption and consumption_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_consumption(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for inventory consumption expense {db_expense.id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process consumption stock movements for expense {db_expense.id}: {e}")
                # Don't fail the expense creation, but log the error
                # The expense is already created, stock movements can be processed later if needed

        # If this expense was created from a bank statement transaction, link it to prevent duplicates
        try:
            # Heuristic: when created from BankStatements UI, the note includes filename; but we prefer explicit linking
            # Support linking via a custom header-like context in the future; for now rely on UI passing back linkage separately
            # Here we do nothing unless an explicit transaction id is provided via hidden field in the future.
            pass
        except Exception:
            pass

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="expense",
            resource_id=str(db_expense.id),
            resource_name=f"Expense {db_expense.id}",
            details=expense.model_dump(),
            status="success",
        )

        # Index the expense for global search
        try:
            search_service.index_expense(db_expense)
        except Exception as e:
            uvicorn_logger.warning(f"Failed to index expense {db_expense.id} for search: {e}")

        # Process gamification event for expense creation
        try:
            from core.services.tenant_database_manager import tenant_db_manager
            from core.services.financial_event_processor import create_financial_event_processor

            # Get tenant database session for gamification
            tenant_session = tenant_db_manager.get_tenant_session(current_user.tenant_id)
            if tenant_session:
                gamification_db = tenant_session()
                try:
                    event_processor = create_financial_event_processor(gamification_db)

                    expense_data = {
                        "vendor": db_expense.vendor,
                        "category": db_expense.category,
                        "amount": float(db_expense.amount) if db_expense.amount else 0
                    }

                    gamification_result = await event_processor.process_expense_added(
                        user_id=current_user.id,
                        expense_id=db_expense.id,
                        expense_data=expense_data
                    )

                    if gamification_result:
                        uvicorn_logger.info(
                            f"Gamification event processed for expense {db_expense.id}: "
                            f"points={gamification_result.points_awarded}"
                        )
                finally:
                    gamification_db.close()
            else:
                uvicorn_logger.warning(f"Could not get tenant session for gamification (tenant {current_user.tenant_id})")
        except Exception as e:
            uvicorn_logger.warning(f"Failed to process gamification event for expense {db_expense.id}: {e}")
            # Don't fail the expense creation if gamification processing fails

        return db_expense
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to create expense")


from pydantic import BaseModel
from typing import List as TypingList, Literal


class BulkLabelsRequest(BaseModel):
    expense_ids: TypingList[int]
    operation: Literal['add', 'remove']
    label: str


class BulkExpenseCreateRequest(BaseModel):
    expenses: TypingList[ExpenseCreate]


class BulkDeleteRequest(BaseModel):
    expense_ids: TypingList[int]


@router.post("/bulk-labels")
async def bulk_labels_expenses(
    payload: BulkLabelsRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "bulk label expenses")
    try:
        if not payload.expense_ids:
            raise HTTPException(status_code=400, detail="No expense IDs provided")
        if not payload.label or not isinstance(payload.label, str):
            raise HTTPException(status_code=400, detail="Label is required")

        target_items = db.query(Expense).filter(
            Expense.id.in_(payload.expense_ids),
            Expense.is_deleted == False
        ).all()
        updated = 0
        for item in target_items:
            labels = list(getattr(item, 'labels', []) or [])
            if payload.operation == 'add':
                val = payload.label.strip()
                if val and val not in labels:
                    if len(labels) >= 10:
                        continue
                    labels.append(val)
            elif payload.operation == 'remove':
                labels = [x for x in labels if x != payload.label]
            else:
                continue
            item.labels = labels or None
            item.updated_at = get_tenant_timezone_aware_datetime(db)
            updated += 1
        db.commit()
        return {"updated": int(updated)}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed bulk label update: {e}")
        raise HTTPException(status_code=500, detail="Failed to bulk update labels")


@router.post("/bulk-create", response_model=List[ExpenseSchema])
async def bulk_create_expenses(
    payload: BulkExpenseCreateRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "create expenses")
    try:
        if not payload.expenses or len(payload.expenses) == 0:
            raise HTTPException(status_code=400, detail="No expenses provided")
        if len(payload.expenses) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 expenses allowed")

        currency_service = CurrencyService(db)
        created_expenses = []

        for expense in payload.expenses:
            currency_code = expense.currency or "USD"
            if not currency_service.validate_currency_code(currency_code):
                raise HTTPException(status_code=400, detail=f"Invalid currency code: {currency_code}")

            expense_dt = expense.expense_date
            if isinstance(expense_dt, date):
                expense_dt = datetime.combine(expense_dt, datetime.min.time()).replace(tzinfo=timezone.utc)

            tax_amount = expense.tax_amount
            total_amount = expense.total_amount
            if tax_amount is None and expense.tax_rate is not None:
                if expense.amount is not None:
                    tax_amount = float(expense.amount) * float(expense.tax_rate) / 100.0
                    if total_amount is None:
                        total_amount = float(expense.amount) + float(tax_amount or 0)

            if expense.invoice_id is not None:
                inv = db.query(Invoice).filter(Invoice.id == expense.invoice_id).first()
                if not inv:
                    raise HTTPException(status_code=400, detail=f"Invoice {expense.invoice_id} not found")

            input_labels = getattr(expense, "labels", None) or ([] if not getattr(expense, "label", None) else [getattr(expense, "label")])
            if input_labels:
                norm = []
                seen = set()
                for s in input_labels:
                    if not isinstance(s, str):
                        continue
                    v = s.strip()
                    if not v or v in seen:
                        continue
                    norm.append(v)
                    seen.add(v)
                    if len(norm) >= 10:
                        break
                input_labels = norm
            else:
                input_labels = None

            db_expense = Expense(
                amount=float(expense.amount),
                currency=currency_code,
                expense_date=expense_dt,
                category=expense.category,
                vendor=expense.vendor,
                label=getattr(expense, "label", None),
                labels=input_labels,
                tax_rate=float(expense.tax_rate) if expense.tax_rate is not None else None,
                tax_amount=float(tax_amount) if tax_amount is not None else None,
                total_amount=float(total_amount) if total_amount is not None else None,
                payment_method=expense.payment_method,
                reference_number=expense.reference_number,
                status=expense.status or ExpenseStatus.RECORDED.value,
                notes=expense.notes,
                user_id=current_user.id,
                invoice_id=expense.invoice_id,
                imported_from_attachment=bool(getattr(expense, "imported_from_attachment", False)),
                analysis_status=getattr(expense, "analysis_status", "not_started"),
                analysis_result=getattr(expense, "analysis_result", None),
                analysis_error=getattr(expense, "analysis_error", None),
                manual_override=bool(getattr(expense, "manual_override", False)),
                receipt_timestamp=getattr(expense, "receipt_timestamp", None),
                receipt_time_extracted=bool(getattr(expense, "receipt_time_extracted", False)),
                created_by_user_id=current_user.id,  # User attribution
                created_at=get_tenant_timezone_aware_datetime(db),
                updated_at=get_tenant_timezone_aware_datetime(db),
            )
            db.add(db_expense)
            created_expenses.append(db_expense)

        db.commit()
        for expense in created_expenses:
            db.refresh(expense)

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="BULK_CREATE",
            resource_type="expense",
            resource_id="bulk",
            resource_name=f"Bulk created {len(created_expenses)} expenses",
            details={"count": len(created_expenses)},
            status="success",
        )

        return created_expenses
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to bulk create expenses: {e}")
        raise HTTPException(status_code=500, detail="Failed to bulk create expenses")


@router.delete("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_expenses(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "bulk delete expenses")

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        if not payload.expense_ids:
            raise HTTPException(status_code=400, detail="No expense IDs provided")

        # Limit bulk delete to prevent performance issues
        if len(payload.expense_ids) > 100:
            raise HTTPException(status_code=400, detail="Cannot delete more than 100 expenses at once")

        # Get all expenses to delete
        expenses_to_delete = db.query(Expense).filter(
            Expense.id.in_(payload.expense_ids),
            Expense.is_deleted == False
        ).all()

        if not expenses_to_delete:
            raise HTTPException(status_code=404, detail="No expenses found")

        # Check if any expenses cannot be deleted
        non_admin = current_user.role != 'admin'
        for expense in expenses_to_delete:
            # Check if expense can be deleted based on current status
            if non_admin and expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete expense #{expense.id} with status '{expense.status}'. Expense is in approval workflow."
                )

            # Prevent deleting an expense that is linked to an invoice
            if getattr(expense, "invoice_id", None) is not None:
                raise HTTPException(status_code=400, detail=f"Expense #{expense.id} is linked to an invoice and cannot be deleted")

        # Process each expense for deletion
        deleted_count = 0
        for expense in expenses_to_delete:
            try:
                # Remove any legacy single receipt file if present
                if expense.receipt_path:
                    await delete_file_from_storage(expense.receipt_path, current_user.tenant_id, current_user.id, db)

                # Remove all attachment files associated with this expense
                try:
                    attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).all()
                    for att in attachments:
                        if getattr(att, "file_path", None):
                            await delete_file_from_storage(att.file_path, current_user.tenant_id, current_user.id, db)
                except Exception as e:
                    logger.warning(f"Failed to enumerate attachments for deletion: {e}")

                # Unlink any bank statement transactions that reference this expense BEFORE deletion
                try:
                    from core.models.models_per_tenant import BankStatementTransaction
                    linked_transactions = db.query(BankStatementTransaction).filter(
                        BankStatementTransaction.expense_id == expense.id
                    ).all()
                    for txn in linked_transactions:
                        txn.expense_id = None
                    if linked_transactions:
                        logger.info(f"Unlinked {len(linked_transactions)} bank transactions from deleted expense {expense.id}")
                except Exception as e:
                    logger.warning(f"Failed to unlink bank transactions from expense {expense.id}: {e}")

                # Unlink any raw emails that reference this expense BEFORE deletion
                try:
                    from core.models.models_per_tenant import RawEmail
                    linked_emails = db.query(RawEmail).filter(
                        RawEmail.expense_id == expense.id
                    ).all()
                    for email in linked_emails:
                        email.expense_id = None
                    if linked_emails:
                        logger.info(f"Unlinked {len(linked_emails)} raw emails from deleted expense {expense.id}")
                except Exception as e:
                    logger.warning(f"Failed to unlink raw emails from expense {expense.id}: {e}")

                # Remove from search index
                try:
                    search_service.delete_document('expenses', str(expense.id))
                except Exception as e:
                    logger.warning(f"Failed to remove expense {expense.id} from search index: {e}")

                # Log audit event for each deleted expense
                log_audit_event(
                    db=db,
                    user_id=current_user.id,
                    user_email=current_user.email,
                    action="BULK_SOFT_DELETE",
                    resource_type="expense",
                    resource_id=str(expense.id),
                    resource_name=f"Expense {expense.id}",
                    details={
                        "amount": float(expense.amount),
                        "currency": expense.currency,
                        "date": expense.expense_date.isoformat() if expense.expense_date else None,
                        "category": expense.category,
                        "vendor": expense.vendor,
                        "status": expense.status,
                        "notes": expense.notes
                    }
                )

                # Soft delete the expense (move to recycle bin)
                expense.is_deleted = True
                expense.deleted_at = get_tenant_timezone_aware_datetime(db)
                expense.deleted_by = current_user.id
                expense.updated_at = get_tenant_timezone_aware_datetime(db)
                deleted_count += 1

            except Exception as e:
                logger.error(f"Failed to delete expense {expense.id}: {e}")
                # Continue with other expenses but log the failure

        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{expense_id:int}/accept-review", response_model=ExpenseSchema)
async def accept_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "review expenses")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    review_service = ReviewService(db)
    success = review_service.accept_review(expense)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to accept review or no review available")

    db.commit()
    db.refresh(expense)

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_ACCEPT_EXPENSE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=getattr(expense, "vendor", None),
        details={"expense_id": expense.id, "review_status": expense.review_status}
    )

    return expense

@router.post("/{expense_id:int}/reject-review", response_model=ExpenseSchema)
async def reject_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_non_viewer(current_user, "review expenses")

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    review_service = ReviewService(db)
    success = review_service.reject_review(expense)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject review")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_REJECT_EXPENSE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=getattr(expense, "vendor", None),
        details={"expense_id": expense.id, "review_status": expense.review_status}
    )

    return expense

@router.post("/{expense_id:int}/review", response_model=ExpenseSchema)
async def run_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Trigger a full re-review (reset status to not_started for the worker to pick up)"""
    require_non_viewer(current_user, "review expenses")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Check if review worker is enabled
    from commercial.ai.services.ai_config_service import AIConfigService
    if not AIConfigService.is_review_worker_enabled(db):
        raise HTTPException(
            status_code=400,
            detail="Review worker is currently disabled. Please enable it in Settings > AI Configuration before triggering a review."
        )

    # Reset review status to pending so it shows immediately in UI
    # The worker will pick it up and process it
    expense.review_status = "pending"
    expense.review_result = None
    expense.reviewed_at = None

    db.commit()
    db.refresh(expense)

    # Publish Kafka event to trigger review
    try:
        from core.services.review_event_service import get_review_event_service
        from core.models.database import get_tenant_context

        tenant_id = get_tenant_context()
        if tenant_id:
            event_service = get_review_event_service()
            event_service.publish_single_review_trigger(
                tenant_id=tenant_id,
                entity_type="expense",
                entity_id=expense_id
            )
            logger.info(f"Published Kafka event to trigger review for expense {expense_id}")
    except Exception as e:
        logger.warning(f"Failed to publish Kafka event for expense review trigger: {e}")

    # Log audit event
    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="REVIEW_TRIGGER_EXPENSE",
        resource_type="expense",
        resource_id=str(expense.id),
        resource_name=getattr(expense, "vendor", None),
        details={"expense_id": expense.id, "review_status": expense.review_status}
    )

    return expense


@router.post("/{expense_id:int}/cancel-review", response_model=ExpenseSchema)
async def cancel_expense_review(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Cancel an in-progress review for an expense"""
    require_non_viewer(current_user, "review expenses")

    # Set tenant context
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.is_deleted == False).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Can only cancel if review is pending, not_started, rejected, or failed
    if expense.review_status not in ["pending", "not_started", "rejected", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel review with status '{expense.review_status}'. Only pending, rejected, failed, or not_started reviews can be cancelled."
        )

    # Cancel the review
    expense.review_status = "not_started"
    expense.review_result = None
    expense.reviewed_at = None

    db.commit()
    db.refresh(expense)

    logger.info(f"Cancelled review for expense {expense_id}")

    return expense


@router.put("/{expense_id:int}", response_model=ExpenseSchema)
async def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "update expenses")

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    # Log the incoming update data for debugging
    uvicorn_logger.info(f"Updating expense {expense_id} with data: {expense.model_dump(exclude_unset=True)}")

    try:
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == False
        ).first()
        if not db_expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        # Check if expense can be modified based on current status
        check_expense_modification_allowed(db_expense)

        previous_status = getattr(db_expense, "analysis_status", None)

        currency_service = CurrencyService(db)
        update_data = expense.model_dump(exclude_unset=True)

        # Validate status transition if status is actually changing
        if "status" in update_data:
            new_status = update_data["status"]
            if db_expense.status != new_status and not validate_status_transition(db_expense.status, new_status):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status transition from '{db_expense.status}' to '{new_status}'"
                )

        if "currency" in update_data:
            if not currency_service.validate_currency_code(update_data["currency"]):
                raise HTTPException(status_code=400, detail=f"Invalid currency code: {update_data['currency']}")

        if "expense_date" in update_data and isinstance(update_data["expense_date"], date):
            update_data["expense_date"] = datetime.combine(update_data["expense_date"], datetime.min.time()).replace(tzinfo=timezone.utc)

        # Validate invoice exists if attempting to (re)link
        if "invoice_id" in update_data and update_data["invoice_id"] is not None:
            inv = db.query(Invoice).filter(Invoice.id == int(update_data["invoice_id"])) .first()
            if not inv:
                raise HTTPException(status_code=400, detail=f"Invoice {update_data['invoice_id']} not found")

        # Recalculate tax/total if needed
        amount = update_data.get("amount", db_expense.amount)
        if amount is not None:
            amount = float(amount)
        tax_rate = update_data.get("tax_rate", db_expense.tax_rate)
        tax_amount = update_data.get("tax_amount", db_expense.tax_amount)
        total_amount = update_data.get("total_amount", db_expense.total_amount)
        if amount is not None:
            if tax_amount is None and tax_rate is not None:
                tax_amount = float(amount) * float(tax_rate) / 100.0
            if total_amount is None:
                total_amount = float(amount) + float(tax_amount or 0)

        update_data["tax_amount"] = tax_amount
        update_data["total_amount"] = total_amount

        # Log invoice link/unlink intent
        if "invoice_id" in update_data:
            uvicorn_logger.info(
                f"Updating expense {expense_id}: invoice_id {db_expense.invoice_id} -> {update_data['invoice_id']}"
            )

        # Handle inventory purchase updates
        if "is_inventory_purchase" in update_data or "inventory_items" in update_data:
            is_inventory_purchase = update_data.get("is_inventory_purchase", db_expense.is_inventory_purchase)
            inventory_items = update_data.get("inventory_items", db_expense.inventory_items)

            # Validate inventory purchase data if being set to true
            if is_inventory_purchase and inventory_items:
                if not inventory_items or len(inventory_items) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Inventory purchase must include at least one item"
                    )

                # Validate each inventory item
                from core.services.inventory_service import InventoryService
                inventory_service = InventoryService(db)

                for item_data in inventory_items:
                    item_id = item_data.get('item_id')
                    quantity = item_data.get('quantity', 0)

                    if not item_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Each inventory item must have an item_id"
                        )

                    # Verify item exists
                    inventory_item = inventory_service.get_item(item_id)
                    if not inventory_item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Inventory item {item_id} not found"
                        )

                    if quantity <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Quantity must be greater than 0 for item {inventory_item.name}"
                    )

        # Handle inventory consumption updates
        if "is_inventory_consumption" in update_data or "consumption_items" in update_data:
            is_inventory_consumption = update_data.get("is_inventory_consumption", db_expense.is_inventory_consumption)
            consumption_items = update_data.get("consumption_items", db_expense.consumption_items)

            # Validate inventory consumption data if being set to true
            if is_inventory_consumption and consumption_items:
                if not consumption_items or len(consumption_items) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Inventory consumption must include at least one item"
                    )

                # Validate each consumption item
                from core.services.inventory_service import InventoryService
                inventory_service = InventoryService(db)

                for item_data in consumption_items:
                    item_id = item_data.get('item_id')
                    quantity = item_data.get('quantity', 0)

                    if not item_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Each consumption item must have an item_id"
                        )

                    # Verify item exists
                    inventory_item = inventory_service.get_item(item_id)
                    if not inventory_item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Inventory item {item_id} not found"
                        )

                    if quantity <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Quantity must be greater than 0 for item {inventory_item.name}"
                        )

                    # Check if there's enough stock
                    if inventory_item.track_stock and inventory_item.current_stock < quantity:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Insufficient stock for {inventory_item.name}. Available: {inventory_item.current_stock}, Requested: {quantity}"
                        )

        # Normalize labels if provided
        if "labels" in update_data:
            raw = update_data.get("labels") or ([] if not update_data.get("label") else [update_data.get("label")])
            norm = []
            seen = set()
            for s in raw:
                if not isinstance(s, str):
                    continue
                v = s.strip()
                if not v or v in seen:
                    continue
                norm.append(v)
                seen.add(v)
                if len(norm) >= 10:
                    break
            update_data["labels"] = norm or None

        for k, v in update_data.items():
            if k == "amount":
                setattr(db_expense, k, float(v) if v is not None else None)
            else:
                setattr(db_expense, k, v)
        # Any manual update marks manual_override true and halts analysis
        db_expense.manual_override = True
        # If analysis was queued/processing, mark as cancelled and try to cancel downstream
        if previous_status in ("queued", "processing"):
            db_expense.analysis_status = "cancelled"
            try:
                cancel_ocr_tasks_for_expense(expense_id)
            except Exception:
                pass

        db_expense.updated_at = get_tenant_timezone_aware_datetime(db)
        db.commit()
        db.refresh(db_expense)
        if "invoice_id" in update_data:
            uvicorn_logger.info(f"Updated expense {expense_id} persisted with invoice_id={db_expense.invoice_id}")

        # Handle inventory stock movements for updated purchases
        if ("is_inventory_purchase" in update_data or "inventory_items" in update_data) and db_expense.is_inventory_purchase and db_expense.inventory_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_purchase(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for updated expense {expense_id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process stock movements for updated expense {expense_id}: {e}")
                # Don't fail the expense update, but log the error
                # The expense is already updated, stock movements can be processed later if needed

        # Handle inventory stock movements for updated consumption
        if ("is_inventory_consumption" in update_data or "consumption_items" in update_data) and db_expense.is_inventory_consumption and db_expense.consumption_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_consumption(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for updated consumption expense {expense_id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process consumption stock movements for updated expense {expense_id}: {e}")
                # Don't fail the expense update, but log the error
                # The expense is already updated, stock movements can be processed later if needed

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details=expense.model_dump(exclude_unset=True),
            status="success",
        )

        # Reindex the expense for global search
        try:
            search_service.index_expense(db_expense)
        except Exception as e:
            uvicorn_logger.warning(f"Failed to reindex expense {expense_id} for search: {e}")

        return db_expense
    except HTTPException as he:
        uvicorn_logger.error(f"HTTP error updating expense {expense_id}: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        db.rollback()
        uvicorn_logger.error(f"Failed to update expense {expense_id}: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update expense")


# Recycle Bin Endpoints (must come before /{expense_id} route)

@router.get("/recycle-bin", response_model=PaginatedDeletedExpenses)
async def get_deleted_expenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
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
            # Get deleted by user information
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
        # Only admins can empty the recycle bin
        if current_user.role != 'admin':
            raise HTTPException(
                status_code=403,
                detail="Only admins can empty the recycle bin"
            )

        # Get count of deleted expenses
        count = db.query(Expense).filter(Expense.is_deleted == True).count()

        if count == 0:
            return {"message": "Recycle bin is already empty", "deleted_count": 0}

        # Define the background task function
        def delete_expenses_background(tenant_id: int, user_id: int, user_email: str, count: int):
            """Background task to delete all expenses in recycle bin"""
            from core.models.database import set_tenant_context
            from core.services.tenant_database_manager import tenant_db_manager

            # Set tenant context for this background task
            set_tenant_context(tenant_id)

            # Get tenant-specific session
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            db_task = SessionLocal_tenant()
            try:
                # Get all deleted expenses
                deleted_expenses = db_task.query(Expense).filter(Expense.is_deleted == True).all()

                # Delete all attachment files from storage before deleting expenses
                try:
                    import asyncio

                    async def delete_files():
                        for expense in deleted_expenses:
                            # Delete legacy receipt file if exists
                            if expense.receipt_path:
                                try:
                                    await delete_file_from_storage(expense.receipt_path, tenant_id, user_id, db_task)
                                except Exception as e:
                                    logger.warning(f"Failed to delete receipt file {expense.receipt_path}: {e}")

                            # Delete modern attachments
                            attachments = db_task.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).all()
                            for att in attachments:
                                if att.file_path:
                                    try:
                                        await delete_file_from_storage(att.file_path, tenant_id, user_id, db_task)
                                    except Exception as e:
                                        logger.warning(f"Failed to delete attachment file {att.file_path}: {e}")

                        if deleted_expenses:
                            logger.info(f"Deleted attachment files for {len(deleted_expenses)} expense(s) during recycle bin empty")

                    # Run async file deletion
                    asyncio.run(delete_files())

                except Exception as e:
                    logger.warning(f"Failed to delete attachment files during expense recycle bin empty: {e}")

                # Delete all expenses in recycle bin
                for expense in deleted_expenses:
                    db_task.delete(expense)

                db_task.commit()

                # Audit log for empty recycle bin
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

        # Add the deletion task to background tasks
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
        # Find the deleted expense
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == True
        ).first()

        if not db_expense:
            raise HTTPException(
                status_code=404,
                detail="Deleted expense not found"
            )

        # Restore the expense
        db_expense.is_deleted = False
        db_expense.deleted_at = None
        db_expense.deleted_by = None
        db_expense.status = restore_request.new_status  # Set the new status
        db_expense.updated_at = get_tenant_timezone_aware_datetime(db)

        db.commit()

        # Audit log for restore
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
        # Find the deleted expense
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == True
        ).first()

        if not db_expense:
            raise HTTPException(
                status_code=404,
                detail="Deleted expense not found"
            )

        # Delete attachment files from storage
        try:
            # Delete legacy receipt file if exists
            if db_expense.receipt_path:
                try:
                    await delete_file_from_storage(db_expense.receipt_path, current_user.tenant_id, current_user.id, db)
                except Exception as e:
                    logger.warning(f"Failed to delete receipt file {db_expense.receipt_path}: {e}")

            # Delete modern attachments
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

        # Permanently delete the expense
        db.delete(db_expense)
        db.commit()

        # Audit log for permanent delete
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


@router.delete("/{expense_id:int}", response_model=RecycleBinExpenseResponse)
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Move an expense to the recycle bin (soft delete)"""
    require_non_viewer(current_user, "delete expenses")

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        uvicorn_logger.info(f"Attempting to delete expense {expense_id} for tenant {current_user.tenant_id}")

        # First attempt to find the expense
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == False
        ).first()

        if not db_expense:
            # If not found, try refreshing the session and querying again
            # This handles cases where the expense was just created and the session hasn't seen it yet
            try:
                db.expire_all()  # Clear the session cache
                db_expense = db.query(Expense).filter(
                    Expense.id == expense_id,
                    Expense.is_deleted == False
                ).first()
            except Exception as e:
                uvicorn_logger.warning(f"Error refreshing session for expense {expense_id}: {e}")

        if not db_expense:
            uvicorn_logger.warning(f"Expense {expense_id} not found for deletion (tenant {current_user.tenant_id})")
            raise HTTPException(status_code=404, detail="Expense not found")

        uvicorn_logger.info(f"Found expense {expense_id}, proceeding with deletion")

        # Check if expense can be deleted based on current status
        # Allow admins to bypass this check
        if current_user.role != 'admin' and db_expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete expense with status '{db_expense.status}'. Expense is in approval workflow."
            )

        # Prevent deleting an expense that is linked to an invoice
        if getattr(db_expense, "invoice_id", None) is not None:
            raise HTTPException(status_code=400, detail=EXPENSE_LINKED_TO_INVOICE)

        # Unlink any bank statement transactions that reference this expense
        try:
            from core.models.models_per_tenant import BankStatementTransaction
            linked_transactions = db.query(BankStatementTransaction).filter(
                BankStatementTransaction.expense_id == expense_id
            ).all()
            for txn in linked_transactions:
                txn.expense_id = None
            if linked_transactions:
                logger.info(f"Unlinked {len(linked_transactions)} bank transactions from deleted expense {expense_id}")
        except Exception as e:
            logger.warning(f"Failed to unlink bank transactions from expense {expense_id}: {e}")

        # Unlink any raw emails that reference this expense
        try:
            from core.models.models_per_tenant import RawEmail
            linked_emails = db.query(RawEmail).filter(
                RawEmail.expense_id == expense_id
            ).all()
            for email in linked_emails:
                email.expense_id = None
            if linked_emails:
                logger.info(f"Unlinked {len(linked_emails)} raw emails from deleted expense {expense_id}")
        except Exception as e:
            logger.warning(f"Failed to unlink raw emails from expense {expense_id}: {e}")

        # Soft delete the expense
        db_expense.is_deleted = True
        db_expense.deleted_at = get_tenant_timezone_aware_datetime(db)
        db_expense.deleted_by = current_user.id
        db_expense.updated_at = get_tenant_timezone_aware_datetime(db)

        db.commit()
        uvicorn_logger.info(f"Successfully deleted expense {expense_id}")

        # After commit, verify the deletion was successful by querying fresh from the database
        # This is critical for multi-session environments
        db.expire_all()  # Clear the session cache
        verification_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == True
        ).first()

        if not verification_expense:
            uvicorn_logger.error(f"CRITICAL: Expense {expense_id} deletion verification failed - expense not marked as deleted!")
            raise HTTPException(status_code=500, detail=f"Expense deletion verification failed (ID: {expense_id})")

        uvicorn_logger.info(f"Successfully verified deletion of expense {expense_id}")

        # Remove from search index
        try:
            search_service.delete_document('expenses', str(expense_id))
        except Exception as e:
            logger.warning(f"Failed to remove expense {expense_id} from search index: {e}")

        # Audit log for soft delete
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="Soft Delete",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details={"message": "Expense moved to recycle bin"},
            status="success"
        )

        return RecycleBinExpenseResponse(
            message="Expense moved to recycle bin successfully",
            expense_id=expense_id,
            action="moved_to_recycle"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_expense: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move expense to recycle bin: {str(e)}"
        )


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

        # Validate filename exists
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Validate file extension
        file_ext = os.path.splitext(file.filename.lower())[1]
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.heic'}
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File type not allowed. Supported: {', '.join(allowed_extensions)}")

        # Validate content type
        allowed_types = {
            'application/pdf': '.pdf',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/heic': '.heic',
            'image/heif': '.heif',
        }
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="File type not allowed. Supported: PDF, JPG, PNG, HEIC, HEIF")

        # Read and validate file size
        MAX_BYTES = 10 * 1024 * 1024
        contents = await file.read()
        if len(contents) > MAX_BYTES:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB")

        # Get tenant context
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=500, detail="Tenant context not available")

        # Sanitize filename
        original_name = file.filename or "receipt"
        base_name = os.path.basename(original_name)
        base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)

        # Enforce maximum of 10 attachments
        existing_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).count()
        if existing_count >= 10:
            raise HTTPException(status_code=400, detail="Maximum of 10 attachments per expense")

        # Initialize cloud storage service
        try:
            try:
                from commercial.cloud_storage.service import CloudStorageService
                from commercial.cloud_storage.config import get_cloud_storage_config

                cloud_config = get_cloud_storage_config()
                cloud_storage_service = CloudStorageService(db, cloud_config)

                # Store file using cloud storage with automatic fallback
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

                # Determine storage location and file path
                if storage_result.file_url:
                    # Cloud storage - use file_key as path
                    file_path = storage_result.file_key
                    file_size = storage_result.file_size or len(contents)
                    is_cloud_stored = True
                else:
                    # Local storage fallback - construct traditional path
                    tenant_folder = f"tenant_{tenant_id}"
                    receipts_dir = Path("attachments") / tenant_folder / "expenses"
                    name_without_ext = os.path.splitext(base_name)[0][:100]
                    ext_from_ct = allowed_types[file.content_type]
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
            # Fallback to local storage
            tenant_folder = f"tenant_{tenant_id}"
            receipts_dir = Path("attachments") / tenant_folder / "expenses"
            receipts_dir.mkdir(parents=True, exist_ok=True)

            name_without_ext = os.path.splitext(base_name)[0][:100]
            ext_from_ct = allowed_types[file.content_type]
            unique_suffix = str(uuid.uuid4())
            filename = f"expense_{expense_id}_{name_without_ext}_{unique_suffix}{ext_from_ct}"
            file_path = receipts_dir / filename

            # Validate file path before writing
            from core.utils.file_validation import validate_file_path
            validated_path = validate_file_path(str(file_path), must_exist=False)

            with open(validated_path, "wb") as buffer:
                buffer.write(contents)

            file_path = str(file_path)
            file_size = len(contents)
            is_cloud_stored = False
            logger.info(f"File stored locally as fallback: {file_path}")

        # Save as attachment record
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

        # Update expense status and queue OCR — non-fatal if anything fails
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

            # Queue OCR processing
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

        # Get all attachments for this expense
        attachments = (
            db.query(ExpenseAttachment)
            .filter(ExpenseAttachment.expense_id == expense_id)
            .order_by(ExpenseAttachment.uploaded_at.desc())
            .all()
        )
        if not attachments or not any(getattr(att, "file_path", None) for att in attachments):
            raise HTTPException(status_code=400, detail="No attachments found to reprocess")

        # Import ProcessingLock model
        from core.models.processing_lock import ProcessingLock

        # Check if expense is already being processed
        if ProcessingLock.is_locked(db, "expense", expense_id):
            # If expense is in a terminal state but locked, it's a stale lock
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

        # Acquire processing lock
        request_id = f"reprocess_{expense_id}_{datetime.now(timezone.utc).timestamp()}"
        if not ProcessingLock.acquire_lock(
            db, "expense", expense_id, current_user.id,
            lock_duration_minutes=30, metadata={"request_id": request_id}
        ):
            # Lock was acquired by someone else between check and acquire
            lock_info = ProcessingLock.get_active_lock_info(db, "expense", expense_id)
            return {
                "message": "Expense is already being processed by another request",
                "status": "already_processing",
                "lock_info": lock_info
            }

        try:
            from core.models.database import get_tenant_context
            tenant_id = get_tenant_context()

            # Check if ai_expense feature is licensed before reprocessing
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

            # Reset status and requeue
            expense.analysis_status = "queued"
            expense.analysis_error = None
            expense.manual_override = False
            expense.updated_at = get_tenant_timezone_aware_datetime(db)
            db.commit()

            # Queue all attachments for reprocessing
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

            # Log audit event
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
            # Release lock on failure
            ProcessingLock.release_lock(db, "expense", expense_id)
            logger.error(f"Failed to reprocess expense {expense_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to reprocess expense")

    except HTTPException:
        raise
    except Exception as e:
        # Release lock on unexpected error
        try:
            ProcessingLock.release_lock(db, "expense", expense_id)
        except:
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

    # Allow deleting attachments even from analyzed expenses (user confirms via UI)

    # Delete file from storage (cloud and/or local)
    if att.file_path:
        await delete_file_from_storage(att.file_path, current_user.tenant_id, current_user.id, db)

    # Delete attachment record from database
    db.delete(att)
    db.commit()
    return None


@router.get("/{expense_id}/attachments/{attachment_id}/download")
async def download_expense_attachment(
    expense_id: int,
    attachment_id: int,
    inline: bool = False,  # Set to True for preview, False for download
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    # Set tenant context for encryption operations
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

    import os
    from io import BytesIO
    import mimetypes

    cloud_enabled = os.getenv('CLOUD_STORAGE_ENABLED', 'false').lower() == 'true'

    # Determine storage type from the path stored in DB:
    # Local paths start with '/' or 'attachments/'; anything else is treated as a cloud key.
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
        """Try to serve from local disk. Returns None if file not found."""
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
        """Try to retrieve from CloudStorageService. Returns None on failure."""
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
        # Cloud key in DB → try S3/cloud first, fall back to local
        response = await _serve_cloud(att.file_path)
        if response:
            return response
        response = _serve_local(att.file_path)
        if response:
            return response
    else:
        # Local path in DB → try local first, fall back to cloud
        response = _serve_local(att.file_path)
        if response:
            return response
        if cloud_enabled:
            response = await _serve_cloud(att.file_path)
            if response:
                return response

    logger.error(f"File not found in any storage: '{att.file_path}'")
    raise HTTPException(status_code=404, detail="Attachment file not found")


# Basic Expense Analytics Endpoints (for Expenses page summary)
@router.get("/analytics/summary")
async def get_expense_summary(
    period: str = "month",  # "day", "week", "month", "quarter", "year"
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    compare_with_previous: bool = True,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get expense summary statistics with period comparisons"""

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        # Base query for all expenses in tenant (not pending approval)
        # Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
        base_query = db.query(Expense).filter(
            Expense.status != 'pending_approval',
            Expense.is_deleted == False
        )

        # Determine date range
        end_dt = datetime.now(timezone.utc)
        start_dt = None

        if start_date and end_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        else:
            # Calculate date range based on period
            if period == "day":
                start_dt = end_dt - timedelta(days=1)
            elif period == "week":
                start_dt = end_dt - timedelta(weeks=1)
            elif period == "month":
                start_dt = end_dt - timedelta(days=30)
            elif period == "quarter":
                start_dt = end_dt - timedelta(days=90)
            elif period == "year":
                start_dt = end_dt - timedelta(days=365)
            else:
                start_dt = end_dt - timedelta(days=30)

        # Current period expenses
        current_expenses = base_query.filter(
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt
        ).all()

        # Calculate summary for current period
        current_total = sum(float(e.total_amount or e.amount or 0) for e in current_expenses)
        current_count = len(current_expenses)

        # Calculate previous period for comparison
        period_length = end_dt - start_dt
        previous_start = start_dt - period_length
        previous_end = start_dt

        previous_expenses = base_query.filter(
            Expense.expense_date >= previous_start,
            Expense.expense_date <= previous_end
        ).all()

        previous_total = sum(float(e.total_amount or e.amount or 0) for e in previous_expenses)
        previous_count = len(previous_expenses)

        # Calculate percentage changes
        total_change = None
        count_change = None
        if previous_total > 0:
            total_change = ((current_total - previous_total) / previous_total) * 100
        if previous_count > 0:
            count_change = ((current_count - previous_count) / previous_count) * 100

        # Calculate category breakdown
        category_totals = {}
        for expense in current_expenses:
            category = expense.category or "Uncategorized"
            amount = float(expense.total_amount or expense.amount or 0)
            category_totals[category] = category_totals.get(category, 0) + amount

        # Sort categories by total amount
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)

        # Calculate daily breakdown for charts
        daily_totals = defaultdict(float)

        for expense in current_expenses:
            date_key = expense.expense_date.date().isoformat()
            daily_totals[date_key] += float(expense.total_amount or expense.amount or 0)

        # Sort daily totals by date
        sorted_daily_totals = sorted(daily_totals.items())

        return {
            "period": {
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "period_type": period
            },
            "current_period": {
                "total_amount": current_total,
                "total_count": current_count,
                "average_amount": current_total / current_count if current_count > 0 else 0
            },
            "previous_period": {
                "total_amount": previous_total,
                "total_count": previous_count,
                "average_amount": previous_total / previous_count if previous_count > 0 else 0
            } if compare_with_previous else None,
            "changes": {
                "total_amount_change_percent": round(total_change, 2) if total_change is not None else None,
                "count_change_percent": round(count_change, 2) if count_change is not None else None
            } if compare_with_previous else None,
            "category_breakdown": [{"category": cat, "amount": amt, "percentage": round((amt / current_total) * 100, 1) if current_total > 0 else 0} for cat, amt in sorted_categories],
            "daily_totals": [{"date": date, "amount": amount} for date, amount in sorted_daily_totals]
        }

    except Exception as e:
        logger.error(f"Failed to get expense summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expense summary")


@router.get("/analytics/trends")
async def get_expense_trends(
    days: int = 90,
    group_by: str = "week",  # "day", "week", "month"
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get expense trends over a time period"""

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    try:

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Base query for all expenses in tenant (not pending approval)
        # Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
        expenses = db.query(Expense).filter(
            Expense.status != 'pending_approval',
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
            Expense.is_deleted == False
        ).all()

        # Group expenses by the requested period
        trend_data = defaultdict(float)
        trend_counts = defaultdict(int)

        for expense in expenses:
            amount = float(expense.total_amount or expense.amount or 0)

            if group_by == "day":
                key = expense.expense_date.date().isoformat()
            elif group_by == "week":
                # Calculate week start (Monday)
                week_start = expense.expense_date.date() - timedelta(days=expense.expense_date.weekday())
                key = week_start.isoformat()
            elif group_by == "month":
                key = f"{expense.expense_date.year}-{expense.expense_date.month:02d}"
            else:
                key = expense.expense_date.date().isoformat()

            trend_data[key] += amount
            trend_counts[key] += 1

        # Convert to sorted list
        sorted_trends = []
        for key in sorted(trend_data.keys()):
            sorted_trends.append({
                "period": key,
                "total_amount": trend_data[key],
                "count": trend_counts[key],
                "average_amount": trend_data[key] / trend_counts[key] if trend_counts[key] > 0 else 0
            })

        # Calculate trend analysis
        if len(sorted_trends) >= 2:
            # Linear regression to calculate trend direction
            x = list(range(len(sorted_trends)))
            y = [item["total_amount"] for item in sorted_trends]

            if len(x) >= 2:
                n = len(x)
                sum_x = sum(x)
                sum_y = sum(y)
                sum_xy = sum(xi * yi for xi, yi in zip(x, y))
                sum_xx = sum(xi * xi for xi in x)

                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
                trend_direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"

                # Calculate volatility (coefficient of variation)
                mean_y = sum_y / n
                variance = sum((yi - mean_y) ** 2 for yi in y) / n
                std_dev = math.sqrt(variance)
                volatility = (std_dev / mean_y * 100) if mean_y > 0 else 0
            else:
                trend_direction = "stable"
                volatility = 0
        else:
            trend_direction = "insufficient_data"
            volatility = 0

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
                "group_by": group_by
            },
            "trends": sorted_trends,
            "analysis": {
                "trend_direction": trend_direction,
                "volatility_percent": round(volatility, 2),
                "total_periods": len(sorted_trends),
                "total_amount": sum(trend_data.values()),
                "average_period_amount": sum(trend_data.values()) / len(trend_data) if trend_data else 0
            }
        }

    except Exception as e:
        logger.error(f"Failed to get expense trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expense trends")


@router.get("/analytics/categories")
async def get_expense_categories_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Get expense analytics by category"""

    # Set tenant context for encryption operations
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    try:
        # Base query for all expenses in tenant (not pending approval)
        # Note: No user_id filter needed - tenant isolation is provided by the per-tenant database
        base_query = db.query(Expense).filter(
            Expense.status != 'pending_approval',
            Expense.is_deleted == False
        )

        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                base_query = base_query.filter(Expense.expense_date >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                base_query = base_query.filter(Expense.expense_date <= end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format")

        # Apply category filter
        if category_filter and category_filter != "all":
            base_query = base_query.filter(Expense.category == category_filter)

        expenses = base_query.all()

        # Group by category
        category_stats = defaultdict(lambda: {
            "total_amount": 0,
            "count": 0,
            "expenses": []
        })

        grand_total = 0
        for expense in expenses:
            category = expense.category or "Uncategorized"
            amount = float(expense.total_amount or expense.amount or 0)
            grand_total += amount

            category_stats[category]["total_amount"] += amount
            category_stats[category]["count"] += 1
            category_stats[category]["expenses"].append({
                "id": expense.id,
                "amount": amount,
                "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
                "vendor": expense.vendor,
                "notes": expense.notes
            })

        # Sort categories by total amount
        sorted_categories = sorted(
            category_stats.items(),
            key=lambda x: x[1]["total_amount"],
            reverse=True
        )

        # Add percentages
        category_analytics = []
        for category, stats in sorted_categories:
            percentage = (stats["total_amount"] / grand_total * 100) if grand_total > 0 else 0
            category_analytics.append({
                "category": category,
                "total_amount": stats["total_amount"],
                "percentage": round(percentage, 1),
                "count": stats["count"],
                "average_amount": stats["total_amount"] / stats["count"] if stats["count"] > 0 else 0,
                "expenses": stats["expenses"][:10]  # Limit to 10 most recent expenses per category
            })

        return {
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "grand_total": grand_total,
            "categories": category_analytics,
            "total_categories": len(category_analytics)
        }

    except Exception as e:
        logger.error(f"Failed to get expense categories analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expense categories analytics")
