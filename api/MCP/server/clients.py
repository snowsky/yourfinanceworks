"""Client Management tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


@mcp.tool()
async def list_clients(skip: int = 0, limit: int = 100) -> dict:
    """
    List all clients with pagination support. Returns client information including balances.

    Args:
        skip: Number of clients to skip for pagination (default: 0)
        limit: Maximum number of clients to return (default: 100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_clients(skip=skip, limit=limit)


@mcp.tool()
async def search_clients(query: str, skip: int = 0, limit: int = 100) -> dict:
    """
    Search for clients by name, email, phone, or address. Supports partial matches.

    Args:
        query: Search query to find clients
        skip: Number of results to skip for pagination (default: 0)
        limit: Maximum number of results to return (default: 100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.search_clients(query=query, skip=skip, limit=limit)


@mcp.tool()
async def get_client(client_id: int) -> dict:
    """
    Get detailed information about a specific client by ID, including balance and payment history.

    Args:
        client_id: ID of the client to retrieve
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_client(client_id=client_id)


@mcp.tool()
async def create_client(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> dict:
    """
    Create a new client with the provided information.

    Args:
        name: Client's full name
        email: Client's email address (optional)
        phone: Client's phone number (optional)
        address: Client's address (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_client(name=name, email=email, phone=phone, address=address)
