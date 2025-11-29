from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CompanyInfo(BaseModel):
    name: str
    email: str
    phone: str
    address: str
    tax_id: str
    logo: Optional[str] = None

class InvoiceSettings(BaseModel):
    prefix: str
    next_number: str
    terms: str
    notes: Optional[str] = None
    send_copy: bool = True
    auto_reminders: bool = True

class SettingsBase(BaseModel):
    tenant_id: int
    key: str
    value: Optional[dict] = None
    ai_chat_history_retention_days: Optional[int] = 7

class Settings(SettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime
    enable_ai_assistant: bool = False
    company_info: CompanyInfo
    invoice_settings: InvoiceSettings
    timezone: Optional[str] = "UTC"
    model_config = ConfigDict(from_attributes=True)

class SettingsUpdate(BaseModel):
    company_info: Optional[CompanyInfo] = None
    invoice_settings: Optional[InvoiceSettings] = None
    timezone: Optional[str] = None 