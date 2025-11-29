"""
Constants for expense status values to ensure consistency across the application.
"""

from enum import Enum


class ExpenseStatus(str, Enum):
    """Enumeration of valid expense status values"""
    
    # Basic statuses
    DRAFT = "draft"  # Expense created but not submitted
    RECORDED = "recorded"  # Legacy status for expenses not requiring approval
    REIMBURSED = "reimbursed"  # Existing status for completed reimbursements
    
    # Approval workflow statuses
    PENDING_APPROVAL = "pending_approval"  # Submitted for approval
    APPROVED = "approved"  # Approved and ready for reimbursement
    REJECTED = "rejected"  # Rejected by approver
    RESUBMITTED = "resubmitted"  # Resubmitted after rejection
    
    @classmethod
    def get_all_values(cls) -> list[str]:
        """Get all valid status values as a list"""
        return [status.value for status in cls]
    
    @classmethod
    def get_approval_workflow_statuses(cls) -> list[str]:
        """Get statuses that are part of the approval workflow"""
        return [
            cls.PENDING_APPROVAL.value,
            cls.APPROVED.value,
            cls.REJECTED.value,
            cls.RESUBMITTED.value
        ]
    
    @classmethod
    def get_non_approval_statuses(cls) -> list[str]:
        """Get statuses that are not part of the approval workflow"""
        return [
            cls.DRAFT.value,
            cls.RECORDED.value,
            cls.REIMBURSED.value
        ]
    
    def can_transition_to(self, new_status: 'ExpenseStatus') -> bool:
        """Check if transition from current status to new status is valid"""
        valid_transitions = {
            self.DRAFT: [self.PENDING_APPROVAL, self.RECORDED],
            self.RECORDED: [self.REIMBURSED],
            self.PENDING_APPROVAL: [self.APPROVED, self.REJECTED],
            self.APPROVED: [self.REIMBURSED],
            self.REJECTED: [self.RESUBMITTED, self.DRAFT],
            self.RESUBMITTED: [self.PENDING_APPROVAL],
            self.REIMBURSED: []  # Terminal status
        }
        
        return new_status in valid_transitions.get(self, [])
    
    def requires_approval_workflow(self) -> bool:
        """Check if this status is part of the approval workflow"""
        return self.value in self.get_approval_workflow_statuses()