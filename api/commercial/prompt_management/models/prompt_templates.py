"""
Prompt Templates Model

Centralized model for managing AI LLM prompts that can be customized
by administrators and users.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.models.models_per_tenant import Base


class PromptTemplate(Base):
    """
    Model for storing customizable AI prompts.
    
    Allows administrators to modify AI behavior without code changes.
    """
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # invoice, bank_statement, email, etc.
    description = Column(Text, nullable=True)
    
    # Template content with variable placeholders
    template_content = Column(Text, nullable=False)
    
    # Variables that can be used in the template (JSON array)
    template_variables = Column(JSON, nullable=True)
    
    # Expected output format (json, text, markdown, etc.)
    output_format = Column(String(20), default="json")
    
    # Default values for variables
    default_values = Column(JSON, nullable=True)
    
    # Versioning
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    
    # Provider-specific overrides (optional)
    provider_overrides = Column(JSON, nullable=True)  # {"openai": "...", "ollama": "..."}
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, nullable=True)  # User ID from tenant context
    updated_by = Column(Integer, nullable=True)  # User ID from tenant context
    
    def __repr__(self):
        return f"<PromptTemplate(name='{self.name}', category='{self.category}', version={self.version})>"

    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_prompt_name_version'),
    )


class PromptUsageLog(Base):
    """
    Model for tracking prompt usage and performance.
    """
    __tablename__ = "prompt_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=False)
    
    # Usage context
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True)  # User ID from tenant context
    provider_name = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    
    # Performance metrics
    processing_time_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Input/output samples (for debugging)
    input_preview = Column(Text, nullable=True)  # First 500 chars of input
    output_preview = Column(Text, nullable=True)  # First 500 chars of output
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    template = relationship("PromptTemplate")
    
    def __repr__(self):
        return f"<PromptUsageLog(template_id={self.template_id}, success={self.success})>"
