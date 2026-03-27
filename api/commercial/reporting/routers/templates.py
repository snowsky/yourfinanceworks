"""
Report template management endpoints.

  GET    /templates               — list templates
  POST   /templates               — create template
  PUT    /templates/{template_id} — update template
  DELETE /templates/{template_id} — delete template
"""

import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.utils.feature_gate import require_feature
from core.services.report_template_service import ReportTemplateService
from core.routers.auth import get_current_user
from core.utils.audit import log_audit_event
from core.exceptions.report_exceptions import (
    TemplateValidationError, TemplateAccessError, ReportValidationError
)
from core.schemas.report import (
    ReportType, ReportTemplateCreate, ReportTemplateUpdate,
    ReportTemplate as ReportTemplateSchema, ReportTemplateListResponse
)
from core.constants.error_codes import (
    FAILED_TO_CREATE_TEMPLATE, FAILED_TO_UPDATE_TEMPLATE, FAILED_TO_DELETE_TEMPLATE
)

from ._shared import get_report_service, get_current_non_viewer_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/templates", response_model=ReportTemplateListResponse)
@require_feature("reporting")
async def get_report_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    report_type: ReportType = Query(None),
    include_shared: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get user's report templates with optional filtering."""
    try:
        template_service = ReportTemplateService(db)
        templates = template_service.list_templates(
            user_id=current_user.id,
            report_type=report_type,
            include_shared=include_shared,
            limit=limit,
            offset=skip
        )

        return ReportTemplateListResponse(templates=templates, total=len(templates))

    except Exception as e:
        logger.error(f"Failed to get report templates: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report templates"
        )


@router.post("/templates", response_model=ReportTemplateSchema)
@require_feature("reporting")
async def create_report_template(
    template: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """Create a new report template."""
    try:
        template_service = ReportTemplateService(db)

        report_service = get_report_service(db)
        report_service.validate_filters(template.report_type, template.filters)

        created_template = template_service.create_template(
            template_data=template,
            user_id=current_user.id
        )

        await log_audit_event(
            db, current_user.id, "template_create",
            f"Created report template: {template.name}",
            {"template_id": created_template.id, "report_type": template.report_type}
        )

        return ReportTemplateSchema.model_validate(created_template)

    except (TemplateValidationError, TemplateAccessError) as e:
        logger.warning(f"Template creation error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ReportValidationError as e:
        logger.warning(f"Template validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template validation error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to create report template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_CREATE_TEMPLATE
        )


@router.put("/templates/{template_id}", response_model=ReportTemplateSchema)
@require_feature("reporting")
async def update_report_template(
    template_id: int,
    template: ReportTemplateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """Update an existing report template."""
    try:
        template_service = ReportTemplateService(db)

        try:
            existing_template = template_service.get_template(template_id, current_user.id)
        except TemplateAccessError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report template not found"
            )

        if template.filters is not None:
            report_service = get_report_service(db)
            report_service.validate_filters(existing_template.report_type, template.filters)

        updated_template = template_service.update_template(
            template_id=template_id,
            template_data=template,
            user_id=current_user.id
        )

        await log_audit_event(
            db, current_user.id, "template_update",
            f"Updated report template: {updated_template.name}",
            {"template_id": template_id}
        )

        return ReportTemplateSchema.model_validate(updated_template)

    except (TemplateValidationError, TemplateAccessError) as e:
        logger.warning(f"Template update error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ReportValidationError as e:
        logger.warning(f"Template validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template validation error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Failed to update report template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_UPDATE_TEMPLATE
        )


@router.delete("/templates/{template_id}")
@require_feature("reporting")
async def delete_report_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_non_viewer_user)
):
    """Delete a report template."""
    try:
        template_service = ReportTemplateService(db)

        try:
            existing_template = template_service.get_template(template_id, current_user.id)
        except TemplateAccessError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report template not found"
            )

        template_service.delete_template(template_id, current_user.id)

        await log_audit_event(
            db, current_user.id, "template_delete",
            f"Deleted report template: {existing_template.name}",
            {"template_id": template_id}
        )

        return {"message": "Report template deleted successfully"}

    except (TemplateValidationError, TemplateAccessError) as e:
        logger.warning(f"Template deletion error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete report template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FAILED_TO_DELETE_TEMPLATE
        )
