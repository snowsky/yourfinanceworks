#!/usr/bin/env python3

import requests
import json
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models.database import get_db
from core.models.models import AIConfig
from sqlalchemy.orm import Session
from config import APP_NAME

def test_litellm_with_mcp():
    """Test if LiteLLM can use MCP tools for invoice analysis"""
    
    # First, get the AI configuration
    db = next(get_db())
    ai_config = db.query(AIConfig).filter(
        AIConfig.is_active == True,
        AIConfig.is_default == True
    ).first()
    
    if not ai_config:
        print("No default AI configuration found")
        return
    
    print(f"Using AI config: {ai_config.provider_name} - {ai_config.model_name}")
    
    # Test the analyze_patterns endpoint directly (which uses MCP-like functionality)
    try:
        # Login to get token
        login_data = {
            "email": "hao.1.wang@gmail.com",
            "password": "123456"
        }
        
        login_response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data)
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return
            
        token = login_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Test the analyze_patterns endpoint (which has MCP-like functionality)
        print("\nTesting analyze_patterns endpoint (MCP-like functionality):")
        analyze_response = requests.get("http://localhost:8000/api/v1/ai/analyze-patterns", headers=headers)
        print(f"Status: {analyze_response.status_code}")
        print(f"Response: {analyze_response.text}")
        
        # Test the suggest_actions endpoint
        print("\nTesting suggest_actions endpoint (MCP-like functionality):")
        suggest_response = requests.get("http://localhost:8000/api/v1/ai/suggest-actions", headers=headers)
        print(f"Status: {suggest_response.status_code}")
        print(f"Response: {suggest_response.text}")
        
        # Now test if we can enhance the chat endpoint to use MCP tools
        print("\nTesting enhanced chat with MCP integration:")
        
        # Create a prompt that should trigger MCP-like analysis
        mcp_prompt = """
        You are an AI assistant for {APP_NAME}. 
        When users ask to "analyze invoice patterns" or "suggest actions", 
        you should use the available tools to provide detailed analysis.
        
        User message: "Analyze my invoice patterns"
        
        Please provide a comprehensive analysis using the available invoice data.
        """
        
        chat_data = {
            "message": mcp_prompt,
            "config_id": ai_config.id
        }
        
        chat_response = requests.post("http://localhost:8000/api/v1/ai/chat", headers=headers, json=chat_data)
        print(f"Chat Status: {chat_response.status_code}")
        print(f"Chat Response: {chat_response.text}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_litellm_with_mcp() 