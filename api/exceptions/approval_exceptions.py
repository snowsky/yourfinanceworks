"""
Custom exceptions for approval workflow system

This module defines comprehensive exceptions for the expense approval workflow,
providing structured error handling with error codes and detailed context.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime


class ApprovalException(Exception):
    """Base exception for approval-related errors"""

    def __init__(
        self, 
        message: str, 
        error_code: str, 
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.user_message = user_message or message
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error_code": self.error_code,
            "message": self.user_message,
            "details": self.details
        }


class ValidationError(ApprovalException):
    """Raised when validation fails"""

    def __init__(self, field: str, value: Any, reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Validation failed for field '{field}' with value '{value}': {reason}"
        user_message = f"Invalid {field}: {reason}"
        super().__init__(
            message,
            "APPROVAL_VALIDATION_ERROR",
            {
                "field": field,
                "value": value,
                "reason": reason,
                **(details or {})
            },
            user_message
        )


class ExpenseValidationError(ApprovalException):
    """Raised when expense validation fails for approval submission"""

    def __init__(self, expense_id: int, missing_fields: List[str], details: Optional[Dict[str, Any]] = None):
        fields_str = ", ".join(missing_fields) if missing_fields else ""
        validation_errors = details.get("validation_errors", []) if details else []
        errors_str = ", ".join(validation_errors) if validation_errors else ""

        message_parts = []
        if fields_str:
            message_parts.append(f"missing required fields: {fields_str}")
        if errors_str:
            message_parts.append(f"validation errors: {errors_str}")

        message = f"Expense {expense_id} validation failed: {'; '.join(message_parts)}"
        user_message = f"Cannot submit expense for approval. Please fix the following issues: {'; '.join(message_parts)}"
        super().__init__(
            message,
            "EXPENSE_VALIDATION_ERROR",
            {
                "expense_id": expense_id,
                "missing_fields": missing_fields,
                **(details or {})
            },
            user_message
        )


class InsufficientApprovalPermissions(ApprovalException):
    """Raised when user lacks approval permissions"""

    def __init__(
        self, 
        user_id: int, 
        required_permission: str, 
        expense_id: Optional[int] = None,
        approval_level: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"User {user_id} lacks permission '{required_permission}'"
        if expense_id:
            message += f" for expense {expense_id}"
        if approval_level:
            message += f" at approval level {approval_level}"
        
        user_message = "You don't have permission to perform this approval action."
        
        super().__init__(
            message,
            "INSUFFICIENT_APPROVAL_PERMISSIONS",
            {
                "user_id": user_id,
                "required_permission": required_permission,
                "expense_id": expense_id,
                "approval_level": approval_level,
                **(details or {})
            },
            user_message
        )


class ExpenseAlreadyApproved(ApprovalException):
    """Raised when trying to modify already approved expense"""

    def __init__(self, expense_id: int, current_status: str, details: Optional[Dict[str, Any]] = None):
        message = f"Expense {expense_id} is already approved (status: {current_status})"
        user_message = "This expense has already been approved and cannot be modified."
        super().__init__(
            message,
            "EXPENSE_ALREADY_APPROVED",
            {
                "expense_id": expense_id,
                "current_status": current_status,
                **(details or {})
            },
            user_message
        )


class ExpenseAlreadyRejected(ApprovalException):
    """Raised when trying to approve already rejected expense"""

    def __init__(self, expense_id: int, rejection_reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Expense {expense_id} is already rejected: {rejection_reason}"
        user_message = "This expense has been rejected and cannot be approved. Please resubmit if needed."
        super().__init__(
            message,
            "EXPENSE_ALREADY_REJECTED",
            {
                "expense_id": expense_id,
                "rejection_reason": rejection_reason,
                **(details or {})
            },
            user_message
        )


class NoApprovalRuleFound(ApprovalException):
    """Raised when no approval rule matches expense criteria"""

    def __init__(
        self, 
        expense_id: int, 
        amount: float, 
        currency: str, 
        category: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"No approval rule found for expense {expense_id} (amount: {currency} {amount}, category: {category})"
        user_message = "No approval workflow is configured for this expense. Please contact your administrator."
        super().__init__(
            message,
            "NO_APPROVAL_RULE_FOUND",
            {
                "expense_id": expense_id,
                "amount": amount,
                "currency": currency,
                "category": category,
                **(details or {})
            },
            user_message
        )


class ApprovalLevelMismatch(ApprovalException):
    """Raised when approval level doesn't match expected level"""

    def __init__(
        self, 
        approval_id: int, 
        current_level: int, 
        expected_level: int,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Approval {approval_id} level mismatch: current {current_level}, expected {expected_level}"
        user_message = "This approval is not at the correct level for processing."
        super().__init__(
            message,
            "APPROVAL_LEVEL_MISMATCH",
            {
                "approval_id": approval_id,
                "current_level": current_level,
                "expected_level": expected_level,
                **(details or {})
            },
            user_message
        )


class InvalidApprovalState(ApprovalException):
    """Raised when approval is in invalid state for operation"""

    def __init__(
        self, 
        approval_id: int, 
        current_state: str, 
        operation: str,
        valid_states: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Approval {approval_id} is in {current_state} state, cannot {operation}"
        if valid_states:
            message += f". Valid states: {', '.join(valid_states)}"
        
        user_message = f"Cannot {operation} this approval in its current state."
        
        super().__init__(
            message,
            "INVALID_APPROVAL_STATE",
            {
                "approval_id": approval_id,
                "current_state": current_state,
                "operation": operation,
                "valid_states": valid_states,
                **(details or {})
            },
            user_message
        )


class ApprovalNotFoundException(ApprovalException):
    """Raised when approval record is not found"""

    def __init__(self, approval_id: int, details: Optional[Dict[str, Any]] = None):
        message = f"Approval {approval_id} not found"
        user_message = "The requested approval was not found."
        super().__init__(
            message,
            "APPROVAL_NOT_FOUND",
            {
                "approval_id": approval_id,
                **(details or {})
            },
            user_message
        )


class ExpenseNotFoundException(ApprovalException):
    """Raised when expense is not found"""

    def __init__(self, expense_id: int, details: Optional[Dict[str, Any]] = None):
        message = f"Expense {expense_id} not found"
        user_message = "The requested expense was not found."
        super().__init__(
            message,
            "EXPENSE_NOT_FOUND",
            {
                "expense_id": expense_id,
                **(details or {})
            },
            user_message
        )


class ApprovalRuleNotFoundException(ApprovalException):
    """Raised when approval rule is not found"""

    def __init__(self, rule_id: int, details: Optional[Dict[str, Any]] = None):
        message = f"Approval rule {rule_id} not found"
        user_message = "The requested approval rule was not found."
        super().__init__(
            message,
            "APPROVAL_RULE_NOT_FOUND",
            {
                "rule_id": rule_id,
                **(details or {})
            },
            user_message
        )


class ApprovalRuleConflictError(ApprovalException):
    """Raised when approval rule conflicts with existing rules"""

    def __init__(
        self, 
        rule_name: str, 
        conflict_type: str, 
        conflicting_rule_id: int,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Approval rule '{rule_name}' conflicts with existing rule {conflicting_rule_id}: {conflict_type}"
        user_message = f"Cannot create approval rule due to conflict: {conflict_type}"
        super().__init__(
            message,
            "APPROVAL_RULE_CONFLICT",
            {
                "rule_name": rule_name,
                "conflict_type": conflict_type,
                "conflicting_rule_id": conflicting_rule_id,
                **(details or {})
            },
            user_message
        )


class DelegationValidationError(ApprovalException):
    """Raised when delegation validation fails"""

    def __init__(
        self, 
        approver_id: int, 
        delegate_id: int, 
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Delegation validation failed for approver {approver_id} to delegate {delegate_id}: {reason}"
        user_message = f"Cannot create delegation: {reason}"
        super().__init__(
            message,
            "DELEGATION_VALIDATION_ERROR",
            {
                "approver_id": approver_id,
                "delegate_id": delegate_id,
                "reason": reason,
                **(details or {})
            },
            user_message
        )


class DelegationConflictError(ApprovalException):
    """Raised when delegation conflicts with existing delegations"""

    def __init__(
        self, 
        approver_id: int, 
        start_date: datetime, 
        end_date: datetime,
        conflicting_delegation_id: int,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Delegation for approver {approver_id} from {start_date} to {end_date} conflicts with existing delegation {conflicting_delegation_id}"
        user_message = "This delegation period conflicts with an existing delegation."
        super().__init__(
            message,
            "DELEGATION_CONFLICT",
            {
                "approver_id": approver_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "conflicting_delegation_id": conflicting_delegation_id,
                **(details or {})
            },
            user_message
        )


class NotificationDeliveryError(ApprovalException):
    """Raised when notification delivery fails"""

    def __init__(
        self, 
        notification_type: str, 
        recipient_id: int, 
        reason: str,
        retry_count: int = 0,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Failed to deliver {notification_type} notification to user {recipient_id}: {reason} (retry {retry_count})"
        user_message = "Notification delivery failed. The system will retry automatically."
        super().__init__(
            message,
            "NOTIFICATION_DELIVERY_ERROR",
            {
                "notification_type": notification_type,
                "recipient_id": recipient_id,
                "reason": reason,
                "retry_count": retry_count,
                **(details or {})
            },
            user_message
        )


class ApprovalWorkflowError(ApprovalException):
    """Raised when approval workflow encounters an error"""

    def __init__(
        self, 
        workflow_step: str, 
        expense_id: int, 
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Approval workflow error at step '{workflow_step}' for expense {expense_id}: {reason}"
        user_message = "An error occurred in the approval workflow. Please try again or contact support."
        super().__init__(
            message,
            "APPROVAL_WORKFLOW_ERROR",
            {
                "workflow_step": workflow_step,
                "expense_id": expense_id,
                "reason": reason,
                **(details or {})
            },
            user_message
        )


class ApprovalServiceError(ApprovalException):
    """Raised when approval service encounters an internal error"""

    def __init__(
        self, 
        operation: str, 
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Approval service error during {operation}: {reason}"
        user_message = "An internal error occurred. Please try again or contact support."
        super().__init__(
            message,
            "APPROVAL_SERVICE_ERROR",
            {
                "operation": operation,
                "reason": reason,
                **(details or {})
            },
            user_message
        )


class BulkApprovalError(ApprovalException):
    """Raised when bulk approval operation partially fails"""

    def __init__(
        self, 
        operation: str, 
        success_count: int, 
        failure_count: int, 
        errors: List[Dict[str, Any]],
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Bulk {operation} completed with {success_count} successes and {failure_count} failures"
        user_message = f"Bulk operation partially completed: {success_count} successful, {failure_count} failed."
        super().__init__(
            message,
            "BULK_APPROVAL_ERROR",
            {
                "operation": operation,
                "success_count": success_count,
                "failure_count": failure_count,
                "errors": errors,
                **(details or {})
            },
            user_message
        )


class ApprovalTimeoutError(ApprovalException):
    """Raised when approval operation times out"""

    def __init__(
        self, 
        operation: str, 
        timeout_seconds: int,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Approval operation '{operation}' timed out after {timeout_seconds} seconds"
        user_message = "The operation took too long to complete. Please try again."
        super().__init__(
            message,
            "APPROVAL_TIMEOUT_ERROR",
            {
                "operation": operation,
                "timeout_seconds": timeout_seconds,
                **(details or {})
            },
            user_message
        )


class ApprovalConcurrencyError(ApprovalException):
    """Raised when concurrent approval operations conflict"""

    def __init__(
        self, 
        expense_id: int, 
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Concurrent approval operation conflict for expense {expense_id} during {operation}"
        user_message = "Another user is currently processing this approval. Please refresh and try again."
        super().__init__(
            message,
            "APPROVAL_CONCURRENCY_ERROR",
            {
                "expense_id": expense_id,
                "operation": operation,
                **(details or {})
            },
            user_message
        )