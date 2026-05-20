"""Reference builders for cash flow entries.

Pure helpers that convert ORM rows into ``CashFlowReference`` objects used by
:mod:`cashflow_service` to attach source records to projected entries. Kept
separate so the main service module stays focused on the forecast pipeline.
"""

from core.models.models_per_tenant import (
    BankStatementTransaction,
    Expense,
    Invoice,
    Payment,
)
from core.schemas.cashflow import CashFlowReference


def invoice_reference(invoice: Invoice) -> CashFlowReference:
    return CashFlowReference(
        type="invoice",
        id=invoice.id,
        label=f"Invoice {invoice.number}",
        url=f"/invoices/view/{invoice.id}",
    )


def expense_reference(expense: Expense) -> CashFlowReference:
    vendor = (expense.vendor or "").strip() or "Unknown vendor"
    category = (expense.category or "").strip() or "Expense"
    return CashFlowReference(
        type="expense",
        id=expense.id,
        label=f"{category}: {vendor}",
        url=f"/expenses/view/{expense.id}",
    )


def payment_reference(payment: Payment) -> CashFlowReference:
    invoice = getattr(payment, "invoice", None)
    if invoice:
        return CashFlowReference(
            type="invoice",
            id=invoice.id,
            label=f"Payment for invoice {invoice.number}",
            url=f"/invoices/view/{invoice.id}",
        )

    return CashFlowReference(
        type="payment",
        id=payment.id,
        label=f"Payment #{payment.id}",
        url="/payments",
    )


def bank_statement_transaction_reference(
    transaction: BankStatementTransaction,
) -> CashFlowReference:
    statement = getattr(transaction, "statement", None)
    date_label = transaction.date.isoformat() if transaction.date else "unknown date"
    description = (transaction.description or "").strip() or "Bank transaction"
    statement_label = (
        getattr(statement, "original_filename", None)
        or f"Statement #{transaction.statement_id}"
    )
    return CashFlowReference(
        type="bank_statement_transaction",
        id=transaction.id,
        label=f"{statement_label} - {date_label} - {description[:60]}",
        url=f"/statements?id={transaction.statement_id}&txn={transaction.id}",
    )
