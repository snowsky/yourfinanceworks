"""Isolated real tenant ORM attribution regressions; no shared conftest."""
from datetime import datetime
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from tests.test_project_cost_permissions import db
from core.models.models_per_tenant import Invoice, InvoiceItem, Payment, Expense
from plugins.time_tracking.models import TimeEntry, Project
from plugins.time_tracking.cost_models import ProjectInvoiceSource
from plugins.time_tracking.invoice_attribution import record_project_invoice_sources, get_project_billing_summary


def make_invoice(db, expense_only=False):
    inv = Invoice(number='TEST', client_id=1, due_date=datetime(2026, 2, 1), subtotal=1000, amount=1130, currency='USD', status='paid')
    db.add(inv)
    db.flush()
    if expense_only:
        source = Expense(id=1, project_id=1, amount=1000, currency='USD', category='other', status='recorded', invoice_id=inv.id, invoiced=True)
    else:
        source = db.get(TimeEntry, 1)
        source.duration_minutes = 600
        source.amount = 1000
        source.invoiced = True
        source.invoice_id = inv.id
        source.status = 'invoiced'
    db.add(source)
    line = InvoiceItem(invoice_id=inv.id, description='expense' if expense_only else 'time', quantity=1 if expense_only else 10, price=1000 if expense_only else 100, amount=1000)
    db.add(line)
    db.flush()
    record_project_invoice_sources(db, 1, [ProjectInvoiceSource(invoice_item_id=line.id, project_id=1, expense_id=1 if expense_only else None, time_entry_id=None if expense_only else 1)])
    return inv, line, source


def test_unique_invoice_and_actual_partial_cash(db):
    inv, line, _ = make_invoice(db)
    db.add(TimeEntry(id=2, project_id=1, client_id=1, user_id=2, started_at=datetime(2026,2,1), duration_minutes=0, hourly_rate=100, amount=0, billable=True, status='invoiced', invoice_id=inv.id, invoiced=True))
    extra = InvoiceItem(invoice_id=inv.id, description='zero time', quantity=0, price=100, amount=0)
    db.add(extra); db.flush()
    record_project_invoice_sources(db, 1, [ProjectInvoiceSource(invoice_item_id=extra.id, project_id=1, time_entry_id=2)])
    payment = Payment(invoice_id=inv.id, amount=300, currency='USD')
    db.add(payment); db.flush()
    r = get_project_billing_summary(db, 1)
    assert (r.invoiced_pre_tax, r.collected_cash) == (1000, 300)
    assert r.attributed_invoice_ids == [inv.id] and r.collections_include_tax
    db.delete(payment); db.flush()
    assert get_project_billing_summary(db,1).collected_cash == 0


@pytest.mark.parametrize('expense_only', [True, False])
def test_sources_and_discounts(db, expense_only):
    inv, _, _ = make_invoice(db, expense_only)
    inv.discount_value = 10
    assert get_project_billing_summary(db,1).invoiced_pre_tax == 900
    inv.discount_type = 'fixed'; inv.discount_value = 1200
    assert get_project_billing_summary(db,1).invoiced_pre_tax == 0


@pytest.mark.parametrize('change', ['manual','line_amount','line_description','deleted_line','source','source_project','recycled','currency','cancelled','refund','negative_payment','payment_currency','legacy'])
def test_unreliable_attribution_is_explicit(db, change):
    inv, line, source = make_invoice(db)
    if change == 'manual': db.add(InvoiceItem(invoice_id=inv.id, description='manual', quantity=1, price=0, amount=0))
    if change == 'line_amount': line.amount = 500
    if change == 'line_description': line.description = 'edited'
    if change == 'deleted_line': db.delete(line)
    if change == 'source': source.duration_minutes = 100
    if change == 'source_project':
        db.add(Project(id=2, client_id=1, name='other', currency='USD')); source.project_id = 2
    if change == 'recycled': inv.is_deleted = True
    if change == 'currency': inv.currency = 'CAD'
    if change == 'cancelled': inv.status = 'cancelled'
    if change == 'refund': inv.status = 'refunded'
    if change == 'negative_payment': db.add(Payment(invoice_id=inv.id, amount=-30, currency='USD'))
    if change == 'payment_currency': db.add(Payment(invoice_id=inv.id, amount=30, currency='CAD'))
    if change == 'legacy': db.get(ProjectInvoiceSource, line.id).snapshot = None
    db.flush()
    r = get_project_billing_summary(db,1)
    assert inv.id in r.unresolved_invoice_ids
    assert not r.cash_complete
    if change not in {'negative_payment','payment_currency'}:
        assert not r.invoicing_complete and r.invoiced_pre_tax == 0
    else:
        assert r.invoiced_pre_tax == 1000
    assert r.collected_cash == 0


