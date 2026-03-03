from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any, Literal


class TimelineEvent(BaseModel):
    """A single event in the client activity timeline."""
    id: str
    event_type: Literal["invoice", "payment", "expense", "bank_transaction", "note"]
    title: str
    description: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    date: str  # ISO 8601
    source: Literal["invoice", "expense", "bank_statement", "note"]
    metadata: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class TimelineResponse(BaseModel):
    """Paginated timeline response."""
    events: List[TimelineEvent]
    total: int
    page: int
    page_size: int
    has_more: bool

    model_config = ConfigDict(from_attributes=True)
