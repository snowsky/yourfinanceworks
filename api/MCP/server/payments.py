"""Payment Management tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


@mcp.tool()
async def list_payments(skip: int = 0, limit: int = 100) -> dict:
    """
    List all payments with pagination support.

    Args:
        skip: Number of payments to skip for pagination (default: 0)
        limit: Maximum number of payments to return (default: 100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_payments(skip=skip, limit=limit)


@mcp.tool()
async def query_payments(query: str) -> dict:
    """
    Query payments using natural language (e.g., 'payments yesterday', 'payments this week', 'cash payments over $100').

    Args:
        query: Natural language query describing the payments to find
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.query_payments(query=query)


@mcp.tool()
async def create_payment(
    invoice_id: int,
    amount: float,
    payment_date: str,
    payment_method: str,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Create a new payment for an invoice.

    Args:
        invoice_id: ID of the invoice this payment is for
        amount: Payment amount
        payment_date: Payment date in ISO format (YYYY-MM-DD)
        payment_method: Payment method (cash, check, credit_card, etc.)
        reference: Payment reference number (optional)
        notes: Additional notes (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_payment(
        invoice_id=invoice_id,
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
    )
