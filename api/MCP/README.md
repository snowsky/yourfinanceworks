# Invoice Application FastMCP Server

This is a **FastMCP** (Model Context Protocol) server that enables AI assistants to interact with the YourFinanceWORKS API.

## 🚀 Quick Start

1. **Install dependencies**:

   ```bash
   cd api/MCP
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `example.env` to `.env` and provide your credentials:

   ```env
   INVOICE_API_BASE_URL=http://localhost:8000/api
   INVOICE_API_EMAIL=your_email@example.com
   INVOICE_API_PASSWORD=your_secure_password
   ```

3. **Run the Server**:
   ```bash
   python -m MCP
   ```

## 📚 Documentation

### 🚀 **New Users Start Here**
- **[Quick Start Guide](QUICK_START.md)** - Get running in 5 minutes
- **[Claude Desktop Setup](CLAUDE_DESKTOP_SETUP.md)** - Complete integration guide
- **[Validation Script](scripts/validate_mcp_setup.py)** - Test your setup automatically

### 📖 **Detailed Documentation**
- **[MCP Server Guide](../../docs/developer/MCP_SERVER_GUIDE.md)** - Architecture and technical overview
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Solutions to common issues

### 🛠️ **Available Tools**

The server exposes several tools for AI interaction:

- `list_clients`, `search_clients`, `create_client`
- `list_invoices`, `search_invoices`, `create_invoice`
- `list_expenses`, `create_expense`, `upload_expense_receipt`
- `list_bank_statements`, `reprocess_bank_statement`
- `list_inventory_items`, `adjust_stock`
- `get_cashflow_forecast`, `get_cashflow_runway`, `run_cashflow_scenario`
- `get_overdue_invoices`, `get_invoice_stats`

## 🖥️ Claude Desktop Integration

**🎯 For easy setup, see the [Claude Desktop Setup Guide](CLAUDE_DESKTOP_SETUP.md)**

For manual configuration, add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "/path/to/venv/bin/python",
      "args": [
        "/path/to/project/api/launch_mcp.py",
        "--email",
        "your@email.com",
        "--password",
        "your_pass"
      ]
    }
  }
}
```

## Security

- Use `.env` for local development; do not commit secrets.
- Tokens are stored in `.mcp_token` by default.
- Ensure the API base URL is accessible by the MCP process.

2. Set up environment variables:

Refer to the **[MCP Server Guide](../../docs/developer/MCP_SERVER_GUIDE.md)** for further configuration and tool details.

### Option A: Using Environment Variables

```bash
export INVOICE_API_BASE_URL="http://localhost:8000/api"
export INVOICE_API_EMAIL="your_email@example.com"
export INVOICE_API_PASSWORD="your_password"
```

### Option B: Using Environment File (Recommended)

Copy the example environment file and customize it:

```bash
cp example.env .env
# Edit .env with your actual values
```

The server will automatically load configuration from a `.env` file in the MCP directory if it exists.

## Configuration

### Environment File (`.env`)

The MCP server supports configuration through environment variables. You can use the provided `example.env` as a template:

```bash
# Copy the example file
cp api/MCP/example.env api/MCP/.env
```

#### Configuration Options

| Environment Variable   | Description                       | Default                     | Required |
| ---------------------- | --------------------------------- | --------------------------- | -------- |
| `INVOICE_API_BASE_URL` | Base URL for the Invoice API      | `http://localhost:8000/api` | No       |
| `INVOICE_API_EMAIL`    | Email for API authentication      | None                        | **Yes**  |
| `INVOICE_API_PASSWORD` | Password for API authentication   | None                        | **Yes**  |
| `REQUEST_TIMEOUT`      | HTTP request timeout in seconds   | `30`                        | No       |
| `DEFAULT_PAGE_SIZE`    | Default pagination size for lists | `100`                       | No       |
| `MAX_PAGE_SIZE`        | Maximum allowed pagination size   | `1000`                      | No       |
| `TOKEN_STORAGE_FILE`   | File path for storing auth tokens | `.mcp_token`                | No       |

#### Example `.env` file:

