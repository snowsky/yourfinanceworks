from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AIConfigBase(BaseModel):
    provider_name: str
    provider_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: str
    is_active: bool = True
    is_default: bool = False

class AIConfigCreate(AIConfigBase):
    pass

class AIConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    provider_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

class AIConfig(AIConfigBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 