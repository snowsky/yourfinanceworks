"""
Authenticated survey management endpoints.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

try:
    from ..compat import get_current_user
    from ..database import get_db
    from ..models.surveys import Question
    from ..schemas.surveys import (
        QuestionCreate,
        QuestionOut,
        QuestionUpdate,
        ResponseOut,
        ResponseSummary,
        SurveyCreate,
        SurveyOut,
        SurveySummary,
        SurveyUpdate,
        ShareInternalRequest,
    )
    from ..services.survey_service import (
        add_question,
        create_survey,
        delete_question,
        delete_survey,
        export_responses_csv,
        get_response,
        get_responses,
        get_survey,
        list_surveys,
        update_question,
        update_survey,
        response_count,
    )
except (ImportError, ValueError):
    from shared.compat import get_current_user
    from shared.database import get_db
    from shared.models.surveys import Question
    from shared.schemas.surveys import (
        QuestionCreate,
        QuestionOut,
        QuestionUpdate,
        ResponseOut,
        ResponseSummary,
        SurveyCreate,
        SurveyOut,
        SurveySummary,
        SurveyUpdate,
        ShareInternalRequest,
    )
    from shared.services.survey_service import (
        add_question,
        create_survey,
        delete_question,
        delete_survey,
        export_responses_csv,
        get_response,
        get_responses,
        get_survey,
        list_surveys,
        update_question,
        update_survey,
        response_count,
    )

router = APIRouter()


def _survey_or_404(survey_id: str, db: Session):
    survey = get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return survey


def _question_or_404(question_id: str, survey_id: str, db: Session):
    q = db.query(Question).filter(
        Question.id == question_id, Question.survey_id == survey_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


# ── Surveys ────────────────────────────────────────────────────────────────────

@router.post("", response_model=SurveyOut, status_code=201)
def create(body: SurveyCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    created_by = getattr(user, "email", None)
    survey = create_survey(db, body, created_by=created_by)
    survey.response_count = 0
    return survey


@router.get("", response_model=list[SurveySummary])
def list_all(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    surveys = list_surveys(db, skip=skip, limit=limit)
    for s in surveys:
        s.response_count = response_count(db, s.id)
    return surveys


@router.get("/{survey_id}", response_model=SurveyOut)
def get_one(survey_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    survey = _survey_or_404(survey_id, db)
    survey.response_count = response_count(db, survey_id)
    return survey


@router.put("/{survey_id}", response_model=SurveyOut)
def update(
    survey_id: str,
    body: SurveyUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    survey = _survey_or_404(survey_id, db)
    survey = update_survey(db, survey, body)
    survey.response_count = response_count(db, survey_id)
    return survey


@router.delete("/{survey_id}", status_code=204)
def delete(survey_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    survey = _survey_or_404(survey_id, db)
    delete_survey(db, survey)


# ── Questions ──────────────────────────────────────────────────────────────────

@router.post("/{survey_id}/questions", response_model=QuestionOut, status_code=201)
def add_q(
    survey_id: str,
    body: QuestionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    survey = _survey_or_404(survey_id, db)
    return add_question(db, survey, body)


@router.put("/{survey_id}/questions/{question_id}", response_model=QuestionOut)
def update_q(
    survey_id: str,
    question_id: str,
    body: QuestionUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _survey_or_404(survey_id, db)
    question = _question_or_404(question_id, survey_id, db)
    return update_question(db, question, body.model_dump(exclude_unset=True))


@router.delete("/{survey_id}/questions/{question_id}", status_code=204)
def delete_q(
    survey_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _survey_or_404(survey_id, db)
    question = _question_or_404(question_id, survey_id, db)
    delete_question(db, question)


# ── Responses ──────────────────────────────────────────────────────────────────

@router.get("/{survey_id}/responses", response_model=list[ResponseSummary])
def list_responses(
    survey_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _survey_or_404(survey_id, db)
    return get_responses(db, survey_id)


@router.get("/{survey_id}/responses/{response_id}", response_model=ResponseOut)
def get_one_response(
    survey_id: str,
    response_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _survey_or_404(survey_id, db)
    resp = get_response(db, response_id, survey_id)
    if not resp:
        raise HTTPException(status_code=404, detail="Response not found")
    return resp


@router.get("/{survey_id}/export")
def export_csv(
    survey_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    survey = _survey_or_404(survey_id, db)
    responses = get_responses(db, survey_id)
    csv_content = export_responses_csv(survey, responses)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="survey-{survey_id}-responses.csv"'
        },
    )


@router.post("/{survey_id}/share-internal")
async def share_internal(
    survey_id: str,
    body: ShareInternalRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Share a survey internally to specific tenants."""
    survey = _survey_or_404(survey_id, db)

    # 1. Authorization check in master database
    try:
        from core.models.database import SessionLocal as MasterSessionLocal
        from core.models.models import user_tenant_association
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Internal sharing is only available when running as a plugin.",
        )

    master_db = MasterSessionLocal()
    try:
        for tenant_id in body.tenant_ids:
            # Primary tenant: role is stored directly on the user object
            if tenant_id == current_user.tenant_id:
                if current_user.role != "admin":
                    raise HTTPException(
                        status_code=403,
                        detail=f"You are not an admin in organization {tenant_id}",
                    )
                continue

            # Additional tenants: look up in user_tenant_association
            membership = master_db.execute(
                select(user_tenant_association.c.role).where(
                    and_(
                        user_tenant_association.c.user_id == current_user.id,
                        user_tenant_association.c.tenant_id == tenant_id,
                    )
                )
            ).fetchone()

            if not membership or membership.role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail=f"You are not an admin in organization {tenant_id}",
                )
    finally:
        master_db.close()

    # 2. Run reminder creation in background
    background_tasks.add_task(
        _create_tenant_reminders,
        survey_id=survey.id,
        survey_title=survey.title,
        survey_slug=survey.slug,
        tenant_ids=body.tenant_ids,
        created_by_id=current_user.id,
        due_date=body.due_date,
    )

    return {"message": "Sharing process started", "status": "processing"}


