# MCP Quick Start Guide

Get your Invoice Application MCP server running in 5 minutes with this step-by-step guide.

## 🚀 Prerequisites

- Python 3.8 or higher
- Invoice Application API running (usually at `http://localhost:8000`)
- Your login credentials for the Invoice Application

## ⚡ Quick Setup (3 Steps)

### Step 1: Install Dependencies

```bash
cd api/MCP
pip install -r requirements.txt
```

### Step 2: Configure Your Credentials

Copy the example environment file and add your credentials:

```bash
cp example.env .env
```

Edit the `.env` file with your actual credentials:

```env
# Replace with your actual credentials
INVOICE_API_BASE_URL=http://localhost:8000/api
INVOICE_API_EMAIL=your_email@example.com
INVOICE_API_PASSWORD=your_actual_password
```

### Step 3: Test the Connection

Run the validation script to make sure everything works:

```bash
python scripts/validate_mcp_setup.py
```

If you see "✅ MCP setup is working!", you're ready to go!

## 🖥️ Using with Claude Desktop

Add this to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "python",
      "args": [
        "/path/to/your/invoice_app/api/launch_mcp.py"
      ],
      "env": {
        "INVOICE_API_BASE_URL": "http://localhost:8000/api",
        "INVOICE_API_EMAIL": "your_email@example.com",
        "INVOICE_API_PASSWORD": "your_actual_password"
      }
    }
  }
}
```

**Important:** Replace the paths and credentials with your actual values.

## 🎯 What You Can Do Now

Once connected, you can ask Claude to:

- **Manage Clients**: "List all clients with outstanding balances"
- **Create Invoices**: "Create a new invoice for client John Doe for $1500"
- **Track Expenses**: "Show me all expenses from last month"
- **Inventory Management**: "Check which items are low in stock"
- **Financial Reports**: "Get overall invoice statistics"

## 🔧 Common Commands

### Run MCP Server Manually
```bash
# From the api directory
python -m MCP

# Or with the launcher
python launch_mcp.py

# With custom settings
python -m MCP --email user@example.com --password mypass --api-url http://localhost:8080/api
```

### Test Specific Tools
```bash
# Run the validation script anytime
python scripts/validate_mcp_setup.py

# Test with verbose output
python -m MCP --verbose
```

## ❓ Need Help?

- **Connection Issues**: Check that your Invoice API is running at the specified URL
- **Authentication Problems**: Verify your email and password are correct
- **Permission Errors**: Ensure your user account has the necessary permissions

For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 📚 Next Steps

- Read the [full documentation](README.md) for all available tools
- Check the [tool reference](README.md#-available-tools) for advanced usage
- Explore the [developer guide](../../docs/developer/MCP_SERVER_GUIDE.md) for technical details
