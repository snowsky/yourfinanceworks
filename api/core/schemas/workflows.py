from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class WorkflowDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key: str
    description: Optional[str] = None
    trigger_type: str
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    is_enabled: bool
    is_system: bool
    is_default: bool
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkflowToggleRequest(BaseModel):
    is_enabled: bool


class WorkflowRunNowResponse(BaseModel):
    workflow_id: int
    processed_count: int
    created_task_count: int
    notification_count: int
    skipped_count: int
    errors: list[str]
