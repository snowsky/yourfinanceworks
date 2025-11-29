#!/usr/bin/env python3
"""
Test script for Slack integration

This script tests the Slack bot functionality without requiring actual Slack setup.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import from the API
sys.path.append(str(Path(__file__).parent.parent))

from core.routers.slack import SlackInvoiceBot, SlackCommandParser

async def test_command_parser():
    """Test the command parser"""
    print("🧪 Testing Command Parser...")
    
    parser = SlackCommandParser()
    
    test_cases = [
        "create client John Doe, email: john@example.com, phone: 555-1234",
        "add client Jane Smith",
        "create invoice for John Doe, amount: 500.00, due: 2024-02-15",
        "invoice Jane Smith 750 due 2024-03-01",
        "list clients",
        "show invoices",
        "find client John",
        "search invoice 123",
        "overdue invoices",
        "outstanding balance",
        "invoice stats",
        "help me please"
    ]
    
    for test_case in test_cases:
        result = parser.parse(test_case)
        print(f"  Input: '{test_case}'")
        print(f"  Output: {result}")
        print()

async def test_bot_responses():
    """Test bot responses with mock data"""
    print("🤖 Testing Bot Responses...")
    
    # Mock command data
    test_commands = [
        {"text": "help"},
        {"text": "list clients"},
        {"text": "invoice stats"},
        {"text": "unknown command here"}
    ]
    
    for command_data in test_commands:
        print(f"  Command: '{command_data['text']}'")
        
        # Create bot instance (without API client for testing)
        bot = SlackInvoiceBot()
        
        # Test parser
        parsed = bot.parser.parse(command_data['text'])
        print(f"  Parsed: {parsed}")
        
        # Test help response
        if parsed['operation'] == 'unknown':
            response = bot._help_response()
            print(f"  Response: {response['text'][:100]}...")
        
        print()

async def test_api_integration():
    """Test API integration if credentials are available"""
    print("🔌 Testing API Integration...")
    
    # Check if we have test credentials
    api_url = os.getenv('INVOICE_API_BASE_URL', 'http://localhost:8000/api')
    email = os.getenv('TEST_EMAIL')
    password = os.getenv('TEST_PASSWORD')
    
    if not email or not password:
        print("  ⚠️  Skipping API test - no credentials provided")
        print("  Set TEST_EMAIL and TEST_PASSWORD environment variables to test API integration")
        return
    
    try:
        bot = SlackInvoiceBot()
        await bot.initialize(api_url, email, password)
        
        # Test a simple command
        result = await bot.process_command({"text": "list clients"})
        print(f"  API Test Result: {result}")
        
        # Cleanup
        if bot.api_client:
            await bot.api_client.close()
        
        print("  ✅ API integration test passed")
        
    except Exception as e:
        print(f"  ❌ API integration test failed: {e}")

def test_slack_payload_parsing():
    """Test parsing of actual Slack payload format"""
    print("📨 Testing Slack Payload Parsing...")
    
    # Mock Slack form data
    mock_form_data = {
        'token': 'test_token',
        'team_id': 'T1234567890',
        'team_domain': 'testteam',
        'channel_id': 'C1234567890',
        'channel_name': 'general',
        'user_id': 'U1234567890',
        'user_name': 'testuser',
        'command': '/invoice',
        'text': 'create client John Doe, email: john@example.com',
        'response_url': 'https://hooks.slack.com/commands/1234567890/1234567890/test'
    }
    
    print("  Mock Slack payload:")
    for key, value in mock_form_data.items():
        print(f"    {key}: {value}")
    
    # Test command extraction
    command_text = mock_form_data.get('text', '')
    parser = SlackCommandParser()
    parsed = parser.parse(command_text)
    
    print(f"  Parsed command: {parsed}")
    print()

async def main():
    """Run all tests"""
    print("🚀 Starting Slack Integration Tests\n")
    
    await test_command_parser()
    await test_bot_responses()
    test_slack_payload_parsing()
    await test_api_integration()
    
    print("✅ All tests completed!")
    print("\n📝 Next steps:")
    print("1. Run: python scripts/setup_slack_integration.py")
    print("2. Configure your Slack app using the generated manifest")
    print("3. Set environment variables for Slack credentials")
    print("4. Test with actual Slack commands")

if __name__ == "__main__":
    asyncio.run(main())