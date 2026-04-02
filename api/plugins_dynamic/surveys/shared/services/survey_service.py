"""
Business logic for survey operations.
"""
from __future__ import annotations

import csv
import io
import re
import secrets
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from shared.models.surveys import Answer, Question, Survey, SurveyResponse
from shared.schemas.surveys import AnswerSubmit, QuestionCreate, SurveyCreate, SurveyUpdate


def _generate_slug(title: str) -> str:
    """Generate a URL-safe, unique slug from a survey title."""
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    suffix = secrets.token_urlsafe(6)
    return f"{base}-{suffix}" if base else suffix


# ── Survey CRUD ────────────────────────────────────────────────────────────────

def create_survey(db: Session, data: SurveyCreate, created_by: Optional[str] = None) -> Survey:
    slug = _generate_slug(data.title)
    survey = Survey(
        title=data.title,
        description=data.description,
        slug=slug,
        allow_anonymous=data.allow_anonymous,
        expires_at=data.expires_at,
        created_by=created_by,
    )
    db.add(survey)
    db.flush()

    for i, q in enumerate(data.questions):
        db.add(Question(
            survey_id=survey.id,
            order_index=q.order_index or i,
            question_type=q.question_type,
            label=q.label,
            required=q.required,
            options=q.options,
        ))

    db.commit()
    db.refresh(survey)
    return survey


def get_survey(db: Session, survey_id: str) -> Optional[Survey]:
    return db.query(Survey).filter(Survey.id == survey_id).first()


def get_survey_by_slug(db: Session, slug: str) -> Optional[Survey]:
    return db.query(Survey).filter(Survey.slug == slug).first()


def list_surveys(db: Session, skip: int = 0, limit: int = 50) -> List[Survey]:
    return (
        db.query(Survey)
        .order_by(Survey.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_survey(db: Session, survey: Survey, data: SurveyUpdate) -> Survey:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(survey, field, value)
    survey.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(survey)
    return survey


def delete_survey(db: Session, survey: Survey) -> None:
    db.delete(survey)
    db.commit()


def response_count(db: Session, survey_id: str) -> int:
    return db.query(SurveyResponse).filter(SurveyResponse.survey_id == survey_id).count()


# ── Question CRUD ──────────────────────────────────────────────────────────────

def add_question(db: Session, survey: Survey, data: QuestionCreate) -> Question:
    max_order = max((q.order_index for q in survey.questions), default=-1)
    question = Question(
        survey_id=survey.id,
        order_index=data.order_index if data.order_index else max_order + 1,
        question_type=data.question_type,
        label=data.label,
        required=data.required,
        options=data.options,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def update_question(db: Session, question: Question, updates: dict) -> Question:
    for field, value in updates.items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question: Question) -> None:
    db.delete(question)
    db.commit()


# ── Response ───────────────────────────────────────────────────────────────────

def submit_response(
    db: Session,
    survey: Survey,
    answers: List[AnswerSubmit],
    respondent_email: Optional[str] = None,
) -> SurveyResponse:
    response = SurveyResponse(survey_id=survey.id, respondent_email=respondent_email)
    db.add(response)
    db.flush()

    for ans in answers:
        db.add(Answer(response_id=response.id, question_id=ans.question_id, value=ans.value))

    db.commit()
    db.refresh(response)
    return response


def get_responses(db: Session, survey_id: str) -> List[SurveyResponse]:
    return (
        db.query(SurveyResponse)
        .filter(SurveyResponse.survey_id == survey_id)
        .order_by(SurveyResponse.submitted_at.desc())
        .all()
    )


def get_response(db: Session, response_id: str, survey_id: str) -> Optional[SurveyResponse]:
    return (
        db.query(SurveyResponse)
        .filter(SurveyResponse.id == response_id, SurveyResponse.survey_id == survey_id)
        .first()
    )


# ── Export ─────────────────────────────────────────────────────────────────────

def export_responses_csv(survey: Survey, responses: List[SurveyResponse]) -> str:
    """Return all responses for a survey as a CSV string."""
    output = io.StringIO()
    q_labels = {q.id: q.label for q in survey.questions}
    q_ids = [q.id for q in survey.questions]

    fieldnames = ["response_id", "respondent_email", "submitted_at"] + [
        q_labels.get(qid, qid) for qid in q_ids
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for resp in responses:
        answer_map = {a.question_id: a.value for a in resp.answers}
        row: dict = {
            "response_id": resp.id,
            "respondent_email": resp.respondent_email or "",
            "submitted_at": resp.submitted_at.isoformat(),
        }
        for qid in q_ids:
            val = answer_map.get(qid, "")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            row[q_labels.get(qid, qid)] = "" if val is None else val
        writer.writerow(row)

    return output.getvalue()
