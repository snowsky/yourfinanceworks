"""Server-side dashboard statistics aggregation.

Replaces the frontend's `dashboardApi.getStats()` which fetched up to 1000
clients + 1000 invoices + all expenses and aggregated in the browser. This
computes the identical `DashboardStats` shape server-side so the client pulls a
small summary instead of thousands of rows.

`_aggregate_stats` is a pure function that mirrors the original TypeScript logic
exactly (filters, currency grouping, month-over-month trends, payment-quality
metrics) and is unit-tested without a DB. `get_dashboard_stats` is the thin DB
layer that feeds it (paid_amount per invoice = SUM of its payments, matching how
the invoice read-model derives it; invoice "date" == created_at).

Month boundaries for trends use UTC (the original used each user's browser
timezone, which was inconsistent between users).
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models.models_per_tenant import Client, Expense, Invoice, Payment

_PAID_STATUSES = ("paid", "partially_paid")
_PENDING_STATUSES = ("pending", "overdue", "partially_paid")
_INCOME_PAYERS = ("client", "")  # payer must be 'client' or empty to count as income


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize to tz-aware UTC.

    Invoice.due_date is stored tz-naive (DateTime) while updated_at/created_at are
    tz-aware (DateTime(timezone=True)); comparing the two raises TypeError. Coerce
    everything to UTC before any comparison/subtraction.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _js_round(x: float) -> int:
    """Match JS Math.round (round half toward +inf), not Python's banker's rounding.

    Math.round(2.5) == 3 and Math.round(-1.5) == -1, both equal floor(x + 0.5).
    """
    return math.floor(x + 0.5)


def _trend(value: float) -> Dict[str, Any]:
    """Mirror: { value: Math.round(trend*10)/10, isPositive: trend >= 0 }."""
    return {"value": _js_round(value * 10) / 10, "isPositive": value >= 0}


def _pct_change(current: float, previous: float) -> float:
    """Mirror calculatePercentageChange: 0-previous guard, else relative change %."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100.0


def _in_month(dt: Optional[datetime], month: int, year: int) -> bool:
    return dt is not None and dt.month == month and dt.year == year


