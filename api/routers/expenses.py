from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
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
import shutil
from collections import defaultdict
import sqlalchemy as sa

from models.database import get_db
from models.models_per_tenant import Expense, ExpenseAttachment, User, Invoice, BankStatementTransaction
from models.models import MasterUser
from routers.auth import get_current_user
from schemas.expense import ExpenseCreate, ExpenseUpdate, Expense as ExpenseSchema
from services.currency_service import CurrencyService
from utils.rbac import require_non_viewer
from utils.audit import log_audit_event
from services.ocr_service import queue_or_process_attachment, cancel_ocr_tasks_for_expense
from constants.error_codes import EXPENSE_LINKED_TO_INVOICE
from constants.expense_status import ExpenseStatus


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Ensure logs are visible under uvicorn
uvicorn_logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/expenses", tags=["expenses"])


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


@router.get("/", response_model=List[ExpenseSchema])
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    label: Optional[str] = None,
    invoice_id: Optional[int] = None,
    unlinked_only: bool = False,
    exclude_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    # Set tenant context for encryption operations
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    
    try:
        # Build the base query with all filters
        query = db.query(Expense).filter(Expense.user_id == current_user.id)
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
        
        # Count total expenses with all filters applied
        total_count = query.count()
        
        # If skip is beyond available data, return empty results
        if skip >= total_count and total_count > 0:
            logger.info(f"Pagination beyond available data: skip={skip} >= total={total_count}, returning empty results")
            return []

        expenses = query.order_by(Expense.id.desc()).offset(skip).limit(limit).all()

        # Log pagination info for debugging
        logger.info(f"Expenses query: total_count={total_count}, skip={skip}, limit={limit}, returned={len(expenses)}, exclude_status={exclude_status}")

        # Add attachment count for preview
        try:
            for ex in expenses:
                ex.attachments_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == ex.id).count()
        except Exception as e:
            logger.warning(f"Failed to get attachment count for expenses: {e}")
        return expenses
    except Exception as e:
        logger.error(f"Failed to list expenses: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expenses")


@router.get("/{expense_id}", response_model=ExpenseSchema)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    # Set tenant context for encryption operations
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    try:
        expense.attachments_count = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).count()
    except Exception as e:
        logger.warning(f"Failed to get attachment count for expense {expense_id}: {e}")

    return expense


@router.post("/", response_model=ExpenseSchema)
async def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "create expenses")

    # Set tenant context for encryption operations
    from models.database import set_tenant_context
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
            from services.inventory_service import InventoryService
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
            from services.inventory_service import InventoryService
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
            is_inventory_purchase=is_inventory_purchase,
            inventory_items=inventory_items,
            is_inventory_consumption=is_inventory_consumption,
            consumption_items=consumption_items,
            imported_from_attachment=bool(getattr(expense, "imported_from_attachment", False)),
            analysis_status=getattr(expense, "analysis_status", "not_started"),
            analysis_result=getattr(expense, "analysis_result", None),
            analysis_error=getattr(expense, "analysis_error", None),
            manual_override=bool(getattr(expense, "manual_override", False)),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)

        # Process inventory stock movements for inventory purchases
        if is_inventory_purchase and inventory_items:
            try:
                from services.inventory_integration_service import InventoryIntegrationService
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
                from services.inventory_integration_service import InventoryIntegrationService
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

        target_items = db.query(Expense).filter(Expense.id.in_(payload.expense_ids)).all()
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
            item.updated_at = datetime.now(timezone.utc)
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
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
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


