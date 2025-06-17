#!/usr/bin/env python3
"""
Test script for the Invoice Application MCP Server

This script tests the basic functionality of the MCP server
without requiring the full MCP protocol implementation.
"""
import asyncio
import sys
import os

# Add the parent directory to the path so we can import the MCP modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from MCP.api_client import InvoiceAPIClient
from MCP.tools import InvoiceTools


async def test_api_client():
    """Test the API client directly"""
    print("Testing Invoice API Client...")
    
    # You need to set these environment variables or modify the values
    email = os.getenv("INVOICE_API_EMAIL", "test@example.com")
    password = os.getenv("INVOICE_API_PASSWORD", "test_password")
    api_url = os.getenv("INVOICE_API_BASE_URL", "http://localhost:8000/api")
    
    if not email or not password or email == "test@example.com":
        print("❌ Please set INVOICE_API_EMAIL and INVOICE_API_PASSWORD environment variables")
        print("   or modify the values in this test script")
        return False
    
    try:
        async with InvoiceAPIClient(base_url=api_url, email=email, password=password) as client:
            print(f"✅ Successfully connected to API at {api_url}")
            
            # Test listing clients
            print("\n📋 Testing list_clients...")
            clients = await client.list_clients(limit=5)
            print(f"✅ Found {len(clients)} clients")
            
            # Test listing invoices
            print("\n🧾 Testing list_invoices...")
            invoices = await client.list_invoices(limit=5)
            print(f"✅ Found {len(invoices)} invoices")
            
            # Test search if we have data
            if clients:
                print(f"\n🔍 Testing search_clients with first client name...")
                first_client_name = clients[0].get('name', '')
                if first_client_name:
                    search_results = await client.search_clients(first_client_name[:3])
                    print(f"✅ Search returned {len(search_results)} results")
            
            # Test analytics
            print("\n📊 Testing analytics...")
            outstanding = await client.get_clients_with_outstanding_balance()
            print(f"✅ Found {len(outstanding)} clients with outstanding balances")
            
            overdue = await client.get_overdue_invoices()
            print(f"✅ Found {len(overdue)} overdue invoices")
            
            return True
            
    except Exception as e:
        print(f"❌ API Client test failed: {e}")
        return False


async def test_fastmcp_tools():
    """Test the FastMCP tools implementation"""
    print("\n" + "="*50)
    print("Testing FastMCP Tools...")
    
    email = os.getenv("INVOICE_API_EMAIL", "test@example.com")
    password = os.getenv("INVOICE_API_PASSWORD", "test_password")
    api_url = os.getenv("INVOICE_API_BASE_URL", "http://localhost:8000/api")
    
    if not email or not password or email == "test@example.com":
        print("❌ Skipping FastMCP tools test - credentials not configured")
        return False
    
    try:
        async with InvoiceAPIClient(base_url=api_url, email=email, password=password) as client:
            tools = InvoiceTools(client)
            
            # Test list_clients tool
            print("\n🔧 Testing list_clients tool...")
            result = await tools.list_clients(skip=0, limit=3)
            
            if result.get("success"):
                print(f"✅ list_clients tool successful - found {result.get('count', 0)} clients")
            else:
                print(f"❌ list_clients tool failed: {result.get('error')}")
                return False
            
            # Test search_clients tool
            print("\n🔧 Testing search_clients tool...")
            result = await tools.search_clients(query="test", limit=2)
            
            if result.get("success"):
                print(f"✅ search_clients tool successful - found {result.get('count', 0)} results")
            else:
                print(f"❌ search_clients tool failed: {result.get('error')}")
            
            # Test list_invoices tool
            print("\n🔧 Testing list_invoices tool...")
            result = await tools.list_invoices(skip=0, limit=3)
            
            if result.get("success"):
                print(f"✅ list_invoices tool successful - found {result.get('count', 0)} invoices")
            else:
                print(f"❌ list_invoices tool failed: {result.get('error')}")
            
            # Test analytics tools
            print("\n🔧 Testing analytics tools...")
            result = await tools.get_clients_with_outstanding_balance()
            
            if result.get("success"):
                print(f"✅ outstanding_balance tool successful - found {result.get('count', 0)} clients")
            else:
                print(f"❌ outstanding_balance tool failed: {result.get('error')}")
            
            return True
            
    except Exception as e:
        print(f"❌ FastMCP Tools test failed: {e}")
        return False


def print_usage():
    """Print usage instructions"""
    print("\n" + "="*60)
    print("Invoice Application MCP Test Results")
    print("="*60)
    print("\nTo use the MCP server:")
    print("1. Set up your environment variables:")
    print("   export INVOICE_API_EMAIL='your_email@example.com'")
    print("   export INVOICE_API_PASSWORD='your_password'")
    print("   export INVOICE_API_BASE_URL='http://localhost:8000/api'")
    print("")
    print("2. Install MCP dependencies:")
    print("   pip install -r MCP/requirements.txt")
    print("")
    print("3. Run the MCP server:")
    print("   python launch_mcp.py --email your_email@example.com --password your_password")
    print("")
    print("4. Configure Claude Desktop to use the MCP server (see MCP/README.md)")
    print("")
    print("Available MCP tools:")
    print("  - list_clients")
    print("  - search_clients")
    print("  - get_client")
    print("  - create_client")
    print("  - list_invoices")
    print("  - search_invoices")
    print("  - get_invoice")
    print("  - create_invoice")
    print("  - get_clients_with_outstanding_balance")
    print("  - get_overdue_invoices")
    print("  - get_invoice_stats")


async def main():
    """Main test function"""
    print("🧪 Invoice Application FastMCP Server Test")
    print("="*50)
    
    # Check if the Invoice API is running
    print("🔍 Checking environment configuration...")
    email = os.getenv("INVOICE_API_EMAIL")
    password = os.getenv("INVOICE_API_PASSWORD")
    api_url = os.getenv("INVOICE_API_BASE_URL", "http://localhost:8000/api")
    
    print(f"   API URL: {api_url}")
    print(f"   Email: {email or 'Not set'}")
    print(f"   Password: {'Set' if password else 'Not set'}")
    
    if not email or not password:
        print("\n⚠️  Warning: API credentials not configured")
        print("   Set INVOICE_API_EMAIL and INVOICE_API_PASSWORD environment variables")
        print("   Or run: python test_mcp.py with credentials set")
    
    # Run tests
    api_success = await test_api_client()
    tools_success = await test_fastmcp_tools()
    
    # Print results
    print("\n" + "="*50)
    print("Test Results:")
    print(f"  API Client:   {'✅ PASS' if api_success else '❌ FAIL'}")
    print(f"  FastMCP Tools: {'✅ PASS' if tools_success else '❌ FAIL'}")
    
    if api_success and tools_success:
        print("\n🎉 All tests passed! Your FastMCP server is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")
    
    print_usage()


if __name__ == "__main__":
    asyncio.run(main()) 