"""
Configuration for the Invoice Application MCP Server
"""
import os
from typing import Optional

class MCPConfig:
    """Configuration settings for the MCP server"""
    
    # API Base URL - can be configured via environment variable
    API_BASE_URL: str = os.getenv("INVOICE_API_BASE_URL", "http://localhost:8000/api/v1")
    
    # Authentication settings
    DEFAULT_EMAIL: Optional[str] = os.getenv("INVOICE_API_EMAIL")
    DEFAULT_PASSWORD: Optional[str] = os.getenv("INVOICE_API_PASSWORD")
    
    # Token storage (in production, this should be more secure)
    TOKEN_STORAGE_FILE: str = os.getenv("TOKEN_STORAGE_FILE", ".mcp_token")
    
    # Request timeouts
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "100"))
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "1000"))
    
    # Token expiration buffer (minutes)
    TOKEN_BUFFER_MINUTES: int = 5

# Global config instance
config = MCPConfig() 