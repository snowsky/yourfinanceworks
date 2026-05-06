"""DocVault tenant models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text

from core.models.models_per_tenant import Base
from core.utils.column_encryptor import EncryptedColumn, EncryptedJSON


class DocVaultEntry(Base):
    __tablename__ = "docvault_entries"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False, index=True)
    title = Column(EncryptedColumn(), nullable=False)
    owner_name = Column(EncryptedColumn(), nullable=True)
    issuer = Column(EncryptedColumn(), nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    issue_date = Column(Date, nullable=True)
    status_override = Column(String, nullable=True)
    public_metadata = Column(JSON, nullable=True)
    sensitive_payload = Column(EncryptedJSON(), nullable=True)
    notes = Column(EncryptedColumn(), nullable=True)
    tags = Column(JSON, nullable=True)
    thumbnail_data_url = Column(Text, nullable=True)
    file_name = Column(EncryptedColumn(), nullable=True)
    file_mime_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    file_data_url = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
