from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from core.schemas.client import Client


class ClientRecordSummary(BaseModel):
    open_invoices_count: int
    overdue_invoices_count: int
    total_outstanding: float
    total_paid: float
    open_tasks_count: int
    completed_tasks_count: int
    last_payment_at: Optional[datetime] = None
    last_invoice_at: Optional[datetime] = None


class ClientActivityItem(BaseModel):
    type: str
    timestamp: datetime
    title: str
    description: Optional[str] = None
    actor_name: Optional[str] = None
    entity_type: str
    entity_id: str
    metadata: Optional[Dict[str, Any]] = None


class ClientTaskItem(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    due_date: datetime
    status: str
    priority: str
    assigned_to_id: int
    task_origin: Optional[str] = None
    workflow_id: Optional[int] = None


class ClientRecordResponse(BaseModel):
    client: Client
    summary: ClientRecordSummary
    recent_activity: list[ClientActivityItem]
    open_tasks: list[ClientTaskItem]
