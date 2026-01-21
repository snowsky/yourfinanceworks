#!/usr/bin/env python3
"""
MCP Setup Validation Script

This script helps users validate that their MCP setup is working correctly.
It tests dependencies, configuration, authentication, and basic tool functionality.
"""
import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Dict, Any

# Add current directory to Python path for imports
current_dir = Path(__file__).parent.parent  # Go up to api/MCP directory
api_dir = Path(__file__).parent.parent.parent  # Go up to api directory
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(api_dir))

class Colors:
    """ANSI color codes for output formatting"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_success(message: str):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message: str):
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def print_header(message: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{message}{Colors.END}")

def validate_dependencies():
    """Validate that required dependencies are installed"""
    print_header("🔍 Validating Dependencies")
    
    required_packages = [
        'fastmcp',
        'httpx', 
        'pydantic',
        'typing_extensions'
    ]
    
    all_good = True
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is missing")
            all_good = False
    
    return all_good

def validate_configuration():
    """Validate environment configuration"""
    print_header("🔧 Validating Configuration")
    
    # Check for .env file
    env_file = current_dir / '.env'
    example_env = current_dir / 'example.env'
    
    if not env_file.exists():
        if example_env.exists():
            print_warning(".env file not found. Found example.env - copy it and add your credentials")
            print_info("Run: cp example.env .env")
        else:
            print_error("Neither .env nor example.env found")
        return False
    
    print_success(".env file found")
    
    # Load and validate environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv(str(env_file))
    except ImportError:
        # Fallback to manual parsing
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    required_vars = ['INVOICE_API_EMAIL', 'INVOICE_API_PASSWORD']
    optional_vars = ['INVOICE_API_BASE_URL']
    
    all_good = True
    for var in required_vars:
        value = os.getenv(var)
        if value and value not in ['your_email@example.com', 'your_secure_password']:
            print_success(f"{var} is configured")
        else:
            print_error(f"{var} is not configured or still has default value")
            all_good = False
    
    for var in optional_vars:
        if os.getenv(var):
            print_success(f"{var} is configured")
        else:
            print_warning(f"{var} not configured (will use default)")
    
    return all_good

def validate_imports():
    """Validate that MCP modules can be imported"""
    print_header("📦 Validating Module Imports")
    
    try:
        from MCP.config import config
        print_success("Config module imported")
        
        from MCP.auth_client import InvoiceAPIAuthClient
        print_success("Auth client imported")
        
        from MCP.api_client import InvoiceAPIClient
        print_success("API client imported")
        
        from MCP.tools import InvoiceTools
        print_success("Tools module imported")
        
        return True
        
    except Exception as e:
        print_error(f"Import failed: {e}")
        return False

async def validate_authentication():
    """Validate API authentication"""
    print_header("🔐 Validating API Authentication")
    
    try:
        from MCP.api_client import InvoiceAPIClient
        from MCP.config import config
        
        # Get configuration
        base_url = os.getenv('INVOICE_API_BASE_URL', config.API_BASE_URL)
        email = os.getenv('INVOICE_API_EMAIL', config.DEFAULT_EMAIL)
        password = os.getenv('INVOICE_API_PASSWORD', config.DEFAULT_PASSWORD)
        
        if not email or not password:
            print_error("Email and password are required for authentication test")
            return False
        
        print_info(f"Testing connection to: {base_url}")
        
        # Create API client and test authentication
        client = InvoiceAPIClient(
            base_url=base_url,
            email=email,
            password=password
        )
        
        # Try to authenticate
        await client.authenticate()
        print_success("Authentication successful")
        
        # Test a simple API call
        try:
            result = await client.get('/clients', params={'limit': 1})
            if result.get('success'):
                print_success("API communication working")
            else:
                print_warning("API communication issue - check permissions")
        except Exception as e:
            print_warning(f"API test failed: {e}")
        
        await client.close()
        return True
        
    except Exception as e:
        print_error(f"Authentication failed: {e}")
        return False

def validate_tools():
    """Validate that MCP tools are properly defined"""
    print_header("🛠️  Validating MCP Tools")
    
    try:
        from MCP.server import mcp
        
        # Get list of tools
        tools = mcp.list_tools()
        tool_count = len(tools)
        
        print_success(f"Found {tool_count} MCP tools")
        
        # Show some example tools
        example_tools = ['list_clients', 'create_invoice', 'list_expenses']
        for tool_name in example_tools:
            if any(tool.name == tool_name for tool in tools):
                print_success(f"Tool '{tool_name}' is available")
            else:
                print_warning(f"Tool '{tool_name}' not found")
        
        return True
        
    except Exception as e:
        print_error(f"Tool validation failed: {e}")
        return False

def generate_claude_config():
    """Generate Claude Desktop configuration"""
    print_header("📝 Generating Claude Desktop Configuration")
    
    # Get current configuration
    base_url = os.getenv('INVOICE_API_BASE_URL', 'http://localhost:8000/api')
    email = os.getenv('INVOICE_API_EMAIL', 'your_email@example.com')
    password = os.getenv('INVOICE_API_PASSWORD', 'your_password')
    
    # Get absolute path to launch script
    launch_script = str(current_dir.parent / 'launch_mcp.py')
    
    config = {
        "mcpServers": {
            "invoice-app": {
                "command": "python",
                "args": [launch_script],
                "env": {
                    "INVOICE_API_BASE_URL": base_url,
                    "INVOICE_API_EMAIL": email,
                    "INVOICE_API_PASSWORD": password
                }
            }
        }
    }
    
    config_json = json.dumps(config, indent=2)
    
    print_info("Claude Desktop Configuration:")
    print(f"{Colors.BLUE}{config_json}{Colors.END}")
    
    # Save to file
    config_file = current_dir / 'claude_desktop_config.json'
    with open(config_file, 'w') as f:
        f.write(config_json)
    
    print_success(f"Configuration saved to: {config_file}")
    print_info("Copy this configuration to your Claude Desktop config file")

async def main():
    """Main validation function"""
    print(f"{Colors.BOLD}{Colors.BLUE}🚀 MCP Setup Validation{Colors.END}")
    print("=" * 50)
    
    # Run all validations
    results = {
        "Dependencies": validate_dependencies(),
        "Configuration": validate_configuration(),
        "Imports": validate_imports(),
        "Authentication": await validate_authentication(),
        "Tools": validate_tools()
    }
    
    # Summary
    print_header("📊 Validation Summary")
    
    passed = sum(results.values())
    total = len(results)
    
    for category, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{category:15} {status}")
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print_success("🎉 MCP setup is working! You're ready to use Claude with your Invoice Application.")
        generate_claude_config()
    else:
        print_error("Some checks failed. Please fix the issues above before proceeding.")
        print_info("For help, see TROUBLESHOOTING.md")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_warning("\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Validation script error: {e}")
        sys.exit(1)
