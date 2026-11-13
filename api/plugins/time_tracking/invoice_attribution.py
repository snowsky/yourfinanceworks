"""Conservative project billing read model; provenance is never inferred from text."""
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy.orm import Session
from core.models.models_per_tenant import Expense, Invoice, InvoiceItem, Payment, SupportedCurrency
from .models import Project, TimeEntry
from .cost_models import ProjectInvoiceSource, ProjectInvoiceLink
from .cost_schemas import ProjectBillingSummary, BillingUnresolvedInvoice


def money(value):
    return Decimal(str(value or 0))


def line_snapshot(item):
    # Flush leaves assigned values in memory; PostgreSQL rounds Numeric columns.
    # Fingerprint both new and reloaded lines at the persisted column precision.
    def numeric_value(name):
        scale = InvoiceItem.__table__.c[name].type.scale
        return str(money(getattr(item, name)).quantize(
            Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP).normalize())

    return dict(description=item.description, inventory_item_id=item.inventory_item_id,
                unit_of_measure=item.unit_of_measure, quantity=numeric_value("quantity"),
                price=numeric_value("price"), amount=str(money(item.amount).normalize()))


def source_snapshot(source):
    result = dict(project_id=source.project_id, invoice_id=source.invoice_id, invoiced=bool(source.invoiced))
    if isinstance(source, TimeEntry):
        result.update(duration_minutes=source.duration_minutes, hourly_rate=str(money(source.hourly_rate).normalize()),
                      amount=str(money(source.amount).normalize()), billable=bool(source.billable), status=source.status)
    else:
        result.update(amount=str(money(source.amount).normalize()), currency=source.currency,
                      is_deleted=bool(source.is_deleted), status=source.status)
    return result


