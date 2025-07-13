import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from MCP.api_client import InvoiceAPIClient
from MCP.tools import InvoiceTools

async def test_mcp_payments():
    # Create a mock API client for testing
    class MockAPIClient:
        async def list_payments(self, skip: int = 0, limit: int = 100):
            # Return the actual payment data we saw in the database
            return [
                {
                    "id": 1,
                    "invoice_id": 1,
                    "amount": 500.0,
                    "payment_date": "2025-07-11T13:46:23.832845",
                    "payment_method": "bank_transfer",
                    "invoice_number": "INV-001",
                    "client_name": "Sample Client"
                },
                {
                    "id": 2,
                    "invoice_id": 2,
                    "amount": 100.0,
                    "payment_date": "2025-07-13T00:00:00",
                    "payment_method": "manual",
                    "invoice_number": "INV-20250711-0001",
                    "client_name": "HcDat"
                },
                {
                    "id": 3,
                    "invoice_id": 3,
                    "amount": 1.0,
                    "payment_date": "2025-07-13T00:00:00",
                    "payment_method": "manual",
                    "invoice_number": "INV-20250711-0002",
                    "client_name": "HcDat"
                },
                {
                    "id": 4,
                    "invoice_id": 4,
                    "amount": 10.0,
                    "payment_date": "2025-07-13T00:00:00",
                    "payment_method": "manual",
                    "invoice_number": "INV-20250711-0003",
                    "client_name": "HcDat"
                }
            ]
    
    # Create tools with mock client
    api_client = MockAPIClient()
    tools = InvoiceTools(api_client)
    
    # Test different queries
    test_queries = [
        "total payment",
        "payments",
        "list payments",
        "show payments"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: '{query}'")
        result = await tools.query_payments(query=query)
        
        if result.get("success"):
            payments = result.get("data", [])
            print(f"Found {len(payments)} payments:")
            for payment in payments:
                print(f"  Payment #{payment.get('id')} - Invoice #{payment.get('invoice_number')} - Amount: ${payment.get('amount')} - Method: {payment.get('payment_method')} - Date: {payment.get('payment_date')}")
        else:
            print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_mcp_payments()) 