#!/usr/bin/env python3
"""
Working test script for MCP tools - adds current directory to Python path
"""
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def test_mcp_imports():
    """Test that MCP modules can be imported"""
    print("🔍 Testing MCP Module Imports...")
    
    try:
        # Test importing the main modules
        from MCP.tools import InvoiceTools
        print("✅ InvoiceTools imported successfully")
        
        from MCP.api_client import InvoiceAPIClient
        print("✅ InvoiceAPIClient imported successfully")
        
        from MCP.config import config
        print("✅ Config imported successfully")
        
        from MCP.auth_client import InvoiceAPIAuthClient
        print("✅ InvoiceAPIAuthClient imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_tools_class():
    """Test the InvoiceTools class methods"""
    print("\n🔍 Testing InvoiceTools Class Methods...")
    
    try:
        from MCP.tools import InvoiceTools
        
        # Create a mock API client for testing
        class MockAPIClient:
            def __init__(self):
                self.base_url = "http://localhost:8000/api"
        
        mock_client = MockAPIClient()
        tools = InvoiceTools(mock_client)
        
        # Test that all expected methods exist
        expected_methods = [
            'list_clients', 'search_clients', 'get_client', 'create_client',
            'list_invoices', 'search_invoices', 'get_invoice', 'create_invoice',
            'list_currencies', 'create_currency', 'convert_currency',
            'list_payments', 'create_payment',
            'get_settings', 'get_tenant_info',
            'list_discount_rules', 'create_discount_rule',
            'create_client_note',
            'send_invoice_email', 'test_email_configuration',
            'get_clients_with_outstanding_balance', 'get_overdue_invoices', 'get_invoice_stats'
        ]
        
        missing_methods = []
        for method in expected_methods:
            if not hasattr(tools, method):
                missing_methods.append(method)
        
        if missing_methods:
            print(f"❌ Missing methods: {missing_methods}")
            return False
        else:
            print(f"✅ All {len(expected_methods)} expected methods found in InvoiceTools")
            return True
            
    except Exception as e:
        print(f"❌ Error testing InvoiceTools: {e}")
        return False

def test_api_client():
    """Test the API client class"""
    print("\n🔍 Testing API Client Class...")
    
    try:
        from MCP.api_client import InvoiceAPIClient
        
        # Test that API client can be instantiated
        client = InvoiceAPIClient(
            base_url="http://localhost:8000/api",
            email="test@example.com",
            password="testpass"
        )
        
        # Check for expected methods
        expected_methods = [
            'list_clients', 'get_client', 'search_clients', 'create_client',
            'list_invoices', 'get_invoice', 'search_invoices', 'create_invoice',
            'list_currencies', 'create_currency', 'convert_currency',
            'list_payments', 'create_payment',
            'get_settings', 'get_tenant_info',
            'list_discount_rules', 'create_discount_rule',
            'create_client_note',
            'send_invoice_email', 'test_email_configuration'
        ]
        
        missing_methods = []
        for method in expected_methods:
            if not hasattr(client, method):
                missing_methods.append(method)
        
        if missing_methods:
            print(f"❌ Missing API client methods: {missing_methods}")
            return False
        else:
            print(f"✅ All {len(expected_methods)} expected API client methods found")
            return True
            
    except Exception as e:
        print(f"❌ Error testing API client: {e}")
        return False

def test_tool_schemas():
    """Test that all tool argument schemas are defined"""
    print("\n🔍 Testing Tool Argument Schemas...")
    
    try:
        from MCP.tools import (
            ListClientsArgs, SearchClientsArgs, GetClientArgs, CreateClientArgs,
            ListInvoicesArgs, SearchInvoicesArgs, GetInvoiceArgs, CreateInvoiceArgs,
            ListCurrenciesArgs, CreateCurrencyArgs, ConvertCurrencyArgs,
            ListPaymentsArgs, CreatePaymentArgs,
            GetSettingsArgs,
            ListDiscountRulesArgs, CreateDiscountRuleArgs,
            CreateClientNoteArgs,
            SendInvoiceEmailArgs, TestEmailArgs,
            GetTenantArgs
        )
        
        schemas = [
            ('ListClientsArgs', ListClientsArgs),
            ('SearchClientsArgs', SearchClientsArgs),
            ('GetClientArgs', GetClientArgs),
            ('CreateClientArgs', CreateClientArgs),
            ('ListInvoicesArgs', ListInvoicesArgs),
            ('SearchInvoicesArgs', SearchInvoicesArgs),
            ('GetInvoiceArgs', GetInvoiceArgs),
            ('CreateInvoiceArgs', CreateInvoiceArgs),
            ('ListCurrenciesArgs', ListCurrenciesArgs),
            ('CreateCurrencyArgs', CreateCurrencyArgs),
            ('ConvertCurrencyArgs', ConvertCurrencyArgs),
            ('ListPaymentsArgs', ListPaymentsArgs),
            ('CreatePaymentArgs', CreatePaymentArgs),
            ('GetSettingsArgs', GetSettingsArgs),
            ('ListDiscountRulesArgs', ListDiscountRulesArgs),
            ('CreateDiscountRuleArgs', CreateDiscountRuleArgs),
            ('CreateClientNoteArgs', CreateClientNoteArgs),
            ('SendInvoiceEmailArgs', SendInvoiceEmailArgs),
            ('TestEmailArgs', TestEmailArgs),
            ('GetTenantArgs', GetTenantArgs)
        ]
        
        print(f"✅ All {len(schemas)} tool argument schemas found:")
        for name, schema in schemas:
            print(f"  - {name}")
        return True
            
    except Exception as e:
        print(f"❌ Error testing tool schemas: {e}")
        return False

def test_config():
    """Test the config module"""
    print("\n🔍 Testing Config Module...")
    
    try:
        from MCP.config import config
        print(f"✅ Config loaded successfully")
        print(f"  - API Base URL: {config.API_BASE_URL}")
        print(f"  - Default Page Size: {config.DEFAULT_PAGE_SIZE}")
        print(f"  - Max Page Size: {config.MAX_PAGE_SIZE}")
        print(f"  - Request Timeout: {config.REQUEST_TIMEOUT}")
        return True
        
    except Exception as e:
        print(f"❌ Error testing config: {e}")
        return False

def test_server_import():
    """Test that the server can be imported (without running it)"""
    print("\n🔍 Testing Server Import...")
    
    try:
        # Import the server module to check for syntax errors
        import MCP.server
        print("✅ Server module imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error importing server: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting MCP Tools Test Suite...\n")
    
    tests = [
        test_mcp_imports,
        test_tools_class,
        test_api_client,
        test_tool_schemas,
        test_config,
        test_server_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! MCP tools are ready to use.")
        print("\n📋 Summary of available tools:")
        print("  • Client Management: list_clients, search_clients, get_client, create_client")
        print("  • Invoice Management: list_invoices, search_invoices, get_invoice, create_invoice")
        print("  • Currency Management: list_currencies, create_currency, convert_currency")
        print("  • Payment Management: list_payments, create_payment")
        print("  • Settings: get_settings, get_tenant_info")
        print("  • Discount Rules: list_discount_rules, create_discount_rule")
        print("  • CRM: create_client_note")
        print("  • Email: send_invoice_email, test_email_configuration")
        print("  • Analytics: get_clients_with_outstanding_balance, get_overdue_invoices, get_invoice_stats")
        
        print("\n🚀 To run the MCP server:")
        print("  python -m MCP --email your_email@example.com --password your_password")
        
        print("\n📝 To use with Claude Desktop, add to claude_desktop_config.json:")
        print("  {")
        print('    "mcpServers": {')
        print('      "invoice-app": {')
        print('        "command": "python",')
        print('        "args": ["-m", "MCP", "--email", "your_email@example.com", "--password", "your_password"],')
        print('        "cwd": "/Users/hao/dev/github/machine_learning/hao_projects/hao_invoice_app/api"')
        print('      }')
        print('    }')
        print('  }')
    else:
        print("⚠️  Some tests failed. Please check the errors above.") 