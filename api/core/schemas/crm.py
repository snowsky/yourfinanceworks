from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ClientNoteBase(BaseModel):
    note: str

class ClientNoteCreate(ClientNoteBase):
    pass

class ClientNote(ClientNoteBase):
    id: int
    user_id: int
    client_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)