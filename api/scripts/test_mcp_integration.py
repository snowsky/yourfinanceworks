#!/usr/bin/env python3

import requests
import json
import asyncio

# Test the MCP integration with LLM
BASE_URL = "http://localhost:8000/api/v1"

async def test_mcp_integration():
    """Test how LLM can use MCP tools"""
    
    # First, login to get token
    login_data = {
        "email": "hao.1.wang@gmail.com",
        "password": "123456"
    }
    
    try:
        login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Login response status: {login_response.status_code}")
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # Test 1: Analyze invoice patterns (should use MCP tools)
            print("\n=== Test 1: Analyze Invoice Patterns (MCP Tools) ===")
            chat_data = {
                "message": "Analyze my invoice patterns and provide insights",
                "config_id": 1
            }
            
            chat_response = requests.post(f"{BASE_URL}/ai/chat", headers=headers, json=chat_data)
            print(f"Chat response status: {chat_response.status_code}")
            print(f"Chat response: {chat_response.text}")
            
            # Test 2: Suggest actions (should use MCP tools)
            print("\n=== Test 2: Suggest Actions (MCP Tools) ===")
            chat_data = {
                "message": "Suggest actions based on my invoice data",
                "config_id": 1
            }
            
            chat_response = requests.post(f"{BASE_URL}/ai/chat", headers=headers, json=chat_data)
            print(f"Chat response status: {chat_response.status_code}")
            print(f"Chat response: {chat_response.text}")
            
            # Test 3: Regular chat (should use LLM)
            print("\n=== Test 3: Regular Chat (LLM) ===")
            chat_data = {
                "message": "Hello, how are you today?",
                "config_id": 1
            }
            
            chat_response = requests.post(f"{BASE_URL}/ai/chat", headers=headers, json=chat_data)
            print(f"Chat response status: {chat_response.status_code}")
            print(f"Chat response: {chat_response.text}")
            
        else:
            print(f"Login failed: {login_response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_integration()) 