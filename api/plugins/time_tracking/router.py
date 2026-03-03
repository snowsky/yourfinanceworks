"""
Time Tracking Plugin — FastAPI Routers

Two APIRouter instances:
  - projects_router  (mounted at /api/v1/projects)
  - time_entries_router (mounted at /api/v1/time-entries)

All routes require authentication via `get_current_user`.
Multi-tenant isolation is via `get_db` which returns the tenant-specific DB session.

Excel export uses openpyxl, matching the pattern in core/services/report_exporter.py.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Client, Invoice, InvoiceItem, Expense
from core.utils.audit import log_audit_event

from .models import Project, ProjectTask, TimeEntry
from .schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectTaskCreate, ProjectTaskUpdate, ProjectTaskResponse,
    TimeEntryCreate, TimeEntryUpdate, TimeEntryResponse,
    TimerStartRequest, TimerStopRequest, TimerActiveResponse,
    ProjectSummaryResponse, UnbilledItemsResponse,
    UnbilledTimeEntry, UnbilledExpense,
    ProjectInvoiceRequest, ProjectInvoiceResponse,
    TimeExportFilters, TimeExportRow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enrich_project(project: Project, db: Session) -> dict:
    """Add client_name and aggregated stats to a project dict."""
    client = db.query(Client).filter(Client.id == project.client_id).first()
    hours_agg = (
        db.query(func.sum(TimeEntry.duration_minutes))
        .filter(TimeEntry.project_id == project.id, TimeEntry.status != "in_progress")
        .scalar()
    ) or 0
    amount_agg = (
        db.query(func.sum(TimeEntry.amount))
        .filter(TimeEntry.project_id == project.id, TimeEntry.invoiced == False)  # noqa: E712
        .scalar()
    ) or 0.0

    data = {
        "id": project.id,
        "client_id": project.client_id,
        "name": project.name,
        "description": project.description,
        "billing_method": project.billing_method,
        "fixed_amount": project.fixed_amount,
        "budget_hours": project.budget_hours,
        "budget_amount": project.budget_amount,
        "status": project.status,
        "currency": project.currency,
        "created_by": project.created_by,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "client_name": client.name if client else None,
        "total_hours_logged": round(hours_agg / 60.0, 2) if hours_agg else 0.0,
        "total_amount_logged": round(float(amount_agg), 2),
    }
    return data


def _enrich_time_entry(entry: TimeEntry, db: Session) -> dict:
    """Add project_name, task_name, client_name to a time entry dict."""
    project = db.query(Project).filter(Project.id == entry.project_id).first()
    task = db.query(ProjectTask).filter(ProjectTask.id == entry.task_id).first() if entry.task_id else None
    client = db.query(Client).filter(Client.id == entry.client_id).first() if entry.client_id else None
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "task_id": entry.task_id,
        "user_id": entry.user_id,
        "client_id": entry.client_id,
        "description": entry.description,
        "notes": entry.notes,
        "started_at": entry.started_at,
        "ended_at": entry.ended_at,
        "duration_minutes": entry.duration_minutes,
        "hourly_rate": entry.hourly_rate,
        "billable": entry.billable,
        "amount": entry.amount,
        "status": entry.status,
        "invoiced": entry.invoiced,
        "invoice_id": entry.invoice_id,
        "invoice_number": entry.invoice_number,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
        "hours": entry.hours,
        "project_name": project.name if project else None,
        "task_name": task.name if task else None,
        "client_name": client.name if client else None,
    }


# ---------------------------------------------------------------------------
# Projects Router
# ---------------------------------------------------------------------------

projects_router = APIRouter()


@projects_router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Create a new project linked to a client."""
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    project = Project(
        **payload.model_dump(),
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="project",
        resource_id=str(project.id),
        resource_name=project.name,
        details=payload.model_dump(),
        status="success"
    )

    return _enrich_project(project, db)


@projects_router.get("", response_model=List[ProjectResponse])
def list_projects(
    status: Optional[str] = Query(None),
    client_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """List all projects with optional filters."""
    q = db.query(Project)
    if status:
        q = q.filter(Project.status == status)
    if client_id:
        q = q.filter(Project.client_id == client_id)
    projects = q.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    return [_enrich_project(p, db) for p in projects]


@projects_router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _enrich_project(project, db)


@projects_router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="project",
        resource_id=str(project.id),
        resource_name=project.name,
        details=payload.model_dump(exclude_unset=True),
        status="success"
    )

    return _enrich_project(project, db)


