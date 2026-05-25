"""Financial liability model.

A ``FinancialLiability`` represents a debt the user owes — credit card,
loan, mortgage, or other — entered manually since we have no automated
liability source. Liabilities are subtracted from assets to compute net
worth.
"""

from enum import Enum

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from core.models.models_per_tenant import Base


class LiabilityKind(str, Enum):
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"
    OTHER = "other"


class FinancialLiability(Base):
    __tablename__ = "financial_liabilities"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(200), nullable=False)
    kind = Column(
        String(32), nullable=False, default=LiabilityKind.OTHER.value, index=True
    )

    balance = Column(Float, nullable=False, default=0.0)
    currency = Column(String(8), nullable=False, default="USD")
    interest_rate = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialLiability(name='{self.name}', kind='{self.kind}', "
            f"balance={self.balance})>"
        )
