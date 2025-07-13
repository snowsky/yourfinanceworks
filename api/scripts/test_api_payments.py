import asyncio
import aiohttp
import json

async def test_api_payments():
    # Test the actual API endpoint
    base_url = "http://localhost:8000/api/v1"
    
    # First, we need to get a token (this is a simplified test)
    async with aiohttp.ClientSession() as session:
        # Get payments directly from API
        async with session.get(f"{base_url}/payments/") as response:
            if response.status == 200:
                payments = await response.json()
                print(f"API returned {len(payments)} payments:")
                for payment in payments:
                    print(f"  Payment #{payment.get('id')} - Invoice #{payment.get('invoice_number')} - Amount: ${payment.get('amount')} - Method: {payment.get('payment_method')} - Date: {payment.get('payment_date')}")
            else:
                print(f"API error: {response.status}")
                text = await response.text()
                print(f"Response: {text}")

if __name__ == "__main__":
    asyncio.run(test_api_payments()) 