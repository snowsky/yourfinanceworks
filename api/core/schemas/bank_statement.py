from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class BankStatementTransactionBase(BaseModel):
    """Base schema for bank statement transactions"""
    date: datetime = Field(..., description="Transaction date")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount")
    transaction_type: Optional[str] = Field(None, description="Type of transaction (debit/credit)")
    balance: Optional[float] = Field(None, description="Account balance after transaction")
    category: Optional[str] = Field(None, description="Transaction category")
    invoice_id: Optional[int] = Field(None, description="Linked invoice ID")
    expense_id: Optional[int] = Field(None, description="Linked expense ID")


class BankStatementTransactionResponse(BankStatementTransactionBase):
    """Response schema for bank statement transactions"""
    id: int

    model_config = ConfigDict(from_attributes=True)


class BankStatementBase(BaseModel):
    """Base schema for bank statements"""
    original_filename: str = Field(..., description="Original filename of the uploaded statement")
    stored_filename: Optional[str] = Field(None, description="Stored filename on the server")
    file_path: Optional[str] = Field(None, description="File path on the server")
    status: str = Field("pending", description="Processing status")
    extracted_count: Optional[int] = Field(0, description="Number of transactions extracted")
    labels: Optional[List[str]] = Field(None, description="Labels for categorization")
    notes: Optional[str] = Field(None, description="Additional notes")
    card_type: str = Field("debit", description="debit|credit")

    # Review Worker fields
    review_status: Optional[str] = Field("not_started", description="Review process status: not_started|pending|diff_found|no_diff|reviewed|failed")
    review_result: Optional[Dict[str, Any]] = Field(None, description="Data extracted by reviewer")
    reviewed_at: Optional[datetime] = Field(None, description="When the review was performed")


class BankStatementResponse(BankStatementBase):
    """Response schema for bank statements with attribution"""
    id: int
    created_at: Optional[datetime] = None
    # User attribution fields
    created_by_user_id: Optional[int] = None
    created_by_username: Optional[str] = None
    created_by_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BankStatementWithTransactions(BankStatementResponse):
    """Bank statement response with transactions"""
    transactions: List[BankStatementTransactionResponse] = []

    model_config = ConfigDict(from_attributes=True)


# === Recycle Bin Schemas ===

class DeletedBankStatement(BankStatementResponse):
    """Schema for displaying deleted bank statements in the recycle bin"""
    is_deleted: bool
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]
    deleted_by_username: Optional[str] = None  # Username of who deleted it

    model_config = ConfigDict(from_attributes=True)


class RecycleBinStatementResponse(BaseModel):
    """Response schema for statement recycle bin operations"""
    message: str
    statement_id: int
    action: str  # "moved_to_recycle", "restored", "permanently_deleted"


class RestoreStatementRequest(BaseModel):
    """Request schema for restoring a statement"""
    new_status: Optional[str] = "processed"  # Status to set when restoring

class PaginatedDeletedBankStatements(BaseModel):
    items: List[DeletedBankStatement]
    total: int

class PaginatedBankStatements(BaseModel):
    statements: List[BankStatementResponse]
    total: int
    success: bool = True