@router.put("/{expense_id}", response_model=ExpenseSchema)
async def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "update expenses")
    
    # Set tenant context for encryption operations
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    
    try:
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
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
        amount = float(update_data.get("amount", db_expense.amount))
        tax_rate = update_data.get("tax_rate", db_expense.tax_rate)
        tax_amount = update_data.get("tax_amount", db_expense.tax_amount)
        total_amount = update_data.get("total_amount", db_expense.total_amount)
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
                from services.inventory_service import InventoryService
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
                from services.inventory_service import InventoryService
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
            setattr(db_expense, k, v if k != "amount" else float(v))
        # Any manual update marks manual_override true and halts analysis
        db_expense.manual_override = True
        # If analysis was queued/processing, mark as cancelled and try to cancel downstream
        if previous_status in ("queued", "processing"):
            db_expense.analysis_status = "cancelled"
            try:
                cancel_ocr_tasks_for_expense(expense_id)
            except Exception:
                pass

        db_expense.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_expense)
        if "invoice_id" in update_data:
            uvicorn_logger.info(f"Updated expense {expense_id} persisted with invoice_id={db_expense.invoice_id}")

        # Handle inventory stock movements for updated purchases
        if ("is_inventory_purchase" in update_data or "inventory_items" in update_data) and db_expense.is_inventory_purchase and db_expense.inventory_items:
            try:
                from services.inventory_integration_service import InventoryIntegrationService
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
                from services.inventory_integration_service import InventoryIntegrationService
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

        return db_expense
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to update expense")


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "delete expenses")
    
    # Set tenant context for encryption operations
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    
    try:
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not db_expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Check if expense can be deleted based on current status
        if db_expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete expense with status '{db_expense.status}'. Expense is in approval workflow."
            )
        
        # Prevent deleting an expense that is linked to an invoice
        if getattr(db_expense, "invoice_id", None) is not None:
            raise HTTPException(status_code=400, detail=EXPENSE_LINKED_TO_INVOICE)
        # If there is a saved receipt, try to remove it from disk
        # Remove any legacy single receipt file if present
        if db_expense.receipt_path and os.path.exists(db_expense.receipt_path):
            try:
                os.remove(db_expense.receipt_path)
            except Exception as e:
                logger.warning(f"Failed to remove legacy receipt file: {e}")

        # Remove all attachment files associated with this expense
        try:
            attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).all()
            for att in attachments:
                if getattr(att, "file_path", None) and os.path.exists(att.file_path):
                    try:
                        os.remove(att.file_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove attachment file {att.file_path}: {e}")
        except Exception as e:
            logger.warning(f"Failed to enumerate attachments for deletion: {e}")

        # Unlink any bank statement transactions that reference this expense BEFORE deletion
        try:
            from models.models_per_tenant import BankStatementTransaction
            linked_transactions = db.query(BankStatementTransaction).filter(
                BankStatementTransaction.expense_id == expense_id
            ).all()
            for txn in linked_transactions:
                txn.expense_id = None
            if linked_transactions:
                logger.info(f"Unlinked {len(linked_transactions)} bank transactions from deleted expense {expense_id}")
        except Exception as e:
            logger.warning(f"Failed to unlink bank transactions from expense {expense_id}: {e}")

        # Delete the expense (unlinking should prevent FK constraint errors)
        db.delete(db_expense)
        db.commit()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="expense",
            resource_id=str(expense_id),
            resource_name=f"Expense {expense_id}",
            details={"message": "Expense deleted"},
            status="success",
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete expense")


@router.post("/{expense_id}/upload-receipt")
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "upload receipts")
    try:
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        # Validate filename exists
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Validate file extension
        file_ext = os.path.splitext(file.filename.lower())[1]
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File type not allowed. Supported: {', '.join(allowed_extensions)}")

        # Validate content type
        allowed_types = {
            'application/pdf': '.pdf',
            'image/jpeg': '.jpg',
            'image/png': '.png',
        }
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="File type not allowed. Supported: PDF, JPG, PNG")

        # Read and validate file size
        MAX_BYTES = 10 * 1024 * 1024
        contents = await file.read()
        if len(contents) > MAX_BYTES:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB")

        # Get tenant context
        from models.database import get_tenant_context
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
        from services.cloud_storage_service import CloudStorageService
        from settings.cloud_storage_config import get_cloud_storage_config
        
        try:
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
            
        except Exception as e:
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
            from utils.file_validation import validate_file_path
            validated_path = validate_file_path(str(file_path), must_exist=False)
            
            with open(validated_path, "wb") as buffer:
                buffer.write(contents)
            
            file_path = str(file_path)
            file_size = len(contents)
            is_cloud_stored = False
            logger.info(f"File stored locally as fallback: {file_path}")

        # Save as attachment record
        from models.models_per_tenant import ExpenseAttachment as EAtt
        attachment = EAtt(
            expense_id=expense_id,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file_size,
            file_path=file_path,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        expense.updated_at = datetime.now(timezone.utc)

        # Mark expense as imported and queue OCR if not manually overridden and AI not disabled
        try:
            expense.imported_from_attachment = True
            disable_ai = getattr(expense, "disable_ai_recognition", False)
            if not expense.manual_override and not disable_ai:
                expense.analysis_status = "queued"
            elif disable_ai:
                expense.analysis_status = "skipped"
                logger.info(f"AI recognition disabled for expense {expense_id}")
            expense.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(expense)
        except Exception:
            db.rollback()

        # TODO: Publish Kafka message for OCR processing
        try:
            from models.database import get_tenant_context
            tenant_id = get_tenant_context()
        except Exception:
            tenant_id = None
        try:
            db.refresh(attachment)
        except Exception:
            pass

        # Only process attachment if AI recognition is not disabled
        disable_ai = getattr(expense, "disable_ai_recognition", False)
        if not disable_ai:
            queue_or_process_attachment(db, tenant_id, expense_id, getattr(attachment, 'id', 0), str(file_path))
        else:
            logger.info(f"Skipping AI processing for expense {expense_id} - AI recognition disabled")

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
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense_id).order_by(ExpenseAttachment.uploaded_at.desc()).all()
    return [
        {
            "id": att.id,
            "filename": att.filename,
            "content_type": att.content_type,
            "size_bytes": att.size_bytes,
            "uploaded_at": att.uploaded_at.isoformat() if att.uploaded_at else None,
        }
        for att in attachments
    ]


