"""
Public survey endpoints — no authentication required.
Respondents use these routes to view and submit surveys.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.schemas.surveys import PublicSurveyOut, SubmitResult, SurveySubmit
from shared.services.survey_service import get_survey_by_slug, submit_response

router = APIRouter()


def _active_survey_or_error(slug: str, db: Session):
    survey = get_survey_by_slug(db, slug)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    if not survey.is_active:
        raise HTTPException(status_code=410, detail="This survey is no longer accepting responses")
    if survey.expires_at and survey.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="This survey has expired")
    return survey


@router.get("/{slug}", response_model=PublicSurveyOut)
def get_public_survey(slug: str, db: Session = Depends(get_db)):
    """Return the survey form for respondents."""
    return _active_survey_or_error(slug, db)


@router.post("/{slug}/submit", response_model=SubmitResult, status_code=201)
def submit(slug: str, body: SurveySubmit, db: Session = Depends(get_db)):
    """Submit a response to a survey."""
    survey = _active_survey_or_error(slug, db)

    # Enforce non-anonymous surveys
    if not survey.allow_anonymous and not body.respondent_email:
        raise HTTPException(
            status_code=400,
            detail="This survey is not anonymous. Please provide your email address.",
        )

    # Validate required questions are answered
    question_ids = {q.id for q in survey.questions}
    required_ids = {q.id for q in survey.questions if q.required}
    submitted_ids = {a.question_id for a in body.answers if a.value not in (None, "", [])}
    missing = required_ids - submitted_ids
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required answers for {len(missing)} question(s)",
        )

    # Drop answers for questions not in this survey
    valid_answers = [a for a in body.answers if a.question_id in question_ids]

    response = submit_response(
        db,
        survey,
        valid_answers,
        respondent_email=body.respondent_email,
    )
    return SubmitResult(
        success=True,
        response_id=response.id,
        message="Thank you! Your response has been recorded.",
    )
