from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import WorkflowDefinition
from core.routers.auth import get_current_user
from core.schemas.workflows import (
    WorkflowCatalogResponse,
    WorkflowCreateRequest,
    WorkflowDefinitionResponse,
    WorkflowRunNowResponse,
    WorkflowToggleRequest,
    WorkflowExecutionLogResponse,
    WorkflowExecutionLogListResponse,
    WorkflowUpdateRequest,
)
from core.services.workflow_service import WorkflowService
from core.utils.audit import log_audit_event
from core.utils.feature_gate import require_feature
from core.utils.rbac import require_admin

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("workflow_automation")(lambda: None)())]
)


def _workflow_audit_details(workflow: WorkflowDefinition) -> dict:
    """Compact audit payload — trigger + flags + enabled state, no PII."""
    return {
        "trigger_type": workflow.trigger_type,
        "is_enabled": workflow.is_enabled,
        "is_system": workflow.is_system,
        "actions": workflow.actions or {},
    }


@router.get("/", response_model=list[WorkflowDefinitionResponse])
async def list_workflows(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    return service.list_workflows()


@router.get("/catalog", response_model=WorkflowCatalogResponse)
async def get_workflow_catalog(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    return WorkflowCatalogResponse(**service.get_catalog())


@router.post("/", response_model=WorkflowDefinitionResponse)
async def create_workflow(
    payload: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    try:
        workflow = service.create_workflow(
            name=payload.name,
            description=payload.description,
            trigger_type=payload.trigger_type,
            action_ids=payload.action_ids,
            assigned_user_id=payload.assigned_user_id,
        )
    except ValueError as exc:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="CREATE",
            resource_type="workflow",
            resource_id=None,
            resource_name=payload.name,
            details={
                "trigger_type": payload.trigger_type,
                "action_ids": payload.action_ids,
            },
            status="error",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="CREATE",
        resource_type="workflow",
        resource_id=str(workflow.id),
        resource_name=workflow.name,
        details=_workflow_audit_details(workflow),
    )
    return workflow


@router.post("/{workflow_id}/toggle", response_model=WorkflowDefinitionResponse)
async def toggle_workflow(
    workflow_id: int,
    payload: WorkflowToggleRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    workflow = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    previous_state = workflow.is_enabled
    workflow.is_enabled = payload.is_enabled
    db.commit()
    db.refresh(workflow)

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="TOGGLE",
        resource_type="workflow",
        resource_id=str(workflow.id),
        resource_name=workflow.name,
        details={
            "trigger_type": workflow.trigger_type,
            "previous_enabled": previous_state,
            "new_enabled": workflow.is_enabled,
        },
    )
    return workflow


@router.post("/{workflow_id}/run", response_model=WorkflowRunNowResponse)
async def run_workflow_now(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)

    try:
        result = service.run_workflow_now(workflow_id)
    except ValueError as exc:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="RUN_NOW",
            resource_type="workflow",
            resource_id=str(workflow_id),
            resource_name=None,
            details=None,
            status="error",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="RUN_NOW",
        resource_type="workflow",
        resource_id=str(workflow_id),
        resource_name=None,
        details={
            "processed_count": result["processed_count"],
            "created_task_count": result["created_task_count"],
            "notification_count": result["notification_count"],
            "skipped_count": result["skipped_count"],
            "error_count": len(result["errors"]),
        },
    )

    return WorkflowRunNowResponse(
        workflow_id=workflow_id,
        processed_count=result["processed_count"],
        created_task_count=result["created_task_count"],
        notification_count=result["notification_count"],
        skipped_count=result["skipped_count"],
        errors=result["errors"],
    )


@router.get("/executions", response_model=WorkflowExecutionLogListResponse)
async def list_execution_logs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    return service.list_execution_logs(status=status, limit=limit, offset=offset)


@router.get("/{workflow_id}/executions", response_model=WorkflowExecutionLogListResponse)
async def list_workflow_execution_logs(
    workflow_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    return service.list_execution_logs(workflow_id=workflow_id, status=status, limit=limit, offset=offset)


@router.put("/{workflow_id}", response_model=WorkflowDefinitionResponse)
async def update_workflow(
    workflow_id: int,
    payload: WorkflowUpdateRequest,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    try:
        workflow = service.update_workflow(
            workflow_id=workflow_id,
            name=payload.name,
            description=payload.description,
            action_ids=payload.action_ids,
            assigned_user_id=payload.assigned_user_id,
        )
    except ValueError as exc:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="workflow",
            resource_id=str(workflow_id),
            resource_name=payload.name,
            details={"action_ids": payload.action_ids},
            status="error",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="workflow",
        resource_id=str(workflow.id),
        resource_name=workflow.name,
        details=_workflow_audit_details(workflow),
    )
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    target = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()
    target_name = target.name if target else None
    target_trigger = target.trigger_type if target else None
    try:
        service.delete_workflow(workflow_id)
    except ValueError as exc:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DELETE",
            resource_type="workflow",
            resource_id=str(workflow_id),
            resource_name=target_name,
            details={"trigger_type": target_trigger} if target_trigger else None,
            status="error",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DELETE",
        resource_type="workflow",
        resource_id=str(workflow_id),
        resource_name=target_name,
        details={"trigger_type": target_trigger} if target_trigger else None,
    )
    return None


@router.post("/{workflow_id}/duplicate", response_model=WorkflowDefinitionResponse)
async def duplicate_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    require_admin(current_user)
    service = WorkflowService(db)
    try:
        clone = service.duplicate_workflow(workflow_id)
    except ValueError as exc:
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="DUPLICATE",
            resource_type="workflow",
            resource_id=str(workflow_id),
            resource_name=None,
            details={"source_workflow_id": workflow_id},
            status="error",
            error_message=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="DUPLICATE",
        resource_type="workflow",
        resource_id=str(clone.id),
        resource_name=clone.name,
        details={
            "source_workflow_id": workflow_id,
            **_workflow_audit_details(clone),
        },
    )
    return clone