def record_project_invoice_sources(db: Session, project_id: int, sources: list[ProjectInvoiceSource]) -> None:
    """Validate and flush in the caller's invoice transaction, never commit here."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    for provenance in sources:
        item = db.get(InvoiceItem, provenance.invoice_item_id)
        exactly_one = (provenance.time_entry_id is None) != (provenance.expense_id is None)
        source = db.get(TimeEntry, provenance.time_entry_id) if provenance.time_entry_id is not None else db.get(Expense, provenance.expense_id) if provenance.expense_id is not None else None
        if (not exactly_one or provenance.project_id != project_id or item is None or source is None
                or source.project_id != project_id or source.invoice_id != item.invoice_id or not source.invoiced):
            raise HTTPException(400, 'Invalid project invoice source')
        invoice = db.get(Invoice, item.invoice_id)
        if invoice.client_id != project.client_id or invoice.currency != project.currency:
            raise HTTPException(400, 'Invalid project invoice relationship')
        provenance.snapshot = dict(line=line_snapshot(item), source=source_snapshot(source),
                                   invoice_line_ids=[row.id for row in db.query(InvoiceItem).filter_by(invoice_id=item.invoice_id)])
        db.add(provenance)
        if db.get(ProjectInvoiceLink, (project_id, item.invoice_id)) is None:
            db.add(ProjectInvoiceLink(project_id=project_id, invoice_id=item.invoice_id))
    db.flush()


def get_project_billing_summary(db: Session, project_id: int) -> ProjectBillingSummary:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    currency = db.query(SupportedCurrency).filter_by(code=project.currency).first()
    entries = db.query(TimeEntry).filter_by(project_id=project_id).all()
    expenses = db.query(Expense).filter_by(project_id=project_id).all()
    return _get_project_billing_summary(db, project, entries, expenses, currency)


def _get_project_billing_summary(db, project, entries, expenses, currency):
    """Reuse records already batch loaded by the profitability read model."""
    project_id = project.id
    quantum = Decimal(1).scaleb(-(currency.decimal_places if currency else 2))
    rounded = lambda n: n.quantize(quantum, rounding=ROUND_HALF_UP)
    invoice_ids = {s.invoice_id for s in entries + expenses if s.invoice_id is not None}
    provenance_ids = db.query(InvoiceItem.invoice_id).join(ProjectInvoiceSource, ProjectInvoiceSource.invoice_item_id == InvoiceItem.id).filter(ProjectInvoiceSource.project_id == project_id)
    durable_ids = db.query(ProjectInvoiceLink.invoice_id).filter_by(project_id=project_id)
    invoice_ids.update(row[0] for row in provenance_ids.union(durable_ids))
    result = ProjectBillingSummary(currency=project.currency)
    result.unbilled_work_value = rounded(sum((money(e.duration_minutes) / 60 * money(e.hourly_rate)
        for e in entries if e.billable and not e.invoiced and e.invoice_id is None
        and e.status in {'logged', 'approved', 'invoiced'} and e.duration_minutes is not None), Decimal(0)))
    if not invoice_ids:
        return result
    invoices = {row.id: row for row in db.query(Invoice).filter(Invoice.id.in_(invoice_ids))}
    items_by_invoice, payments_by_invoice = defaultdict(list), defaultdict(list)
    for item in db.query(InvoiceItem).filter(InvoiceItem.invoice_id.in_(invoice_ids)):
        items_by_invoice[item.invoice_id].append(item)
    mappings = {row.invoice_item_id: row for row in db.query(ProjectInvoiceSource).join(
        InvoiceItem, ProjectInvoiceSource.invoice_item_id == InvoiceItem.id,
    ).filter(InvoiceItem.invoice_id.in_(invoice_ids))}
    for payment in db.query(Payment).filter(Payment.invoice_id.in_(invoice_ids)):
        payments_by_invoice[payment.invoice_id].append(payment)
    time_sources = {row.id: row for row in entries}
    expense_sources = {row.id: row for row in expenses}
    for invoice_id in sorted(invoice_ids):
        invoice = invoices.get(invoice_id)
        reasons = []
        if invoice is None:
            reasons.append('missing_invoice')
        elif invoice.is_deleted:
            reasons.append('deleted_invoice')
        elif invoice.status not in {'draft', 'pending', 'sent', 'overdue', 'paid', 'partially_paid'}:
            reasons.append('unsupported_credit_or_refund_status' if invoice.status in {'refunded', 'credited'} else 'unsupported_invoice_status')
        elif invoice.currency != project.currency:
            reasons.append('invoice_currency_mismatch')
        elif invoice.client_id != project.client_id:
            reasons.append('invoice_client_mismatch')
        items = items_by_invoice[invoice_id]
        item_ids = {item.id for item in items}
        if not items:
            reasons.append('missing_invoice_lines')
        for item in items:
            mapping = mappings.get(item.id)
            if mapping is None or mapping.project_id != project_id:
                reasons.append('mixed_or_unmapped_invoice_lines')
                continue
            source = time_sources.get(mapping.time_entry_id) if mapping.time_entry_id is not None else expense_sources.get(mapping.expense_id)
            snapshot = mapping.snapshot
            if not snapshot:
                reasons.append('missing_provenance_snapshot')
            elif (source is None or source.project_id != project_id or source.invoice_id != invoice_id
                  or snapshot.get('source') != source_snapshot(source)
                  or snapshot.get('line') != line_snapshot(item)
                  or not set(snapshot.get('invoice_line_ids', [])).issubset(item_ids)):
                reasons.append('changed_or_deleted_invoice_source_or_line')
        if invoice and money(invoice.subtotal) != sum((money(i.amount) for i in items), Decimal(0)):
            reasons.append('invoice_subtotal_mismatch')
        if not reasons:
            subtotal, discount = money(invoice.subtotal), money(invoice.discount_value)
            if subtotal < 0 or discount < 0 or invoice.discount_type not in {'percentage', 'fixed'} or (invoice.discount_type == 'percentage' and discount > 100):
                reasons.append('unsupported_credit_or_discount')
            elif any(money(item.amount) < 0 for item in items):
                reasons.append('unsupported_credit_line')
        if reasons:
            result.invoicing_complete = False
            result.cash_complete = False
        else:
            net = subtotal - (subtotal * discount / 100 if invoice.discount_type == 'percentage' else min(discount, subtotal))
            result.invoiced_pre_tax += rounded(net)
            # Allocate supported invoice discounts by each line's pre-discount amount.
            # This is a separate invoice measure, never part of time work value.
            expense_lines = sum((money(item.amount) for item in items
                                 if mappings[item.id].expense_id is not None), Decimal(0))
            result.expense_reimbursements_pre_tax += rounded(
                expense_lines * net / subtotal if subtotal else Decimal(0))
            result.attributed_invoice_ids.append(invoice_id)
            payments = payments_by_invoice[invoice_id]
            for payment in payments:
                if payment.currency != project.currency:
                    reasons.append('payment_currency_mismatch')
                elif money(payment.amount) < 0:
                    reasons.append('unsupported_negative_payment_or_refund')
            if reasons:
                # Refund allocation has no supported ledger; withhold this invoice's
                # cash instead of presenting a misleading pre-refund amount.
                result.cash_complete = False
            else:
                result.collected_cash += rounded(sum((money(p.amount) for p in payments), Decimal(0)))
        if reasons:
            result.unresolved_invoice_ids.append(invoice_id)
            result.unresolved_invoices.append(BillingUnresolvedInvoice(invoice_id=invoice_id, reasons=sorted(set(reasons))))
    return result
