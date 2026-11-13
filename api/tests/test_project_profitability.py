"""Contribution regressions using disposable tenant ORM fixtures (--noconftest)."""
from datetime import datetime
from decimal import Decimal
import pytest
from tests.test_project_cost_permissions import db
from core.models.models_per_tenant import Expense, ExpenseApproval
from plugins.time_tracking.models import TimeEntry, Project
from plugins.time_tracking.cost_models import TimeEntryCost, TimeEntryCostExpense
from plugins.time_tracking.profitability_service import get_project_profitability


def setup_cost(db, minutes=600, cost='40'):
    db.get(TimeEntry, 1).duration_minutes = minutes
    db.add(TimeEntryCost(time_entry_id=1, method='hourly', hourly_cost=Decimal(cost), currency='USD'))
    db.flush()


def expense(db, **kwargs):
    values = dict(id=1, project_id=1, amount=100, currency='USD', category='supplier', status='recorded')
    values.update(kwargs)
    db.add(Expense(**values))
    db.flush()


def test_hourly_contribution_example(db):
    setup_cost(db)
    db.add(TimeEntry(id=2, project_id=1, client_id=1, user_id=2, started_at=datetime(2026,2,1), duration_minutes=120, hourly_rate=100, billable=False, status='logged'))
    db.add(TimeEntryCost(time_entry_id=2, method='hourly', hourly_cost=40, currency='USD'))
    expense(db, total_amount=113, tax_amount=13)
    r = get_project_profitability(db, 1)
    assert (r.work_value, r.known_cost, r.contribution, r.margin_percent) == tuple(map(Decimal, ['1000','580','420','42']))
    assert sum(b.hourly_cost for b in r.contributors) + r.expense_bucket.amount == r.known_cost


@pytest.mark.parametrize('cost,minutes,rate,expected', [('0',60,100,'100'),('200',60,100,'-100'),('40',60,0,'-40')])
def test_zero_and_negative(db,cost,minutes,rate,expected):
    setup_cost(db, minutes,cost)
    db.get(TimeEntry,1).hourly_rate=rate
    r=get_project_profitability(db,1)
    assert r.contribution == Decimal(expected)
    assert (r.margin_percent is None) == (rate == 0)


def test_missing_active_and_budgets(db):
    p=db.get(Project,1)
    p.budget_hours=1.875
    p.budget_amount=150
    r=get_project_profitability(db,1)
    assert r.missing_hours == Decimal('1.5') and r.contribution is None
    assert r.hours_budget_percent == 80 and r.amount_budget_percent == 100
    assert r.budget_warnings == ['hours_80_percent','amount_100_percent']
    db.get(TimeEntry,1).status='in_progress'
    r=get_project_profitability(db,1)
    assert r.completed_hours == 0 and r.contribution == 0
    assert r.excluded_records[0].reason == 'active_timer'


@pytest.mark.parametrize('status,deleted,currency,reason', [('pending_approval',False,'USD','pending_approval'),('draft',False,'USD','unknown_expense_status'),('recorded',True,'USD','deleted_expense'),('recorded',False,'CAD','currency_mismatch'),('rejected',False,'USD','rejected_expense')])
def test_supplier_any_invalid_link_is_incomplete(db,status,deleted,currency,reason):
    db.add(TimeEntryCost(time_entry_id=1,method='supplier_expense',currency='USD'))
    expense(db,status=status,is_deleted=deleted,currency=currency)
    expense(db,id=2,amount=0)
    db.add_all([TimeEntryCostExpense(time_entry_id=1,expense_id=i) for i in [1,2]])
    r=get_project_profitability(db,1)
    assert r.contribution is None and r.missing_hours == Decimal('1.5')
    assert reason in [x.reason for x in r.unresolved_records+r.excluded_records]


def test_supplier_missing_and_shared(db):
    db.add(TimeEntryCost(time_entry_id=1,method='supplier_expense',currency='USD'))
    assert get_project_profitability(db,1).contribution is None
    expense(db)
    db.add(TimeEntryCostExpense(time_entry_id=1,expense_id=1))
    assert get_project_profitability(db,1).known_cost == 100
    assert get_project_profitability(db,1).contributors[0].hourly_cost == 0


@pytest.mark.parametrize('status', ['recorded','approved','pending_approval'])
def test_pending_approver_never_complete(db,status):
    setup_cost(db)
    expense(db,status=status)
    for i,s in enumerate(['approved','pending'],1):
        db.add(ExpenseApproval(id=i,expense_id=1,approver_id=1,status=s,submitted_at=datetime(2026,2,1)))
    assert get_project_profitability(db,1).contribution is None


def test_resubmitted_approval_cycle(db):
    setup_cost(db)
    expense(db,status='approved',amount=0)
    for i,s,date in [(1,'rejected',1),(2,'approved',2)]:
        db.add(ExpenseApproval(id=i,expense_id=1,approver_id=1,status=s,submitted_at=datetime(2026,2,date)))
    assert get_project_profitability(db,1).contribution == 600


def test_unknown_amount_currency_and_nonhourly(db):
    setup_cost(db)
    expense(db,amount=None)
    assert get_project_profitability(db,1).contribution is None
    db.get(Expense,1).amount=0
    db.get(TimeEntryCost,1).currency='CAD'
    assert get_project_profitability(db,1).contribution is None
    db.get(Project,1).billing_method='fixed_cost'
    r=get_project_profitability(db,1)
    assert r.status == 'unsupported_billing_method' and r.contribution is None


