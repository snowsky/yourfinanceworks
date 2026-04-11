"""Invoice Management and Analytics tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


# Invoice Management Tools

@mcp.tool()
async def list_invoices(skip: int = 0, limit: int = 100) -> dict:
    """
    List all invoices with pagination support. Returns invoice information including client names and payment status.

    Args:
        skip: Number of invoices to skip for pagination (default: 0)
        limit: Maximum number of invoices to return (default: 100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_invoices(skip=skip, limit=limit)


@mcp.tool()
async def search_invoices(query: str, skip: int = 0, limit: int = 100) -> dict:
    """
    Search for invoices by number, client name, status, notes, or amount. Supports partial matches.

    Args:
        query: Search query to find invoices
        skip: Number of results to skip for pagination (default: 0)
        limit: Maximum number of results to return (default: 100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.search_invoices(query=query, skip=skip, limit=limit)


@mcp.tool()
async def get_invoice(invoice_id: int) -> dict:
    """
    Get detailed information about a specific invoice by ID, including client information and payment status.

    Args:
        invoice_id: ID of the invoice to retrieve
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_invoice(invoice_id=invoice_id)


@mcp.tool()
async def create_invoice(
    client_id: int,
    amount: float,
    due_date: str,
    status: str = "draft",
    notes: Optional[str] = None,
) -> dict:
    """
    Create a new invoice for a client with the specified amount and due date.

    Args:
        client_id: ID of the client this invoice belongs to
        amount: Total amount of the invoice
        due_date: Due date in ISO format (YYYY-MM-DD)
        status: Status of the invoice (default: "draft")
        notes: Additional notes for the invoice (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_invoice(
        client_id=client_id, amount=amount, due_date=due_date, status=status, notes=notes
    )


# Analytics Tools

@mcp.tool()
async def get_clients_with_outstanding_balance() -> dict:
    """
    Get all clients that have outstanding balances (unpaid invoices).
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_clients_with_outstanding_balance()


@mcp.tool()
async def get_overdue_invoices() -> dict:
    """
    Get all invoices that are past their due date and still unpaid.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_overdue_invoices()


@mcp.tool()
async def get_invoice_stats() -> dict:
    """
    Get overall invoice statistics including total income and other metrics.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_invoice_stats()


@mcp.tool()
async def analyze_invoice_patterns() -> dict:
    """Analyze invoice patterns to identify trends and provide recommendations."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.analyze_invoice_patterns()


@mcp.tool()
async def suggest_invoice_actions() -> dict:
    """Suggest actionable items based on invoice analysis."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.suggest_invoice_actions()
