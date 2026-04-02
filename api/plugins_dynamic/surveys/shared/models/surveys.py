"""
SQLAlchemy models for yfw-surveys.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from shared.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(String(36), primary_key=True, default=_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    slug = Column(String(120), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    allow_anonymous = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    questions = relationship(
        "Question",
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    responses = relationship(
        "SurveyResponse",
        back_populates="survey",
        cascade="all, delete-orphan",
    )


class Question(Base):
    __tablename__ = "survey_questions"

    id = Column(String(36), primary_key=True, default=_uuid)
    survey_id = Column(String(36), ForeignKey("surveys.id"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False, default=0)
    # text | paragraph | multiple_choice | checkbox | rating | boolean
    question_type = Column(String(50), nullable=False)
    label = Column(Text, nullable=False)
    required = Column(Boolean, default=False, nullable=False)
    # list[str] for choice types; {"min": 1, "max": 5, "label_min": "", "label_max": ""} for rating
    options = Column(JSON, nullable=True)

    survey = relationship("Survey", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(String(36), primary_key=True, default=_uuid)
    survey_id = Column(String(36), ForeignKey("surveys.id"), nullable=False, index=True)
    respondent_email = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    survey = relationship("Survey", back_populates="responses")
    answers = relationship("Answer", back_populates="response", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "survey_answers"

    id = Column(String(36), primary_key=True, default=_uuid)
    response_id = Column(String(36), ForeignKey("survey_responses.id"), nullable=False, index=True)
    question_id = Column(String(36), ForeignKey("survey_questions.id"), nullable=False, index=True)
    # str | list[str] | int | bool depending on question type
    value = Column(JSON, nullable=True)

    response = relationship("SurveyResponse", back_populates="answers")
    question = relationship("Question", back_populates="answers")