@projects_router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Soft-delete: sets status to 'archived'."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = "archived"
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="project",
        resource_id=str(project.id),
        resource_name=project.name,
        details={"status": "archived"},
        status="success"
    )


@projects_router.get("/{project_id}/summary", response_model=ProjectSummaryResponse)
def get_project_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return KPI summary for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = db.query(Client).filter(Client.id == project.client_id).first()

    # Aggregate time entries (logged/approved only, not in_progress)
    total_minutes = (
        db.query(func.sum(TimeEntry.duration_minutes))
        .filter(TimeEntry.project_id == project_id, TimeEntry.status != "in_progress")
        .scalar()
    ) or 0
    total_amount = (
        db.query(func.sum(TimeEntry.amount))
        .filter(TimeEntry.project_id == project_id, TimeEntry.status != "in_progress")
        .scalar()
    ) or 0.0
    total_expenses = (
        db.query(func.sum(Expense.amount))
        .filter(getattr(Expense, "project_id", None) == project_id)
        .scalar()
    ) or 0.0

    # Unbilled
    unbilled_minutes = (
        db.query(func.sum(TimeEntry.duration_minutes))
        .filter(
            TimeEntry.project_id == project_id,
            TimeEntry.invoiced == False,  # noqa: E712
            TimeEntry.status != "in_progress",
        )
        .scalar()
    ) or 0
    unbilled_amount = (
        db.query(func.sum(TimeEntry.amount))
        .filter(
            TimeEntry.project_id == project_id,
            TimeEntry.invoiced == False,  # noqa: E712
            TimeEntry.status != "in_progress",
        )
        .scalar()
    ) or 0.0

    total_hours = round(total_minutes / 60.0, 2)
    unbilled_hours = round(unbilled_minutes / 60.0, 2)

    hours_pct = None
    if project.budget_hours and project.budget_hours > 0:
        hours_pct = round((total_hours / project.budget_hours) * 100, 1)

    budget_pct = None
    if project.budget_amount and project.budget_amount > 0:
        budget_pct = round((float(total_amount) / project.budget_amount) * 100, 1)

    return ProjectSummaryResponse(
        project_id=project.id,
        project_name=project.name,
        client_id=project.client_id,
        client_name=client.name if client else None,
        status=project.status,
        billing_method=project.billing_method,
        budget_hours=project.budget_hours,
        budget_amount=project.budget_amount,
        total_hours_logged=total_hours,
        total_amount_logged=round(float(total_amount), 2),
        total_expenses=round(float(total_expenses), 2),
        unbilled_hours=unbilled_hours,
        unbilled_amount=round(float(unbilled_amount), 2),
        hours_used_pct=hours_pct,
        budget_used_pct=budget_pct,
    )


