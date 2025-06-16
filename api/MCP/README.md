# Invoice Application MCP Server

This is a Model Context Protocol (MCP) server that provides AI models with tools to interact with the Invoice Application API. It enables AI assistants to list, search, create, and manage clients and invoices through a standardized interface.

## Features

### Client Management
- **List Clients**: Get paginated list of all clients with balance information
- **Search Clients**: Search clients by name, email, phone, or address
- **Get Client Details**: Retrieve detailed information for a specific client
- **Create Client**: Add new clients to the system

### Invoice Management
- **List Invoices**: Get paginated list of all invoices with client information
- **Search Invoices**: Search invoices by number, client name, status, notes, or amount
- **Get Invoice Details**: Retrieve detailed information for a specific invoice
- **Create Invoice**: Generate new invoices for clients

### Analytics & Reporting
- **Outstanding Balances**: Find clients with unpaid invoices
- **Overdue Invoices**: Identify invoices past their due date
- **Invoice Statistics**: Get overall financial metrics

## Installation

1. Install the required dependencies:
```bash
cd api/MCP
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export INVOICE_API_BASE_URL="http://localhost:8000/api"
export INVOICE_API_EMAIL="your_email@example.com"
export INVOICE_API_PASSWORD="your_password"
```

## Usage

### Running the MCP Server

```bash
# From the api directory
python -m MCP

# Or with explicit arguments
python -m MCP.server --email user@example.com --password mypassword --api-url http://localhost:8000/api

# With verbose logging
python -m MCP.server --verbose
```

### Configuration

The server can be configured through environment variables or command-line arguments:

| Environment Variable | CLI Argument | Default | Description |
|---------------------|--------------|---------|-------------|
| `INVOICE_API_BASE_URL` | `--api-url` | `http://localhost:8000/api` | Base URL for the Invoice API |
| `INVOICE_API_EMAIL` | `--email` | None | Email for API authentication |
| `INVOICE_API_PASSWORD` | `--password` | None | Password for API authentication |
| `REQUEST_TIMEOUT` | N/A | 30 | HTTP request timeout in seconds |
| `DEFAULT_PAGE_SIZE` | N/A | 100 | Default pagination size |
| `MAX_PAGE_SIZE` | N/A | 1000 | Maximum pagination size |

### Using with Claude Desktop

