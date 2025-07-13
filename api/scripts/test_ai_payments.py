import asyncio
import httpx
from typing import Dict, Any, List

# Simulate the AuthenticatedAPIClient from the AI router
class AuthenticatedAPIClient:
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.jwt_token = jwt_token
        self._client = httpx.AsyncClient(timeout=30.0)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request using JWT token"""
        try:
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            headers.update(kwargs.pop('headers', {}))
            
            response = await self._client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed - token may be expired")
            raise Exception(f"API request failed: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Request error: {e}")
    
    async def list_payments(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._make_request(
            "GET", 
            "/payments/",
            params={"skip": skip, "limit": limit}
        )

# Simulate the InvoiceTools class
class InvoiceTools:
    def __init__(self, api_client):
        self.api_client = api_client
    
    async def query_payments(self, query: str) -> Dict[str, Any]:
        """Query payments using natural language"""
        try:
            from datetime import datetime, date, timedelta
            
            # Get all payments first
            payments = await self.api_client.list_payments(skip=0, limit=1000)
            
            # For this test, just return all payments without filtering
            return {
                "success": True,
                "data": payments,
                "count": len(payments),
                "query": query,
                "date_filter_applied": False,
                "date_description": "",
                "total_payments_checked": len(payments)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to query payments: {e}"}

async def test_ai_payments():
    # This is a test - we need a valid JWT token
    # For now, let's just test the structure
    print("Testing AI router payment query structure...")
    
    # Simulate what happens in the AI router
    jwt_token = "test_token"  # This would be the actual JWT token
    api_client = AuthenticatedAPIClient(
        base_url="http://localhost:8000/api/v1",
        jwt_token=jwt_token
    )
    tools = InvoiceTools(api_client)
    
    # Test the query_payments method
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
    asyncio.run(test_ai_payments()) 