# Claude Desktop Setup Guide

Complete guide to connect your Invoice Application with Claude Desktop using MCP.

## 🎯 What This Enables

Once connected, Claude Desktop can:
- **Access your financial data** securely
- **Create and manage invoices** through natural language
- **Track expenses and inventory** with simple commands
- **Generate reports** and analytics on demand
- **Automate workflows** based on your business data

## 📋 Prerequisites

1. **Claude Desktop** installed on your computer
2. **Invoice Application API** running and accessible
3. **MCP Server** configured (see [QUICK_START.md](QUICK_START.md))

## 🛠️ Setup Methods

### Method 1: Automatic Configuration (Recommended)

Run the validation script to generate your configuration automatically:

```bash
cd api/MCP
python scripts/validate_mcp_setup.py
```

The script will:
- Test your MCP setup
- Generate the configuration file
- Show you exactly what to copy

### Method 2: Manual Configuration

#### Step 1: Find Your Configuration

Run this command to get your project path:
```bash
cd api/MCP
pwd
```

#### Step 2: Locate Claude Desktop Config

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

#### Step 3: Add MCP Configuration

Add this to your `claude_desktop_config.json`:

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

**Important:**
- Replace `/path/to/your/invoice_app` with your actual project path
- Replace credentials with your actual login details
- Keep the `env` section for security (don't hardcode credentials in args)

#### Step 4: Restart Claude Desktop

Close and restart Claude Desktop to load the new configuration.

## ✅ Verification

### Check Connection Status

1. Open Claude Desktop
2. Look for "Invoice Application" in the connected services
3. Start a new conversation and try:

```
List my clients with outstanding balances
```

If you get a response with client data, the connection is working!

### Test Common Commands

Try these commands to verify everything works:

```
Show me the last 5 invoices
Create a new client named "Test Company"
List all expenses from this month
Check which inventory items are low in stock
```

## 🔧 Advanced Configuration

### Using Virtual Environment

If you use a virtual environment (recommended):

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "/path/to/your/venv/bin/python",
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

### Production/Remote API

For production or remote API servers:

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "python",
      "args": [
        "/path/to/your/invoice_app/api/launch_mcp.py"
      ],
      "env": {
        "INVOICE_API_BASE_URL": "https://your-api.company.com/api",
        "INVOICE_API_EMAIL": "your_email@company.com",
        "INVOICE_API_PASSWORD": "your_secure_password"
      }
    }
  }
}
```

### Multiple Environments

You can configure multiple MCP servers for different environments:

```json
{
  "mcpServers": {
    "invoice-app-dev": {
      "command": "python",
      "args": ["/path/to/dev/api/launch_mcp.py"],
      "env": {
        "INVOICE_API_BASE_URL": "http://localhost:8000/api",
        "INVOICE_API_EMAIL": "dev@company.com",
        "INVOICE_API_PASSWORD": "dev_password"
      }
    },
    "invoice-app-prod": {
      "command": "python", 
      "args": ["/path/to/prod/api/launch_mcp.py"],
      "env": {
        "INVOICE_API_BASE_URL": "https://api.company.com/api",
        "INVOICE_API_EMAIL": "admin@company.com",
        "INVOICE_API_PASSWORD": "prod_password"
      }
    }
  }
}
```

## 🎨 Example Conversations

### Invoice Management
```
User: Create a new invoice for John Doe's company for $2500 due next Friday

Claude: I'll create that invoice for you.
[Creates invoice with client lookup, amount, due date calculation]

User: Send that invoice by email

Claude: I'll send the invoice to John Doe's email address.
[Sends invoice with default template]
```

### Financial Analysis
```
User: Show me a summary of this month's financial activity

Claude: Here's your financial summary for this month:
[Shows total income, expenses, profit, outstanding invoices]

User: Which clients have overdue payments?

Claude: The following clients have overdue payments:
[Lists overdue invoices with amounts and days overdue]
```

### Inventory Management
```
User: Check if we need to reorder any products

Claude: Based on current stock levels and sales velocity, these items need reordering:
[Shows low stock alerts with suggested quantities]

User: Update the stock for wireless mouse to 100 units

Claude: I'll update the stock level for wireless mouse to 100 units.
[Updates inventory with reason: "Manual stock adjustment"]
```

## 🔒 Security Best Practices

### Environment Variables
- **Always** use the `env` section for credentials
- **Never** hardcode passwords in the `args` array
- **Consider** using environment-specific configuration files

### File Permissions
```bash
# Restrict access to your config file
chmod 600 claude_desktop_config.json
```

### Network Security
- Use HTTPS URLs for production APIs
- Ensure your API has proper authentication
- Consider VPN access for remote development

## 🐛 Troubleshooting

### Common Issues

**"MCP server not found"**
- Check that the Python path is correct
- Verify the launch script exists at the specified path
- Ensure Python dependencies are installed

**"Authentication failed"**
- Verify your email and password are correct
- Check that the API URL is accessible
- Ensure your user account is active

**"Connection refused"**
- Make sure the Invoice API is running
- Check the API URL and port
- Verify firewall settings

**"Permission denied"**
- Check file permissions on the launch script
- Ensure Python executable has execute permissions
- Verify virtual environment access

### Debug Mode

Enable verbose logging for troubleshooting:

```json
{
  "mcpServers": {
    "invoice-app": {
      "command": "python",
      "args": [
        "/path/to/your/invoice_app/api/launch_mcp.py",
        "--verbose"
      ],
      "env": { ... }
    }
  }
}
```

### Test Connection Manually

Test the MCP server directly:

```bash
cd api/MCP
python -m MCP --email your@email.com --password yourpass --verbose
```

## 📞 Getting Help

If you encounter issues:

1. **Check the validation script**: `python scripts/validate_mcp_setup.py`
2. **Review the troubleshooting guide**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. **Check the main documentation**: [README.md](README.md)
4. **Verify API connectivity**: Ensure your Invoice Application API is accessible

## 🔄 Updates and Maintenance

### Updating MCP Server

When you update the Invoice Application:

```bash
cd api/MCP
git pull
pip install -r requirements.txt
python scripts/validate_mcp_setup.py
```

### Changing Credentials

If you change your password:

1. Update the `.env` file in `api/MCP/`
2. Update your `claude_desktop_config.json`
3. Restart Claude Desktop

### Backup Configuration

Keep a backup of your working configuration:

```bash
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json ~/claude_config_backup.json
```
