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
)
from core.services.workflow_service import WorkflowService
from core.utils.feature_gate import require_feature
from core.utils.rbac import require_admin

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(lambda db=Depends(get_db): require_feature("workflow_automation")(lambda: None)())]
)


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
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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

    workflow.is_enabled = payload.is_enabled
    db.commit()
    db.refresh(workflow)
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WorkflowRunNowResponse(
        workflow_id=workflow_id,
        processed_count=result["processed_count"],
        created_task_count=result["created_task_count"],
        notification_count=result["notification_count"],
        skipped_count=result["skipped_count"],
        errors=result["errors"],
    )