def test_shared_supplier_cost_once_and_breakdowns(db):
    db.add(TimeEntry(id=2, project_id=1, client_id=1, user_id=1, task_id=None,
                     started_at=datetime(2026,2,1), duration_minutes=30, hourly_rate=100,
                     billable=False, status='approved'))
    expense(db,amount=70)
    for i in [1,2]:
        db.add(TimeEntryCost(time_entry_id=i, method='supplier_expense', currency='USD'))
        db.add(TimeEntryCostExpense(time_entry_id=i,expense_id=1))
    r=get_project_profitability(db,1)
    assert r.status == 'complete' and r.known_cost == 70
    assert r.expense_bucket.expense_ids == [1]
    assert sum(b.hourly_cost for b in r.contributors)+r.expense_bucket.amount == r.known_cost
    assert sum(b.hourly_cost for b in r.tasks)+r.expense_bucket.amount == r.known_cost
    assert all(b.supplier_expense_ids == [1] for b in r.contributors)


@pytest.mark.parametrize('budget', [None,0])
def test_no_budgets(db,budget):
    setup_cost(db)
    db.get(Project,1).budget_hours=budget
    db.get(Project,1).budget_amount=budget
    r=get_project_profitability(db,1)
    assert r.hours_budget_percent is None and r.amount_budget_percent is None
    assert r.budget_warnings == []


@pytest.mark.parametrize('status,reason', [('mystery','unknown_expense_status'),('pending_approval','pending_approval'),('draft','unknown_expense_status')])
def test_unresolved_standalone_expense(db,status,reason):
    setup_cost(db)
    expense(db,status=status)
    r=get_project_profitability(db,1)
    assert r.contribution is None
    assert r.unresolved_records[0].reason == reason


def test_ocr_and_cancelled_approval_unsubmission(db):
    setup_cost(db)
    expense(db,imported_from_attachment=True,analysis_status='processing')
    assert get_project_profitability(db,1).unresolved_records[0].reason == 'unresolved_ocr'
    db.get(Expense,1).manual_override=True
    db.add(ExpenseApproval(expense_id=1,approver_id=1,status='cancelled',submitted_at=datetime(2026,2,1)))
    assert get_project_profitability(db,1).status == 'complete'


def test_rejected_standalone_visible_exclusion(db):
    setup_cost(db)
    expense(db,status='rejected')
    r=get_project_profitability(db,1)
    assert r.status == 'complete' and r.known_cost == 400
    assert r.excluded_records[0].reason == 'rejected_expense'


def test_currency_precision_and_half_up(db):
    from core.models.models_per_tenant import SupportedCurrency
    setup_cost(db,minutes=1,cost='0')
    db.get(Project,1).currency='JPY'
    db.get(TimeEntryCost,1).currency='JPY'
    db.get(TimeEntry,1).hourly_rate=90
    db.add(SupportedCurrency(code='JPY',name='Yen',symbol='Y',decimal_places=0))
    assert get_project_profitability(db,1).work_value == Decimal('2')


def test_wrong_project_supplier_and_hard_deleted_links(db):
    setup_cost(db)
    db.get(TimeEntryCost,1).method='supplier_expense'
    db.get(TimeEntryCost,1).hourly_cost=None
    expense(db,project_id=99)
    db.add(TimeEntryCostExpense(time_entry_id=1,expense_id=1))
    r=get_project_profitability(db,1)
    assert r.known_cost == 0 and r.contribution is None
    assert 'wrong_project' in [x.reason for x in r.unresolved_records]
    db.query(TimeEntryCostExpense).delete()
    db.query(Expense).delete()
    assert get_project_profitability(db,1).contribution is None


def test_batched_queries_and_not_found(db):
    from sqlalchemy import event
    from fastapi import HTTPException
    setup_cost(db)
    queries=[]
    def count(conn,cursor,statement,parameters,context,executemany):
        queries.append(statement)
    event.listen(db.bind,'before_cursor_execute',count)
    get_project_profitability(db,1)
    event.remove(db.bind,'before_cursor_execute',count)
    assert len(queries) <= 7
    with pytest.raises(HTTPException) as exc:
        get_project_profitability(db,999)
    assert exc.value.status_code == 404


def test_profitability_route_requires_tenant_admin():
    # Full HTTP dependency execution remains the deployed-image integration task.
    import ast
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1] / 'plugins/time_tracking/profitability_router.py').read_text()
    tree=ast.parse(source)
    route=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_project_profitability')
    assert 'Depends(cost_admin)' in ast.get_source_segment(source,route)
    assert '/{project_id}/profitability' in ast.unparse(route.decorator_list[0])


@pytest.mark.parametrize('states,complete', [
    (['approved', 'cancelled'], True),
    (['approved', 'pending'], False),
    (['approved', 'rejected', 'cancelled'], False),
    (['approved'], False),
])
def test_partially_approved_unsubmission(db, states, complete):
    setup_cost(db)
    expense(db, status='recorded')
    for level, status in enumerate(states, 1):
        db.add(ExpenseApproval(
            expense_id=1, approver_id=1, status=status,
            approval_level=level, submitted_at=datetime(2026, 2, 1),
        ))
    result = get_project_profitability(db, 1)
    assert (result.status == 'complete') is complete
    assert result.known_cost == (Decimal('500') if complete else Decimal('400'))
    assert result.contribution == (Decimal('500') if complete else None)