```env
# Invoice Application MCP Server Configuration

# API Configuration - REQUIRED
INVOICE_API_BASE_URL=http://localhost:8000/api
INVOICE_API_EMAIL=your_email@example.com
INVOICE_API_PASSWORD=your_secure_password

# Request Configuration - OPTIONAL
REQUEST_TIMEOUT=30

# Pagination Configuration - OPTIONAL
DEFAULT_PAGE_SIZE=100
MAX_PAGE_SIZE=1000

# Token Storage - OPTIONAL
# TOKEN_STORAGE_FILE=.mcp_token
```

### Configuration Priority

The server uses the following configuration priority (highest to lowest):

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **`.env` file values**
4. **Default values** (lowest priority)

Examples:

```bash
# Using .env file only
python -m MCP

# Override .env with command-line arguments
python -m MCP --email different@email.com --api-url http://different-server:8000/api

# Mix of .env and command-line (email from CLI, password from .env)
python -m MCP --email override@email.com
```

### Security Best Practices

⚠️ **Important Security Notes:**

- **Never commit `.env` files** to version control
- Use strong, unique passwords
- Consider using environment variables in production instead of files
- The `TOKEN_STORAGE_FILE` contains sensitive authentication tokens - keep it secure
- Regularly rotate API credentials

```bash
# Add .env to your .gitignore
echo ".env" >> .gitignore
echo ".mcp_token" >> .gitignore
```

## Usage

### Running the FastMCP Server

```bash
# From the api directory - recommended approach
python -m MCP --email user@example.com --password mypassword

# With custom API URL
python -m MCP --email user@example.com --password mypassword --api-url http://localhost:8000/api/v1

# With verbose logging
python -m MCP --email user@example.com --password mypassword --verbose
```

### Command-Line Usage

The server can be configured through command-line arguments, which override environment variables:

| CLI Argument | Environment Variable   | Default                        | Description                     |
| ------------ | ---------------------- | ------------------------------ | ------------------------------- |
| `--api-url`  | `INVOICE_API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL for the Invoice API    |
| `--email`    | `INVOICE_API_EMAIL`    | None                           | Email for API authentication    |
| `--password` | `INVOICE_API_PASSWORD` | None                           | Password for API authentication |
| `--verbose`  | N/A                    | False                          | Enable verbose logging          |

### Using with Claude Desktop

Add this to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "/path/to/your/venv/bin/python",
      "args": [
        "/path/to/your/project/api/launch_mcp.py",
        "--email",
        "your_email@example.com",
        "--password",
        "your_password"
      ],
      "env": {
        "INVOICE_API_BASE_URL": "http://localhost:8000/api/v1"
      }
    }
  }
}
```

**Important**: Use the full path to your virtual environment's Python interpreter to ensure all dependencies are available.

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
    "amount": 1500.0,
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

### Currency Management Tools

#### `list_currencies`

List supported currencies with optional filtering for active currencies only.

**Parameters:**

- `active_only` (boolean, optional): Return only active currencies (default: true)

**Example:**

```json
{
  "name": "list_currencies",
  "arguments": {
    "active_only": true
  }
}
```

#### `create_currency`

Create a custom currency for the tenant.

**Parameters:**

- `code` (string): Currency code (e.g., USD, EUR)
- `name` (string): Currency name
- `symbol` (string): Currency symbol
- `decimal_places` (int, optional): Number of decimal places (default: 2)
- `is_active` (boolean, optional): Whether the currency is active (default: true)

**Example:**

```json
{
  "name": "create_currency",
  "arguments": {
    "code": "BTC",
    "name": "Bitcoin",
    "symbol": "₿",
    "decimal_places": 8,
    "is_active": true
  }
}
```

#### `convert_currency`

Convert amount from one currency to another using current or historical exchange rates.

**Parameters:**

- `amount` (float): Amount to convert
- `from_currency` (string): Source currency code
- `to_currency` (string): Target currency code
- `conversion_date` (string, optional): Date for conversion rate in YYYY-MM-DD format

**Example:**

