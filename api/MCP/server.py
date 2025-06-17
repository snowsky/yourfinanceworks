"""
Invoice Application FastMCP Server

This is the main FastMCP server for the Invoice Application.
It provides tools for AI models to interact with the invoice system API.
"""
import argparse
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator

from fastmcp import FastMCP

from .api_client import InvoiceAPIClient
from .tools import InvoiceTools
from .config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServerContext:
    """Context class to hold server state"""
    def __init__(self):
        self.api_client: Optional[InvoiceAPIClient] = None
        self.tools: Optional[InvoiceTools] = None

# Global context instance
server_context = ServerContext()

@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    """FastMCP lifespan context manager for initialization and cleanup"""
    args = parse_arguments()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Validate required credentials
    if not args.email or not args.password:
        logger.error("Email and password are required for API authentication")
        logger.error("Set them via command line arguments or environment variables:")
        logger.error("  INVOICE_API_EMAIL and INVOICE_API_PASSWORD")
        sys.exit(1)
    
    logger.info("Starting Invoice FastMCP Server...")
    logger.info(f"API Base URL: {args.api_url}")
    
    try:
        # Initialize API client and tools
        server_context.api_client = InvoiceAPIClient(
            base_url=args.api_url,
            email=args.email,
            password=args.password
        )
        server_context.tools = InvoiceTools(server_context.api_client)
        logger.info(f"Initialized API client for {args.api_url}")
        
        yield
        
    finally:
        # Cleanup
        if server_context.api_client:
            await server_context.api_client.close()
            server_context.api_client = None
            logger.info("Cleaned up API client")

# Initialize FastMCP server with lifespan
mcp = FastMCP("Invoice Application MCP Server", lifespan=lifespan)

# Client Management Tools

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
async def create_client(name: str, email: Optional[str] = None, phone: Optional[str] = None, address: Optional[str] = None) -> dict:
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
async def create_invoice(client_id: int, amount: float, due_date: str, status: str = "draft", notes: Optional[str] = None) -> dict:
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
    
    return await server_context.tools.create_invoice(client_id=client_id, amount=amount, due_date=due_date, status=status, notes=notes)

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

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Invoice Application FastMCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  INVOICE_API_BASE_URL    Base URL for the Invoice API (default: http://localhost:8000/api)
  INVOICE_API_EMAIL       Email for API authentication
  INVOICE_API_PASSWORD    Password for API authentication
  REQUEST_TIMEOUT         HTTP request timeout in seconds (default: 30)
  DEFAULT_PAGE_SIZE       Default pagination size (default: 100)
  MAX_PAGE_SIZE          Maximum pagination size (default: 1000)

Examples:
  # Run with default settings
  python -m MCP
  
  # Run with custom API URL
  python -m MCP --api-url http://api.mycompany.com/api
  
  # Run with custom credentials
  python -m MCP --email user@example.com --password mypassword

Available Tools:
  - list_clients: List all clients with pagination
  - search_clients: Search clients by name, email, phone, or address
  - get_client: Get detailed client information by ID
  - create_client: Create a new client
  - list_invoices: List all invoices with pagination
  - search_invoices: Search invoices by various fields
  - get_invoice: Get detailed invoice information by ID
  - create_invoice: Create a new invoice
  - get_clients_with_outstanding_balance: Get clients with unpaid invoices
  - get_overdue_invoices: Get invoices past their due date
  - get_invoice_stats: Get overall invoice statistics
        """
    )
    
    parser.add_argument(
        "--api-url",
        help="Base URL for the Invoice API",
        default=config.API_BASE_URL
    )
    parser.add_argument(
        "--email",
        help="Email for API authentication",
        default=config.DEFAULT_EMAIL
    )
    parser.add_argument(
        "--password",
        help="Password for API authentication",
        default=config.DEFAULT_PASSWORD
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()

def main():
    """Main entry point - simplified to just run FastMCP"""
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

# Legacy compatibility functions - deprecated but kept for backwards compatibility
def main_sync():
    """Legacy sync entry point - use main() instead"""
    logger.warning("main_sync() is deprecated, use main() instead")
    main()

if __name__ == "__main__":
    main() 