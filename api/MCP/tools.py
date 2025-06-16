"""
MCP Tools for Invoice Application
"""
from typing import Any, Dict, List, Optional
import json
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field

from .api_client import InvoiceAPIClient
from .auth_client import AuthenticationError


# Tool argument schemas
class ListClientsArgs(BaseModel):
    skip: int = Field(default=0, description="Number of clients to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of clients to return")


class SearchClientsArgs(BaseModel):
    query: str = Field(description="Search query to find clients by name, email, phone, or address")
    skip: int = Field(default=0, description="Number of results to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of results to return")


class GetClientArgs(BaseModel):
    client_id: int = Field(description="ID of the client to retrieve")


class CreateClientArgs(BaseModel):
    name: str = Field(description="Client's full name")
    email: Optional[str] = Field(default=None, description="Client's email address")
    phone: Optional[str] = Field(default=None, description="Client's phone number")
    address: Optional[str] = Field(default=None, description="Client's address")


class ListInvoicesArgs(BaseModel):
    skip: int = Field(default=0, description="Number of invoices to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of invoices to return")


class SearchInvoicesArgs(BaseModel):
    query: str = Field(description="Search query to find invoices by number, client name, status, notes, or amount")
    skip: int = Field(default=0, description="Number of results to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of results to return")


class GetInvoiceArgs(BaseModel):
    invoice_id: int = Field(description="ID of the invoice to retrieve")


class CreateInvoiceArgs(BaseModel):
    client_id: int = Field(description="ID of the client this invoice belongs to")
    amount: float = Field(description="Total amount of the invoice")
    due_date: str = Field(description="Due date of the invoice in ISO format (YYYY-MM-DD)")
    status: str = Field(default="draft", description="Status of the invoice (draft, sent, paid, etc.)")
    notes: Optional[str] = Field(default=None, description="Additional notes for the invoice")


# MCP Tools definitions
TOOLS: List[Tool] = [
    Tool(
        name="list_clients",
        description="List all clients with pagination support. Returns client information including balances.",
        inputSchema=ListClientsArgs.model_json_schema()
    ),
    Tool(
        name="search_clients",
        description="Search for clients by name, email, phone, or address. Supports partial matches.",
        inputSchema=SearchClientsArgs.model_json_schema()
    ),
    Tool(
        name="get_client",
        description="Get detailed information about a specific client by ID, including balance and payment history.",
        inputSchema=GetClientArgs.model_json_schema()
    ),
    Tool(
        name="create_client",
        description="Create a new client with the provided information.",
        inputSchema=CreateClientArgs.model_json_schema()
    ),
    Tool(
        name="list_invoices",
        description="List all invoices with pagination support. Returns invoice information including client names and payment status.",
        inputSchema=ListInvoicesArgs.model_json_schema()
    ),
    Tool(
        name="search_invoices",
        description="Search for invoices by number, client name, status, notes, or amount. Supports partial matches.",
        inputSchema=SearchInvoicesArgs.model_json_schema()
    ),
    Tool(
        name="get_invoice",
        description="Get detailed information about a specific invoice by ID, including client information and payment status.",
        inputSchema=GetInvoiceArgs.model_json_schema()
    ),
    Tool(
        name="create_invoice",
        description="Create a new invoice for a client with the specified amount and due date.",
        inputSchema=CreateInvoiceArgs.model_json_schema()
    ),
    Tool(
        name="get_clients_with_outstanding_balance",
        description="Get all clients that have outstanding balances (unpaid invoices).",
        inputSchema={}
    ),
    Tool(
        name="get_overdue_invoices",
        description="Get all invoices that are past their due date and still unpaid.",
        inputSchema={}
    ),
    Tool(
        name="get_invoice_stats",
        description="Get overall invoice statistics including total income and other metrics.",
        inputSchema={}
    )
]