@projects_router.get("/{project_id}/unbilled", response_model=UnbilledItemsResponse)
def get_unbilled_items(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return all unbilled time entries and expenses for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    entries = (
        db.query(TimeEntry)
        .filter(
            TimeEntry.project_id == project_id,
            TimeEntry.invoiced == False,  # noqa: E712
            TimeEntry.status != "in_progress",
        )
        .all()
    )

    # Expenses tagged to this project — handles case where project_id column may not exist
    expenses = []
    try:
        expenses = (
            db.query(Expense)
            .filter(
                getattr(Expense, "project_id") == project_id,  # noqa: B009
                getattr(Expense, "invoiced", False) == False,  # noqa: E712,B009
            )
            .all()
        )
    except Exception:
        pass

    time_items = []
    for e in entries:
        task = db.query(ProjectTask).filter(ProjectTask.id == e.task_id).first() if e.task_id else None
        time_items.append(
            UnbilledTimeEntry(
                id=e.id,
                task_name=task.name if task else None,
                description=e.description,
                started_at=e.started_at,
                hours=e.hours,
                hourly_rate=e.hourly_rate,
                amount=e.amount or 0.0,
                billable=e.billable,
            )
        )

    expense_items = [
        UnbilledExpense(
            id=exp.id,
            category=getattr(exp, "category", None),
            vendor=getattr(exp, "vendor", None),
            expense_date=str(getattr(exp, "expense_date", "")),
            amount=float(getattr(exp, "amount", 0) or 0),
            currency=getattr(exp, "currency", None),
        )
        for exp in expenses
    ]

    total_time = sum(i.amount for i in time_items)
    total_expense = sum(i.amount for i in expense_items)

    return UnbilledItemsResponse(
        project_id=project_id,
        time_entries=time_items,
        expenses=expense_items,
        total_time_amount=round(total_time, 2),
        total_expense_amount=round(total_expense, 2),
        grand_total=round(total_time + total_expense, 2),
    )


@projects_router.post("/{project_id}/invoice", response_model=ProjectInvoiceResponse, status_code=201)
def create_invoice_from_project(
    project_id: int,
    payload: ProjectInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Generate an invoice from selected unbilled time entries and expenses."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not payload.time_entry_ids and not payload.expense_ids:
        raise HTTPException(status_code=400, detail="No items selected for invoicing")

    # Fetch selected time entries
    time_entries = (
        db.query(TimeEntry)
        .filter(
            TimeEntry.id.in_(payload.time_entry_ids),
            TimeEntry.project_id == project_id,
            TimeEntry.invoiced == False,  # noqa: E712
        )
        .all()
    )

    expenses = []
    if payload.expense_ids:
        try:
            expenses = (
                db.query(Expense)
                .filter(
                    Expense.id.in_(payload.expense_ids),
                    getattr(Expense, "project_id") == project_id,  # noqa: B009
                )
                .all()
            )
        except Exception:
            pass

    # Build invoice line items
    line_items = []
    total = 0.0

    for entry in time_entries:
        amount = entry.amount or 0.0
        line_items.append({
            "description": f"{entry.description or 'Time'} ({entry.hours:.2f}h @ {entry.hourly_rate}/hr)",
            "quantity": entry.hours,
            "price": entry.hourly_rate,
            "amount": amount,
        })
        total += amount

    for exp in expenses:
        amt = float(getattr(exp, "amount", 0) or 0)
        line_items.append({
            "description": f"Expense: {getattr(exp, 'vendor', '') or ''} - {getattr(exp, 'category', '')}",
            "quantity": 1,
            "price": amt,
            "amount": amt,
        })
        total += amt

    if not line_items:
        raise HTTPException(status_code=400, detail="No valid items found to invoice")

    # Generate invoice number
    existing_count = db.query(Invoice).count()
    invoice_number = f"INV-{existing_count + 1:05d}"

    now = datetime.now(timezone.utc)
    due_date_str = payload.due_date or now.strftime("%Y-%m-%d")
    due_date = datetime.strptime(due_date_str, "%Y-%m-%d") if isinstance(due_date_str, str) else due_date_str

    invoice = Invoice(
        number=invoice_number,
        client_id=project.client_id,
        due_date=due_date,
        amount=round(total, 2),
        subtotal=round(total, 2),
        currency=project.currency,
        status="pending",
        notes=payload.notes or f"Generated from project: {project.name}",
        created_at=now,
        updated_at=now,
        created_by_user_id=current_user.id
    )
    db.add(invoice)
    db.flush()  # get invoice.id

    # Add line items
    for item in line_items:
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            description=item["description"],
            quantity=item["quantity"],
            price=item["price"],
            amount=item["amount"],
        ))

    # Mark time entries as invoiced
    for entry in time_entries:
        entry.invoiced = True
        entry.invoice_id = invoice.id
        entry.invoice_number = invoice_number
        entry.status = "invoiced"
        entry.updated_at = now

    # Mark expenses as invoiced (if column exists)
    for exp in expenses:
        try:
            exp.invoiced = True
            exp.invoice_id = invoice.id
        except Exception:
            pass

    db.commit()
    db.refresh(invoice)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="invoice",
        resource_id=str(invoice.id),
        resource_name=f"Invoice {invoice.number}",
        details={
            "project_id": project.id,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "due_date": due_date_str,
            "line_items_count": len(line_items)
        },
        status="success"
    )

    return ProjectInvoiceResponse(
        invoice_id=invoice.id,
        invoice_number=invoice.number,
        amount=invoice.amount,
        currency=invoice.currency,
    )


# ---------------------------------------------------------------------------
# Task sub-routes (nested under projects)
# ---------------------------------------------------------------------------

