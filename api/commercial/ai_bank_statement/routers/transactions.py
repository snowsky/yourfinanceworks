"""Transaction CRUD and cross-statement transaction link endpoints."""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_non_viewer
from core.utils.feature_gate import require_feature
from core.models.models_per_tenant import BankStatement, BankStatementTransaction
from core.schemas.bank_statement import TransactionLinkCreate
from core.services import transaction_link_service
from core.utils.audit import log_audit_event
from ._shared import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Duplicate Detection ───────────────────────────────────────────────────────


@router.get("/transactions/duplicates", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def get_duplicate_transaction_groups(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return groups of cross-statement transactions that appear to be duplicates.

    A group contains transactions with identical (date, description, amount) across
    at least two different non-deleted statements that are NOT already linked via
    a TransactionLink.
    """
    tenant_id = get_tenant_id()
    groups = transaction_link_service.find_cross_statement_duplicate_groups(
        db=db, tenant_id=tenant_id
    )
    return {"success": True, "duplicate_groups": groups, "count": len(groups)}


# ── Transaction Link Endpoints ────────────────────────────────────────────────


@router.post("/transactions/links", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def create_transaction_link(
    payload: TransactionLinkCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Link two transactions from different statements (e.g., inter-account transfer or FX conversion)."""
    require_non_viewer(current_user, "link transactions")
    tenant_id = get_tenant_id()

    link = transaction_link_service.create_link(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        txn_a_id=payload.transaction_a_id,
        txn_b_id=payload.transaction_b_id,
        link_type=payload.link_type,
        notes=payload.notes,
    )

    # Build response with enriched data
    enriched = transaction_link_service.enrich_transactions_with_links(
        db, [payload.transaction_a_id, payload.transaction_b_id]
    )

    log_audit_event(db, current_user.id, current_user.email, "transaction_link_created",
        "transaction_link", resource_id=str(link.id),
        details={"transaction_a_id": link.transaction_a_id, "transaction_b_id": link.transaction_b_id, "link_type": link.link_type})

    return {
        "success": True,
        "link": {
            "id": link.id,
            "link_type": link.link_type,
            "notes": link.notes,
            "created_at": link.created_at.isoformat() if link.created_at else None,
            "linked_for_a": enriched.get(payload.transaction_a_id),
            "linked_for_b": enriched.get(payload.transaction_b_id),
        }
    }


@router.delete("/transactions/links/{link_id}", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def delete_transaction_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Remove a cross-statement transaction link."""
    require_non_viewer(current_user, "unlink transactions")
    tenant_id = get_tenant_id()

    transaction_link_service.delete_link(db=db, tenant_id=tenant_id, link_id=link_id)

    log_audit_event(db, current_user.id, current_user.email, "transaction_link_deleted",
        "transaction_link", resource_id=str(link_id))

    return {"success": True}


# ── Per-Statement Transaction Endpoints ───────────────────────────────────────


@router.patch("/{statement_id}/transactions/{transaction_id}", response_model=Dict[str, Any])
async def patch_statement_transaction(
    statement_id: int,
    transaction_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "edit bank statement transaction")
    tenant_id = get_tenant_id()

    txn = (
        db.query(BankStatementTransaction)
        .join(BankStatement)
        .filter(
            BankStatementTransaction.id == transaction_id,
            BankStatementTransaction.statement_id == statement_id,
            BankStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    allowed_fields = {"expense_id", "invoice_id", "category", "description", "amount", "balance", "transaction_type", "date", "notes"}
    for field, value in payload.items():
        if field not in allowed_fields:
            continue
        if field in ("expense_id", "invoice_id"):
            try:
                setattr(txn, field, int(value) if value not in (None, "") else None)
            except Exception:
                setattr(txn, field, None)
        else:
            setattr(txn, field, value)

    db.commit()
    return {"success": True}


@router.delete("/{statement_id}/transactions/{transaction_id}", response_model=Dict[str, Any])
async def delete_statement_transaction(
    statement_id: int,
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_non_viewer(current_user, "delete bank statement transaction")
    tenant_id = get_tenant_id()

    txn = (
        db.query(BankStatementTransaction)
        .join(BankStatement)
        .filter(
            BankStatementTransaction.id == transaction_id,
            BankStatementTransaction.statement_id == statement_id,
            BankStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(txn)
    db.flush()

    statement = db.query(BankStatement).filter(BankStatement.id == statement_id).first()
    if statement:
        statement.extracted_count = db.query(BankStatementTransaction).filter(
            BankStatementTransaction.statement_id == statement_id
        ).count()

    db.commit()
    log_audit_event(db, current_user.id, current_user.email, "transaction_deleted",
                    f"Deleted transaction {transaction_id} from statement {statement_id}")
    return {"success": True}


@router.put("/{statement_id}/transactions", response_model=Dict[str, Any])
async def replace_statement_transactions(
    statement_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
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

    items = payload.get("transactions", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="transactions must be an array")

    try:
        # Snapshot previous transactions for audit summary
        prev_rows = (
            db.query(BankStatementTransaction)
            .filter(BankStatementTransaction.statement_id == s.id)
            .order_by(
                BankStatementTransaction.date.asc(), BankStatementTransaction.id.asc()
            )
            .all()
        )
        prev_count = len(prev_rows)
        prev_ids = [
            getattr(r, "id", None)
            for r in prev_rows
            if getattr(r, "id", None) is not None
        ]
        # Replace transactions: simple strategy but preserve invoice links if provided
        db.query(BankStatementTransaction).filter(
            BankStatementTransaction.statement_id == s.id
        ).delete()

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
                transaction_type=(
                    t.get("transaction_type")
                    if t.get("transaction_type") in ("debit", "credit")
                    else ("debit" if float(t.get("amount", 0)) < 0 else "credit")
                ),
                balance=(
                    float(t["balance"]) if t.get("balance") not in (None, "") else None
                ),
                category=t.get("category") or None,
                notes=t.get("notes", None),
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
        raise HTTPException(
            status_code=500, detail=f"Failed to update transactions: {e}"
        )
