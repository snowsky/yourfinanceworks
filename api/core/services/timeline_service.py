"""
Client Activity Timeline Service

Aggregates invoices, payments, expenses (inferred via vendor name),
bank statement transactions (via invoice/expense links), and client notes
into a unified chronological timeline.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models.models_per_tenant import (
    Client,
    ClientNote,
    Invoice,
    Payment,
    Expense,
    BankStatement,
    BankStatementTransaction,
)
from core.schemas.timeline import TimelineEvent

logger = logging.getLogger(__name__)


def _format_amount(amount: Optional[float], currency: Optional[str] = None) -> str:
    """Format an amount with currency symbol for display."""
    if amount is None:
        return ""
    curr = currency or "USD"
    return f"{curr} {amount:,.2f}"


def _iso_date(dt: object) -> str:
    """Convert a date/datetime to ISO 8601 string."""
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    # date object
    return dt.isoformat()


def _get_invoice_events(
    db: Session,
    client_id: int,
    allowed_types: Optional[Set[str]],
    allowed_sources: Optional[Set[str]],
) -> List[TimelineEvent]:
    """Fetch invoice timeline events for a client."""
    if allowed_types and "invoice" not in allowed_types:
        return []
    if allowed_sources and "invoice" not in allowed_sources:
        return []

    invoices = (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id, Invoice.is_deleted == False)
        .all()
    )

    events: List[TimelineEvent] = []
    for inv in invoices:
        due_str = ""
        if inv.due_date:
            due_str = f" due on {inv.due_date.strftime('%Y-%m-%d') if hasattr(inv.due_date, 'strftime') else str(inv.due_date)}"

        events.append(TimelineEvent(
            id=f"invoice-{inv.id}",
            event_type="invoice",
            title=f"Invoice #{inv.number}",
            description=f"{_format_amount(inv.amount, inv.currency)}{due_str}",
            amount=inv.amount,
            currency=inv.currency,
            status=inv.status,
            date=_iso_date(inv.created_at),
            source="invoice",
            metadata={
                "invoice_id": inv.id,
                "invoice_number": inv.number,
                "due_date": _iso_date(inv.due_date),
            },
        ))
    return events


def _get_payment_events(
    db: Session,
    client_id: int,
    allowed_types: Optional[Set[str]],
    allowed_sources: Optional[Set[str]],
) -> List[TimelineEvent]:
    """Fetch payment timeline events for a client (via invoice→client link)."""
    if allowed_types and "payment" not in allowed_types:
        return []
    if allowed_sources and "invoice" not in allowed_sources:
        return []

    payments = (
        db.query(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Invoice.client_id == client_id, Invoice.is_deleted == False)
        .all()
    )

    events: List[TimelineEvent] = []
    for pay in payments:
        inv_number = pay.invoice.number if pay.invoice else "N/A"
        events.append(TimelineEvent(
            id=f"payment-{pay.id}",
            event_type="payment",
            title=f"Payment received for #{inv_number}",
            description=f"{_format_amount(pay.amount, pay.currency)} via {pay.payment_method or 'N/A'}",
            amount=pay.amount,
            currency=pay.currency,
            status="completed",
            date=_iso_date(pay.payment_date),
            source="invoice",
            metadata={
                "payment_id": pay.id,
                "invoice_id": pay.invoice_id,
                "invoice_number": inv_number,
                "payment_method": pay.payment_method,
                "reference_number": pay.reference_number,
            },
        ))
    return events


def _get_expense_events(
    db: Session,
    client_name: str,
    allowed_types: Optional[Set[str]],
    allowed_sources: Optional[Set[str]],
) -> List[TimelineEvent]:
    """
    Fetch expense timeline events inferred by matching the expense vendor
    field to the client name (case-insensitive).
    These are flagged with matched=true since there is no direct FK.
    """
    if allowed_types and "expense" not in allowed_types:
        return []
    if allowed_sources and "expense" not in allowed_sources:
        return []

    # Inferred match: expense.vendor matches client.name (case-insensitive)
    expenses = (
        db.query(Expense)
        .filter(
            func.lower(Expense.vendor) == func.lower(client_name),
            Expense.is_deleted == False,
        )
        .all()
    )

    events: List[TimelineEvent] = []
    for exp in expenses:
        events.append(TimelineEvent(
            id=f"expense-{exp.id}",
            event_type="expense",
            title=f"Expense (matched): {exp.category or 'Uncategorized'}",
            description=_format_amount(exp.amount, exp.currency),
            amount=exp.amount,
            currency=exp.currency,
            status=exp.status,
            date=_iso_date(exp.expense_date),
            source="expense",
            metadata={
                "expense_id": exp.id,
                "category": exp.category,
                "vendor": exp.vendor,
                "matched": True,
            },
        ))
    return events


def _get_bank_transaction_events(
    db: Session,
    client_id: int,
    client_name: str,
    allowed_types: Optional[Set[str]],
    allowed_sources: Optional[Set[str]],
) -> List[TimelineEvent]:
    """
    Fetch bank statement transaction events associated with a client.
    Association is inferred via:
      1. Transaction linked to one of the client's invoices (invoice_id FK)
      2. Transaction linked to a matched expense (expense_id FK) where
         expense.vendor matches client name
    """
    if allowed_types and "bank_transaction" not in allowed_types:
        return []
    if allowed_sources and "bank_statement" not in allowed_sources:
        return []

    # 1. Transactions linked to the client's invoices
    client_invoice_ids = (
        db.query(Invoice.id)
        .filter(Invoice.client_id == client_id, Invoice.is_deleted == False)
        .all()
    )
    invoice_id_set = {row[0] for row in client_invoice_ids}

    # 2. Transactions linked to matched expenses (vendor = client name)
    matched_expense_ids = (
        db.query(Expense.id)
        .filter(
            func.lower(Expense.vendor) == func.lower(client_name),
            Expense.is_deleted == False,
        )
        .all()
    )
    expense_id_set = {row[0] for row in matched_expense_ids}

    if not invoice_id_set and not expense_id_set:
        return []

    # Build OR filter
    filters = []
    if invoice_id_set:
        filters.append(BankStatementTransaction.invoice_id.in_(invoice_id_set))
    if expense_id_set:
        filters.append(BankStatementTransaction.expense_id.in_(expense_id_set))

    from sqlalchemy import or_
    transactions = (
        db.query(BankStatementTransaction)
        .filter(or_(*filters))
        .all()
    )

    events: List[TimelineEvent] = []
    for txn in transactions:
        # Determine if this is a direct (via invoice) or inferred (via expense) match
        is_direct = txn.invoice_id is not None and txn.invoice_id in invoice_id_set
        is_matched = not is_direct

        prefix = "Bank Transaction (matched): " if is_matched else "Bank Transaction: "
        events.append(TimelineEvent(
            id=f"bank_transaction-{txn.id}",
            event_type="bank_transaction",
            title=f"{prefix}{txn.description[:60]}",
            description=f"{_format_amount(txn.amount)} — {txn.transaction_type}",
            amount=txn.amount,
            currency=None,
            status="reconciled" if txn.invoice_id or txn.expense_id else "pending",
            date=_iso_date(txn.date),
            source="bank_statement",
            metadata={
                "transaction_id": txn.id,
                "statement_id": txn.statement_id,
                "transaction_type": txn.transaction_type,
                "balance": txn.balance,
                "invoice_id": txn.invoice_id,
                "expense_id": txn.expense_id,
                "matched": is_matched,
            },
        ))
    return events


def _get_note_events(
    db: Session,
    client_id: int,
    allowed_types: Optional[Set[str]],
    allowed_sources: Optional[Set[str]],
) -> List[TimelineEvent]:
    """Fetch client note timeline events."""
    if allowed_types and "note" not in allowed_types:
        return []
    if allowed_sources and "note" not in allowed_sources:
        return []

    notes = (
        db.query(ClientNote)
        .filter(ClientNote.client_id == client_id)
        .all()
    )

    events: List[TimelineEvent] = []
    for note in notes:
        preview = (note.note or "")[:120]
        if len(note.note or "") > 120:
            preview += "…"
        events.append(TimelineEvent(
            id=f"note-{note.id}",
            event_type="note",
            title="Client Note",
            description=preview,
            amount=None,
            currency=None,
            status=None,
            date=_iso_date(note.created_at),
            source="note",
            metadata={
                "note_id": note.id,
                "user_id": note.user_id,
                "full_note": note.note,
            },
        ))
    return events


def get_client_timeline(
    db: Session,
    client_id: int,
    page: int = 1,
    page_size: int = 20,
    event_types: Optional[str] = None,
    source_filter: Optional[str] = None,
) -> dict:
    """
    Aggregate all timeline events for a client and return a paginated response.

    Args:
        db: Tenant database session.
        client_id: The client to build the timeline for.
        page: 1-indexed page number.
        page_size: Number of events per page.
        event_types: Comma-separated event type filter (e.g. "invoice,note").
        source_filter: Comma-separated source filter (e.g. "invoice,bank_statement").

    Returns:
        A dict matching the TimelineResponse schema.
    """
    # Validate client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        return None  # Caller should raise 404

    client_name: str = client.name or ""

    # Parse filters
    allowed_types: Optional[Set[str]] = None
    if event_types:
        allowed_types = {t.strip() for t in event_types.split(",") if t.strip()}

    allowed_sources: Optional[Set[str]] = None
    if source_filter:
        allowed_sources = {s.strip() for s in source_filter.split(",") if s.strip()}

    # Collect all events
    all_events: List[TimelineEvent] = []
    all_events.extend(_get_invoice_events(db, client_id, allowed_types, allowed_sources))
    all_events.extend(_get_payment_events(db, client_id, allowed_types, allowed_sources))
    all_events.extend(_get_expense_events(db, client_name, allowed_types, allowed_sources))
    all_events.extend(_get_bank_transaction_events(db, client_id, client_name, allowed_types, allowed_sources))
    all_events.extend(_get_note_events(db, client_id, allowed_types, allowed_sources))

    # Sort by date descending
    all_events.sort(key=lambda e: e.date, reverse=True)

    total = len(all_events)
    start = (page - 1) * page_size
    end = start + page_size
    page_events = all_events[start:end]

    return {
        "events": page_events,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }
