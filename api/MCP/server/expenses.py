"""Expense Management tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


@mcp.tool()
async def list_expenses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    invoice_id: Optional[int] = None,
    unlinked_only: bool = False,
) -> dict:
    """
    List expenses with optional filters and pagination.

    Args:
        skip: Number of expenses to skip (default: 0)
        limit: Max number of expenses to return (default: 100)
        category: Filter by category (optional)
        invoice_id: Filter by linked invoice id (optional)
        unlinked_only: Return only expenses not linked to any invoice (default: False)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_expenses(
        skip=skip, limit=limit, category=category, invoice_id=invoice_id, unlinked_only=unlinked_only
    )


@mcp.tool()
async def get_expense(expense_id: int) -> dict:
    """Get a specific expense by ID."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_expense(expense_id=expense_id)


@mcp.tool()
async def create_expense(
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
) -> dict:
    """Create a new expense."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_expense(
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        category=category,
        vendor=vendor,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        payment_method=payment_method,
        reference_number=reference_number,
        status=status,
        notes=notes,
        invoice_id=invoice_id,
    )


@mcp.tool()
async def update_expense(
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
) -> dict:
    """Update an existing expense."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_expense(
        expense_id=expense_id,
        amount=amount,
        currency=currency,
        expense_date=expense_date,
        category=category,
        vendor=vendor,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        payment_method=payment_method,
        reference_number=reference_number,
        status=status,
        notes=notes,
        invoice_id=invoice_id,
    )


@mcp.tool()
async def delete_expense(expense_id: int) -> dict:
    """Delete an expense by ID."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_expense(expense_id=expense_id)


@mcp.tool()
async def upload_expense_receipt(
    expense_id: int,
    file_path: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> dict:
    """Upload a receipt file for an expense."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.upload_expense_receipt(
        expense_id=expense_id, file_path=file_path, filename=filename, content_type=content_type
    )


@mcp.tool()
async def list_expense_attachments(expense_id: int) -> dict:
    """List attachments for an expense."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_expense_attachments(expense_id=expense_id)


@mcp.tool()
async def delete_expense_attachment(expense_id: int, attachment_id: int) -> dict:
    """Delete an attachment for an expense."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_expense_attachment(
        expense_id=expense_id, attachment_id=attachment_id
    )