@router.post("/{expense_id}/reprocess")
async def reprocess_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Reprocess expense OCR analysis for pending/queued expenses."""
    require_non_viewer(current_user, "reprocess expenses")
    try:
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        if expense.analysis_status not in ["pending", "queued", "failed"]:
            raise HTTPException(status_code=400, detail=f"Cannot reprocess expense with status: {expense.analysis_status}")
        
        # Find the most recent attachment
        att = (
            db.query(ExpenseAttachment)
            .filter(ExpenseAttachment.expense_id == expense_id)
            .order_by(ExpenseAttachment.uploaded_at.desc())
            .first()
        )
        if not att or not getattr(att, "file_path", None):
            raise HTTPException(status_code=400, detail="No attachment found to reprocess")
        
        from models.database import get_tenant_context
        tenant_id = get_tenant_context()
        
        # Reset status and requeue
        expense.analysis_status = "queued"
        expense.analysis_error = None
        expense.manual_override = False
        expense.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        queue_or_process_attachment(
            db=db,
            tenant_id=tenant_id,
            expense_id=expense_id,
            attachment_id=att.id,
            file_path=str(att.file_path),
        )
        
        return {"message": "Expense reprocessing started", "status": "queued"}
    except HTTPException:
        raise
    except Exception as e:
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
    att = db.query(ExpenseAttachment).filter(ExpenseAttachment.id == attachment_id, ExpenseAttachment.expense_id == expense_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Prevent deleting attachments for expenses already analyzed as done
    try:
        exp = db.query(Expense).filter(Expense.id == expense_id).first()
        if exp and getattr(exp, "analysis_status", None) == "done":
            raise HTTPException(status_code=400, detail="Cannot delete attachments from an analyzed expense")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to verify expense status before deleting attachment: {e}")
    
    # Try to remove file from storage (cloud or local)
    try:
        if att.file_path:
            # Check if this is a cloud storage file
            if not att.file_path.startswith('/') and not att.file_path.startswith('attachments'):
                # This is likely a cloud storage file key - delete from cloud storage
                try:
                    from services.cloud_storage_service import CloudStorageService
                    from settings.cloud_storage_config import get_cloud_storage_config
                    from models.database import get_tenant_context
                    
                    tenant_id = get_tenant_context()
                    if tenant_id:
                        cloud_config = get_cloud_storage_config()
                        cloud_storage_service = CloudStorageService(db, cloud_config)
                        
                        # Delete file from cloud storage
                        delete_result = await cloud_storage_service.delete_file(
                            file_key=att.file_path,
                            tenant_id=str(tenant_id),
                            user_id=current_user.id
                        )
                        
                        if delete_result.success:
                            logger.info(f"Successfully deleted file from cloud storage: {att.file_path}")
                        else:
                            logger.warning(f"Failed to delete file from cloud storage: {delete_result.error_message}")
                    else:
                        logger.warning("No tenant context available for cloud storage deletion")
                        
                except Exception as e:
                    logger.warning(f"Failed to delete file from cloud storage: {e}")
            else:
                # Local file - delete from disk
                if os.path.exists(att.file_path):
                    os.remove(att.file_path)
                    logger.info(f"Successfully deleted local file: {att.file_path}")
                else:
                    logger.warning(f"Local file not found: {att.file_path}")
    except Exception as e:
        logger.warning(f"Failed to remove attachment file: {e}")
    
    # Delete attachment record from database
    db.delete(att)
    db.commit()
    return None


@router.get("/{expense_id}/attachments/{attachment_id}/download")
async def download_expense_attachment(
    expense_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    # Set tenant context for encryption operations
    from models.database import set_tenant_context
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

    # Check if this is a cloud storage file (file_path doesn't start with local path)
    if not att.file_path.startswith('/') and not att.file_path.startswith('attachments'):
        # This is a cloud storage file - download directly using boto3
        try:
            import boto3
            from botocore.config import Config
            import os
            from io import BytesIO

            logger.info(f"Downloading S3 file directly: key='{att.file_path}'")

            # Get AWS credentials from environment
            aws_access_key = os.getenv('AWS_S3_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_S3_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_S3_REGION', 'us-east-1')
            bucket_name = os.getenv('AWS_S3_BUCKET_NAME')

            if not all([aws_access_key, aws_secret_key, bucket_name]):
                logger.error("Missing AWS S3 configuration")
                raise Exception("AWS S3 configuration incomplete")

            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
                config=Config(signature_version='s3v4')
            )

            # Download file content
            response = s3_client.get_object(Bucket=bucket_name, Key=att.file_path)

            file_content = response['Body'].read()
            content_length = len(file_content)

            logger.info(f"Downloaded S3 file: size={content_length}, type={response.get('ContentType', 'application/octet-stream')}")

            # Return file content directly
            media_type = att.content_type or response.get('ContentType', 'application/octet-stream')

            return StreamingResponse(
                BytesIO(file_content),
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename={att.filename}",
                    "Content-Length": str(content_length)
                }
            )

        except Exception as e:
            logger.error(f"S3 download exception: {e}")
            # Fall back to local file handling
            raise Exception(f"S3 download error: {e}")

    # Local file or cloud storage fallback - serve directly
    try:
        from utils.file_validation import validate_file_path
        validated_path = validate_file_path(att.file_path)
        media_type = att.content_type or 'application/octet-stream'
        return FileResponse(path=validated_path, filename=att.filename, media_type=media_type)
    except Exception as e:
        logger.error(f"Failed to serve local file: {e}")
        raise HTTPException(status_code=404, detail="Attachment file not accessible")


# Expense Analytics Endpoints
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
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    
    try:
        # Base query for expenses owned by current user and not pending approval
        base_query = db.query(Expense).filter(
            Expense.user_id == current_user.id,
            Expense.status != 'pending_approval'
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
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    try:

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Base query for expenses owned by current user and not pending approval
        expenses = db.query(Expense).filter(
            Expense.user_id == current_user.id,
            Expense.status != 'pending_approval',
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date
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
    from models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)
    try:
        # Base query for expenses owned by current user and not pending approval
        base_query = db.query(Expense).filter(
            Expense.user_id == current_user.id,
            Expense.status != 'pending_approval'
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
