"""
Invoice Application MCP Server

This is the main Model Context Protocol server for the Invoice Application.
It provides tools for AI models to interact with the invoice system API.
"""
import asyncio
import json
import sys
from typing import Any, Dict, Sequence
import argparse
import logging

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
)

from .api_client import InvoiceAPIClient
from .tools import TOOLS, InvoiceTools
from .config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InvoiceMCPServer:
    """MCP Server for Invoice Application"""
    
    def __init__(self, api_base_url: str = None, email: str = None, password: str = None):
        self.server = Server("invoice-app-mcp")
        self.api_client = None
        self.tools = None
        
        # Configuration
        self.api_base_url = api_base_url or config.API_BASE_URL
        self.email = email or config.DEFAULT_EMAIL
        self.password = password or config.DEFAULT_PASSWORD
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register MCP handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List available tools"""
            return ListToolsResult(tools=TOOLS)
        
        @self.server.call_tool()
        async def handle_call_tool(request: CallToolRequest) -> CallToolResult:
            """Handle tool execution requests"""
            try:
                # Initialize API client if not already done
                if self.api_client is None:
                    self.api_client = InvoiceAPIClient(
                        base_url=self.api_base_url,
                        email=self.email,
                        password=self.password
                    )
                    self.tools = InvoiceTools(self.api_client)
                
                # Execute the requested tool
                result = await self.tools.execute_tool(
                    name=request.params.name,
                    arguments=request.params.arguments or {}
                )
                
                return CallToolResult(content=result)
                
            except Exception as e:
                logger.error(f"Error executing tool {request.params.name}: {e}")
                error_content = [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"Tool execution failed: {str(e)}"
                    })
                )]
                return CallToolResult(content=error_content)
    
    async def run_stdio(self):
        """Run the server using stdio transport"""
        try:
            logger.info("Starting Invoice MCP Server...")
            logger.info(f"API Base URL: {self.api_base_url}")
            logger.info(f"Available tools: {len(TOOLS)}")
            
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="invoice-app-mcp",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=None,
                            experimental_capabilities=None,
                        ),
                    ),
                )
        finally:
            # Clean up
            if self.api_client:
                await self.api_client.close()


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Invoice Application MCP Server",
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
  python -m MCP.server
  
  # Run with custom API URL
  python -m MCP.server --api-url http://api.mycompany.com/api
  
  # Run with custom credentials
  python -m MCP.server --email user@example.com --password mypassword

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


async def main():
    """Main entry point"""
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
    
    # Create and run the server
    server = InvoiceMCPServer(
        api_base_url=args.api_url,
        email=args.email,
        password=args.password
    )
    
    try:
        await server.run_stdio()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 