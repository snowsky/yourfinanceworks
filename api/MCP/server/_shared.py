"""
Shared server state: ServerContext, FastMCP instance, lifespan, argument parsing,
and the main entry point.

All tool-registration modules import ``mcp`` and ``server_context`` from here.
"""
import argparse
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator

from fastmcp import FastMCP

from ..api_client import InvoiceAPIClient
from ..tools import InvoiceTools
from ..config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServerContext:
    """Context class to hold server state"""

    def __init__(self) -> None:
        self.api_client: Optional[InvoiceAPIClient] = None
        self.tools: Optional[InvoiceTools] = None


# Global context instance shared by all tool modules
server_context = ServerContext()


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    """FastMCP lifespan context manager for initialization and cleanup"""
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    if not args.email or not args.password:
        logger.error("Email and password are required for API authentication")
        logger.error("Set them via command line arguments or environment variables:")
        logger.error("  INVOICE_API_EMAIL and INVOICE_API_PASSWORD")
        sys.exit(1)

    logger.info("Starting Invoice FastMCP Server...")
    logger.info(f"API Base URL: {args.api_url}")

    try:
        try:
            server_context.api_client = InvoiceAPIClient(
                base_url=args.api_url,
                email=args.email,
                password=args.password,
            )
            server_context.tools = InvoiceTools(server_context.api_client)
            logger.info(f"Initialized API client for {args.api_url}")
        except Exception as e:
            logger.error(f"Failed to initialize API client: {e}")
            raise

        yield

    finally:
        if server_context.api_client:
            await server_context.api_client.close()
            server_context.api_client = None
            logger.info("Cleaned up API client")


# FastMCP server instance — shared by all tool-registration modules
mcp = FastMCP("Invoice Application MCP Server", lifespan=lifespan)


def parse_arguments() -> argparse.Namespace:
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
  - get_cashflow_forecast: Get projected inflows, outflows, balances, and alerts
  - get_cashflow_runway: Calculate cash runway from recent burn rate
  - run_cashflow_scenario: Run a cash flow what-if scenario
  - get_cashflow_alerts: Get cash flow threshold alerts
  - get_cashflow_thresholds: Get cash flow projection settings
  - update_cashflow_thresholds: Update cash flow projection settings
  - list_expenses: List expenses with optional filters
  - get_expense: Get expense by ID
  - create_expense: Create a new expense
  - update_expense: Update an expense
  - delete_expense: Delete an expense
  - upload_expense_receipt: Upload a receipt for an expense
  - list_expense_attachments: List attachments for an expense
  - delete_expense_attachment: Delete an attachment for an expense
  - list_statements: List bank statements with optional filtering (supports month filtering)
  - list_bank_statements: List bank statements with optional filtering
  - get_bank_statement: Get bank statement with transactions
  - reprocess_bank_statement: Reprocess a bank statement
  - update_bank_statement_meta: Update bank statement metadata
  - delete_bank_statement: Delete a bank statement
  - get_clients_with_outstanding_balance: Get clients with unpaid invoices
  - get_overdue_invoices: Get invoices past their due date
  - get_invoice_stats: Get overall invoice statistics
  - get_settings: Get tenant settings
  - list_discount_rules: List discount rules
  - create_discount_rule: Create a discount rule
  - create_client_note: Create a client note
  - send_invoice_email: Send invoice via email
  - test_email_configuration: Test email configuration
  - get_tenant_info: Get current tenant information
  - list_ai_configs: List all AI configurations
  - create_ai_config: Create a new AI configuration
  - update_ai_config: Update an AI configuration
  - test_ai_config: Test an AI configuration
  - get_page_views_analytics: Get page view analytics
  - get_audit_logs: Get audit logs with filters
  - get_notification_settings: Get notification settings
  - update_notification_settings: Update notification settings
  - get_ai_status: Get AI status for PDF processing
  - process_pdf_upload: Upload and process PDF files
  - export_accounting_journal: Download accountant-ready journal CSV
  - export_tax_summary: Download tax summary CSV
  - get_tenant_stats: Get detailed tenant statistics
  - create_tenant: Create a new tenant
  - update_tenant: Update tenant information
  - delete_tenant: Delete a tenant
  - list_tenant_users: List users in a tenant
  - create_tenant_user: Create a user in a tenant
  - update_tenant_user: Update a user in a tenant
  - delete_tenant_user: Delete a user from a tenant
  - promote_user_to_admin: Promote user to admin
  - reset_user_password: Reset user password
  - get_system_stats: Get system-wide statistics
  - export_tenant_data: Export tenant data
  - import_tenant_data: Import data into tenant
        """,
    )

    parser.add_argument(
        "--api-url",
        help="Base URL for the Invoice API",
        default=config.API_BASE_URL,
    )
    parser.add_argument(
        "--email",
        help="Email for API authentication",
        default=config.DEFAULT_EMAIL,
    )
    parser.add_argument(
        "--password",
        help="Password for API authentication",
        default=config.DEFAULT_PASSWORD,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point - simplified to just run FastMCP"""
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


# Legacy compatibility functions - deprecated but kept for backwards compatibility
def main_sync() -> None:
    """Legacy sync entry point - use main() instead"""
    import warnings

    warnings.warn("main_sync() is deprecated, use main() instead", DeprecationWarning, stacklevel=2)
    main()
