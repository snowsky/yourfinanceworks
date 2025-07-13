import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from MCP.tools import InvoiceTools

# Simulate the AI router's AuthenticatedAPIClient
class AuthenticatedAPIClient:
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.jwt_token = jwt_token
        self._client = None  # We'll mock this
    
    async def list_payments(self, skip: int = 0, limit: int = 100):
        # Mock the actual payment data from the database
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

async def test_ai_mcp_integration():
    print("Testing AI router + MCP tools integration...")
    
    # Simulate what the AI router does
    jwt_token = "test_token"
    api_client = AuthenticatedAPIClient(
        base_url="http://localhost:8000/api/v1",
        jwt_token=jwt_token
    )
    
    # Create InvoiceTools with the AI router's client
    tools = InvoiceTools(api_client)
    
    # Test the query_payments method
    print("\nTesting query_payments with 'total payment'...")
    result = await tools.query_payments("total payment")
    
    print(f"Result: {result}")
    if result.get("success"):
        payments = result.get("data", [])
        print(f"Found {len(payments)} payments:")
        for payment in payments:
            print(f"  Payment #{payment.get('id')} - Invoice #{payment.get('invoice_number')} - Amount: ${payment.get('amount')} - Method: {payment.get('payment_method')} - Date: {payment.get('payment_date')}")
    else:
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_ai_mcp_integration()) 