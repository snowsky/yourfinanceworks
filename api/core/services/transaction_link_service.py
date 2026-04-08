"""Service layer for cross-statement transaction linking."""
from typing import Optional, List, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.models.models_per_tenant import TransactionLink, BankStatementTransaction, BankStatement


def create_link(
    db: Session,
    tenant_id: int,
    user_id: Optional[int],
    txn_a_id: int,
    txn_b_id: int,
    link_type: str = "transfer",
    notes: Optional[str] = None,
) -> TransactionLink:
    """Create a link between two transactions.

    Normalizes the pair (a_id = min, b_id = max) to ensure the UniqueConstraint works correctly.
    Validates that both transactions belong to the tenant and that neither is already linked.
    """
    if txn_a_id == txn_b_id:
        raise HTTPException(status_code=400, detail="Cannot link a transaction to itself")

    # Normalize pair
    a_id = min(txn_a_id, txn_b_id)
    b_id = max(txn_a_id, txn_b_id)

    # Validate both transactions belong to this tenant
    txn_a = (
        db.query(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.id)
        .filter(BankStatementTransaction.id == a_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not txn_a:
        raise HTTPException(status_code=404, detail=f"Transaction {a_id} not found")

    txn_b = (
        db.query(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.id)
        .filter(BankStatementTransaction.id == b_id, BankStatement.tenant_id == tenant_id)
        .first()
    )
    if not txn_b:
        raise HTTPException(status_code=404, detail=f"Transaction {b_id} not found")

    # Check neither transaction already has a link
    existing = (
        db.query(TransactionLink)
        .filter(
            or_(
                TransactionLink.transaction_a_id == a_id,
                TransactionLink.transaction_b_id == a_id,
                TransactionLink.transaction_a_id == b_id,
                TransactionLink.transaction_b_id == b_id,
            )
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="One or both transactions are already linked to another transaction")

    link = TransactionLink(
        transaction_a_id=a_id,
        transaction_b_id=b_id,
        link_type=link_type,
        notes=notes,
        created_by_user_id=user_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def delete_link(
    db: Session,
    tenant_id: int,
    link_id: int,
) -> None:
    """Delete a transaction link. Validates that the link belongs to this tenant."""
    link = db.query(TransactionLink).filter(TransactionLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Transaction link not found")

    # Validate ownership via either transaction
    txn = (
        db.query(BankStatementTransaction)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.id)
        .filter(
            BankStatementTransaction.id == link.transaction_a_id,
            BankStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction link not found")

    db.delete(link)
    db.commit()


def enrich_transactions_with_links(
    db: Session,
    transaction_ids: List[int],
) -> Dict[int, dict]:
    """Batch-fetch all links for a set of transaction IDs.

    Returns a dict keyed by transaction_id, where each value is a dict with
    the linked_transfer info from that transaction's perspective.
    """
    if not transaction_ids:
        return {}

    links = (
        db.query(TransactionLink)
        .filter(
            or_(
                TransactionLink.transaction_a_id.in_(transaction_ids),
                TransactionLink.transaction_b_id.in_(transaction_ids),
            )
        )
        .all()
    )

    if not links:
        return {}

    # Fetch the "other side" transactions with their statements in one query
    other_txn_ids = set()
    for link in links:
        if link.transaction_a_id in transaction_ids:
            other_txn_ids.add(link.transaction_b_id)
        if link.transaction_b_id in transaction_ids:
            other_txn_ids.add(link.transaction_a_id)

    other_txns = (
        db.query(BankStatementTransaction, BankStatement)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.id)
        .filter(BankStatementTransaction.id.in_(other_txn_ids))
        .all()
    )
    txn_to_statement = {txn.id: stmt for txn, stmt in other_txns}

    result: Dict[int, dict] = {}
    for link in links:
        # Determine which side is the "caller" and which is "other"
        pairs = []
        if link.transaction_a_id in transaction_ids:
            pairs.append((link.transaction_a_id, link.transaction_b_id))
        if link.transaction_b_id in transaction_ids:
            pairs.append((link.transaction_b_id, link.transaction_a_id))

        for caller_id, other_id in pairs:
            stmt = txn_to_statement.get(other_id)
            if stmt:
                result[caller_id] = {
                    "id": link.id,
                    "link_type": link.link_type,
                    "notes": link.notes,
                    "linked_transaction_id": other_id,
                    "linked_statement_id": stmt.id,
                    "linked_statement_filename": stmt.original_filename,
                    "created_at": link.created_at.isoformat() if link.created_at else None,
                }

    return result


def find_cross_statement_duplicate_groups(db: Session, tenant_id: int) -> List[List[Dict]]:
    """Return groups of transactions sharing (date, description, round(amount, 2))
    across 2+ different non-deleted statements, excluding already-linked pairs.

    Each group is a list of transaction dicts with statement info.
    """
    from collections import defaultdict

    rows = (
        db.query(BankStatementTransaction, BankStatement)
        .join(BankStatement, BankStatementTransaction.statement_id == BankStatement.id)
        .filter(BankStatement.tenant_id == tenant_id, BankStatement.is_deleted == False)
        .all()
    )

    buckets: Dict[tuple, List[Dict]] = defaultdict(list)
    for txn, stmt in rows:
        key = (str(txn.date), (txn.description or "").strip().lower(), round(float(txn.amount), 2))
        buckets[key].append({
            "id": txn.id,
            "statement_id": txn.statement_id,
            "statement_filename": stmt.original_filename,
            "date": str(txn.date),
            "description": txn.description,
            "amount": txn.amount,
            "transaction_type": txn.transaction_type,
        })

    candidate_groups = [g for g in buckets.values() if len({e["statement_id"] for e in g}) >= 2]
    if not candidate_groups:
        return []

    all_ids = {e["id"] for g in candidate_groups for e in g}
    links = db.query(TransactionLink).filter(
        or_(
            TransactionLink.transaction_a_id.in_(all_ids),
            TransactionLink.transaction_b_id.in_(all_ids),
        )
    ).all()
    linked_pairs = {
        (min(lnk.transaction_a_id, lnk.transaction_b_id), max(lnk.transaction_a_id, lnk.transaction_b_id))
        for lnk in links
    }

    def all_pairs_linked(group: List[Dict]) -> bool:
        ids = [e["id"] for e in group]
        return all(
            (min(ids[i], ids[j]), max(ids[i], ids[j])) in linked_pairs
            for i in range(len(ids))
            for j in range(i + 1, len(ids))
        )

    return [g for g in candidate_groups if not all_pairs_linked(g)]
