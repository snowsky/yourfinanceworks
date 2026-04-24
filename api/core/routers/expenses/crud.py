"""Core CRUD operations, bulk operations, and potential-duplicate detection."""

import logging
from collections import defaultdict
from datetime import date, datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.constants.error_codes import EXPENSE_LINKED_TO_INVOICE
from core.constants.expense_status import ExpenseStatus
from core.models.database import get_db, get_master_db
from core.models.models import MasterUser
from core.models.models_per_tenant import (
    BankStatementTransaction,
    Client,
    Expense,
    ExpenseAttachment,
    Invoice,
)
from core.routers.auth import get_current_user
from core.schemas.expense import (
    DeletedExpense,
    Expense as ExpenseSchema,
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseUpdate,
    PaginatedDeletedExpenses,
    RecycleBinExpenseResponse,
    RestoreExpenseRequest,
)
from core.services.currency_service import CurrencyService
from core.services.review_service import ReviewService
from core.services.search_service import search_service
from core.utils.audit import log_audit_event
from core.utils.file_deletion import delete_file_from_storage
from core.utils.rbac import require_non_viewer
from core.utils.timezone import get_tenant_timezone_aware_datetime
from commercial.ai.services.ocr_service import cancel_ocr_tasks_for_expense

from ._shared import (
    BulkDeleteRequest,
    BulkExpenseCreateRequest,
    BulkLabelsRequest,
    _apply_creator_fallback,
    _find_potential_expense_duplicates,
    _is_expense_duplicate_detection_eligible,
    check_expense_modification_allowed,
    validate_status_transition,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
uvicorn_logger = logging.getLogger("uvicorn.error")

router = APIRouter()


@router.get("/", response_model=ExpenseListResponse)
async def list_expenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: str = None,
    label: str = None,
    invoice_id: int = None,
    unlinked_only: bool = False,
    exclude_status: str = None,
    status: str = None,
    search: str = None,
    created_by_user_id: int = None,
    include_total: bool = False,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        logger.info(f"list_expenses: current_user.id={current_user.id}, tenant_id={current_user.tenant_id}, search={search}, include_total={include_total}")
        from sqlalchemy.orm import joinedload
        query = db.query(Expense).options(joinedload(Expense.created_by)).filter(Expense.is_deleted == False)
        base_count = query.count()
        logger.info(f"list_expenses: current_user.id={current_user.id}, tenant_id={current_user.tenant_id}, search={search}")
        if category and category != "all":
            query = query.filter(Expense.category == category)
        if label:
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
        if status:
            query = query.filter(Expense.status == status)
        if created_by_user_id is not None:
            query = query.filter(Expense.created_by_user_id == created_by_user_id)

        if search:
            logger.info(f"list_expenses: applying search filter with term={search}")
            search_lower = search.lower()

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
            total_count = query.count()
            logger.info(f"list_expenses: total_count (after all filters)={total_count}")

            if skip >= total_count and total_count > 0:
                logger.info(f"Pagination beyond available data: skip={skip} >= total={total_count}, returning empty results")
                expenses = []
            else:
                expenses = query.order_by(Expense.id.desc()).offset(skip).limit(limit).all()

        logger.info(f"Expenses query: total_count={total_count}, skip={skip}, limit={limit}, returned={len(expenses)}, exclude_status={exclude_status}")

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

        _apply_creator_fallback(expenses, master_db)

        try:
            if expenses:
                expense_ids = [ex.id for ex in expenses]
                txn_rows = (
                    db.query(BankStatementTransaction.expense_id, BankStatementTransaction.id, BankStatementTransaction.statement_id)
                    .filter(BankStatementTransaction.expense_id.in_(expense_ids))
                    .all()
                )
                txn_map: dict[int, tuple[int, int]] = {row[0]: (row[1], row[2]) for row in txn_rows}
                for ex in expenses:
                    txn = txn_map.get(ex.id)
                    ex.__dict__['statement_transaction_id'] = txn[0] if txn else None
                    ex.__dict__['statement_id'] = txn[1] if txn else None
        except Exception as e:
            logger.warning(f"Failed to get statement_transaction_id for expenses: {e}")

        return {
            "success": True,
            "expenses": [ExpenseSchema.model_validate(ex) for ex in expenses],
            "total": total_count
        }
    except Exception as e:
        logger.error(f"Failed to list expenses: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch expenses")


@router.get("/potential-duplicates")
async def get_potential_expense_duplicates(
    date_window_days: int = Query(3, ge=1, le=14),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return groups of likely duplicate expenses (same amount + vendor, date within ±window days).

    Groups with fewer than 2 members are excluded. Vendor comparison is done in
    Python after decryption because vendor uses EncryptedColumn.
    """
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    def _date(e: Expense):
        return e.expense_date.date() if hasattr(e.expense_date, 'date') else e.expense_date

    all_exp = (
        db.query(Expense)
        .filter(Expense.is_deleted == False)
        .order_by(Expense.expense_date, Expense.id)
        .all()
    )

    buckets: dict = defaultdict(list)
    for e in all_exp:
        try:
            if not _is_expense_duplicate_detection_eligible(e):
                continue
            vendor_key = (e.vendor or "").strip().lower()
            if not vendor_key:
                continue
            amount_key = round(float(e.amount or 0), 2)
            buckets[(amount_key, vendor_key)].append(e)
        except (TypeError, ValueError) as exc:
            logger.debug(f"Skipping expense {e.id} in duplicate scan: {exc}")

    groups = []
    for expenses_in_bucket in buckets.values():
        if len(expenses_in_bucket) < 2:
            continue
        expenses_sorted = sorted(expenses_in_bucket, key=_date)

        current_cluster = [expenses_sorted[0]]
        for e in expenses_sorted[1:]:
            if abs((_date(e) - _date(current_cluster[0])).days) <= date_window_days:
                current_cluster.append(e)
            else:
                if len(current_cluster) >= 2:
                    groups.append([
                        {
                            "id": ex.id,
                            "amount": ex.amount,
                            "expense_date": str(_date(ex)),
                            "vendor": ex.vendor,
                            "category": ex.category,
                            "status": ex.status,
                        }
                        for ex in current_cluster
                    ])
                current_cluster = [e]

        if len(current_cluster) >= 2:
            groups.append([
                {
                    "id": ex.id,
                    "amount": ex.amount,
                    "expense_date": str(_date(ex)),
                    "vendor": ex.vendor,
                    "category": ex.category,
                    "status": ex.status,
                }
                for ex in current_cluster
            ])

    return {"success": True, "duplicate_groups": groups, "count": len(groups)}


@router.get("/{expense_id:int}", response_model=ExpenseSchema)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    uvicorn_logger.info(f"Fetching expense {expense_id} for tenant {current_user.tenant_id}")

    from sqlalchemy.orm import joinedload
    from core.models.models_per_tenant import User
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

    if not expense.created_by and expense.created_by_user_id:
        try:
            creator = db.query(User).filter(User.id == expense.created_by_user_id).first()
            if creator:
                expense.created_by = creator
        except Exception as e:
            logger.warning(f"Failed to load creator for expense {expense_id}: {e}")

    _apply_creator_fallback([expense], master_db)

    try:
        txn = (
            db.query(BankStatementTransaction.id, BankStatementTransaction.statement_id)
            .filter(BankStatementTransaction.expense_id == expense_id)
            .first()
        )
        expense.__dict__['statement_transaction_id'] = txn[0] if txn else None
        expense.__dict__['statement_id'] = txn[1] if txn else None
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

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        currency_service = CurrencyService(db)
        currency_code = expense.currency or "USD"
        if not currency_service.validate_currency_code(currency_code):
            raise HTTPException(status_code=400, detail=f"Invalid currency code: {currency_code}")

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

        resolved_client_id = expense.client_id
        if expense.invoice_id is not None:
            inv = db.query(Invoice).filter(Invoice.id == expense.invoice_id).first()
            if not inv:
                raise HTTPException(status_code=400, detail=f"Invoice {expense.invoice_id} not found")
            if expense.client_id is not None and expense.client_id != inv.client_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"client_id {expense.client_id} does not match invoice's client (client_id={inv.client_id})",
                )
            resolved_client_id = inv.client_id
            uvicorn_logger.info(f"Creating expense linked to invoice_id={expense.invoice_id}")
        elif expense.client_id is not None:
            if not db.query(Client).filter(Client.id == expense.client_id).first():
                raise HTTPException(status_code=400, detail=f"Client {expense.client_id} not found")

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

        is_inventory_purchase = bool(getattr(expense, "is_inventory_purchase", False))
        inventory_items = getattr(expense, "inventory_items", None)

        is_inventory_consumption = bool(getattr(expense, "is_inventory_consumption", False))
        consumption_items = getattr(expense, "consumption_items", None)

        if is_inventory_purchase:
            if not inventory_items or len(inventory_items) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Inventory purchase must include at least one item"
                )

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

        if is_inventory_consumption:
            if not consumption_items or len(consumption_items) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Inventory consumption must include at least one item"
                )

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
            client_id=resolved_client_id,
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
            created_by_user_id=current_user.id,
            created_at=get_tenant_timezone_aware_datetime(db),
            updated_at=get_tenant_timezone_aware_datetime(db),
        )
        db.add(db_expense)
        db.flush()
        expense_id = db_expense.id
        uvicorn_logger.info(f"Expense flushed with ID: {expense_id}")

        db.commit()
        uvicorn_logger.info(f"Expense committed with ID: {expense_id}")

        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if not db_expense:
            uvicorn_logger.error(f"CRITICAL: Expense {expense_id} not found after commit!")
            raise HTTPException(status_code=500, detail=f"Expense was created but cannot be retrieved (ID: {expense_id})")

        uvicorn_logger.info(f"Successfully created and verified expense with ID: {db_expense.id}")

        if is_inventory_purchase and inventory_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_purchase(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for inventory purchase expense {db_expense.id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process stock movements for expense {db_expense.id}: {e}")

        if is_inventory_consumption and consumption_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_consumption(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for inventory consumption expense {db_expense.id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process consumption stock movements for expense {db_expense.id}: {e}")

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

        try:
            search_service.index_expense(db_expense)
        except Exception as e:
            uvicorn_logger.warning(f"Failed to index expense {db_expense.id} for search: {e}")

        try:
            from core.services.tenant_database_manager import tenant_db_manager
            from core.services.financial_event_processor import create_financial_event_processor

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

        potential_duplicate_id = None
        try:
            if _is_expense_duplicate_detection_eligible(db_expense):
                exp_date = db_expense.expense_date.date() if hasattr(db_expense.expense_date, 'date') else db_expense.expense_date
                dup_candidates = _find_potential_expense_duplicates(
                    db=db,
                    amount=float(db_expense.amount or 0),
                    expense_date=exp_date,
                    date_window_days=1,
                    exclude_id=db_expense.id,
                )
                if dup_candidates:
                    potential_duplicate_id = dup_candidates[0]["id"]
        except Exception as dup_err:
            uvicorn_logger.warning(f"Duplicate check failed for expense {db_expense.id}: {dup_err}")

        expense_schema = ExpenseSchema.model_validate(db_expense)
        expense_schema.potential_duplicate_id = potential_duplicate_id
        return expense_schema
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create expense: {e}")
        raise HTTPException(status_code=500, detail="Failed to create expense")


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


@router.post("/bulk-create", response_model=list)
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
                created_by_user_id=current_user.id,
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

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        if not payload.expense_ids:
            raise HTTPException(status_code=400, detail="No expense IDs provided")

        if len(payload.expense_ids) > 100:
            raise HTTPException(status_code=400, detail="Cannot delete more than 100 expenses at once")

        expenses_to_delete = db.query(Expense).filter(
            Expense.id.in_(payload.expense_ids),
            Expense.is_deleted == False
        ).all()

        if not expenses_to_delete:
            raise HTTPException(status_code=404, detail="No expenses found")

        non_admin = current_user.role != 'admin'
        for expense in expenses_to_delete:
            if non_admin and expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete expense #{expense.id} with status '{expense.status}'. Expense is in approval workflow."
                )

            if getattr(expense, "invoice_id", None) is not None:
                raise HTTPException(status_code=400, detail=f"Expense #{expense.id} is linked to an invoice and cannot be deleted")

        deleted_count = 0
        for expense in expenses_to_delete:
            try:
                if expense.receipt_path:
                    await delete_file_from_storage(expense.receipt_path, current_user.tenant_id, current_user.id, db)

                try:
                    attachments = db.query(ExpenseAttachment).filter(ExpenseAttachment.expense_id == expense.id).all()
                    for att in attachments:
                        if getattr(att, "file_path", None):
                            await delete_file_from_storage(att.file_path, current_user.tenant_id, current_user.id, db)
                except Exception as e:
                    logger.warning(f"Failed to enumerate attachments for deletion: {e}")

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

                try:
                    search_service.delete_document('expenses', str(expense.id))
                except Exception as e:
                    logger.warning(f"Failed to remove expense {expense.id} from search index: {e}")

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

                expense.is_deleted = True
                expense.deleted_at = get_tenant_timezone_aware_datetime(db)
                expense.deleted_by = current_user.id
                expense.updated_at = get_tenant_timezone_aware_datetime(db)
                deleted_count += 1

            except Exception as e:
                logger.error(f"Failed to delete expense {expense.id}: {e}")

        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{expense_id:int}", response_model=ExpenseSchema)
async def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "update expenses")

    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    uvicorn_logger.info(f"Updating expense {expense_id} with data: {expense.model_dump(exclude_unset=True)}")

    try:
        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == False
        ).first()
        if not db_expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        check_expense_modification_allowed(db_expense)

        previous_status = getattr(db_expense, "analysis_status", None)

        currency_service = CurrencyService(db)
        update_data = expense.model_dump(exclude_unset=True)

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

        if "invoice_id" in update_data and update_data["invoice_id"] is not None:
            inv = db.query(Invoice).filter(Invoice.id == int(update_data["invoice_id"])).first()
            if not inv:
                raise HTTPException(status_code=400, detail=f"Invoice {update_data['invoice_id']} not found")
            effective_client_id = update_data.get("client_id", db_expense.client_id)
            if effective_client_id is not None and effective_client_id != inv.client_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"client_id {effective_client_id} does not match invoice's client (client_id={inv.client_id})",
                )
            update_data["client_id"] = inv.client_id
        elif "client_id" in update_data and update_data["client_id"] is not None:
            if not db.query(Client).filter(Client.id == int(update_data["client_id"])).first():
                raise HTTPException(status_code=400, detail=f"Client {update_data['client_id']} not found")
            effective_invoice_id = update_data.get("invoice_id", db_expense.invoice_id)
            if effective_invoice_id is not None:
                inv = db.query(Invoice).filter(Invoice.id == effective_invoice_id).first()
                if inv and update_data["client_id"] != inv.client_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"client_id {update_data['client_id']} does not match the linked invoice's client (client_id={inv.client_id})",
                    )

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

        if "invoice_id" in update_data:
            uvicorn_logger.info(
                f"Updating expense {expense_id}: invoice_id {db_expense.invoice_id} -> {update_data['invoice_id']}"
            )

        if "is_inventory_purchase" in update_data or "inventory_items" in update_data:
            is_inventory_purchase = update_data.get("is_inventory_purchase", db_expense.is_inventory_purchase)
            inventory_items = update_data.get("inventory_items", db_expense.inventory_items)

            if is_inventory_purchase and inventory_items:
                if not inventory_items or len(inventory_items) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Inventory purchase must include at least one item"
                    )

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

        if "is_inventory_consumption" in update_data or "consumption_items" in update_data:
            is_inventory_consumption = update_data.get("is_inventory_consumption", db_expense.is_inventory_consumption)
            consumption_items = update_data.get("consumption_items", db_expense.consumption_items)

            if is_inventory_consumption and consumption_items:
                if not consumption_items or len(consumption_items) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Inventory consumption must include at least one item"
                    )

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

                    if inventory_item.track_stock and inventory_item.current_stock < quantity:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Insufficient stock for {inventory_item.name}. Available: {inventory_item.current_stock}, Requested: {quantity}"
                        )

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
        db_expense.manual_override = True
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

        if ("is_inventory_purchase" in update_data or "inventory_items" in update_data) and db_expense.is_inventory_purchase and db_expense.inventory_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_purchase(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for updated expense {expense_id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process stock movements for updated expense {expense_id}: {e}")

        if ("is_inventory_consumption" in update_data or "consumption_items" in update_data) and db_expense.is_inventory_consumption and db_expense.consumption_items:
            try:
                from core.services.inventory_integration_service import InventoryIntegrationService
                integration_service = InventoryIntegrationService(db)

                movements = integration_service.process_expense_inventory_consumption(db_expense, current_user.id)
                if movements:
                    uvicorn_logger.info(f"Processed {len(movements)} stock movements for updated consumption expense {expense_id}")

            except Exception as e:
                uvicorn_logger.error(f"Failed to process consumption stock movements for updated expense {expense_id}: {e}")

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


@router.delete("/{expense_id:int}", response_model=RecycleBinExpenseResponse)
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Move an expense to the recycle bin (soft delete)"""
    require_non_viewer(current_user, "delete expenses")

    import traceback
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        uvicorn_logger.info(f"Attempting to delete expense {expense_id} for tenant {current_user.tenant_id}")

        db_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == False
        ).first()

        if not db_expense:
            try:
                db.expire_all()
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

        if current_user.role != 'admin' and db_expense.status in [ExpenseStatus.PENDING_APPROVAL.value, ExpenseStatus.APPROVED.value]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete expense with status '{db_expense.status}'. Expense is in approval workflow."
            )

        if getattr(db_expense, "invoice_id", None) is not None:
            raise HTTPException(status_code=400, detail=EXPENSE_LINKED_TO_INVOICE)

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

        db_expense.is_deleted = True
        db_expense.deleted_at = get_tenant_timezone_aware_datetime(db)
        db_expense.deleted_by = current_user.id
        db_expense.updated_at = get_tenant_timezone_aware_datetime(db)

        db.commit()
        uvicorn_logger.info(f"Successfully deleted expense {expense_id}")

        db.expire_all()
        verification_expense = db.query(Expense).filter(
            Expense.id == expense_id,
            Expense.is_deleted == True
        ).first()

        if not verification_expense:
            uvicorn_logger.error(f"CRITICAL: Expense {expense_id} deletion verification failed - expense not marked as deleted!")
            raise HTTPException(status_code=500, detail=f"Expense deletion verification failed (ID: {expense_id})")

        uvicorn_logger.info(f"Successfully verified deletion of expense {expense_id}")

        try:
            search_service.delete_document('expenses', str(expense_id))
        except Exception as e:
            logger.warning(f"Failed to remove expense {expense_id} from search index: {e}")

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

        from core.schemas.expense import RecycleBinExpenseResponse
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