Add this to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "python",
      "args": ["-m", "MCP.server", "--email", "your_email@example.com", "--password", "your_password"],
      "cwd": "/path/to/your/invoice/app/api",
      "env": {
        "INVOICE_API_BASE_URL": "http://localhost:8000/api"
      }
    }
  }
}
```

## Available Tools

### Client Tools

#### `list_clients`
List all clients with pagination support.

**Parameters:**
- `skip` (int, optional): Number of clients to skip for pagination (default: 0)
- `limit` (int, optional): Maximum number of clients to return (default: 100)

**Example:**
```json
{
  "name": "list_clients",
  "arguments": {
    "skip": 0,
    "limit": 50
  }
}
```

#### `search_clients`
Search for clients by name, email, phone, or address.

**Parameters:**
- `query` (string): Search query to find clients
- `skip` (int, optional): Number of results to skip for pagination (default: 0)
- `limit` (int, optional): Maximum number of results to return (default: 100)

**Example:**
```json
{
  "name": "search_clients",
  "arguments": {
    "query": "john doe",
    "limit": 20
  }
}
```

#### `get_client`
Get detailed information about a specific client.

**Parameters:**
- `client_id` (int): ID of the client to retrieve

**Example:**
```json
{
  "name": "get_client",
  "arguments": {
    "client_id": 123
  }
}
```

#### `create_client`
Create a new client.

**Parameters:**
- `name` (string): Client's full name
- `email` (string, optional): Client's email address
- `phone` (string, optional): Client's phone number
- `address` (string, optional): Client's address

**Example:**
```json
{
  "name": "create_client",
  "arguments": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-234-567-8900",
    "address": "123 Main St, City, State 12345"
  }
}
```

### Invoice Tools

#### `list_invoices`
List all invoices with pagination support.

**Parameters:**
- `skip` (int, optional): Number of invoices to skip for pagination (default: 0)
- `limit` (int, optional): Maximum number of invoices to return (default: 100)

#### `search_invoices`
Search for invoices by number, client name, status, notes, or amount.

**Parameters:**
- `query` (string): Search query to find invoices
- `skip` (int, optional): Number of results to skip for pagination (default: 0)
- `limit` (int, optional): Maximum number of results to return (default: 100)

#### `get_invoice`
Get detailed information about a specific invoice.

**Parameters:**
- `invoice_id` (int): ID of the invoice to retrieve

#### `create_invoice`
Create a new invoice for a client.

**Parameters:**
- `client_id` (int): ID of the client this invoice belongs to
- `amount` (float): Total amount of the invoice
- `due_date` (string): Due date in ISO format (YYYY-MM-DD)
- `status` (string, optional): Status of the invoice (default: "draft")
- `notes` (string, optional): Additional notes for the invoice

**Example:**
```json
{
  "name": "create_invoice",
  "arguments": {
    "client_id": 123,
    "amount": 1500.00,
    "due_date": "2024-02-15",
    "status": "sent",
    "notes": "Payment for consulting services"
  }
}
```

### Analytics Tools

#### `get_clients_with_outstanding_balance`
Get all clients that have outstanding balances (unpaid invoices).

#### `get_overdue_invoices`
Get all invoices that are past their due date and still unpaid.

#### `get_invoice_stats`
Get overall invoice statistics including total income and other metrics.

## Response Format

All tools return a JSON response with the following structure:

```json
{
  "success": true,
  "data": [...],
  "count": 10,
  "message": "Optional message",
  "pagination": {
    "skip": 0,
    "limit": 100
  }
}
```

For errors:
```json
{
  "success": false,
  "error": "Error description"
}
```

## Authentication

The MCP server handles authentication automatically by:

1. Using provided credentials to authenticate with the Invoice API
2. Storing and managing JWT tokens securely
3. Automatically refreshing tokens when they expire
4. Retrying requests with fresh tokens on authentication failures

## Security Considerations

- Store credentials securely (use environment variables, not hardcoded values)
- The token storage file (`.mcp_token`) contains sensitive information
- Use HTTPS in production environments
- Regularly rotate API credentials

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your email and password are correct
   - Ensure the Invoice API is running and accessible
   - Check that your user account is active

2. **Connection Refused**
   - Verify the API base URL is correct
   - Ensure the Invoice API server is running
   - Check firewall and network settings

3. **Permission Denied**
   - Verify your user has appropriate permissions
   - Check that you're authenticating with the correct tenant

### Debug Mode

Run with verbose logging to see detailed request/response information:

```bash
python -m MCP.server --verbose
```

## Development

### Project Structure

```
MCP/
├── __init__.py          # Package initialization
├── __main__.py          # Module entry point
├── server.py            # Main MCP server implementation
├── api_client.py        # HTTP client for Invoice API
├── auth_client.py       # Authentication handling
├── tools.py             # MCP tool definitions and implementations
├── config.py            # Configuration management
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

### Adding New Tools

1. Define the tool schema in `tools.py`
2. Add the tool to the `TOOLS` list
3. Implement the tool method in the `InvoiceTools` class
4. Add the method to the `execute_tool` method mapping

### Testing

Test the MCP server with a simple client:

```python
import asyncio
from MCP.api_client import InvoiceAPIClient

async def test_client():
    async with InvoiceAPIClient(email="test@example.com", password="password") as client:
        clients = await client.list_clients()
        print(f"Found {len(clients)} clients")

asyncio.run(test_client())
```

## License

This MCP server is part of the Invoice Application project. Please refer to the main project license. 