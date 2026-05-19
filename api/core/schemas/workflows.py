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


class WorkflowCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str
    action_ids: list[str]


class WorkflowToggleRequest(BaseModel):
    is_enabled: bool


class WorkflowRunNowResponse(BaseModel):
    workflow_id: int
    processed_count: int
    created_task_count: int
    notification_count: int
    skipped_count: int
    errors: list[str]


class WorkflowOption(BaseModel):
    id: str
    label: str
    description: str


class WorkflowCatalogResponse(BaseModel):
    triggers: list[WorkflowOption]
    actions: list[WorkflowOption]


class WorkflowExecutionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    workflow_name: Optional[str] = None
    workflow_key: Optional[str] = None
    event_key: str
    entity_type: str
    entity_id: str
    status: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class WorkflowExecutionLogListResponse(BaseModel):
    total: int
    logs: list[WorkflowExecutionLogResponse]


class WorkflowUpdateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    action_ids: list[str]