```json
{
  "name": "convert_currency",
  "arguments": {
    "amount": 100.0,
    "from_currency": "USD",
    "to_currency": "EUR",
    "conversion_date": "2024-01-15"
  }
}
```

### Payment Management Tools

### Expense Management Tools

#### `list_expenses`

List expenses with optional filters and pagination.

**Parameters:**

- `skip` (int, optional): Number of records to skip (default: 0)
- `limit` (int, optional): Max records to return (default: 100)
- `category` (string, optional): Filter by category
- `invoice_id` (int, optional): Filter by linked invoice id
- `unlinked_only` (bool, optional): Only expenses not linked to any invoice

**Example:**

```json
{
  "name": "list_expenses",
  "arguments": {
    "skip": 0,
    "limit": 50,
    "category": "office_supplies",
    "unlinked_only": true
  }
}
```

#### `get_expense`

Get a single expense by ID.

**Parameters:**

- `expense_id` (int): Expense ID

**Example:**

```json
{
  "name": "get_expense",
  "arguments": {
    "expense_id": 123
  }
}
```

#### `create_expense`

Create a new expense.

**Parameters:**

- `amount` (float): Expense amount before tax
- `currency` (string): Currency code (e.g., USD)
- `expense_date` (string): ISO date (YYYY-MM-DD)
- `category` (string): Expense category
- `vendor` (string, optional)
- `tax_rate` (float, optional)
- `tax_amount` (float, optional)
- `total_amount` (float, optional)
- `payment_method` (string, optional)
- `reference_number` (string, optional)
- `status` (string, optional)
- `notes` (string, optional)
- `invoice_id` (int, optional)

**Example:**

```json
{
  "name": "create_expense",
  "arguments": {
    "amount": 150.0,
    "currency": "USD",
    "expense_date": "2024-01-15",
    "category": "office_supplies",
    "vendor": "Office Depot",
    "tax_rate": 8.5,
    "tax_amount": 12.75,
    "total_amount": 162.75,
    "payment_method": "credit_card",
    "reference_number": "REF-12345",
    "status": "approved",
    "notes": "Monthly office supplies purchase"
  }
}
```

#### `update_expense`

Update fields of an existing expense.

**Parameters:**

- `expense_id` (int): ID of the expense to update
- Other fields same as `create_expense`, all optional

**Example:**

```json
{
  "name": "update_expense",
  "arguments": {
    "expense_id": 123,
    "category": "travel",
    "notes": "Updated category to travel"
  }
}
```

#### `delete_expense`

Delete an expense by ID.

**Parameters:**

- `expense_id` (int): ID to delete

**Example:**

```json
{
  "name": "delete_expense",
  "arguments": {
    "expense_id": 123
  }
}
```

#### `upload_expense_receipt`

Upload an attachment file for an expense.

**Parameters:**

- `expense_id` (int)
- `file_path` (string): Absolute path to local file to upload
- `filename` (string, optional): Override filename
- `content_type` (string, optional): Explicit MIME type

**Notes:** Up to 5 attachments per expense. Allowed types: PDF, JPG, PNG. Max 10 MB as enforced by backend.

**Example:**

```json
{
  "name": "upload_expense_receipt",
  "arguments": {
    "expense_id": 123,
    "file_path": "/path/to/receipt.pdf",
    "filename": "office_supplies_receipt.pdf",
    "content_type": "application/pdf"
  }
}
```

#### `list_expense_attachments`

List attachments for an expense.

**Parameters:**

- `expense_id` (int)

**Example:**

```json
{
  "name": "list_expense_attachments",
  "arguments": {
    "expense_id": 123
  }
}
```

#### `delete_expense_attachment`

Delete an attachment of an expense.

**Parameters:**

- `expense_id` (int)
- `attachment_id` (int)

**Example:**

```json
{
  "name": "delete_expense_attachment",
  "arguments": {
    "expense_id": 123,
    "attachment_id": 456
  }
}
```

### Statement Management Tools

#### `list_statements`

List all imported statements with pagination support.

**Parameters:**

- `skip` (int, optional): Number of records to skip (default: 0)
- `limit` (int, optional): Max records to return (default: 100)
- `account_name` (string, optional): Filter by bank account name
- `status` (string, optional): Filter by processing status

