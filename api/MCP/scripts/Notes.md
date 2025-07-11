### Under api folder and run:

```
python MCP/scripts/test_mcp_working.py
```

### Outputs:

```
🚀 Starting MCP Tools Test Suite...

🔍 Testing MCP Module Imports...
✅ InvoiceTools imported successfully
✅ InvoiceAPIClient imported successfully
✅ Config imported successfully
✅ InvoiceAPIAuthClient imported successfully

🔍 Testing InvoiceTools Class Methods...
✅ All 23 expected methods found in InvoiceTools

🔍 Testing API Client Class...
✅ All 20 expected API client methods found

🔍 Testing Tool Argument Schemas...
✅ All 20 tool argument schemas found:
  - ListClientsArgs
  - SearchClientsArgs
  - GetClientArgs
  - CreateClientArgs
  - ListInvoicesArgs
  - SearchInvoicesArgs
  - GetInvoiceArgs
  - CreateInvoiceArgs
  - ListCurrenciesArgs
  - CreateCurrencyArgs
  - ConvertCurrencyArgs
  - ListPaymentsArgs
  - CreatePaymentArgs
  - GetSettingsArgs
  - ListDiscountRulesArgs
  - CreateDiscountRuleArgs
  - CreateClientNoteArgs
  - SendInvoiceEmailArgs
  - TestEmailArgs
  - GetTenantArgs

🔍 Testing Config Module...
✅ Config loaded successfully
  - API Base URL: http://localhost:8000/api
  - Default Page Size: 100
  - Max Page Size: 1000
  - Request Timeout: 30

🔍 Testing Server Import...
✅ Server module imported successfully

📊 Test Results: 6/6 tests passed
🎉 All tests passed! MCP tools are ready to use.

📋 Summary of available tools:
  • Client Management: list_clients, search_clients, get_client, create_client
  • Invoice Management: list_invoices, search_invoices, get_invoice, create_invoice
  • Currency Management: list_currencies, create_currency, convert_currency
  • Payment Management: list_payments, create_payment
  • Settings: get_settings, get_tenant_info
  • Discount Rules: list_discount_rules, create_discount_rule
  • CRM: create_client_note
  • Email: send_invoice_email, test_email_configuration
  • Analytics: get_clients_with_outstanding_balance, get_overdue_invoices, get_invoice_stats

🚀 To run the MCP server:
  python -m MCP --email your_email@example.com --password your_password

📝 To use with Claude Desktop, add to claude_desktop_config.json:
  {
    "mcpServers": {
      "invoice-app": {
        "command": "python",
        "args": ["-m", "MCP", "--email", "your_email@example.com", "--password", "your_password"],
        "cwd": "PATH_TO_REPO/api"
      }
    }
  }
```