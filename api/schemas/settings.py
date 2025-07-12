from pydantic import BaseModel
from typing import Optional

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

class Settings(SettingsBase):
    id: int
    enable_ai_assistant: bool = False
    company_info: CompanyInfo
    invoice_settings: InvoiceSettings

class SettingsUpdate(BaseModel):
    company_info: Optional[CompanyInfo] = None
    invoice_settings: Optional[InvoiceSettings] = None 