@projects_router.post("/{project_id}/tasks", response_model=ProjectTaskResponse, status_code=201)
def create_task(
    project_id: int,
    payload: ProjectTaskCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = ProjectTask(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        estimated_hours=payload.estimated_hours,
        hourly_rate=payload.hourly_rate,
        status=payload.status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="project_task",
        resource_id=str(task.id),
        resource_name=task.name,
        details=payload.model_dump(),
        status="success"
    )

    return {**task.__dict__, "actual_hours": 0.0}


@projects_router.get("/{project_id}/tasks", response_model=List[ProjectTaskResponse])
def list_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
    results = []
    for task in tasks:
        actual_minutes = (
            db.query(func.sum(TimeEntry.duration_minutes))
            .filter(TimeEntry.task_id == task.id, TimeEntry.status != "in_progress")
            .scalar()
        ) or 0
        results.append({**task.__dict__, "actual_hours": round(actual_minutes / 60.0, 2)})
    return results


@projects_router.patch("/{project_id}/tasks/{task_id}", response_model=ProjectTaskResponse)
def update_task(
    project_id: int,
    task_id: int,
    payload: ProjectTaskUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    task = db.query(ProjectTask).filter(
        ProjectTask.id == task_id,
        ProjectTask.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="project_task",
        resource_id=str(task.id),
        resource_name=task.name,
        details=payload.model_dump(exclude_unset=True),
        status="success"
    )

    actual_minutes = (
        db.query(func.sum(TimeEntry.duration_minutes))
        .filter(TimeEntry.task_id == task_id, TimeEntry.status != "in_progress")
        .scalar()
    ) or 0
    return {**task.__dict__, "actual_hours": round(actual_minutes / 60.0, 2)}


@projects_router.delete("/{project_id}/tasks/{task_id}", status_code=204)
def delete_task(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    task = db.query(ProjectTask).filter(
        ProjectTask.id == task_id,
        ProjectTask.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="project_task",
        resource_id=str(task_id),
        resource_name=task.name,
        status="success"
    )


# ---------------------------------------------------------------------------
# Time Entries Router
# ---------------------------------------------------------------------------

time_entries_router = APIRouter()


# ---- IMPORTANT: static paths first, THEN /{entry_id} ----

@time_entries_router.post("/timer/start", response_model=TimeEntryResponse, status_code=201)
def timer_start(
    payload: TimerStartRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Start the live timer. Only one active timer per user is allowed."""
    # Check for an already-running timer
    existing = (
        db.query(TimeEntry)
        .filter(TimeEntry.user_id == current_user.id, TimeEntry.status == "in_progress")
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="A timer is already running. Stop it first.")

    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.now(timezone.utc)
    started = payload.started_at or now

    entry = TimeEntry(
        project_id=payload.project_id,
        task_id=payload.task_id,
        user_id=current_user.id,
        client_id=project.client_id,
        description=payload.description,
        hourly_rate=payload.hourly_rate,
        billable=payload.billable,
        started_at=started,
        ended_at=None,
        status="in_progress",
        invoiced=False,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="START",
        resource_type="timer",
        resource_id=str(entry.id),
        resource_name=f"Timer for Project {payload.project_id}",
        details=payload.model_dump(),
        status="success"
    )

    return _enrich_time_entry(entry, db)


@time_entries_router.post("/timer/stop", response_model=TimeEntryResponse)
def timer_stop(
    payload: TimerStopRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Stop the active timer, compute duration and amount."""
    entry = (
        db.query(TimeEntry)
        .filter(TimeEntry.user_id == current_user.id, TimeEntry.status == "in_progress")
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="No active timer found")

    now = datetime.now(timezone.utc)
    ended = payload.ended_at or now

    # Compute duration
    delta = ended - entry.started_at
    entry.ended_at = ended
    entry.duration_minutes = max(1, int(delta.total_seconds() / 60))
    entry.notes = payload.notes
    entry.status = "logged"
    entry.updated_at = now
    entry.compute_amount()

    db.commit()
    db.refresh(entry)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="STOP",
        resource_type="timer",
        resource_id=str(entry.id),
        resource_name=f"Timer for Project {entry.project_id}",
        details={
            "duration_minutes": entry.duration_minutes,
            "amount": entry.amount,
            "notes": entry.notes
        },
        status="success"
    )

    return _enrich_time_entry(entry, db)


@time_entries_router.get("/timer/active", response_model=TimerActiveResponse)
def timer_active(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Return the currently active timer for the current user (if any)."""
    entry = (
        db.query(TimeEntry)
        .filter(TimeEntry.user_id == current_user.id, TimeEntry.status == "in_progress")
        .order_by(TimeEntry.started_at.desc())
        .first()
    )
    if not entry:
        return TimerActiveResponse(active=False, entry=None, elapsed_seconds=None)

    now = datetime.now(timezone.utc)
    started = entry.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed = int((now - started).total_seconds())

    enriched = _enrich_time_entry(entry, db)
    return TimerActiveResponse(
        active=True,
        entry=TimeEntryResponse(**enriched),
        elapsed_seconds=elapsed,
    )


@time_entries_router.get("/export/monthly")
def export_monthly(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    project_id: Optional[int] = Query(None),
    client_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    billable_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """
    Export a monthly time report as a .xlsx file.
    Sheet 1: Time Log (one row per entry)
    Sheet 2: Summary (totals by project)
    """
    from calendar import monthrange
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    _, last_day = monthrange(year, month)
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
    end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    q = (
        db.query(TimeEntry)
        .filter(
            TimeEntry.started_at >= start_dt,
            TimeEntry.started_at <= end_dt,
            TimeEntry.status != "in_progress",
        )
    )
    if project_id:
        q = q.filter(TimeEntry.project_id == project_id)
    if client_id:
        q = q.filter(TimeEntry.client_id == client_id)
    if user_id:
        q = q.filter(TimeEntry.user_id == user_id)
    if billable_only:
        q = q.filter(TimeEntry.billable == True)  # noqa: E712

    entries = q.order_by(TimeEntry.started_at.asc()).all()

    # Build row data
    rows: list[TimeExportRow] = []
    project_totals: dict[str, dict] = {}

    for entry in entries:
        project = db.query(Project).filter(Project.id == entry.project_id).first()
        task = db.query(ProjectTask).filter(ProjectTask.id == entry.task_id).first() if entry.task_id else None
        client = db.query(Client).filter(Client.id == entry.client_id).first() if entry.client_id else None

        proj_name = project.name if project else f"Project {entry.project_id}"
        client_name = client.name if client else f"Client {entry.client_id}"

        row = TimeExportRow(
            date=entry.started_at.strftime("%Y-%m-%d"),
            client_id=entry.client_id,
            client_name=client_name,
            project_name=proj_name,
            task_name=task.name if task else None,
            description=entry.description,
            notes=entry.notes,
            hours=entry.hours,
            hourly_rate=entry.hourly_rate,
            amount=entry.amount or 0.0,
            billable=entry.billable,
            status=entry.status,
            invoiced=entry.invoiced,
            invoice_number=entry.invoice_number,
        )
        rows.append(row)

        # Accumulate summary by project
        if proj_name not in project_totals:
            project_totals[proj_name] = {"hours": 0.0, "amount": 0.0, "client": client_name}
        project_totals[proj_name]["hours"] += entry.hours
        project_totals[proj_name]["amount"] += entry.amount or 0.0

    # Build Excel workbook
    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    # --- Sheet 1: Time Log ---
    ws = wb.create_sheet(title="Time Log")
    headers = [
        "Date", "Client ID", "Client Name", "Project", "Task",
        "Description", "Notes", "Hours", "Hourly Rate", "Amount",
        "Billable", "Status", "Invoiced", "Invoice #"
    ]
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    for row_idx, row in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=row.date)
        ws.cell(row=row_idx, column=2, value=row.client_id)
        ws.cell(row=row_idx, column=3, value=row.client_name)
        ws.cell(row=row_idx, column=4, value=row.project_name)
        ws.cell(row=row_idx, column=5, value=row.task_name)
        ws.cell(row=row_idx, column=6, value=row.description)
        ws.cell(row=row_idx, column=7, value=row.notes)
        ws.cell(row=row_idx, column=8, value=round(row.hours, 2))
        ws.cell(row=row_idx, column=9, value=row.hourly_rate)
        ws.cell(row=row_idx, column=10, value=round(row.amount, 2))
        ws.cell(row=row_idx, column=11, value="Yes" if row.billable else "No")
        ws.cell(row=row_idx, column=12, value=row.status)
        ws.cell(row=row_idx, column=13, value="Yes" if row.invoiced else "No")
        ws.cell(row=row_idx, column=14, value=row.invoice_number)

        # Alternating row colors
        if row_idx % 2 == 0:
            row_fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = row_fill

    # Auto-width columns
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value and len(str(cell.value)) > max_len:
                    max_len = len(str(cell.value))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    # Totals row
    total_row = len(rows) + 2
    ws.cell(row=total_row, column=7, value="TOTAL").font = Font(bold=True)
    ws.cell(row=total_row, column=8, value=round(sum(r.hours for r in rows), 2)).font = Font(bold=True)
    ws.cell(row=total_row, column=10, value=round(sum(r.amount for r in rows), 2)).font = Font(bold=True)

    # --- Sheet 2: Summary ---
    ws2 = wb.create_sheet(title="Summary")
    ws2["A1"] = f"Time Report — {year}-{month:02d}"
    ws2["A1"].font = Font(size=14, bold=True)

    ws2["A3"] = "Project"
    ws2["B3"] = "Client"
    ws2["C3"] = "Total Hours"
    ws2["D3"] = "Total Amount"
    for col in ["A3", "B3", "C3", "D3"]:
        ws2[col].font = Font(bold=True)
        ws2[col].fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
        ws2[col].font = Font(bold=True, color="FFFFFF")

    for i, (proj_name, data) in enumerate(project_totals.items(), 4):
        ws2.cell(row=i, column=1, value=proj_name)
        ws2.cell(row=i, column=2, value=data["client"])
        ws2.cell(row=i, column=3, value=round(data["hours"], 2))
        ws2.cell(row=i, column=4, value=round(data["amount"], 2))

    for col in ws2.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value and len(str(cell.value)) > max_len:
                    max_len = len(str(cell.value))
            except Exception:
                pass
        ws2.column_dimensions[col_letter].width = min(max_len + 2, 40)

    # Serialize to bytes
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    excel_bytes = buffer.getvalue()
    buffer.close()

    filename = f"time_report_{year}_{month:02d}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---- Standard CRUD (AFTER static paths) ----

@time_entries_router.post("", response_model=TimeEntryResponse, status_code=201)
def create_time_entry(
    payload: TimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Manually log a time entry (not a timer start)."""
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.now(timezone.utc)

    # Compute duration if ended_at is provided and duration_minutes is not
    duration_minutes = payload.duration_minutes
    ended_at = payload.ended_at
    if ended_at and duration_minutes is None:
        delta = ended_at - payload.started_at
        duration_minutes = max(1, int(delta.total_seconds() / 60))

    entry = TimeEntry(
        project_id=payload.project_id,
        task_id=payload.task_id,
        user_id=current_user.id,
        client_id=project.client_id,
        description=payload.description,
        notes=payload.notes,
        started_at=payload.started_at,
        ended_at=ended_at,
        duration_minutes=duration_minutes,
        hourly_rate=payload.hourly_rate,
        billable=payload.billable,
        status="logged",
        invoiced=False,
        created_at=now,
        updated_at=now,
    )
    entry.compute_amount()
    db.add(entry)
    db.commit()
    db.refresh(entry)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="time_entry",
        resource_id=str(entry.id),
        resource_name=f"Time Log for Project {payload.project_id}",
        details=payload.model_dump(),
        status="success"
    )

    return _enrich_time_entry(entry, db)


@time_entries_router.get("", response_model=List[TimeEntryResponse])
def list_time_entries(
    project_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    client_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    invoiced: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    q = db.query(TimeEntry)
    if project_id:
        q = q.filter(TimeEntry.project_id == project_id)
    if task_id:
        q = q.filter(TimeEntry.task_id == task_id)
    if user_id:
        q = q.filter(TimeEntry.user_id == user_id)
    if client_id:
        q = q.filter(TimeEntry.client_id == client_id)
    if status:
        q = q.filter(TimeEntry.status == status)
    if invoiced is not None:
        q = q.filter(TimeEntry.invoiced == invoiced)
    entries = q.order_by(TimeEntry.started_at.desc()).offset(skip).limit(limit).all()
    return [_enrich_time_entry(e, db) for e in entries]


@time_entries_router.patch("/{entry_id}", response_model=TimeEntryResponse)
def update_time_entry(
    entry_id: int,
    payload: TimeEntryUpdate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    entry = db.query(TimeEntry).filter(TimeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    # Recompute duration from started_at/ended_at if both are set and duration_minutes not explicit
    if entry.started_at and entry.ended_at and "duration_minutes" not in payload.model_dump(exclude_unset=True):
        delta = entry.ended_at - entry.started_at
        entry.duration_minutes = max(1, int(delta.total_seconds() / 60))

    entry.compute_amount()
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="time_entry",
        resource_id=str(entry.id),
        resource_name=f"Time Log for Project {entry.project_id}",
        details=payload.model_dump(exclude_unset=True),
        status="success"
    )

    return _enrich_time_entry(entry, db)


@time_entries_router.delete("/{entry_id}", status_code=204)
def delete_time_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    entry = db.query(TimeEntry).filter(TimeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    db.delete(entry)
    db.commit()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="time_entry",
        resource_id=str(entry_id),
        resource_name=f"Time Log for Project {entry.project_id}",
        status="success"
    )
