from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class PageView(Base):
    __tablename__ = "page_views"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), index=True)
    tenant_id = Column(Integer, index=True)
    path = Column(String(500), index=True)
    method = Column(String(10))
    user_agent = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    response_time_ms = Column(Integer)
    status_code = Column(Integer)
