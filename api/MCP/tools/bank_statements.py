"""
Bank statement-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ListBankStatementsArgs(BaseModel):
    skip: int = Field(default=0, description="Number of statements to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of statements to return")
    status: Optional[str] = Field(default=None, description="Filter by processing status")
    account_name: Optional[str] = Field(default=None, description="Filter by account name")


class GetBankStatementArgs(BaseModel):
    statement_id: int = Field(description="ID of bank statement to retrieve")


class ReprocessBankStatementArgs(BaseModel):
    statement_id: int = Field(description="ID of bank statement to reprocess")
    force_reprocess: bool = Field(default=False, description="Force reprocessing even if already processed")


class UpdateBankStatementMetaArgs(BaseModel):
    statement_id: int = Field(description="ID of bank statement to update")
    account_name: Optional[str] = Field(default=None, description="Bank account name")
    statement_period: Optional[str] = Field(default=None, description="Statement period description")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    status: Optional[str] = Field(default=None, description="Processing status")


class DeleteBankStatementArgs(BaseModel):
    statement_id: int = Field(description="ID of bank statement to delete")
    confirm_deletion: bool = Field(default=False, description="Confirmation flag to prevent accidental deletion")


class BankStatementToolsMixin:
    # Statement Management
    async def list_statements(self) -> Dict[str, Any]:
        """List all statements with enhanced formatting"""
        try:
            response = await self.api_client.list_statements()

            # Extract statements from response
            statements = self._extract_items_from_response(response, ["statements", "items", "data"])

            # Format statements for better readability
            formatted_statements = []
            for stmt in statements:
                formatted = self._format_statement_for_display(stmt)
                formatted_statements.append(formatted)

            return {
                "success": True,
                "data": formatted_statements,
                "count": len(formatted_statements)
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list bank statements: {e}"}

    # Recycle Bin Management
    async def list_deleted_statements(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List all deleted statements in the recycle bin"""
        try:
            response = await self.api_client.list_deleted_statements(skip=skip, limit=limit)

            # Extract items from paginated response
            deleted_statements = self._extract_items_from_response(response, ["items", "data", "statements"])

            return {
                "success": True,
                "data": deleted_statements,
                "count": len(deleted_statements),
                "pagination": {"skip": skip, "limit": limit}
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to list deleted statements: {e}"}

    async def restore_statement(self, statement_id: int) -> Dict[str, Any]:
        """Restore a deleted statement from the recycle bin"""
        try:
            result = await self.api_client.restore_statement(statement_id)
            return {
                "success": True,
                "data": result,
                "message": "Bank statement restored successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to restore bank statement: {e}"}

    async def permanently_delete_statement(self, statement_id: int) -> Dict[str, Any]:
        """Permanently delete a statement from the recycle bin"""
        try:
            ok = await self.api_client.permanently_delete_statement(statement_id)
            if not ok:
                return {"success": False, "error": "Failed to permanently delete bank statement"}
            return {"success": True, "message": "Bank statement permanently deleted"}
        except Exception as e:
            return {"success": False, "error": f"Failed to permanently delete bank statement: {e}"}

    # === Bank Statement Management Tools (later, more complete versions) ===

    async def list_bank_statements(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        account_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """List bank statements with optional filtering and enhanced formatting"""
        try:
            params = {"skip": skip, "limit": limit}
            if status:
                params["status"] = status
            if account_name:
                params["search"] = account_name  # Use search parameter for account name filtering

            response = await self.api_client._make_request("GET", "/statements", params=params)

            # Extract statements from response
            statements = self._extract_items_from_response(response, ["statements", "items", "data"])

            # Format statements for better readability
            formatted_statements = []
            for stmt in statements:
                formatted = self._format_statement_for_display(stmt)
                formatted_statements.append(formatted)

            return {
                "success": True,
                "data": formatted_statements,
                "count": len(formatted_statements),
                "pagination": {
                    "skip": skip,
                    "limit": limit
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list bank statements: {e}"}

    async def get_bank_statement(self, statement_id: int) -> Dict[str, Any]:
        """Get detailed information about a bank statement"""
        try:
            response = await self.api_client._make_request("GET", f"/statements/{statement_id}")
            return {
                "success": True,
                "data": response.get("statement", {}),
                "transaction_count": len(response.get("statement", {}).get("transactions", []))
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get bank statement: {e}"}

    async def reprocess_bank_statement(self, statement_id: int, force_reprocess: bool = False) -> Dict[str, Any]:
        """Reprocess a bank statement"""
        try:
            response = await self.api_client._make_request("POST", f"/statements/{statement_id}/reprocess", json={"force_reprocess": force_reprocess})
            return {
                "success": True,
                "data": response,
                "message": "Bank statement reprocessing started"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to reprocess bank statement: {e}"}

    async def update_bank_statement_meta(
        self,
        statement_id: int,
        account_name: Optional[str] = None,
        statement_period: Optional[str] = None,
        notes: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update bank statement metadata"""
        try:
            update_data = {}
            if account_name is not None:
                update_data["account_name"] = account_name
            if statement_period is not None:
                update_data["statement_period"] = statement_period
            if notes is not None:
                update_data["notes"] = notes
            if status is not None:
                update_data["status"] = status

            response = await self.api_client._make_request("PUT", f"/statements/{statement_id}", json=update_data)
            return {
                "success": True,
                "data": response.get("statement", {}),
                "message": "Bank statement metadata updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update bank statement metadata: {e}"}

    async def delete_bank_statement(self, statement_id: int, confirm_deletion: bool = False) -> Dict[str, Any]:
        """Delete a bank statement"""
        try:
            if not confirm_deletion:
                return {
                    "success": False,
                    "error": "Deletion not confirmed. Please set confirm_deletion=true to proceed."
                }

            await self.api_client._make_request("DELETE", f"/statements/{statement_id}")
            return {
                "success": True,
                "message": "Bank statement deleted successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to delete bank statement: {e}"}
