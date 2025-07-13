#!/usr/bin/env python3
"""
Test MCP tools directly
"""
import asyncio
import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from MCP.tools import InvoiceTools
from MCP.api_client import InvoiceAPIClient

async def test_mcp_tools():
    """Test MCP tools directly"""
    print("🧪 Testing MCP tools directly...")
    
    try:
        # Initialize MCP tools
        api_client = InvoiceAPIClient(
            base_url="http://localhost:8000/api/v1",
            email="admin@example.com",
            password="password"
        )
        tools = InvoiceTools(api_client)
        
        print("✅ MCP tools initialized successfully")
        
        # Test analyze_invoice_patterns
        print("\n1. Testing analyze_invoice_patterns...")
        result = await tools.analyze_invoice_patterns()
        print(f"Result: {result}")
        
        # Test list_clients
        print("\n2. Testing list_clients...")
        result = await tools.list_clients(limit=5)
        print(f"Result: {result}")
        
        # Test list_invoices
        print("\n3. Testing list_invoices...")
        result = await tools.list_invoices(limit=5)
        print(f"Result: {result}")
        
        print("\n✅ All MCP tool tests completed!")
        
    except Exception as e:
        print(f"❌ Error testing MCP tools: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_tools()) 