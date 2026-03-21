"""
Prompt Improvement Job Model

Tracks AI-assisted prompt improvement sessions initiated from the chat interface.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from sqlalchemy.sql import func
from core.models.models_per_tenant import Base


class PromptImprovementJob(Base):
    """
    Tracks an agentic prompt improvement loop initiated by a user chat message.

    Lifecycle: pending → running → succeeded | exhausted | failed
    """
    __tablename__ = "prompt_improvement_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    tenant_id = Column(Integer, nullable=True)

    # Original user complaint
    user_message = Column(Text, nullable=False)

    # Optional document context
    document_id = Column(Integer, nullable=True)
    document_type = Column(String(50), nullable=True)  # invoice | expense | bank_statement | portfolio

    # Resolved during identification
    prompt_name = Column(String(100), nullable=True)
    prompt_category = Column(String(50), nullable=True)

    # Job state
    status = Column(String(20), nullable=False, default="pending", index=True)
    current_iteration = Column(Integer, default=0)
    max_iterations = Column(Integer, default=5)

    # Per-iteration log: [{iteration, prompt_preview, evaluation, reason}]
    iteration_log = Column(JSON, nullable=True, default=list)

    # Winning prompt (set only on success)
    final_prompt_content = Column(Text, nullable=True)
    final_prompt_version = Column(Integer, nullable=True)

    # Human-readable result for chat display
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_prompt_improvement_jobs_status_created", "status", "created_at"),
    )

    def __repr__(self):
        return (
            f"<PromptImprovementJob(id={self.id}, prompt={self.prompt_name!r}, "
            f"status={self.status!r}, iter={self.current_iteration}/{self.max_iterations})>"
        )