def _create_tenant_reminders(
    survey_id: str,
    survey_title: str,
    survey_slug: str,
    tenant_ids: List[int],
    created_by_id: int,
    due_date: datetime | None,
):
    """Background task to create reminders for all users in target tenants."""
    from core.models.models_per_tenant import (
        RecurrencePattern,
        Reminder,
        ReminderPriority,
        ReminderStatus,
        User as TenantUser,
    )
    from core.services.tenant_database_manager import tenant_db_manager
    try:
        from config import config
        ui_base_url = getattr(config, "UI_BASE_URL", "http://localhost:8080")
    except ImportError:
        ui_base_url = "http://localhost:8080"
    survey_url = f"{ui_base_url}/surveys/{survey_slug}"

    for tenant_id in tenant_ids:
        try:
            SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
            tenant_db = SessionLocal_tenant()
            try:
                # Find all active users in this tenant
                users = tenant_db.query(TenantUser).filter(TenantUser.is_active == True).all()

                # Get user ID in this tenant — if the master user id doesn't exist, we skip or use a system user
                # But per requirements, the admin is in these orgs, so the ID should match.
                # However, for safety, we'll verify or just use a valid tenant user as creator.
                tenant_admin = tenant_db.query(TenantUser).filter(TenantUser.id == created_by_id).first()
                if not tenant_admin:
                    # Fallback to the first active user if we can't find the admin in this tenant
                    tenant_admin = tenant_db.query(TenantUser).filter(TenantUser.is_active == True).first()

                if not tenant_admin:
                    logging.warning(f"No active users found in tenant {tenant_id}, skipping reminders.")
                    return

                for user in users:
                    reminder = Reminder(
                        title=f"Survey: {survey_title}",
                        description=f"Please complete this survey: {survey_url}",
                        due_date=due_date or datetime.now(timezone.utc),
                        status=ReminderStatus.PENDING,
                        priority=ReminderPriority.MEDIUM,
                        created_by_id=tenant_admin.id,
                        assigned_to_id=user.id,
                        recurrence_pattern=RecurrencePattern.NONE,
                    )
                    tenant_db.add(reminder)
                tenant_db.commit()
            finally:
                tenant_db.close()
        except Exception as e:
            logging.error(f"Failed to create reminders for tenant {tenant_id}: {e}")
