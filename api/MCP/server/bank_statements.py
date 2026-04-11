"""Bank Statement Management tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


@mcp.tool()
async def list_bank_statements(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    account_name: Optional[str] = None,
) -> dict:
    """
    List bank statements with optional filtering and pagination.

    Args:
        skip: Number of statements to skip for pagination (default: 0)
        limit: Maximum number of statements to return (default: 100)
        status: Filter by processing status (optional)
        account_name: Filter by account name (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_bank_statements(
        skip=skip, limit=limit, status=status, account_name=account_name
    )


@mcp.tool()
async def get_bank_statement(statement_id: int) -> dict:
    """
    Get detailed information about a bank statement including all transactions.

    Args:
        statement_id: ID of bank statement to retrieve
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_bank_statement(statement_id=statement_id)


@mcp.tool()
async def reprocess_bank_statement(
    statement_id: int, force_reprocess: bool = False
) -> dict:
    """
    Reprocess a bank statement to extract transactions again.

    Args:
        statement_id: ID of bank statement to reprocess
        force_reprocess: Force reprocessing even if already processed (default: False)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.reprocess_bank_statement(
        statement_id=statement_id, force_reprocess=force_reprocess
    )


@mcp.tool()
async def update_bank_statement_meta(
    statement_id: int,
    account_name: Optional[str] = None,
    statement_period: Optional[str] = None,
    notes: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """
    Update bank statement metadata like account name, period, notes, and status.

    Args:
        statement_id: ID of bank statement to update
        account_name: Bank account name (optional)
        statement_period: Statement period description (optional)
        notes: Additional notes (optional)
        status: Processing status (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_bank_statement_meta(
        statement_id=statement_id,
        account_name=account_name,
        statement_period=statement_period,
        notes=notes,
        status=status,
    )


@mcp.tool()
async def delete_bank_statement(
    statement_id: int, confirm_deletion: bool = False
) -> dict:
    """
    Delete a bank statement and all associated transactions.

    Args:
        statement_id: ID of bank statement to delete
        confirm_deletion: Confirmation flag to prevent accidental deletion (default: False)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_bank_statement(
        statement_id=statement_id, confirm_deletion=confirm_deletion
    )