**Example:**

```json
{
  "name": "list_statements",
  "arguments": {
    "skip": 0,
    "limit": 50,
    "account_name": "Business Checking",
    "status": "processed"
  }
}
```

#### `get_bank_statement`

Get detailed information about a specific statement.

**Parameters:**

- `statement_id` (int): ID of the statement to retrieve

**Example:**

```json
{
  "name": "get_bank_statement",
  "arguments": {
    "statement_id": 123
  }
}
```

#### `reprocess_bank_statement`

Reprocess a statement for better transaction matching and categorization.

**Parameters:**

- `statement_id` (int): ID of the statement to reprocess
- `force_reprocess` (bool, optional): Force reprocessing even if already processed (default: false)

**Example:**

```json
{
  "name": "reprocess_bank_statement",
  "arguments": {
    "statement_id": 123,
    "force_reprocess": true
  }
}
```

#### `update_bank_statement_meta`

Update metadata for a statement (name, description, etc.).

**Parameters:**

- `statement_id` (int): ID of the statement to update
- `account_name` (string, optional): Bank account name
- `statement_period` (string, optional): Statement period description
- `notes` (string, optional): Additional notes
- `status` (string, optional): Processing status

**Example:**

```json
{
  "name": "update_bank_statement_meta",
  "arguments": {
    "statement_id": 123,
    "account_name": "Business Checking - Updated",
    "statement_period": "January 2024",
    "notes": "Updated with correct account name",
    "status": "reviewed"
  }
}
```

#### `delete_bank_statement`

Delete a statement and all associated transactions.

**Parameters:**

- `statement_id` (int): ID of the statement to delete
- `confirm_deletion` (bool, optional): Confirmation flag to prevent accidental deletion (default: false)

**Example:**

```json
{
  "name": "delete_bank_statement",
  "arguments": {
    "statement_id": 123,
    "confirm_deletion": true
  }
}
```

### Inventory Management Tools

#### `list_inventory_categories`

List all inventory categories with optional filtering for active categories only.

**Parameters:**

- `active_only` (boolean, optional): Return only active categories (default: true)

**Example:**

```json
{
  "name": "list_inventory_categories",
  "arguments": {
    "active_only": true
  }
}
```

#### `create_inventory_category`

Create a new inventory category for organizing inventory items.

**Parameters:**

- `name` (string): Category name
- `description` (string, optional): Category description
- `is_active` (boolean, optional): Whether category is active (default: true)

**Example:**

```json
{
  "name": "create_inventory_category",
  "arguments": {
    "name": "Electronics",
    "description": "Electronic devices and components",
    "is_active": true
  }
}
```

#### `update_inventory_category`

Update an existing inventory category.

**Parameters:**

- `category_id` (int): ID of category to update
- `name` (string, optional): New category name
- `description` (string, optional): New category description
- `is_active` (boolean, optional): New active status

**Example:**

```json
{
  "name": "update_inventory_category",
  "arguments": {
    "category_id": 123,
    "name": "Updated Electronics",
    "description": "Updated description"
  }
}
```

#### `list_inventory_items`

List inventory items with optional filtering and pagination.

**Parameters:**

- `skip` (int, optional): Number of items to skip for pagination (default: 0)
- `limit` (int, optional): Maximum number of items to return (default: 100)
- `query` (string, optional): Search query for items
- `category_id` (int, optional): Filter by category ID
- `item_type` (string, optional): Filter by item type
- `low_stock_only` (boolean, optional): Return only low stock items (default: false)
- `track_stock` (boolean, optional): Filter by stock tracking setting

**Example:**

```json
{
  "name": "list_inventory_items",
  "arguments": {
    "skip": 0,
    "limit": 50,
    "category_id": 123,
    "low_stock_only": true
  }
}
```

#### `create_inventory_item`

Create a new inventory item with detailed specifications.

**Parameters:**

