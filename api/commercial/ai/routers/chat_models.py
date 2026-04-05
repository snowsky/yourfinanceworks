# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

from typing import Any, Dict, Optional

from pydantic import BaseModel, validator


class ChatRequest(BaseModel):
    message: str
    config_id: int = 0  # Default to 0 if not provided
    page_context: Optional[Dict[str, Any]] = None


class ChatMessageRequest(BaseModel):
    message: str
    sender: str  # 'user' or 'ai'

    @validator('sender')
    def validate_sender(cls, v):
        if v not in ['user', 'ai']:
            raise ValueError('sender must be either "user" or "ai"')
        return v
