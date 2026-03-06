from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
import csv

from commercial.accounting_export.service import AccountingExportService


def _sample_data():
    client = SimpleNamespace(name="Acme Corp")
    invoice = SimpleNamespace(
        id=11,
        number="INV-0011",
        amount=113.0,
        subtotal=100.0,
        tax_amount=13.0,
        tax_rate=13.0,
        currency="USD",
        created_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
        status="sent",
        client=client,
    )
    expense = SimpleNamespace(
        id=7,
        amount=100.0,
        total_amount=113.0,
        tax_amount=13.0,
        tax_rate=13.0,
        currency="USD",
        expense_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        vendor="Office Supply Co",
        reference_number="EXP-REF-7",
        status="recorded",
        category="Office",
    )
    payment = SimpleNamespace(
        id=5,
        amount=113.0,
        currency="USD",
        payment_date=datetime(2026, 1, 25, tzinfo=timezone.utc),
        reference_number="PAY-REF-5",
        payment_method="bank_transfer",
        invoice=invoice,
    )
    return expense, invoice, payment


def _non_tax_data():
    client = SimpleNamespace(name="No Tax Client")
    invoice = SimpleNamespace(
        id=12,
        number="INV-0012",
        amount=100.0,
        subtotal=100.0,
        tax_amount=0.0,
        tax_rate=0.0,
        currency="USD",
        created_at=datetime(2026, 1, 21, tzinfo=timezone.utc),
        status="sent",
        client=client,
    )
    expense = SimpleNamespace(
        id=8,
        amount=100.0,
        total_amount=100.0,
        tax_amount=0.0,
        tax_rate=0.0,
        currency="USD",
        expense_date=datetime(2026, 1, 16, tzinfo=timezone.utc),
        vendor="No Tax Vendor",
        reference_number="EXP-REF-8",
        status="recorded",
        category="Office",
    )
    payment = SimpleNamespace(
        id=6,
        amount=100.0,
        currency="USD",
        payment_date=datetime(2026, 1, 26, tzinfo=timezone.utc),
        reference_number="PAY-REF-6",
        payment_method="bank_transfer",
        invoice=invoice,
    )
    return expense, invoice, payment


def test_journal_entries_are_balanced_per_transaction():
    service = AccountingExportService()
    expense, invoice, payment = _sample_data()

    entries = service.build_journal_entries([expense], [invoice], [payment])

    totals = defaultdict(lambda: Decimal("0"))
    for row in entries:
        totals[row["journal_number"]] += Decimal(row["debit"]) - Decimal(row["credit"])

    assert totals["EXP-7"] == Decimal("0.00")
    assert totals["INV-11"] == Decimal("0.00")
    assert totals["PAY-5"] == Decimal("0.00")


def test_expense_creates_input_tax_recoverable_line():
    service = AccountingExportService()
    expense, _, _ = _sample_data()

    rows = [r for r in service.build_journal_entries([expense], [], []) if r["journal_number"] == "EXP-7"]

    assert len(rows) == 3
    recoverable_tax_row = next(r for r in rows if r["account_code"] == "1300")
    assert recoverable_tax_row["tax_code"] == "INPUT"
    assert recoverable_tax_row["tax_amount"] == "13.00"
    assert recoverable_tax_row["debit"] == "13.00"
    assert recoverable_tax_row["credit"] == "0.00"


def test_expense_base_row_does_not_repeat_tax_metadata():
    service = AccountingExportService()
    expense, _, _ = _sample_data()

    rows = [r for r in service.build_journal_entries([expense], [], []) if r["journal_number"] == "EXP-7"]
    expense_row = next(r for r in rows if r["account_code"] == "5000")

    assert expense_row["tax_code"] == ""
    assert expense_row["tax_rate"] == ""
    assert expense_row["tax_amount"] == ""


def test_tax_summary_contains_input_and_output_tax_groups():
    service = AccountingExportService()
    expense, invoice, _ = _sample_data()

    rows = service.build_tax_summary_rows(
        expenses=[expense],
        invoices=[invoice],
        date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    by_type = {row["tax_type"]: row for row in rows}

    assert "input" in by_type
    assert "output" in by_type

    assert by_type["input"]["taxable_amount"] == "100.00"
    assert by_type["input"]["tax_amount"] == "13.00"
    assert by_type["input"]["gross_amount"] == "113.00"
    assert by_type["input"]["tax_rate"] == "13.00"

    assert by_type["output"]["taxable_amount"] == "100.00"
    assert by_type["output"]["tax_amount"] == "13.00"
    assert by_type["output"]["gross_amount"] == "113.00"
    assert by_type["output"]["tax_rate"] == "13.00"


def test_journal_csv_uses_accountant_headers():
    service = AccountingExportService()
    expense, invoice, payment = _sample_data()

    csv_content = service.generate_journal_csv([expense], [invoice], [payment])
    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)

    assert len(rows) > 0
    assert reader.fieldnames == service.JOURNAL_HEADERS


def test_filter_tax_relevant_records_excludes_non_tax_documents():
    service = AccountingExportService()
    tax_expense, tax_invoice, tax_payment = _sample_data()
    non_tax_expense, non_tax_invoice, non_tax_payment = _non_tax_data()

    expenses, invoices, payments = service.filter_tax_relevant_records(
        expenses=[tax_expense, non_tax_expense],
        invoices=[tax_invoice, non_tax_invoice],
        payments=[tax_payment, non_tax_payment],
    )

    assert [expense.id for expense in expenses] == [7]
    assert [invoice.id for invoice in invoices] == [11]
    assert [payment.id for payment in payments] == [5]


def test_tax_relevant_payment_filter_works_without_invoice_list():
    service = AccountingExportService()
    _, tax_invoice, tax_payment = _sample_data()

    expenses, invoices, payments = service.filter_tax_relevant_records(
        expenses=[],
        invoices=[],
        payments=[tax_payment],
    )

    assert expenses == []
    assert invoices == []
    assert [payment.id for payment in payments] == [5]
