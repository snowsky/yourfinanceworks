"""
Pydantic schemas for yfw-surveys.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── Question ───────────────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    question_type: str  # text | paragraph | multiple_choice | checkbox | rating | boolean
    label: str
    required: bool = False
    order_index: int = 0
    options: Optional[Any] = None


class QuestionUpdate(BaseModel):
    question_type: Optional[str] = None
    label: Optional[str] = None
    required: Optional[bool] = None
    order_index: Optional[int] = None
    options: Optional[Any] = None


class QuestionOut(BaseModel):
    id: str
    survey_id: str
    question_type: str
    label: str
    required: bool
    order_index: int
    options: Optional[Any] = None

    model_config = {"from_attributes": True}


# ── Survey ─────────────────────────────────────────────────────────────────────

class SurveyCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    allow_anonymous: bool = True
    expires_at: Optional[datetime] = None
    questions: List[QuestionCreate] = []


class SurveyUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    allow_anonymous: Optional[bool] = None
    expires_at: Optional[datetime] = None


class SurveyOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    slug: str
    is_active: bool
    allow_anonymous: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    questions: List[QuestionOut] = []
    response_count: int = 0

    model_config = {"from_attributes": True}


class SurveySummary(BaseModel):
    id: str
    title: str
    slug: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    response_count: int = 0

    model_config = {"from_attributes": True}


# ── Public survey (for respondents, no sensitive fields) ───────────────────────

class PublicSurveyOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    allow_anonymous: bool
    questions: List[QuestionOut] = []

    model_config = {"from_attributes": True}


# ── Submission ─────────────────────────────────────────────────────────────────

class AnswerSubmit(BaseModel):
    question_id: str
    value: Optional[Any] = None


class SurveySubmit(BaseModel):
    respondent_email: Optional[str] = None
    answers: List[AnswerSubmit]


class SubmitResult(BaseModel):
    success: bool
    response_id: str
    message: str


# ── Response detail ────────────────────────────────────────────────────────────

class AnswerOut(BaseModel):
    question_id: str
    value: Optional[Any] = None

    model_config = {"from_attributes": True}


class ResponseOut(BaseModel):
    id: str
    survey_id: str
    respondent_email: Optional[str] = None
    submitted_at: datetime
    answers: List[AnswerOut] = []

    model_config = {"from_attributes": True}


class ResponseSummary(BaseModel):
    id: str
    respondent_email: Optional[str] = None
    submitted_at: datetime

    model_config = {"from_attributes": True}


# ── Sharing & Reminders ────────────────────────────────────────────────────────

class ShareInternalRequest(BaseModel):
    tenant_ids: List[int]
    due_date: Optional[datetime] = None
