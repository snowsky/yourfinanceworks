"""Tenant-session read model for protected profitability endpoints.

All collections are batch loaded; accessing an ORM relationship is unnecessary.
"""
from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from core.models.models_per_tenant import Expense, ExpenseApproval, SupportedCurrency
from .models import Project, TimeEntry
from .cost_models import TimeEntryCost, TimeEntryCostExpense
from .cost_schemas import ProjectProfitabilityInput, ProfitabilityEntry, ProfitabilityExpense
from .profitability_calculations import calculate_profitability


def get_project_profitability(db: Session, project_id: int):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Project not found')
    entries = db.query(TimeEntry).filter_by(project_id=project_id).order_by(TimeEntry.id).all()
    costs = {c.time_entry_id: c for c in db.query(TimeEntryCost).join(TimeEntry, TimeEntry.id == TimeEntryCost.time_entry_id).filter(TimeEntry.project_id == project_id)}
    links = defaultdict(list)
    for link in db.query(TimeEntryCostExpense).join(TimeEntry, TimeEntry.id == TimeEntryCostExpense.time_entry_id).filter(TimeEntry.project_id == project_id):
        links[link.time_entry_id].append(link.expense_id)
    linked_ids = {i for ids in links.values() for i in ids}
    expenses = db.query(Expense).filter(or_(Expense.project_id == project_id, Expense.id.in_(linked_ids))).order_by(Expense.id).all()
    approvals = defaultdict(list)
    for approval in db.query(ExpenseApproval).filter(ExpenseApproval.expense_id.in_([e.id for e in expenses])):
        approvals[approval.expense_id].append(approval)
    expense_inputs = []
    for expense in expenses:
        records = approvals[expense.id]
        # A submission creates all level rows with the same timestamp. Old
        # rejected/cancelled cycles must not poison a successful resubmission.
        latest = max((a.submitted_at for a in records), default=None)
        states = [a.status for a in records if a.submitted_at == latest]
        expense_inputs.append(ProfitabilityExpense(
            id=expense.id, project_id=expense.project_id, amount=expense.amount,
            currency=expense.currency, status=expense.status, is_deleted=expense.is_deleted,
            approval_statuses=states, imported_from_attachment=expense.imported_from_attachment,
            analysis_status=expense.analysis_status, manual_override=expense.manual_override,
        ))
    entry_inputs = []
    for entry in entries:
        cost = costs.get(entry.id)
        entry_inputs.append(ProfitabilityEntry(
            id=entry.id, user_id=entry.user_id, task_id=entry.task_id, status=entry.status,
            duration_minutes=entry.duration_minutes, billable=entry.billable, hourly_rate=entry.hourly_rate,
            cost_method=cost.method if cost else None, hourly_cost=cost.hourly_cost if cost else None,
            cost_currency=cost.currency if cost else None, expense_ids=links[entry.id],
        ))
    currency = db.query(SupportedCurrency).filter_by(code=project.currency).first()
    return calculate_profitability(ProjectProfitabilityInput(
        project_id=project.id, currency=project.currency, billing_method=project.billing_method,
        decimal_places=currency.decimal_places if currency else 2,
        budget_hours=project.budget_hours, budget_amount=project.budget_amount,
        entries=entry_inputs, expenses=expense_inputs,
    ))
