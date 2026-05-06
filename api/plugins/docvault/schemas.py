"""DocVault API schemas."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DocVaultCategory = Literal["credit_card", "ssl_certificate", "id_card", "document", "secret"]


class DocVaultEntryBase(BaseModel):
    category: DocVaultCategory
    title: str = Field(min_length=1, max_length=160)
    owner_name: str | None = None
    issuer: str | None = None
    expiry_date: date | None = None
    issue_date: date | None = None
    public_metadata: dict[str, Any] = Field(default_factory=dict)
    sensitive_payload: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    thumbnail_data_url: str | None = None
    file_name: str | None = None
    file_mime_type: str | None = None
    file_size: int | None = None
    file_data_url: str | None = None


class DocVaultEntryCreate(DocVaultEntryBase):
    pass


class DocVaultEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    owner_name: str | None = None
    issuer: str | None = None
    expiry_date: date | None = None
    issue_date: date | None = None
    public_metadata: dict[str, Any] | None = None
    sensitive_payload: dict[str, Any] | None = None
    notes: str | None = None
    tags: list[str] | None = None
    thumbnail_data_url: str | None = None
    file_name: str | None = None
    file_mime_type: str | None = None
    file_size: int | None = None
    file_data_url: str | None = None


class DocVaultEntryResponse(DocVaultEntryBase):
    id: int
    created_by: int | None = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    expiry_status: str
    days_delta: int | None = None
    alerting: bool = False
    sensitive_available: bool = False

    model_config = {"from_attributes": True}


class DocVaultUnlockRequest(BaseModel):
    factor_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    window: int = Field(default=1, ge=0)


class DocVaultScanRequest(BaseModel):
    category: Literal["credit_card", "id_card"]
    file_name: str | None = None
    image_data_url: str | None = None


class DocVaultScanResponse(BaseModel):
    category: str
    extracted: dict[str, Any]
    confidence: float
    method: str
    requires_confirmation: bool = True
