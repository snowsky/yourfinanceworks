from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class ApprovalStatus(str, Enum):
    """Approval status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"



class ExpenseApprovalBase(BaseModel):
    """Base schema for expense approvals"""
    expense_id: int = Field(..., description="ID of the expense being approved")
    approver_id: int = Field(..., description="ID of the approver")
    approval_rule_id: Optional[int] = Field(None, description="ID of the approval rule that triggered this")
    status: ApprovalStatus = Field(ApprovalStatus.PENDING, description="Approval status")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection")
    notes: Optional[str] = Field(None, description="Additional notes from approver")
    approval_level: int = Field(1, ge=1, description="Approval level")
    is_current_level: bool = Field(True, description="Whether this is the current approval level")


class ExpenseApprovalCreate(BaseModel):
    """Schema for creating expense approvals (submission)"""
    expense_id: int = Field(..., description="ID of the expense to submit for approval")
    approver_id: int = Field(..., description="Specific approver ID to assign this approval to")
    notes: Optional[str] = Field(None, description="Optional notes for the submission")


class ExpenseApprovalDecision(BaseModel):
    """Schema for approval decisions"""
    status: ApprovalStatus = Field(..., description="Approval decision")
    rejection_reason: Optional[str] = Field(None, description="Required if status is rejected")
    notes: Optional[str] = Field(None, description="Optional notes from approver")

    @field_validator('rejection_reason')
    @classmethod
    def validate_rejection_reason(cls, v, info):
        if info.data.get('status') == ApprovalStatus.REJECTED and not v:
            raise ValueError('rejection_reason is required when rejecting an expense')
        return v


class ExpenseApproval(ExpenseApprovalBase):
    """Schema for expense approval responses"""
    id: int
    submitted_at: datetime
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalDelegateBase(BaseModel):
    """Base schema for approval delegates"""
    approver_id: int = Field(..., description="ID of the approver")
    delegate_id: int = Field(..., description="ID of the delegate")
    start_date: datetime = Field(..., description="Start date of delegation")
    end_date: datetime = Field(..., description="End date of delegation")
    is_active: bool = Field(True, description="Whether the delegation is active")

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        if info.data.get('start_date') and v <= info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    @field_validator('delegate_id')
    @classmethod
    def validate_delegate_id(cls, v, info):
        if info.data.get('approver_id') == v:
            raise ValueError('delegate_id cannot be the same as approver_id')
        return v


class ApprovalDelegateCreate(ApprovalDelegateBase):
    """Schema for creating approval delegates"""
    pass


class ApprovalDelegateUpdate(BaseModel):
    """Schema for updating approval delegates"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class ApprovalDelegate(ApprovalDelegateBase):
    """Schema for approval delegate responses"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingApprovalSummary(BaseModel):
    """Summary of pending approvals for dashboard"""
    total_pending: int = Field(..., description="Total number of pending approvals")
    total_amount: float = Field(..., description="Total amount of pending expenses")
    currency: str = Field(..., description="Currency for the total amount")
    oldest_submission: Optional[datetime] = Field(None, description="Date of oldest pending submission")
    by_category: List[dict] = Field(default_factory=list, description="Breakdown by expense category")


class ApprovalHistoryItem(BaseModel):
    """Individual approval history item"""
    id: int
    approver_name: str = Field(..., description="Name of the approver")
    approver_email: str = Field(..., description="Email of the approver")
    status: ApprovalStatus
    approval_level: int
    submitted_at: datetime
    decided_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseApprovalHistory(BaseModel):
    """Complete approval history for an expense"""
    expense_id: int
    current_status: str = Field(..., description="Current expense status")
    approval_history: List[ApprovalHistoryItem] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


class ApprovalMetrics(BaseModel):
    """Approval workflow metrics"""
    total_approvals: int
    approved_count: int
    rejected_count: int
    pending_count: int
    average_approval_time_hours: Optional[float] = None
    approval_rate: float = Field(..., description="Percentage of approvals vs rejections")
    
    model_config = ConfigDict(from_attributes=True)


# Extended expense schemas with approval information
class ExpenseWithApprovalStatus(BaseModel):
    """Expense with approval status information"""
    id: int
    amount: float
    currency: str
    expense_date: date
    category: str
    vendor: Optional[str] = None
    status: str
    current_approval_status: Optional[ApprovalStatus] = None
    current_approver_name: Optional[str] = None
    submitted_for_approval_at: Optional[datetime] = None
    approval_level: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)