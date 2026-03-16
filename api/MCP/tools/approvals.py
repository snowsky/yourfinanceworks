"""
Approval workflow-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GetAvailableApproversArgs(BaseModel):
    pass  # No arguments needed


class SubmitExpenseForApprovalArgs(BaseModel):
    expense_id: int = Field(description="ID of the expense to submit")
    notes: Optional[str] = Field(default=None, description="Optional submission notes")
    approver_id: Optional[int] = Field(default=None, description="Optional specific approver ID")


class GetPendingApprovalsArgs(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1, le=100, description="Maximum number of results")
    offset: Optional[int] = Field(default=None, ge=0, description="Number of results to skip")


class GetPendingApprovalsSummaryArgs(BaseModel):
    pass  # No arguments needed


class ApproveExpenseArgs(BaseModel):
    approval_id: int = Field(description="ID of the approval to approve")
    notes: Optional[str] = Field(default=None, description="Optional approval notes")


class RejectExpenseArgs(BaseModel):
    approval_id: int = Field(description="ID of the approval to reject")
    rejection_reason: str = Field(description="Required rejection reason")
    notes: Optional[str] = Field(default=None, description="Optional additional notes")


class GetApprovalHistoryArgs(BaseModel):
    expense_id: int = Field(description="ID of the expense")


class GetApprovalMetricsArgs(BaseModel):
    approver_id: Optional[int] = Field(default=None, description="Filter by specific approver ID")


class GetApprovalDashboardStatsArgs(BaseModel):
    pass  # No arguments needed


class GetApprovedExpensesArgs(BaseModel):
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum number of records")


class GetProcessedExpensesArgs(BaseModel):
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum number of records")


class CreateApprovalDelegationArgs(BaseModel):
    delegate_id: int = Field(description="ID of the user to delegate to")
    start_date: str = Field(description="Delegation start date (YYYY-MM-DD)")
    end_date: str = Field(description="Delegation end date (YYYY-MM-DD)")
    is_active: bool = Field(default=True, description="Whether delegation is active")


class GetApprovalDelegationsArgs(BaseModel):
    include_inactive: bool = Field(default=False, description="Include inactive delegations")


class UpdateApprovalDelegationArgs(BaseModel):
    delegation_id: int = Field(description="ID of the delegation to update")
    start_date: Optional[str] = Field(default=None, description="New start date")
    end_date: Optional[str] = Field(default=None, description="New end date")
    is_active: Optional[bool] = Field(default=None, description="New active status")


class DeactivateApprovalDelegationArgs(BaseModel):
    delegation_id: int = Field(description="ID of the delegation to deactivate")


class ApprovalToolsMixin:
    # === Approval Management Tools (later, more complete versions) ===

    async def get_available_approvers(self) -> Dict[str, Any]:
        """Get list of available approvers"""
        try:
            response = await self.api_client._make_request("GET", "/approvals/approvers")
            return {
                "success": True,
                "data": response,
                "count": len(response),
                "message": f"Found {len(response)} available approvers"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get available approvers: {e}"}

    async def submit_expense_for_approval(self, expense_id: int, notes: Optional[str] = None, approver_id: Optional[int] = None) -> Dict[str, Any]:
        """Submit an expense for approval"""
        try:
            payload = {"expense_id": expense_id}
            if notes:
                payload["notes"] = notes
            if approver_id:
                payload["approver_id"] = approver_id

            response = await self.api_client._make_request("POST", f"/approvals/expenses/{expense_id}/submit-approval", json=payload)
            return {
                "success": True,
                "data": response,
                "message": "Expense submitted for approval successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to submit expense for approval: {e}"}

    async def get_pending_approvals(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """Get pending approvals for current user"""
        try:
            params = {}
            if limit is not None:
                params["limit"] = limit
            if offset is not None:
                params["offset"] = offset

            response = await self.api_client._make_request("GET", "/approvals/pending", params=params)

            # Extract approvals from response
            approvals = self._extract_items_from_response(response, ["approvals", "items", "data"])

            return {
                "success": True,
                "data": approvals,
                "total": response.get("total", 0) if isinstance(response, dict) else len(approvals),
                "message": f"Found {response.get('total', 0) if isinstance(response, dict) else len(approvals)} pending approvals"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get pending approvals: {e}"}

    async def get_pending_approvals_summary(self) -> Dict[str, Any]:
        """Get summary of pending approvals"""
        try:
            response = await self.api_client._make_request("GET", "/approvals/pending/summary")
            return {
                "success": True,
                "data": response,
                "message": "Pending approvals summary retrieved"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get pending approvals summary: {e}"}

    async def approve_expense(self, approval_id: int, notes: Optional[str] = None) -> Dict[str, Any]:
        """Approve an expense"""
        try:
            payload = {"status": "approved"}
            if notes:
                payload["notes"] = notes

            response = await self.api_client._make_request("POST", f"/approvals/{approval_id}/approve", json=payload)
            return {
                "success": True,
                "data": response,
                "message": "Expense approved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to approve expense: {e}"}

    async def reject_expense(self, approval_id: int, rejection_reason: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Reject an expense"""
        try:
            payload = {
                "status": "rejected",
                "rejection_reason": rejection_reason
            }
            if notes:
                payload["notes"] = notes

            response = await self.api_client._make_request("POST", f"/approvals/{approval_id}/reject", json=payload)
            return {
                "success": True,
                "data": response,
                "message": "Expense rejected successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to reject expense: {e}"}

    async def get_approval_history(self, expense_id: int) -> Dict[str, Any]:
        """Get approval history for an expense"""
        try:
            response = await self.api_client._make_request("GET", f"/approvals/history/{expense_id}")
            return {
                "success": True,
                "data": response,
                "message": "Approval history retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get approval history: {e}"}

    async def get_approval_metrics(self, approver_id: Optional[int] = None) -> Dict[str, Any]:
        """Get approval workflow metrics"""
        try:
            params = {}
            if approver_id:
                params["approver_id"] = approver_id

            response = await self.api_client._make_request("GET", "/approvals/metrics", params=params)
            return {
                "success": True,
                "data": response,
                "message": "Approval metrics retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get approval metrics: {e}"}

    async def get_approval_dashboard_stats(self) -> Dict[str, Any]:
        """Get approval dashboard statistics"""
        try:
            response = await self.api_client._make_request("GET", "/approvals/dashboard-stats")
            return {
                "success": True,
                "data": response,
                "message": "Dashboard statistics retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get dashboard stats: {e}"}

    async def get_approved_expenses(self, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        """Get expenses approved by current user"""
        try:
            params = {"skip": skip, "limit": limit}
            response = await self.api_client._make_request("GET", "/approvals/approved-expenses", params=params)

            # Extract expenses from response
            expenses = self._extract_items_from_response(response, ["expenses", "items", "data"])

            return {
                "success": True,
                "data": expenses,
                "total": response.get("total", 0) if isinstance(response, dict) else len(expenses),
                "message": f"Found {response.get('total', 0) if isinstance(response, dict) else len(expenses)} approved expenses"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get approved expenses: {e}"}

    async def get_processed_expenses(self, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
        """Get expenses processed (approved/rejected) by current user"""
        try:
            params = {"skip": skip, "limit": limit}
            response = await self.api_client._make_request("GET", "/approvals/processed-expenses", params=params)

            # Extract expenses from response
            expenses = self._extract_items_from_response(response, ["expenses", "items", "data"])

            return {
                "success": True,
                "data": expenses,
                "total": response.get("total", 0) if isinstance(response, dict) else len(expenses),
                "message": f"Found {response.get('total', 0) if isinstance(response, dict) else len(expenses)} processed expenses"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get processed expenses: {e}"}

    async def create_approval_delegation(self, delegate_id: int, start_date: str, end_date: str, is_active: bool = True) -> Dict[str, Any]:
        """Create an approval delegation"""
        try:
            payload = {
                "delegate_id": delegate_id,
                "start_date": start_date,
                "end_date": end_date,
                "is_active": is_active
            }
            response = await self.api_client._make_request("POST", "/approvals/delegate", json=payload)
            return {
                "success": True,
                "data": response,
                "message": "Approval delegation created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create approval delegation: {e}"}

    async def get_approval_delegations(self, include_inactive: bool = False) -> Dict[str, Any]:
        """Get approval delegations for current user"""
        try:
            params = {"include_inactive": include_inactive}
            response = await self.api_client._make_request("GET", "/approvals/delegates", params=params)
            return {
                "success": True,
                "data": response,
                "count": len(response),
                "message": f"Found {len(response)} delegations"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get approval delegations: {e}"}

    async def update_approval_delegation(self, delegation_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None, is_active: Optional[bool] = None) -> Dict[str, Any]:
        """Update an approval delegation"""
        try:
            payload = {}
            if start_date:
                payload["start_date"] = start_date
            if end_date:
                payload["end_date"] = end_date
            if is_active is not None:
                payload["is_active"] = is_active

            response = await self.api_client._make_request("PUT", f"/approvals/delegates/{delegation_id}", json=payload)
            return {
                "success": True,
                "data": response,
                "message": "Approval delegation updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update approval delegation: {e}"}

    async def deactivate_approval_delegation(self, delegation_id: int) -> Dict[str, Any]:
        """Deactivate an approval delegation"""
        try:
            response = await self.api_client._make_request("DELETE", f"/approvals/delegates/{delegation_id}")
            return {
                "success": True,
                "data": response,
                "message": "Approval delegation deactivated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to deactivate approval delegation: {e}"}