- `name` (string): Item name
- `unit_price` (float): Unit selling price
- `sku` (string, optional): Stock Keeping Unit
- `description` (string, optional): Item description
- `category_id` (int, optional): Category ID
- `cost_price` (float, optional): Unit cost price
- `currency` (string, optional): Currency code (default: "USD")
- `track_stock` (boolean, optional): Whether to track stock levels (default: true)
- `current_stock` (float, optional): Current stock quantity (default: 0)
- `minimum_stock` (float, optional): Minimum stock level (default: 0)
- `unit_of_measure` (string, optional): Unit of measure (default: "each")
- `item_type` (string, optional): Type of item (default: "product")
- `is_active` (boolean, optional): Whether item is active (default: true)

**Example:**

```json
{
  "name": "create_inventory_item",
  "arguments": {
    "name": "Wireless Mouse",
    "unit_price": 29.99,
    "sku": "WM-001",
    "description": "Ergonomic wireless mouse",
    "category_id": 123,
    "current_stock": 50,
    "minimum_stock": 10
  }
}
```

#### `update_inventory_item`

Update an existing inventory item.

**Parameters:**

- `item_id` (int): ID of item to update
- Other parameters same as `create_inventory_item`, all optional

**Example:**

```json
{
  "name": "update_inventory_item",
  "arguments": {
    "item_id": 456,
    "unit_price": 34.99,
    "current_stock": 45
  }
}
```

#### `adjust_stock`

Adjust stock levels for an inventory item manually.

**Parameters:**

- `item_id` (int): ID of inventory item
- `quantity` (float): Quantity to adjust (positive for increase, negative for decrease)
- `reason` (string, optional): Reason for adjustment (default: "Manual adjustment")

**Example:**

```json
{
  "name": "adjust_stock",
  "arguments": {
    "item_id": 456,
    "quantity": 25,
    "reason": "Received new shipment"
  }
}
```

#### `get_inventory_analytics`

Get comprehensive inventory analytics and statistics.

**Example:**

```json
{
  "name": "get_inventory_analytics",
  "arguments": {}
}
```

#### `get_low_stock_items`

Get items with stock levels below their minimum threshold.

**Example:**

```json
{
  "name": "get_low_stock_items",
  "arguments": {}
}
```

#### `list_payments`

List all payments with pagination support.

**Parameters:**

- `skip` (int, optional): Number of payments to skip for pagination (default: 0)
- `limit` (int, optional): Maximum number of payments to return (default: 100)

#### `create_payment`

Create a new payment for an invoice.

**Parameters:**

- `invoice_id` (int): ID of the invoice this payment is for
- `amount` (float): Payment amount
- `payment_date` (string): Payment date in ISO format (YYYY-MM-DD)
- `payment_method` (string): Payment method (cash, check, credit_card, etc.)
- `reference` (string, optional): Payment reference number
- `notes` (string, optional): Additional notes

**Example:**

```json
{
  "name": "create_payment",
  "arguments": {
    "invoice_id": 123,
    "amount": 500.0,
    "payment_date": "2024-01-15",
    "payment_method": "credit_card",
    "reference": "TXN-12345",
    "notes": "Partial payment"
  }
}
```

### Cash Flow Tools

#### `get_cashflow_forecast`

Get projected cash inflows, outflows, daily balances, and alerts.

**Parameters:**

- `period` (string, optional): Forecast period, one of `7d`, `30d`, `90d`, or `365d` (default: `30d`)
- `current_balance` (float, optional): Override for starting cash balance

#### `get_cashflow_runway`

Calculate cash runway using recent income and burn rate.

**Parameters:**

- `current_balance` (float, optional): Override for starting cash balance

#### `run_cashflow_scenario`

Run a what-if scenario against a forecast.

**Parameters:**

- `description` (string): Scenario description
- `period` (string, optional): Forecast period, one of `7d`, `30d`, `90d`, or `365d`
- `delayed_invoice_ids` (array of int, optional): Invoice IDs to delay
- `delay_days` (int, optional): Number of days to delay selected invoices
- `additional_expense` (float, optional): Added one-time expense amount
- `additional_expense_date` (string, optional): ISO date for added expense (`YYYY-MM-DD`)
- `revenue_change_percent` (float, optional): Percent change to projected revenue
- `expense_change_percent` (float, optional): Percent change to projected expenses
- `current_balance` (float, optional): Override for starting cash balance

