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
from datetime import datetime

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

# Currency Management Tools

@mcp.tool()
async def list_currencies(active_only: bool = True) -> dict:
    """
    List supported currencies with optional filtering for active currencies only.
    
    Args:
        active_only: Return only active currencies (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.list_currencies(active_only=active_only)

@mcp.tool()
async def create_currency(code: str, name: str, symbol: str, decimal_places: int = 2, is_active: bool = True) -> dict:
    """
    Create a custom currency for the tenant.
    
    Args:
        code: Currency code (e.g., USD, EUR)
        name: Currency name
        symbol: Currency symbol
        decimal_places: Number of decimal places (default: 2)
        is_active: Whether the currency is active (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.create_currency(code=code, name=name, symbol=symbol, decimal_places=decimal_places, is_active=is_active)

@mcp.tool()
async def convert_currency(amount: float, from_currency: str, to_currency: str, conversion_date: Optional[str] = None) -> dict:
    """
    Convert amount from one currency to another using current or historical exchange rates.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code
        conversion_date: Date for conversion rate in YYYY-MM-DD format (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.convert_currency(amount=amount, from_currency=from_currency, to_currency=to_currency, conversion_date=conversion_date)

# Payment Management Tools

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
async def create_payment(invoice_id: int, amount: float, payment_date: str, payment_method: str, reference: Optional[str] = None, notes: Optional[str] = None) -> dict:
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
    
    return await server_context.tools.create_payment(invoice_id=invoice_id, amount=amount, payment_date=payment_date, payment_method=payment_method, reference=reference, notes=notes)

# Settings Tools

@mcp.tool()
async def get_settings() -> dict:
    """
    Get tenant settings including company information and invoice settings.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.get_settings()

# Discount Rules Tools

@mcp.tool()
async def list_discount_rules() -> dict:
    """
    List all discount rules for the current tenant.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.list_discount_rules()

@mcp.tool()
async def create_discount_rule(name: str, discount_type: str, discount_value: float, min_amount: Optional[float] = None, max_discount: Optional[float] = None, priority: int = 1, is_active: bool = True, currency: Optional[str] = None) -> dict:
    """
    Create a new discount rule for the tenant.
    
    Args:
        name: Name of the discount rule
        discount_type: Type of discount (percentage, fixed)
        discount_value: Discount value
        min_amount: Minimum amount for discount to apply (optional)
        max_discount: Maximum discount amount (optional)
        priority: Priority of the rule, higher number = higher priority (default: 1)
        is_active: Whether the rule is active (default: True)
        currency: Currency code for the rule (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.create_discount_rule(name=name, discount_type=discount_type, discount_value=discount_value, min_amount=min_amount, max_discount=max_discount, priority=priority, is_active=is_active, currency=currency)

# CRM Tools

@mcp.tool()
async def create_client_note(client_id: int, title: str, content: str, note_type: str = "general") -> dict:
    """
    Create a note for a client.
    
    Args:
        client_id: ID of the client
        title: Note title
        content: Note content
        note_type: Type of note (general, call, meeting, etc.) (default: "general")
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.create_client_note(client_id=client_id, title=title, content=content, note_type=note_type)

# Email Tools

@mcp.tool()
async def send_invoice_email(invoice_id: int, to_email: Optional[str] = None, to_name: Optional[str] = None, subject: Optional[str] = None, message: Optional[str] = None) -> dict:
    """
    Send an invoice via email.
    
    Args:
        invoice_id: ID of the invoice to send
        to_email: Recipient email address (optional, uses client email if not provided)
        to_name: Recipient name (optional, uses client name if not provided)
        subject: Email subject (optional)
        message: Custom message (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.send_invoice_email(invoice_id=invoice_id, to_email=to_email, to_name=to_name, subject=subject, message=message)

@mcp.tool()
async def test_email_configuration(test_email: str) -> dict:
    """
    Test email configuration by sending a test email.
    
    Args:
        test_email: Email address to send test email to
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.test_email_configuration(test_email=test_email)

# Tenant Tools

@mcp.tool()
async def get_tenant_info() -> dict:
    """
    Get current tenant information including company details and settings.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}
    
    return await server_context.tools.get_tenant_info()

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
  - list_currencies: List supported currencies
  - create_currency: Create a custom currency
  - convert_currency: Convert amount between currencies
  - list_payments: List all payments with pagination
  - create_payment: Create a new payment
  - get_settings: Get tenant settings
  - list_discount_rules: List all discount rules
  - create_discount_rule: Create a new discount rule
  - create_client_note: Create a note for a client
  - send_invoice_email: Send an invoice via email
  - test_email_configuration: Test email configuration
  - get_tenant_info: Get current tenant information
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