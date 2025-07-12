#!/usr/bin/env python3

import requests
import json

# Test the AI configuration and chat functionality
BASE_URL = "http://localhost:8000/api/v1"

def test_ai_config():
    """Test AI configuration endpoints"""
    
    # First, try to login
    login_data = {
        "email": "hao.1.wang@gmail.com",
        "password": "123456"
    }
    
    try:
        login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"Login response status: {login_response.status_code}")
        print(f"Login response: {login_response.text}")
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # Test AI config endpoint
            config_response = requests.get(f"{BASE_URL}/ai-config/", headers=headers)
            print(f"\nAI Config response status: {config_response.status_code}")
            print(f"AI Config response: {config_response.text}")
            
            if config_response.status_code == 200:
                configs = config_response.json()
                print(f"\nFound {len(configs)} AI configurations")
                for config in configs:
                    print(f"  - ID: {config['id']}, Provider: {config['provider_name']}, Model: {config['model_name']}, Active: {config['is_active']}, Default: {config['is_default']}")
                
                # Find default config
                default_config = next((c for c in configs if c['is_active'] and c['is_default']), None)
                
                if default_config:
                    print(f"\nDefault config found: {default_config['id']}")
                    
                    # Test AI chat
                    chat_data = {
                        "message": "Hello, this is a test message",
                        "config_id": default_config['id']
                    }
                    
                    chat_response = requests.post(f"{BASE_URL}/ai/chat", headers=headers, json=chat_data)
                    print(f"\nChat response status: {chat_response.status_code}")
                    print(f"Chat response: {chat_response.text}")
                else:
                    print("\nNo default AI configuration found!")
            else:
                print(f"Failed to get AI configs: {config_response.text}")
        else:
            print(f"Login failed: {login_response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ai_config() 