class InvoiceTools:
    """Implementation of MCP tools for the Invoice Application"""
    
    def __init__(self, api_client: InvoiceAPIClient):
        self.api_client = api_client
    
    async def list_clients(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """List all clients"""
        try:
            args = ListClientsArgs(**arguments)
            clients = await self.api_client.list_clients(skip=args.skip, limit=args.limit)
            
            response = {
                "success": True,
                "data": clients,
                "count": len(clients),
                "pagination": {
                    "skip": args.skip,
                    "limit": args.limit
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except AuthenticationError as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Authentication failed: {e}"})
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to list clients: {e}"})
            )]
    
    async def search_clients(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search for clients"""
        try:
            args = SearchClientsArgs(**arguments)
            clients = await self.api_client.search_clients(
                query=args.query, 
                skip=args.skip, 
                limit=args.limit
            )
            
            response = {
                "success": True,
                "data": clients,
                "count": len(clients),
                "search_query": args.query,
                "pagination": {
                    "skip": args.skip,
                    "limit": args.limit
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to search clients: {e}"})
            )]
    
    async def get_client(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get a specific client"""
        try:
            args = GetClientArgs(**arguments)
            client = await self.api_client.get_client(args.client_id)
            
            response = {
                "success": True,
                "data": client
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to get client: {e}"})
            )]
    
    async def create_client(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Create a new client"""
        try:
            args = CreateClientArgs(**arguments)
            client_data = args.model_dump(exclude_none=True)
            client = await self.api_client.create_client(client_data)
            
            response = {
                "success": True,
                "data": client,
                "message": "Client created successfully"
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to create client: {e}"})
            )]
    
    async def list_invoices(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """List all invoices"""
        try:
            args = ListInvoicesArgs(**arguments)
            invoices = await self.api_client.list_invoices(skip=args.skip, limit=args.limit)
            
            response = {
                "success": True,
                "data": invoices,
                "count": len(invoices),
                "pagination": {
                    "skip": args.skip,
                    "limit": args.limit
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to list invoices: {e}"})
            )]
    
    async def search_invoices(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search for invoices"""
        try:
            args = SearchInvoicesArgs(**arguments)
            invoices = await self.api_client.search_invoices(
                query=args.query,
                skip=args.skip,
                limit=args.limit
            )
            
            response = {
                "success": True,
                "data": invoices,
                "count": len(invoices),
                "search_query": args.query,
                "pagination": {
                    "skip": args.skip,
                    "limit": args.limit
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to search invoices: {e}"})
            )]
    
    async def get_invoice(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get a specific invoice"""
        try:
            args = GetInvoiceArgs(**arguments)
            invoice = await self.api_client.get_invoice(args.invoice_id)
            
            response = {
                "success": True,
                "data": invoice
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to get invoice: {e}"})
            )]
    
    async def create_invoice(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Create a new invoice"""
        try:
            args = CreateInvoiceArgs(**arguments)
            invoice_data = args.model_dump(exclude_none=True)
            invoice = await self.api_client.create_invoice(invoice_data)
            
            response = {
                "success": True,
                "data": invoice,
                "message": "Invoice created successfully"
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to create invoice: {e}"})
            )]
    
    async def get_clients_with_outstanding_balance(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get clients with outstanding balances"""
        try:
            clients = await self.api_client.get_clients_with_outstanding_balance()
            
            response = {
                "success": True,
                "data": clients,
                "count": len(clients),
                "message": f"Found {len(clients)} clients with outstanding balances"
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to get clients with outstanding balance: {e}"})
            )]
    
    async def get_overdue_invoices(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get overdue invoices"""
        try:
            invoices = await self.api_client.get_overdue_invoices()
            
            response = {
                "success": True,
                "data": invoices,
                "count": len(invoices),
                "message": f"Found {len(invoices)} overdue invoices"
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to get overdue invoices: {e}"})
            )]
    
    async def get_invoice_stats(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get invoice statistics"""
        try:
            stats = await self.api_client.get_invoice_stats()
            
            response = {
                "success": True,
                "data": stats
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2, default=str)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Failed to get invoice stats: {e}"})
            )]
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute a tool by name"""
        method_map = {
            "list_clients": self.list_clients,
            "search_clients": self.search_clients,
            "get_client": self.get_client,
            "create_client": self.create_client,
            "list_invoices": self.list_invoices,
            "search_invoices": self.search_invoices,
            "get_invoice": self.get_invoice,
            "create_invoice": self.create_invoice,
            "get_clients_with_outstanding_balance": self.get_clients_with_outstanding_balance,
            "get_overdue_invoices": self.get_overdue_invoices,
            "get_invoice_stats": self.get_invoice_stats,
        }
        
        if name not in method_map:
            return [TextContent(
                type="text",
                text=json.dumps({"success": False, "error": f"Unknown tool: {name}"})
            )]
        
        return await method_map[name](arguments) 