def test_unbilled_independent_of_invoice_values(db):
    assert get_project_billing_summary(db,1).unbilled_work_value == Decimal('150')
    make_invoice(db)
    assert get_project_billing_summary(db,1).unbilled_work_value == 0


def test_source_validation_and_transaction_failure(db):
    inv, line, source = make_invoice(db)
    db.rollback()
    # A real flush failure rolls back invoice, lines and source as a single unit.
    def fail(mapper, connection, target):
        raise RuntimeError('source insert failed')
    event.listen(ProjectInvoiceSource, 'before_insert', fail)
    try:
        with pytest.raises(RuntimeError):
            make_invoice(db)
        db.rollback()
        assert db.query(Invoice).count() == 0
        assert db.query(InvoiceItem).count() == 0
        assert db.query(ProjectInvoiceSource).count() == 0
        assert db.get(TimeEntry,1).invoice_id is None
    finally:
        event.remove(ProjectInvoiceSource, 'before_insert', fail)


def invoice_route():
    """Actual route body + real ORM; intentionally not HTTP/auth proof."""
    import ast
    from pathlib import Path
    from datetime import timezone
    from types import SimpleNamespace
    from plugins.time_tracking.schemas import ProjectInvoiceResponse
    tree = ast.parse(Path('api/plugins/time_tracking/router.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_invoice_from_project')
    node.decorator_list = []
    node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
    ns = dict(HTTPException=HTTPException, Project=Project, TimeEntry=TimeEntry, Expense=Expense,
              Invoice=Invoice, InvoiceItem=InvoiceItem, ProjectInvoiceSource=ProjectInvoiceSource,
              record_project_invoice_sources=record_project_invoice_sources, datetime=datetime,
              timezone=timezone, log_audit_event=lambda **kwargs: None,
              ProjectInvoiceResponse=ProjectInvoiceResponse)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<actual-project-invoice-body>', 'exec'), ns)
    return ns['create_invoice_from_project']


@pytest.mark.parametrize('expense_only', [True, False])
def test_actual_generation_records_provenance(db, expense_only):
    from types import SimpleNamespace
    from plugins.time_tracking.schemas import ProjectInvoiceRequest
    if expense_only:
        db.add(Expense(id=1, project_id=1, amount=200, currency='USD', category='other', status='recorded'))
        db.flush()
    result = invoice_route()(1, ProjectInvoiceRequest(time_entry_ids=[] if expense_only else [1], expense_ids=[1] if expense_only else []), db, SimpleNamespace(id=1, email='admin'))
    billing = get_project_billing_summary(db,1)
    assert billing.attributed_invoice_ids == [result.invoice_id]
    assert billing.invoicing_complete


def test_actual_generation_rolls_back_source_insert_failure(db):
    from types import SimpleNamespace
    from plugins.time_tracking.schemas import ProjectInvoiceRequest
    def fail(mapper, connection, target):
        raise RuntimeError('source insert failed')
    event.listen(ProjectInvoiceSource,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError):
            invoice_route()(1, ProjectInvoiceRequest(time_entry_ids=[1]),db,SimpleNamespace(id=1,email='admin'))
        # Route, not test, must already have rolled the unit of work back.
        assert db.query(Invoice).count() == 0
        assert db.get(TimeEntry,1).invoice_id is None
    finally:
        event.remove(ProjectInvoiceSource,'before_insert',fail)


def test_generation_rejects_missing_selected_source(db):
    from types import SimpleNamespace
    from plugins.time_tracking.schemas import ProjectInvoiceRequest
    with pytest.raises(HTTPException):
        invoice_route()(1, ProjectInvoiceRequest(time_entry_ids=[1,999]), db, SimpleNamespace(id=1,email='admin'))
    assert db.query(Invoice).count() == 0


def test_mixed_project_invoice_is_unresolved(db):
    inv, _, _ = make_invoice(db)
    db.add(Project(id=2, client_id=1, name='other', currency='USD'))
    db.add(TimeEntry(id=2, project_id=2, client_id=1, user_id=2, started_at=datetime(2026,2,1), duration_minutes=0, hourly_rate=100, amount=0, billable=True, status='invoiced', invoice_id=inv.id, invoiced=True))
    line = InvoiceItem(invoice_id=inv.id, description='other project', quantity=0, price=100, amount=0)
    db.add(line); db.flush()
    record_project_invoice_sources(db,2,[ProjectInvoiceSource(invoice_item_id=line.id,project_id=2,time_entry_id=2)])
    r = get_project_billing_summary(db,1)
    assert r.invoiced_pre_tax == 0 and not r.invoicing_complete
    assert 'mixed_or_unmapped_invoice_lines' in r.unresolved_invoices[0].reasons


def test_partial_known_totals_and_provenance_survives_source_reassignment(db):
    inv, line, source = make_invoice(db)
    db.add(Payment(invoice_id=inv.id, amount=300, currency='USD'))
    source.invoice_id = None
    db.flush()
    r = get_project_billing_summary(db,1)
    assert r.unresolved_invoice_ids == [inv.id] and not r.invoicing_complete


def test_rejects_foreign_source_mapping(db):
    inv, line, source = make_invoice(db)
    db.add(Project(id=2,client_id=1,name='other',currency='USD')); db.flush()
    with pytest.raises(HTTPException):
        record_project_invoice_sources(db,2,[ProjectInvoiceSource(invoice_item_id=line.id,project_id=2,time_entry_id=1)])


def test_snapshot_migration_retains_legacy_rows(db):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util
    from pathlib import Path
    from sqlalchemy import text
    # Exercise actual upgrade against a disposable table shaped like revision029.
    with db.bind.begin() as conn:
        conn.execute(text('DROP TABLE project_invoice_links'))
        conn.execute(text('DROP TABLE project_invoice_sources'))
        conn.execute(text('CREATE TABLE project_invoice_sources (invoice_item_id INTEGER PRIMARY KEY, project_id INTEGER, time_entry_id INTEGER, expense_id INTEGER)'))
        conn.execute(text('INSERT INTO project_invoice_sources VALUES (1, 1, 1, NULL)'))
        spec = importlib.util.spec_from_file_location('snapshot_migration',Path('api/alembic/versions/030_project_invoice_snapshots.py'))
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        assert conn.execute(text('SELECT snapshot FROM project_invoice_sources')).scalar() is None
        migration.downgrade()
        assert conn.execute(text('SELECT COUNT(*) FROM project_invoice_sources')).scalar() == 1


def test_durable_discovery_after_all_lines_and_source_links_removed(db):
    inv, line, source = make_invoice(db)
    source.invoice_id = None
    source.invoiced = False
    db.delete(db.get(ProjectInvoiceSource,line.id))
    db.delete(line)
    db.flush()
    r = get_project_billing_summary(db,1)
    assert r.unresolved_invoice_ids == [inv.id]
    assert not r.invoicing_complete and not r.cash_complete
    assert r.invoiced_pre_tax == 0


def test_provenance_restricts_hard_source_deletion(db):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    make_invoice(db)
    db.commit()
    db.execute(text('PRAGMA foreign_keys=ON'))
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(text('DELETE FROM time_entries WHERE id=1'))
    assert db.get(TimeEntry,1) is not None


def test_known_totals_retained_when_another_invoice_is_unresolved(db):
    inv, _, _ = make_invoice(db)
    db.add(Payment(invoice_id=inv.id,amount=300,currency='USD'))
    legacy = Invoice(number='LEGACY',client_id=1,due_date=datetime(2026,2,1),subtotal=50,amount=50,currency='USD',status='paid')
    db.add(legacy); db.flush()
    db.add(Expense(project_id=1,amount=50,currency='USD',category='other',status='recorded',invoice_id=legacy.id,invoiced=True))
    db.add(InvoiceItem(invoice_id=legacy.id,description='legacy',quantity=1,price=50,amount=50)); db.flush()
    result = get_project_billing_summary(db,1)
    assert (result.invoiced_pre_tax,result.collected_cash) == (1000,300)
    assert result.unresolved_invoice_ids == [legacy.id]
    assert not result.invoicing_complete and not result.cash_complete


@pytest.mark.parametrize('field,value', [('inventory_item_id', 1), ('unit_of_measure', 'days')])
def test_all_writable_line_metadata_edits_invalidate_attribution(db, field, value):
    from core.models.models_per_tenant import InventoryItem
    inv, line, _ = make_invoice(db)
    db.add(InventoryItem(id=1, name='service', unit_price=100, currency='USD'))
    db.add(Payment(invoice_id=inv.id, amount=300, currency='USD'))
    db.flush()
    original = get_project_billing_summary(db, 1)
    assert original.invoicing_complete and original.cash_complete
    assert (original.invoiced_pre_tax, original.collected_cash) == (1000, 300)
    setattr(line, field, value)
    db.flush()
    changed = get_project_billing_summary(db, 1)
    assert not changed.invoicing_complete and not changed.cash_complete
    assert (changed.invoiced_pre_tax, changed.collected_cash) == (0, 0)
    assert changed.unresolved_invoice_ids == [inv.id]
    assert 'changed_or_deleted_invoice_source_or_line' in changed.unresolved_invoices[0].reasons
    setattr(line, field, None)
    db.flush()
    restored = get_project_billing_summary(db, 1)
    assert restored.invoicing_complete and restored.cash_complete
    assert (restored.invoiced_pre_tax, restored.collected_cash) == (1000, 300)