**Example:**

```json
{
  "name": "run_cashflow_scenario",
  "arguments": {
    "description": "Client pays two weeks late and expenses rise",
    "period": "90d",
    "delayed_invoice_ids": [123, 456],
    "delay_days": 14,
    "expense_change_percent": 10
  }
}
```

#### `get_cashflow_alerts`

Get cash flow alerts based on configured thresholds.

**Parameters:**

- `current_balance` (float, optional): Override for starting cash balance

#### `get_cashflow_thresholds`

Get cash flow alert threshold and projection settings.

#### `update_cashflow_thresholds`

Update cash flow alert threshold and projection settings.

**Parameters:**

- `settings` (object): Partial settings object, such as `safety_threshold`, `warning_threshold`, `currency`, `include_bank_statement_patterns`, `bank_statement_lookback_days`, `bank_statement_intervals`, `bank_statement_inflow_categories`, or `bank_statement_outflow_categories`

### Settings Tools

#### `get_settings`

Get tenant settings including company information and invoice settings.

**Example:**

```json
{
  "name": "get_settings",
  "arguments": {}
}
```

### Discount Rules Tools

#### `list_discount_rules`

List all discount rules for the current tenant.

**Example:**

```json
{
  "name": "list_discount_rules",
  "arguments": {}
}
```

#### `create_discount_rule`

Create a new discount rule for the tenant.

**Parameters:**

- `name` (string): Name of the discount rule
- `discount_type` (string): Type of discount (percentage, fixed)
- `discount_value` (float): Discount value
- `min_amount` (float, optional): Minimum amount for discount to apply
- `max_discount` (float, optional): Maximum discount amount
- `priority` (int, optional): Priority of the rule, higher number = higher priority (default: 1)
- `is_active` (boolean, optional): Whether the rule is active (default: true)
- `currency` (string, optional): Currency code for the rule

**Example:**

```json
{
  "name": "create_discount_rule",
  "arguments": {
    "name": "Bulk Discount",
    "discount_type": "percentage",
    "discount_value": 10.0,
    "min_amount": 1000.0,
    "max_discount": 500.0,
    "priority": 1,
    "is_active": true,
    "currency": "USD"
  }
}
```

### CRM Tools

#### `create_client_note`

Create a note for a client.

**Parameters:**

- `client_id` (int): ID of the client
- `title` (string): Note title
- `content` (string): Note content
- `note_type` (string, optional): Type of note (general, call, meeting, etc.) (default: "general")

**Example:**

```json
{
  "name": "create_client_note",
  "arguments": {
    "client_id": 123,
    "title": "Follow-up Call",
    "content": "Called client to discuss payment terms. They agreed to pay within 30 days.",
    "note_type": "call"
  }
}
```

### Email Tools

#### `send_invoice_email`

Send an invoice via email.

**Parameters:**

- `invoice_id` (int): ID of the invoice to send
- `to_email` (string, optional): Recipient email address (uses client email if not provided)
- `to_name` (string, optional): Recipient name (uses client name if not provided)
- `subject` (string, optional): Email subject
- `message` (string, optional): Custom message

**Example:**

```json
{
  "name": "send_invoice_email",
  "arguments": {
    "invoice_id": 123,
    "to_email": "client@example.com",
    "to_name": "John Doe",
    "subject": "Invoice #INV-001",
    "message": "Please find attached invoice for our services."
  }
}
```

#### `test_email_configuration`

Test email configuration by sending a test email.

**Parameters:**

- `test_email` (string): Email address to send test email to

**Example:**

```json
{
  "name": "test_email_configuration",
  "arguments": {
    "test_email": "test@example.com"
  }
}
```

### Tenant Tools

#### `get_tenant_info`

Get current tenant information including company details and settings.

**Example:**