def _aggregate_stats(
    invoices: List[Dict[str, Any]],
    expenses: List[Dict[str, Any]],
    total_clients: int,
    now: datetime,
) -> Dict[str, Any]:
    """Pure aggregation mirroring the original client-side getStats().

    invoice dicts: amount, paid_amount, currency, status, payer, created_at,
                   updated_at, due_date, client_id
    expense dicts: currency, total_amount, amount
    """
    total_income: Dict[str, float] = {}
    pending_invoices: Dict[str, float] = {}
    total_expenses: Dict[str, float] = {}

    for inv in invoices:
        currency = inv.get("currency") or "USD"
        payer = (inv.get("payer") or "").lower()
        status = inv.get("status")
        amount = inv.get("amount") or 0
        paid = inv.get("paid_amount") or 0

        if status in _PAID_STATUSES and payer in _INCOME_PAYERS:
            total_income[currency] = total_income.get(currency, 0) + paid

        if status in _PENDING_STATUSES:
            outstanding = amount - paid
            if outstanding > 0:
                pending_invoices[currency] = pending_invoices.get(currency, 0) + outstanding

    for exp in expenses:
        currency = exp.get("currency") or "USD"
        # JS `expense.total_amount || expense.amount || 0` — 0/None falls through.
        amount = exp.get("total_amount") or exp.get("amount") or 0
        total_expenses[currency] = total_expenses.get(currency, 0) + amount

    invoices_paid = sum(1 for i in invoices if i.get("status") == "paid")
    invoices_pending = sum(1 for i in invoices if i.get("status") == "pending")
    invoices_overdue = sum(1 for i in invoices if i.get("status") == "overdue")

    # --- month-over-month trends (UTC) ---
    cur_m, cur_y = now.month, now.year
    prev_m, prev_y = (12, cur_y - 1) if cur_m == 1 else (cur_m - 1, cur_y)

    def monthly_income(m: int, y: int) -> float:
        return sum(
            (i.get("paid_amount") or 0)
            for i in invoices
            if _in_month(i.get("created_at"), m, y) and i.get("status") in _PAID_STATUSES
        )

    def monthly_pending(m: int, y: int) -> float:
        total = 0.0
        for i in invoices:
            if _in_month(i.get("created_at"), m, y) and i.get("status") in _PENDING_STATUSES:
                outstanding = (i.get("amount") or 0) - (i.get("paid_amount") or 0)
                if outstanding > 0:
                    total += outstanding
        return total

    def monthly_clients(m: int, y: int) -> int:
        return len(
            {i.get("client_id") for i in invoices if _in_month(i.get("created_at"), m, y)}
        )

    def monthly_overdue(m: int, y: int) -> int:
        return sum(
            1
            for i in invoices
            if _in_month(i.get("created_at"), m, y) and i.get("status") == "overdue"
        )

    income_trend = _pct_change(monthly_income(cur_m, cur_y), monthly_income(prev_m, prev_y))
    pending_trend = _pct_change(monthly_pending(cur_m, cur_y), monthly_pending(prev_m, prev_y))
    clients_trend = _pct_change(monthly_clients(cur_m, cur_y), monthly_clients(prev_m, prev_y))
    overdue_trend = _pct_change(monthly_overdue(cur_m, cur_y), monthly_overdue(prev_m, prev_y))

    # --- payment-quality metrics ---
    on_time_payment_rate = 0
    average_payment_time = 0
    overdue_rate = 0

    if invoices:
        paid_invoices = [i for i in invoices if i.get("status") in _PAID_STATUSES]
        overdue_invoices = [i for i in invoices if i.get("status") == "overdue"]

        if paid_invoices:
            on_time = [
                i
                for i in paid_invoices
                if i.get("due_date")
                and i.get("updated_at")
                and _as_utc(i["updated_at"]) <= _as_utc(i["due_date"])
            ]
            on_time_payment_rate = _js_round(len(on_time) / len(paid_invoices) * 100)

            total_days = 0
            for i in paid_invoices:
                created = _as_utc(i.get("created_at"))  # invoice.date == created_at
                paid_at = _as_utc(i.get("updated_at"))
                if created and paid_at:
                    total_days += math.ceil((paid_at - created).total_seconds() / 86400)
            average_payment_time = _js_round(total_days / len(paid_invoices))

        overdue_rate = _js_round(len(overdue_invoices) / len(invoices) * 100)

    return {
        "totalIncome": total_income,
        "pendingInvoices": pending_invoices,
        "totalExpenses": total_expenses,
        "totalClients": total_clients,
        "invoicesPaid": invoices_paid,
        "invoicesPending": invoices_pending,
        "invoicesOverdue": invoices_overdue,
        "paymentTrends": {
            "onTimePaymentRate": on_time_payment_rate,
            "averagePaymentTime": average_payment_time,
            "overdueRate": overdue_rate,
        },
        "trends": {
            "income": _trend(income_trend),
            "pending": _trend(pending_trend),
            "clients": _trend(clients_trend),
            "overdue": _trend(overdue_trend),
        },
    }


def get_dashboard_stats(db: Session) -> Dict[str, Any]:
    """Compute DashboardStats for the current tenant DB session.

    Mirrors what the dashboard's list calls returned (non-deleted invoices/
    expenses) but aggregates ALL rows server-side — it intentionally drops the
    client-side fetch caps (invoices were capped at 1000, expenses at the list
    endpoint's default of 100), which silently under-counted tenants that
    exceeded them. For tenants under those limits the numbers are identical.
    """
    # paid_amount per invoice = SUM of its payments (how the read-model derives it)
    paid_subq = (
        db.query(
            Payment.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("paid"),
        )
        .group_by(Payment.invoice_id)
        .subquery()
    )

    invoice_rows = (
        db.query(
            Invoice.amount,
            Invoice.currency,
            Invoice.status,
            Invoice.payer,
            Invoice.created_at,
            Invoice.updated_at,
            Invoice.due_date,
            Invoice.client_id,
            func.coalesce(paid_subq.c.paid, 0.0).label("paid_amount"),
        )
        .outerjoin(paid_subq, paid_subq.c.invoice_id == Invoice.id)
        .filter(Invoice.is_deleted == False)  # noqa: E712
        .all()
    )
    invoices = [
        {
            "amount": r.amount,
            "currency": r.currency,
            "status": r.status,
            "payer": r.payer,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "due_date": r.due_date,
            "client_id": r.client_id,
            "paid_amount": r.paid_amount,
        }
        for r in invoice_rows
    ]

    expense_rows = (
        db.query(Expense.currency, Expense.total_amount, Expense.amount)
        .filter(Expense.is_deleted == False)  # noqa: E712
        .all()
    )
    expenses = [
        {"currency": e.currency, "total_amount": e.total_amount, "amount": e.amount}
        for e in expense_rows
    ]

    total_clients = db.query(func.count(Client.id)).scalar() or 0

    return _aggregate_stats(invoices, expenses, total_clients, datetime.now(timezone.utc))
