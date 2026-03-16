"""
Expense-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ListExpensesArgs(BaseModel):
    skip: int = Field(default=0, description="Number of expenses to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of expenses to return")
    category: Optional[str] = Field(default=None, description="Filter by category")
    invoice_id: Optional[int] = Field(default=None, description="Filter by linked invoice id")
    unlinked_only: bool = Field(default=False, description="Return only expenses not linked to any invoice")


class CreateExpenseArgs(BaseModel):
    amount: float = Field(description="Expense amount before tax")
    currency: str = Field(default="USD", description="Currency code for the expense")
    expense_date: str = Field(description="Expense date in ISO format (YYYY-MM-DD)")
    category: str = Field(description="Expense category")
    vendor: Optional[str] = Field(default=None, description="Vendor or payee")
    tax_rate: Optional[float] = Field(default=None, description="Tax rate percentage")
    tax_amount: Optional[float] = Field(default=None, description="Calculated tax amount, if provided")
    total_amount: Optional[float] = Field(default=None, description="Total amount including tax")
    payment_method: Optional[str] = Field(default=None, description="Payment method")
    reference_number: Optional[str] = Field(default=None, description="Reference number")
    status: Optional[str] = Field(default="recorded", description="Status of the expense")
    notes: Optional[str] = Field(default=None, description="Notes about the expense")
    invoice_id: Optional[int] = Field(default=None, description="Linked invoice ID, if any")


class UpdateExpenseArgs(BaseModel):
    expense_id: int = Field(description="ID of the expense to update")
    amount: Optional[float] = Field(default=None)
    currency: Optional[str] = Field(default=None)
    expense_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD")
    category: Optional[str] = Field(default=None)
    vendor: Optional[str] = Field(default=None)
    tax_rate: Optional[float] = Field(default=None)
    tax_amount: Optional[float] = Field(default=None)
    total_amount: Optional[float] = Field(default=None)
    payment_method: Optional[str] = Field(default=None)
    reference_number: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    invoice_id: Optional[int] = Field(default=None)


class UploadExpenseReceiptArgs(BaseModel):
    expense_id: int = Field(description="ID of the expense")
    file_path: str = Field(description="Absolute path to the file to upload")
    filename: Optional[str] = Field(default=None, description="Override filename")
    content_type: Optional[str] = Field(default=None, description="Explicit content type")


class ExpenseToolsMixin:
    async def list_expenses(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        invoice_id: Optional[int] = None,
        unlinked_only: bool = False,
    ) -> Dict[str, Any]:
        try:
            response = await self.api_client.list_expenses(
                skip=skip,
                limit=limit,
                category=category,
                invoice_id=invoice_id,
                unlinked_only=unlinked_only,
            )

            # Extract expenses from response
            expenses = self._extract_items_from_response(response, ["expenses", "items", "data"])

            return {
                "success": True,
                "data": expenses,
                "count": len(expenses),
                "pagination": {"skip": skip, "limit": limit},
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list expenses: {e}"}

    async def search_expenses(self, query: str, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Search for expenses"""
        try:
            response = await self.api_client.search_expenses(
                query=query,
                skip=skip,
                limit=limit
            )

            # Extract expenses from response
            expenses = self._extract_items_from_response(response, ["expenses", "items", "data"])

            return {
                "success": True,
                "data": expenses,
                "count": len(expenses),
                "search_query": query,
                "pagination": {
                    "skip": skip,
                    "limit": limit
                }
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to search expenses: {e}"}

    async def get_expense(self, expense_id: int) -> Dict[str, Any]:
        try:
            expense = await self.api_client.get_expense(expense_id)
            return {"success": True, "data": expense}
        except Exception as e:
            return {"success": False, "error": f"Failed to get expense: {e}"}

    async def create_expense(
        self,
        amount: float,
        currency: str,
        expense_date: str,
        category: str,
        vendor: Optional[str] = None,
        tax_rate: Optional[float] = None,
        tax_amount: Optional[float] = None,
        total_amount: Optional[float] = None,
        payment_method: Optional[str] = None,
        reference_number: Optional[str] = None,
        status: Optional[str] = "recorded",
        notes: Optional[str] = None,
        invoice_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            payload: Dict[str, Any] = {
                "amount": amount,
                "currency": currency,
                "expense_date": expense_date,
                "category": category,
                "status": status or "recorded",
            }
            if vendor is not None:
                payload["vendor"] = vendor
            if tax_rate is not None:
                payload["tax_rate"] = tax_rate
            if tax_amount is not None:
                payload["tax_amount"] = tax_amount
            if total_amount is not None:
                payload["total_amount"] = total_amount
            if payment_method is not None:
                payload["payment_method"] = payment_method
            if reference_number is not None:
                payload["reference_number"] = reference_number
            if notes is not None:
                payload["notes"] = notes
            if invoice_id is not None:
                payload["invoice_id"] = invoice_id

            expense = await self.api_client.create_expense(payload)
            return {"success": True, "data": expense, "message": "Expense created successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to create expense: {e}"}

    async def update_expense(
        self,
        expense_id: int,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        expense_date: Optional[str] = None,
        category: Optional[str] = None,
        vendor: Optional[str] = None,
        tax_rate: Optional[float] = None,
        tax_amount: Optional[float] = None,
        total_amount: Optional[float] = None,
        payment_method: Optional[str] = None,
        reference_number: Optional[str] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        invoice_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            payload: Dict[str, Any] = {}
            if amount is not None:
                payload["amount"] = amount
            if currency is not None:
                payload["currency"] = currency
            if expense_date is not None:
                payload["expense_date"] = expense_date
            if category is not None:
                payload["category"] = category
            if vendor is not None:
                payload["vendor"] = vendor
            if tax_rate is not None:
                payload["tax_rate"] = tax_rate
            if tax_amount is not None:
                payload["tax_amount"] = tax_amount
            if total_amount is not None:
                payload["total_amount"] = total_amount
            if payment_method is not None:
                payload["payment_method"] = payment_method
            if reference_number is not None:
                payload["reference_number"] = reference_number
            if status is not None:
                payload["status"] = status
            if notes is not None:
                payload["notes"] = notes
            if invoice_id is not None:
                payload["invoice_id"] = invoice_id

            expense = await self.api_client.update_expense(expense_id, payload)
            return {"success": True, "data": expense, "message": "Expense updated successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to update expense: {e}"}

    async def delete_expense(self, expense_id: int) -> Dict[str, Any]:
        try:
            ok = await self.api_client.delete_expense(expense_id)
            if not ok:
                return {"success": False, "error": "Failed to delete expense"}
            return {"success": True, "message": "Expense deleted"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete expense: {e}"}

    async def upload_expense_receipt(
        self, expense_id: int, file_path: str, filename: Optional[str] = None, content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            result = await self.api_client.upload_expense_receipt(
                expense_id=expense_id,
                file_path=file_path,
                filename=filename,
                content_type=content_type,
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": f"Failed to upload expense receipt: {e}"}

    async def list_expense_attachments(self, expense_id: int) -> Dict[str, Any]:
        try:
            items = await self.api_client.list_expense_attachments(expense_id)
            return {"success": True, "data": items, "count": len(items)}
        except Exception as e:
            return {"success": False, "error": f"Failed to list expense attachments: {e}"}

    async def delete_expense_attachment(self, expense_id: int, attachment_id: int) -> Dict[str, Any]:
        try:
            ok = await self.api_client.delete_expense_attachment(expense_id, attachment_id)
            if not ok:
                return {"success": False, "error": "Failed to delete expense attachment"}
            return {"success": True, "message": "Expense attachment deleted"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete expense attachment: {e}"}
