from pydantic import BaseModel
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

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        } 