```json
{
  "name": "get_tenant_info",
  "arguments": {}
}
```

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
python -m MCP --verbose
```

## Development

### Project Structure

```
MCP/
├── __init__.py          # Package initialization
├── __main__.py          # Module entry point
├── server.py            # Main FastMCP server implementation
├── api_client.py        # HTTP client for Invoice API
├── auth_client.py       # Authentication handling
├── tools.py             # FastMCP tool implementations
├── config.py            # Configuration management
├── requirements.txt     # Python dependencies (includes FastMCP)
└── README.md           # This file
```

### FastMCP Benefits

This implementation uses FastMCP, which provides several advantages over traditional MCP:

- **Simplified Development**: Decorator-based tool definitions (`@mcp.tool()`)
- **Automatic Type Inference**: Uses Python type hints for schema generation
- **Better Error Handling**: Built-in error management and logging
- **Modern Python**: Leverages async/await and modern Python features
- **Reduced Boilerplate**: Less code needed compared to traditional MCP

### Adding New Tools

With FastMCP, adding new tools is simpler:

1. Add a new function in `server.py` with the `@mcp.tool()` decorator
2. Define the function parameters with proper type hints
3. Implement the business logic by calling the appropriate `InvoiceTools` method
4. Return a dictionary with the response data

Example:

```python
@mcp.tool()
async def get_client_invoices(client_id: int, status: Optional[str] = None) -> dict:
    """Get all invoices for a specific client, optionally filtered by status."""
    if tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    # Implementation would go here
    return await tools.get_client_invoices(client_id=client_id, status=status)
```

### Testing

Test the FastMCP server with the included test script:

```bash
cd api
python MCP/test_mcp.py
```

Or test the API client directly:

```python
import asyncio
from MCP.api_client import InvoiceAPIClient

async def test_client():
    async with InvoiceAPIClient(email="test@example.com", password="password") as client:
        clients = await client.list_clients()
        print(f"Found {len(clients)} clients")

asyncio.run(test_client())
```

## Why FastMCP?

FastMCP was chosen for this implementation because it:

- **Reduces Complexity**: Traditional MCP requires extensive boilerplate code for tool definitions, schemas, and request handling. FastMCP eliminates this with decorators and automatic type inference.

- **Improves Developer Experience**: Function signatures become the API - no need to manually define JSON schemas or handle argument parsing.

- **Better Error Handling**: Built-in error management and consistent response formatting.

- **Modern Python Features**: Full support for type hints, async/await, and modern Python patterns.

- **Maintainability**: Less code means fewer bugs and easier maintenance.

## License

This FastMCP server is part of the Invoice Application project. Please refer to the main project license.

## Recent Updates

### AI-Powered Intent Classification (Latest)

- **Eliminated Hardcoded Patterns**: Replaced keyword pattern matching with AI-based intent classification
- **Dynamic Tool Selection**: AI automatically determines which MCP tool to use based on message meaning
- **Natural Language Understanding**: Supports natural language variations without maintaining pattern lists
- **Improved Accuracy**: AI classification provides better understanding of user intent
- **Automatic Default Config**: System automatically sets single active AI config as default
- **Enhanced Debugging**: Added comprehensive logging for intent classification and tool selection

### AI Intent Classification System

The MCP server now uses AI-powered intent classification to route queries:

1. **Intent Classification**: Uses AI to classify user messages into predefined business categories
2. **Dynamic Tool Selection**: Automatically selects appropriate MCP tools based on classified intent
3. **Business Categories**: Supports analyze_patterns, payments, clients, invoices, expenses, statements, currencies, outstanding, overdue, statistics
4. **LLM Fallback**: Uses LLM for general questions classified as non-business queries
5. **Adaptive Understanding**: AI understands natural language variations without hardcoded patterns

### Usage Examples with AI Classification

```
# These all get classified as "statements" intent:
"Show statements"
"What statements do I have?"
"Display my banking information"
"List all my bank account statements"

# These all get classified as "expenses" intent:
"List all expenses"
"What did I spend money on?"
"Show my business expenses"
"Display expense information"

# These all get classified as "clients" intent:
"List all my clients"
"Who are my customers?"
"Show me client information"
"Display customer details"
```
