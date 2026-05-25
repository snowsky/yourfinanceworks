"""Net-worth snapshot model.

Each ``NetWorthSnapshot`` row is one account's balance at one point in time.
A "snapshot run" writes many rows with the same ``snapshot_date`` — one per
bank account, one per investment portfolio, one per liability — and the
summary view sums them at read time.
"""

from enum import Enum

from sqlalchemy import Column, Date, DateTime, Float, Index, Integer, String
from sqlalchemy.sql import func

from core.models.models_per_tenant import Base


class AccountKind(str, Enum):
    BANK = "bank"
    INVESTMENT = "investment"
    LIABILITY = "liability"


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    snapshot_date = Column(Date, nullable=False, index=True)
    account_kind = Column(String(32), nullable=False, index=True)
    # ID of the source row in its native table (BankStatement.id,
    # InvestmentPortfolio.id, FinancialLiability.id). Nullable for synthetic
    # bank "accounts" identified only by bank_name.
    account_ref = Column(Integer, nullable=True)
    label = Column(String(200), nullable=False)

    balance = Column(Float, nullable=False, default=0.0)
    currency = Column(String(8), nullable=False, default="USD")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_net_worth_snapshots_date_kind",
            "snapshot_date",
            "account_kind",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NetWorthSnapshot(date={self.snapshot_date}, "
            f"kind='{self.account_kind}', label='{self.label}', "
            f"balance={self.balance})>"
        )
