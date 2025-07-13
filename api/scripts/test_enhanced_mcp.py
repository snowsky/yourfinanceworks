#!/usr/bin/env python3
"""
Test script for enhanced MCP integration with AI chat endpoint
"""
import asyncio
import aiohttp
import json
import sys
import os

# Add the api directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_ai_chat_endpoint():
    """Test the enhanced AI chat endpoint with various MCP tool patterns"""
    
    # Test cases for different MCP tool patterns
    test_cases = [
        # Pattern 1: Analyze invoice patterns
        {
            "name": "Analyze invoice patterns",
            "message": "Can you analyze my invoice patterns and trends?",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 2: Suggest actions
        {
            "name": "Suggest actions",
            "message": "What actions should I take based on my invoice data?",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 3: Client management
        {
            "name": "List clients",
            "message": "Show me all my clients",
            "expected_source": "mcp_tools"
        },
        {
            "name": "Search clients",
            "message": "Search for clients named John",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 4: Invoice management
        {
            "name": "List invoices",
            "message": "Show me all my invoices",
            "expected_source": "mcp_tools"
        },
        {
            "name": "Search invoices",
            "message": "Find invoices for client ABC",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 5: Payment queries
        {
            "name": "List payments",
            "message": "Show me all payments",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 6: Currency queries
        {
            "name": "List currencies",
            "message": "What currencies do you support?",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 7: Outstanding balance queries
        {
            "name": "Outstanding balances",
            "message": "Who owes me money?",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 8: Overdue invoice queries
        {
            "name": "Overdue invoices",
            "message": "Show me overdue invoices",
            "expected_source": "mcp_tools"
        },
        
        # Pattern 9: Statistics queries
        {
            "name": "Invoice statistics",
            "message": "How many invoices do I have?",
            "expected_source": "mcp_tools"
        },
        
        # General LLM fallback
        {
            "name": "General question",
            "message": "What is the weather like today?",
            "expected_source": "llm"
        }
    ]
    
    # API endpoint
    base_url = "http://localhost:8000/api/v1"
    chat_endpoint = f"{base_url}/ai/chat"
    
    # Test credentials (you may need to adjust these)
    test_credentials = {
        "email": "admin@example.com",
        "password": "password"
    }
    
    async with aiohttp.ClientSession() as session:
        # First, get authentication token
        print("🔐 Getting authentication token...")
        auth_response = await session.post(
            f"{base_url}/auth/login",
            json=test_credentials
        )
        
        if auth_response.status != 200:
            print(f"❌ Authentication failed: {auth_response.status}")
            auth_text = await auth_response.text()
            print(f"Response: {auth_text}")
            return
        
        auth_data = await auth_response.json()
        token = auth_data.get("access_token")
        
        if not token:
            print("❌ No access token received")
            return
        
        print("✅ Authentication successful")
        
        # Test headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Run test cases
        print(f"\n🧪 Testing {len(test_cases)} MCP tool patterns...")
        print("=" * 60)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. Testing: {test_case['name']}")
            print(f"   Message: '{test_case['message']}'")
            
            try:
                # Send chat request
                chat_data = {
                    "message": test_case["message"]
                }
                
                response = await session.post(
                    chat_endpoint,
                    json=chat_data,
                    headers=headers
                )
                
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get("success"):
                        data = result.get("data", {})
                        source = data.get("source", "unknown")
                        response_text = data.get("response", "")
                        
                        # Check if source matches expected
                        if source == test_case["expected_source"]:
                            print(f"   ✅ SUCCESS - Source: {source}")
                            print(f"   📝 Response preview: {response_text[:100]}...")
                        else:
                            print(f"   ⚠️  UNEXPECTED - Expected: {test_case['expected_source']}, Got: {source}")
                            print(f"   📝 Response preview: {response_text[:100]}...")
                    else:
                        print(f"   ❌ FAILED - {result.get('error', 'Unknown error')}")
                else:
                    print(f"   ❌ HTTP {response.status}")
                    error_text = await response.text()
                    print(f"   Error: {error_text}")
                    
            except Exception as e:
                print(f"   ❌ EXCEPTION: {e}")
        
        print("\n" + "=" * 60)
        print("🎯 Enhanced MCP Integration Test Complete!")

if __name__ == "__main__":
    print("🚀 Starting Enhanced MCP Integration Test")
    print("This test will verify that the AI chat endpoint can use various MCP tools")
    print("based on pattern matching in user messages.\n")
    
    asyncio.run(test_ai_chat_endpoint()) 