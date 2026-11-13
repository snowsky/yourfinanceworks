"""Pure Decimal contribution estimates; no database or optional commercial imports."""
from decimal import Decimal, ROUND_HALF_UP
from .cost_schemas import (
    ProjectProfitabilityInput, ProjectProfitabilityResponse, ProfitabilityRecord,
    ProfitabilityBreakdown,
)

ZERO = Decimal(0)


def expense_eligibility(expense, project_id, currency):
    """Return (reason, excluded). Approval outcomes come from core stored state.

    The loader supplies only the latest submission cycle. Pending rows in any
    level prevent completion, even if a stale expense status says approved.
    Cancelled historical rows after unsubmission are harmless for recorded costs.
    """
    if expense.project_id != project_id:
        return 'wrong_project', False
    if expense.is_deleted:
        return 'deleted_expense', True
    if expense.status in ('rejected', 'cancelled', 'deleted'):
        return f'{expense.status}_expense', True
    if expense.currency != currency:
        return 'currency_mismatch', False
    states = expense.approval_statuses
    if expense.status == 'pending_approval' or 'pending' in states:
        return 'pending_approval', False
    if any(s not in ('approved', 'rejected', 'cancelled') for s in states):
        return 'unknown_approval_status', False
    if expense.status == 'approved':
        if not states or any(s != 'approved' for s in states):
            return 'unresolved_approval', False
    elif expense.status == 'recorded':
        if any(s != 'cancelled' for s in states):
            return 'unresolved_approval', False
    else:
        return 'unknown_expense_status', False
    if expense.imported_from_attachment and not expense.manual_override and expense.analysis_status != 'done':
        return 'unresolved_ocr', False
    if expense.amount is None or not expense.amount.is_finite():
        return 'missing_amount', False
    return None, False


def calculate_profitability(data: ProjectProfitabilityInput) -> ProjectProfitabilityResponse:
    r = ProjectProfitabilityResponse(project_id=data.project_id, currency=data.currency, status='complete')
    if data.billing_method != 'hourly':
        r.status = 'unsupported_billing_method'
        return r
    quantum = Decimal(1).scaleb(-data.decimal_places)
    money = lambda v: v.quantize(quantum, rounding=ROUND_HALF_UP)
    percent = lambda v: v.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    eligible_expenses = set()
    expense_ids = set()
    for expense in data.expenses:
        if expense.id in expense_ids:
            continue
        expense_ids.add(expense.id)
        reason, excluded = expense_eligibility(expense, data.project_id, data.currency)
        if reason:
            records = r.excluded_records if excluded else r.unresolved_records
            records.append(ProfitabilityRecord(record_type='expense', record_id=expense.id, reason=reason))
        else:
            eligible_expenses.add(expense.id)
            r.expense_bucket.amount += money(expense.amount)
            r.expense_bucket.expense_ids.append(expense.id)
    contributors, tasks = {}, {}
    labor_cost = ZERO
    for entry in data.entries:
        if entry.status not in ('logged', 'completed', 'approved', 'invoiced'):
            reason = 'active_timer' if entry.status == 'in_progress' else 'ineligible_time_entry'
            r.excluded_records.append(ProfitabilityRecord(record_type='time_entry', record_id=entry.id, reason=reason))
            continue
        if entry.duration_minutes is None or entry.duration_minutes < 0:
            r.unresolved_records.append(ProfitabilityRecord(record_type='time_entry', record_id=entry.id, reason='missing_duration'))
            continue
        hours = Decimal(entry.duration_minutes) / 60
        r.completed_hours += hours
        if entry.billable:
            r.billable_hours += hours
            if entry.hourly_rate is None or not entry.hourly_rate.is_finite():
                r.unresolved_records.append(ProfitabilityRecord(record_type='time_entry', record_id=entry.id, reason='missing_billing_rate'))
            else:
                r.work_value += money(hours * entry.hourly_rate)
        else:
            r.nonbillable_hours += hours
        reason, cost = None, ZERO
        if entry.cost_currency and entry.cost_currency != data.currency:
            reason = 'currency_mismatch'
        elif entry.cost_method == 'hourly':
            if entry.expense_ids:
                reason = 'conflicting_cost_methods'
            elif entry.hourly_cost is None or not entry.hourly_cost.is_finite() or entry.hourly_cost < 0:
                reason = 'missing_hourly_cost'
            else:
                cost = money(hours * entry.hourly_cost)
        elif entry.cost_method == 'supplier_expense':
            if not entry.expense_ids or any(i not in eligible_expenses for i in entry.expense_ids):
                reason = 'unresolved_supplier_expense'
        else:
            reason = 'missing_cost_snapshot'
        if reason:
            r.missing_hours += hours
            r.unresolved_records.append(ProfitabilityRecord(record_type='time_entry', record_id=entry.id, reason=reason))
        labor_cost += cost
        for mapping, key in ((contributors, entry.user_id), (tasks, entry.task_id)):
            bucket = mapping.setdefault(key, ProfitabilityBreakdown(id=key))
            bucket.completed_hours += hours
            bucket.hourly_cost += cost
            bucket.entry_ids.append(entry.id)
            bucket.supplier_expense_ids = sorted(set(bucket.supplier_expense_ids + entry.expense_ids))
    r.contributors = list(contributors.values())
    r.tasks = list(tasks.values())
    r.known_cost = labor_cost + r.expense_bucket.amount
    r.work_value = money(r.work_value)
    r.known_cost = money(r.known_cost)
    if r.unresolved_records:
        r.status = 'incomplete'
    else:
        r.contribution = money(r.work_value - r.known_cost)
        if r.work_value:
            r.margin_percent = percent(r.contribution / r.work_value * 100)
    for label, used, budget, field in (
        ('hours', r.completed_hours, data.budget_hours, 'hours_budget_percent'),
        ('amount', r.work_value, data.budget_amount, 'amount_budget_percent'),
    ):
        if budget is not None and budget > 0:
            raw = used / budget * 100
            setattr(r, field, percent(raw))
            if raw >= 100:
                r.budget_warnings.append(f'{label}_100_percent')
            elif raw >= 80:
                r.budget_warnings.append(f'{label}_80_percent')
    return r
