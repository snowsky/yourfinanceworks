#!/usr/bin/env python3
"""
Example usage of the External API for PDF statement processing.

This example shows how to:
1. Create an API key
2. Process a bank statement PDF
3. Handle the response data
"""

import requests
import json
from pathlib import Path

class BankStatementAPI:
    """Client for the Bank Statement Processing API."""
    
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })
    
    def create_api_key(self, username, password, client_config):
        """Create a new API key (requires login first)."""
        # First, login to get access token
        login_response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            data={
                'username': username,
                'password': password
            }
        )
        login_response.raise_for_status()
        
        # Set authorization header with access token
        token = login_response.json()['access_token']
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
        
        # Create API key
        response = self.session.post(
            f"{self.base_url}/api/v1/external-auth/api-keys",
            json=client_config
        )
        response.raise_for_status()
        
        api_key_data = response.json()
        self.api_key = api_key_data['api_key']
        
        # Update session to use API key for future requests
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}'
        })
        
        return api_key_data
    
    def process_statement(self, file_path, format='csv'):
        """Process a bank statement file."""
        if not self.api_key:
            raise ValueError("API key required. Create one first or provide in constructor.")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/pdf')}
            data = {'format': format}
            
            response = self.session.post(
                f"{self.base_url}/api/v1/statements/process",
                files=files,
                data=data
            )
        
        response.raise_for_status()
        
        if format == 'json':
            return response.json()
        else:
            return response.text
    
    def health_check(self):
        """Check API health and authentication."""
        response = self.session.get(f"{self.base_url}/api/v1/statements/health")
        response.raise_for_status()
        return response.json()
    
    def get_usage_stats(self):
        """Get API usage statistics."""
        response = self.session.get(f"{self.base_url}/api/v1/statements/usage")
        response.raise_for_status()
        return response.json()
    
    def list_api_keys(self):
        """List all API keys for the current user."""
        response = self.session.get(f"{self.base_url}/api/v1/external-auth/api-keys")
        response.raise_for_status()
        return response.json()


def example_create_api_key():
    """Example: Create a new API key."""
    
    # Initialize client without API key
    client = BankStatementAPI("https://your-domain.com")
    
    # Configuration for the new API key
    api_key_config = {
        "client_name": "My Bank Statement Processor",
        "client_description": "Automated processing of bank statements",
        "allowed_transaction_types": ["income", "expense"],
        "allowed_currencies": ["USD", "EUR", "GBP"],
        "max_transaction_amount": 50000.00,
        "rate_limit_per_minute": 30,
        "rate_limit_per_hour": 500,
        "rate_limit_per_day": 5000,
        "is_sandbox": False
    }
    
    try:
        # Create API key (requires login)
        api_key_data = client.create_api_key(
            username="your_username",
            password="your_password",
            client_config=api_key_config
        )
        
        print("✅ API Key Created Successfully!")
        print(f"Client ID: {api_key_data['client_id']}")
        print(f"API Key: {api_key_data['api_key']}")
        print(f"⚠️  Save this API key securely - it won't be shown again!")
        
        return api_key_data['api_key']
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Failed to create API key: {e}")
        print(f"Response: {e.response.text}")
        return None


def example_process_statement(api_key, file_path):
    """Example: Process a bank statement file."""
    
    # Initialize client with API key
    client = BankStatementAPI("https://your-domain.com", api_key)
    
    try:
        # Health check first
        health = client.health_check()
        print(f"✅ API Health: {health['status']}")
        
        # Process the statement
        print(f"📄 Processing file: {file_path}")
        
        # Get JSON response
        json_result = client.process_statement(file_path, format='json')
        transactions = json_result['transactions']
        
        print(f"✅ Found {len(transactions)} transactions")
        
        # Print first few transactions
        for i, txn in enumerate(transactions[:3]):
            print(f"  {i+1}. {txn['date']} - {txn['description']} - ${txn['amount']}")
        
        if len(transactions) > 3:
            print(f"  ... and {len(transactions) - 3} more transactions")
        
        # Also get CSV format
        csv_result = client.process_statement(file_path, format='csv')
        print(f"\n📊 CSV Output (first 200 chars):")
        print(csv_result[:200] + "..." if len(csv_result) > 200 else csv_result)
        
        return transactions
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Failed to process statement: {e}")
        print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def example_usage_monitoring(api_key):
    """Example: Monitor API usage."""
    
    client = BankStatementAPI("https://your-domain.com", api_key)
    
    try:
        # Get usage statistics
        usage = client.get_usage_stats()
        
        print("📊 API Usage Statistics:")
        print(f"  Client: {usage['client_name']}")
        print(f"  Total Requests: {usage['total_requests']}")
        print(f"  Total Transactions: {usage['total_transactions_submitted']}")
        print(f"  Last Used: {usage['last_used_at']}")
        
        print("\n🚦 Rate Limits:")
        limits = usage['rate_limits']
        print(f"  Per Minute: {limits['per_minute']}")
        print(f"  Per Hour: {limits['per_hour']}")
        print(f"  Per Day: {limits['per_day']}")
        
        return usage
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Failed to get usage stats: {e}")
        return None


def main():
    """Main example workflow."""
    
    print("🏦 Bank Statement API Example")
    print("=" * 50)
    
    # Example 1: Create API Key (uncomment to use)
    # print("\n1️⃣ Creating API Key...")
    # api_key = example_create_api_key()
    
    # Example 2: Use existing API key
    api_key = "ak_your_existing_api_key_here"  # Replace with your actual API key
    
    if not api_key or api_key == "ak_your_existing_api_key_here":
        print("⚠️  Please set a valid API key in the script")
        return
    
    # Example 3: Process a statement
    print("\n2️⃣ Processing Bank Statement...")
    statement_file = "path/to/your/bank_statement.pdf"  # Replace with actual file path
    
    if Path(statement_file).exists():
        transactions = example_process_statement(api_key, statement_file)
    else:
        print(f"⚠️  File not found: {statement_file}")
        print("Please update the file path in the script")
    
    # Example 4: Monitor usage
    print("\n3️⃣ Checking Usage Statistics...")
    usage = example_usage_monitoring(api_key)
    
    print("\n✅ Example completed!")


if __name__ == "__main__":
    main()