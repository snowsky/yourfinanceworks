"""
Accountant-oriented tax export service.

Provides two concrete export formats for tax/accounting workflows:
1. Accounting Journal CSV (double-entry lines)
2. Tax Summary CSV (input/output tax aggregates)
"""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from core.models.models_per_tenant import Expense, Invoice, Payment

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Decimal:
    """Convert nullable numeric values to Decimal safely."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_amount(value: Decimal) -> str:
    return f"{_quantize(value):.2f}"


def _iso_date(value: Any) -> str:
    """Return a YYYY-MM-DD date for datetime/date/string values."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value)
    if "T" in text:
        return text.split("T", 1)[0]
    if " " in text:
        return text.split(" ", 1)[0]
    return text


class AccountingExportService:
    """Build accountant/tax-ready exports from invoice app transactions."""

    DEFAULT_ACCOUNT_MAPPING: Dict[str, Dict[str, str]] = {
        "bank": {"code": "1000", "name": "Bank"},
        "accounts_receivable": {"code": "1100", "name": "Accounts Receivable"},
        "recoverable_tax": {"code": "1300", "name": "Recoverable Tax"},
        "accounts_payable": {"code": "2000", "name": "Accounts Payable"},
        "tax_payable": {"code": "2200", "name": "Tax Payable"},
        "revenue": {"code": "4000", "name": "Sales Revenue"},
        "expense": {"code": "5000", "name": "Operating Expense"},
    }

    JOURNAL_HEADERS = [
        "entry_date",
        "journal_number",
        "source_type",
        "source_id",
        "reference",
        "description",
        "account_code",
        "account_name",
        "debit",
        "credit",
        "tax_code",
        "tax_rate",
        "tax_amount",
        "currency",
        "counterparty",
        "document_status",
    ]

    TAX_SUMMARY_HEADERS = [
        "tax_type",
        "tax_code",
        "tax_rate",
        "transaction_count",
        "taxable_amount",
        "tax_amount",
        "gross_amount",
        "currency",
        "period_start",
        "period_end",
    ]

    def __init__(self, db: Optional[Session] = None, account_mapping: Optional[Dict[str, Any]] = None):
        self.db = db
        self.account_mapping = self._merge_account_mapping(account_mapping or {})

    def _merge_account_mapping(self, overrides: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        mapping: Dict[str, Dict[str, str]] = {
            key: value.copy() for key, value in self.DEFAULT_ACCOUNT_MAPPING.items()
        }
        for key, value in overrides.items():
            if key in mapping and isinstance(value, dict):
                mapping[key].update({k: str(v) for k, v in value.items() if v is not None})
        return mapping

    def fetch_records(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        include_expenses: bool = True,
        include_invoices: bool = True,
        include_payments: bool = True,
        include_drafts: bool = False,
    ) -> Tuple[List[Expense], List[Invoice], List[Payment]]:
        """Load source transactions from DB with date range filtering."""
        if not self.db:
            raise ValueError("Database session is required for fetch_records")

        expenses: List[Expense] = []
        invoices: List[Invoice] = []
        payments: List[Payment] = []

        if include_expenses:
            query = self.db.query(Expense).filter(Expense.is_deleted.is_(False))
            if date_from:
                query = query.filter(Expense.expense_date >= self._normalize_date_filter(date_from))
            if date_to:
                query = query.filter(Expense.expense_date <= self._normalize_date_filter(date_to))
            expenses = query.order_by(Expense.expense_date, Expense.id).all()

        if include_invoices:
            query = self.db.query(Invoice).options(joinedload(Invoice.client)).filter(Invoice.is_deleted.is_(False))
            if not include_drafts:
                query = query.filter(Invoice.status != "draft")
            if date_from:
                query = query.filter(Invoice.created_at >= self._normalize_date_filter(date_from))
            if date_to:
                query = query.filter(Invoice.created_at <= self._normalize_date_filter(date_to))
            invoices = query.order_by(Invoice.created_at, Invoice.id).all()

        if include_payments:
            query = self.db.query(Payment).options(
                joinedload(Payment.invoice).joinedload(Invoice.client)
            )
            if date_from:
                query = query.filter(Payment.payment_date >= self._normalize_date_filter(date_from))
            if date_to:
                query = query.filter(Payment.payment_date <= self._normalize_date_filter(date_to))
            payments = query.order_by(Payment.payment_date, Payment.id).all()

        return expenses, invoices, payments

    def build_journal_entries(
        self,
        expenses: List[Any],
        invoices: List[Any],
        payments: List[Any],
    ) -> List[Dict[str, str]]:
        """Build balanced journal entries for expenses, invoices, and payments."""
        entries: List[Dict[str, str]] = []

        for expense in expenses:
            entries.extend(self._build_expense_entries(expense))

        for invoice in invoices:
            entries.extend(self._build_invoice_entries(invoice))

        for payment in payments:
            entries.extend(self._build_payment_entries(payment))

        entries.sort(key=lambda row: (row["entry_date"], row["journal_number"], row["account_code"]))
        return entries

    def filter_tax_relevant_records(
        self,
        expenses: List[Any],
        invoices: List[Any],
        payments: List[Any],
    ) -> Tuple[List[Any], List[Any], List[Any]]:
        """Keep only records that are tax-relevant."""
        taxable_expenses = [expense for expense in expenses if self._is_taxable_expense(expense)]
        taxable_invoices = [invoice for invoice in invoices if self._is_taxable_invoice(invoice)]
        taxable_invoice_ids = {
            getattr(invoice, "id", None)
            for invoice in taxable_invoices
            if getattr(invoice, "id", None) is not None
        }

        taxable_payments: List[Any] = []
        for payment in payments:
            invoice = getattr(payment, "invoice", None)
            invoice_id = getattr(invoice, "id", None) if invoice is not None else None
            if (
                invoice is not None
                and invoice_id is not None
                and self._is_taxable_invoice(invoice)
            ):
                taxable_invoice_ids.add(invoice_id)
            if invoice_id is not None and invoice_id in taxable_invoice_ids:
                taxable_payments.append(payment)

        return taxable_expenses, taxable_invoices, taxable_payments

    def build_tax_summary_rows(
        self,
        expenses: List[Any],
        invoices: List[Any],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, str]]:
        """Build tax summary rows grouped by tax type/rate/currency."""
        summary: Dict[Tuple[str, str, str], Dict[str, Decimal]] = defaultdict(
            lambda: {
                "transaction_count": Decimal("0"),
                "taxable_amount": Decimal("0"),
                "tax_amount": Decimal("0"),
                "gross_amount": Decimal("0"),
            }
        )

        for expense in expenses:
            tax_amount = _to_decimal(getattr(expense, "tax_amount", None))
            if tax_amount <= 0:
                continue
            gross = _to_decimal(getattr(expense, "total_amount", None))
            if gross <= 0:
                gross = _to_decimal(getattr(expense, "amount", None)) + tax_amount
            taxable = gross - tax_amount
            rate = _to_decimal(getattr(expense, "tax_rate", None))
            if rate <= 0 and taxable > 0:
                rate = (tax_amount / taxable) * Decimal("100")
            rate_key = _format_amount(rate)
            currency = str(getattr(expense, "currency", "USD") or "USD")
            key = ("input", rate_key, currency)
            summary[key]["transaction_count"] += Decimal("1")
            summary[key]["taxable_amount"] += taxable
            summary[key]["tax_amount"] += tax_amount
            summary[key]["gross_amount"] += gross

        for invoice in invoices:
            gross = _to_decimal(getattr(invoice, "amount", None))
            output_tax, tax_rate, taxable = self._extract_invoice_tax(invoice, gross)
            if output_tax <= 0:
                continue
            rate_key = _format_amount(tax_rate)
            currency = str(getattr(invoice, "currency", "USD") or "USD")
            key = ("output", rate_key, currency)
            summary[key]["transaction_count"] += Decimal("1")
            summary[key]["taxable_amount"] += taxable
            summary[key]["tax_amount"] += output_tax
            summary[key]["gross_amount"] += gross

        rows: List[Dict[str, str]] = []
        period_start = _iso_date(date_from)
        period_end = _iso_date(date_to)

        for (tax_type, rate_key, currency), values in sorted(summary.items()):
            rows.append(
                {
                    "tax_type": tax_type,
                    "tax_code": "INPUT" if tax_type == "input" else "OUTPUT",
                    "tax_rate": rate_key,
                    "transaction_count": str(int(values["transaction_count"])),
                    "taxable_amount": _format_amount(values["taxable_amount"]),
                    "tax_amount": _format_amount(values["tax_amount"]),
                    "gross_amount": _format_amount(values["gross_amount"]),
                    "currency": currency,
                    "period_start": period_start,
                    "period_end": period_end,
                }
            )

        return rows

    def generate_journal_csv(
        self,
        expenses: List[Any],
        invoices: List[Any],
        payments: List[Any],
    ) -> str:
        """Generate accountant-style journal CSV."""
        entries = self.build_journal_entries(expenses, invoices, payments)
        return self._rows_to_csv(entries, self.JOURNAL_HEADERS)

    def generate_tax_summary_csv(
        self,
        expenses: List[Any],
        invoices: List[Any],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> str:
        """Generate tax summary CSV grouped by input/output tax rate."""
        rows = self.build_tax_summary_rows(expenses, invoices, date_from, date_to)
        return self._rows_to_csv(rows, self.TAX_SUMMARY_HEADERS)

    def _is_taxable_expense(self, expense: Any) -> bool:
        tax_amount = _to_decimal(getattr(expense, "tax_amount", None))
        if tax_amount > 0:
            return True
        tax_rate = _to_decimal(getattr(expense, "tax_rate", None))
        return tax_rate > 0

    def _is_taxable_invoice(self, invoice: Any) -> bool:
        gross = _to_decimal(getattr(invoice, "amount", None))
        output_tax, _, _ = self._extract_invoice_tax(invoice, gross)
        return output_tax > 0

    def _extract_invoice_tax(
        self,
        invoice: Any,
        gross: Optional[Decimal] = None,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Resolve invoice tax from explicit tax fields only.

        The export intentionally avoids deriving tax from amount/subtotal because
        in this codebase subtotal is pre-discount and amount is post-discount.
        """
        gross_amount = gross if gross is not None else _to_decimal(getattr(invoice, "amount", None))

        output_tax = _to_decimal(getattr(invoice, "tax_amount", None))
        tax_rate = _to_decimal(getattr(invoice, "tax_rate", None))

        custom_fields = getattr(invoice, "custom_fields", None)
        if isinstance(custom_fields, dict):
            if output_tax <= 0:
                output_tax = _to_decimal(
                    custom_fields.get("tax_amount")
                    or custom_fields.get("output_tax")
                    or custom_fields.get("vat_amount")
                )
            if tax_rate <= 0:
                tax_rate = _to_decimal(
                    custom_fields.get("tax_rate")
                    or custom_fields.get("output_tax_rate")
                    or custom_fields.get("vat_rate")
                )

        if output_tax < 0:
            output_tax = Decimal("0")
        if gross_amount > 0 and output_tax > gross_amount:
            output_tax = gross_amount

        taxable = gross_amount - output_tax
        if taxable < 0:
            taxable = Decimal("0")

        if tax_rate <= 0 and output_tax > 0 and taxable > 0:
            tax_rate = (output_tax / taxable) * Decimal("100")

        return output_tax, tax_rate, taxable

    def _build_expense_entries(self, expense: Any) -> List[Dict[str, str]]:
        gross = _to_decimal(getattr(expense, "total_amount", None))
        base = _to_decimal(getattr(expense, "amount", None))
        tax_amount = _to_decimal(getattr(expense, "tax_amount", None))
        if gross <= 0:
            gross = base + tax_amount
        if gross <= 0:
            return []
        if base <= 0:
            base = gross - tax_amount
        if base < 0:
            base = Decimal("0")

        tax_rate = _to_decimal(getattr(expense, "tax_rate", None))
        if tax_rate <= 0 and base > 0 and tax_amount > 0:
            tax_rate = (tax_amount / base) * Decimal("100")

        category = str(getattr(expense, "category", "") or "")
        expense_account = self._resolve_expense_account(category)
        payable_account = self.account_mapping["accounts_payable"]
        recoverable_tax_account = self.account_mapping["recoverable_tax"]

        journal_number = f"EXP-{getattr(expense, 'id', '')}"
        entry_date = _iso_date(getattr(expense, "expense_date", None))
        counterparty = str(getattr(expense, "vendor", "") or "")
        reference = str(getattr(expense, "reference_number", "") or "")
        description = f"Expense {getattr(expense, 'id', '')} {counterparty}".strip()
        currency = str(getattr(expense, "currency", "USD") or "USD")
        status = str(getattr(expense, "status", "") or "")

        rows: List[Dict[str, str]] = [
            self._journal_row(
                entry_date=entry_date,
                journal_number=journal_number,
                source_type="expense",
                source_id=str(getattr(expense, "id", "")),
                reference=reference,
                description=description,
                account_code=expense_account["code"],
                account_name=expense_account["name"],
                debit=base,
                credit=Decimal("0"),
                tax_code="",
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                currency=currency,
                counterparty=counterparty,
                document_status=status,
            )
        ]

        if tax_amount > 0:
            rows.append(
                self._journal_row(
                    entry_date=entry_date,
                    journal_number=journal_number,
                    source_type="expense",
                    source_id=str(getattr(expense, "id", "")),
                    reference=reference,
                    description=description,
                    account_code=recoverable_tax_account["code"],
                    account_name=recoverable_tax_account["name"],
                    debit=tax_amount,
                    credit=Decimal("0"),
                    tax_code="INPUT",
                    tax_rate=tax_rate,
                    tax_amount=tax_amount,
                    currency=currency,
                    counterparty=counterparty,
                    document_status=status,
                )
            )

        rows.append(
            self._journal_row(
                entry_date=entry_date,
                journal_number=journal_number,
                source_type="expense",
                source_id=str(getattr(expense, "id", "")),
                reference=reference,
                description=description,
                account_code=payable_account["code"],
                account_name=payable_account["name"],
                debit=Decimal("0"),
                credit=gross,
                tax_code="",
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                currency=currency,
                counterparty=counterparty,
                document_status=status,
            )
        )

        return rows

    def _build_invoice_entries(self, invoice: Any) -> List[Dict[str, str]]:
        gross = _to_decimal(getattr(invoice, "amount", None))
        if gross <= 0:
            return []
        output_tax, tax_rate, revenue_amount = self._extract_invoice_tax(invoice, gross)

        ar_account = self.account_mapping["accounts_receivable"]
        revenue_account = self.account_mapping["revenue"]
        tax_payable_account = self.account_mapping["tax_payable"]

        client_name = ""
        client = getattr(invoice, "client", None)
        if client is not None:
            client_name = str(getattr(client, "name", "") or "")

        journal_number = f"INV-{getattr(invoice, 'id', '')}"
        entry_date = _iso_date(getattr(invoice, "created_at", None))
        reference = str(getattr(invoice, "number", "") or "")
        description = f"Invoice {reference} {client_name}".strip()
        currency = str(getattr(invoice, "currency", "USD") or "USD")
        status = str(getattr(invoice, "status", "") or "")

        rows: List[Dict[str, str]] = [
            self._journal_row(
                entry_date=entry_date,
                journal_number=journal_number,
                source_type="invoice",
                source_id=str(getattr(invoice, "id", "")),
                reference=reference,
                description=description,
                account_code=ar_account["code"],
                account_name=ar_account["name"],
                debit=gross,
                credit=Decimal("0"),
                tax_code="",
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                currency=currency,
                counterparty=client_name,
                document_status=status,
            ),
            self._journal_row(
                entry_date=entry_date,
                journal_number=journal_number,
                source_type="invoice",
                source_id=str(getattr(invoice, "id", "")),
                reference=reference,
                description=description,
                account_code=revenue_account["code"],
                account_name=revenue_account["name"],
                debit=Decimal("0"),
                credit=revenue_amount,
                tax_code="",
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                currency=currency,
                counterparty=client_name,
                document_status=status,
            ),
        ]

        if output_tax > 0:
            rows.append(
                self._journal_row(
                    entry_date=entry_date,
                    journal_number=journal_number,
                    source_type="invoice",
                    source_id=str(getattr(invoice, "id", "")),
                    reference=reference,
                    description=description,
                    account_code=tax_payable_account["code"],
                    account_name=tax_payable_account["name"],
                    debit=Decimal("0"),
                    credit=output_tax,
                    tax_code="OUTPUT",
                    tax_rate=tax_rate,
                    tax_amount=output_tax,
                    currency=currency,
                    counterparty=client_name,
                    document_status=status,
                )
            )

        return rows

    def _build_payment_entries(self, payment: Any) -> List[Dict[str, str]]:
        invoice = getattr(payment, "invoice", None)
        if invoice is not None and bool(getattr(invoice, "is_deleted", False)):
            return []

        amount = _to_decimal(getattr(payment, "amount", None))
        if amount == 0:
            return []
        amount = abs(amount)

        bank_account = self.account_mapping["bank"]
        ar_account = self.account_mapping["accounts_receivable"]

        client_name = ""
        if invoice is not None:
            client = getattr(invoice, "client", None)
            if client is not None:
                client_name = str(getattr(client, "name", "") or "")

        journal_number = f"PAY-{getattr(payment, 'id', '')}"
        entry_date = _iso_date(getattr(payment, "payment_date", None))
        reference = str(getattr(payment, "reference_number", "") or "")
        description = f"Payment {getattr(payment, 'id', '')} {client_name}".strip()
        currency = str(getattr(payment, "currency", "USD") or "USD")
        status = "posted"

        rows: List[Dict[str, str]] = [
            self._journal_row(
                entry_date=entry_date,
                journal_number=journal_number,
                source_type="payment",
                source_id=str(getattr(payment, "id", "")),
                reference=reference,
                description=description,
                account_code=bank_account["code"],
                account_name=bank_account["name"],
                debit=amount,
                credit=Decimal("0"),
                tax_code="",
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                currency=currency,
                counterparty=client_name,
                document_status=status,
            ),
            self._journal_row(
                entry_date=entry_date,
                journal_number=journal_number,
                source_type="payment",
                source_id=str(getattr(payment, "id", "")),
                reference=reference,
                description=description,
                account_code=ar_account["code"],
                account_name=ar_account["name"],
                debit=Decimal("0"),
                credit=amount,
                tax_code="",
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                currency=currency,
                counterparty=client_name,
                document_status=status,
            ),
        ]
        return rows

    def _resolve_expense_account(self, category: str) -> Dict[str, str]:
        if not category:
            return self.account_mapping["expense"]
        key = f"expense_{category.strip().lower().replace(' ', '_')}"
        account = self.account_mapping.get(key)
        if account:
            return account
        return self.account_mapping["expense"]

    def _journal_row(
        self,
        entry_date: str,
        journal_number: str,
        source_type: str,
        source_id: str,
        reference: str,
        description: str,
        account_code: str,
        account_name: str,
        debit: Decimal,
        credit: Decimal,
        tax_code: str,
        tax_rate: Decimal,
        tax_amount: Decimal,
        currency: str,
        counterparty: str,
        document_status: str,
    ) -> Dict[str, str]:
        return {
            "entry_date": entry_date,
            "journal_number": journal_number,
            "source_type": source_type,
            "source_id": source_id,
            "reference": reference,
            "description": description,
            "account_code": account_code,
            "account_name": account_name,
            "debit": _format_amount(debit),
            "credit": _format_amount(credit),
            "tax_code": tax_code,
            "tax_rate": _format_amount(tax_rate) if tax_code else "",
            "tax_amount": _format_amount(tax_amount) if tax_code else "",
            "currency": currency,
            "counterparty": counterparty,
            "document_status": document_status,
        }

    def _rows_to_csv(self, rows: List[Dict[str, str]], headers: List[str]) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})
        return output.getvalue()

    def _normalize_date_filter(self, date_value: datetime) -> datetime:
        if date_value.tzinfo is None:
            return date_value.replace(tzinfo=timezone.utc)
        return date_value
