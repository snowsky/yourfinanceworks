"""
Authentication client for Invoice API MCP integration
"""
import json
import os
from typing import Optional, Dict, Any
import httpx
from datetime import datetime, timedelta, timezone

from .config import config


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class InvoiceAPIAuthClient:
    """Handles authentication with the Invoice API"""
    
    def __init__(self, base_url: str = None, email: str = None, password: str = None):
        self.base_url = base_url or config.API_BASE_URL
        self.email = email or config.DEFAULT_EMAIL
        self.password = password or config.DEFAULT_PASSWORD
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT)
    
    async def _load_token_from_file(self) -> bool:
        """Load token from file if it exists and is valid"""
        try:
            if os.path.exists(config.TOKEN_STORAGE_FILE):
                with open(config.TOKEN_STORAGE_FILE, 'r') as f:
                    data = json.load(f)
                    self._token = data.get('token')
                    expires_str = data.get('expires')
                    if expires_str:
                        self._token_expires = datetime.fromisoformat(expires_str)
                        
                    # Check if token is still valid (with 5 minute buffer)
                    if self._token_expires and self._token_expires > datetime.now(timezone.utc) + timedelta(minutes=5):
                        return True
        except Exception:
            pass
        
        return False
    
    async def _save_token_to_file(self):
        """Save current token to file"""
        try:
            data = {
                'token': self._token,
                'expires': self._token_expires.isoformat() if self._token_expires else None
            }
            with open(config.TOKEN_STORAGE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass  # Ignore file save errors
    
    async def _authenticate(self) -> str:
        """Authenticate with the API and get access token"""
        if not self.email or not self.password:
            raise AuthenticationError("Email and password must be provided for authentication")
        
        try:
            response = await self._client.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.email,
                    "password": self.password
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self._token = data["access_token"]
            
            # Estimate token expiry (typically 30 minutes from API)
            self._token_expires = datetime.now(timezone.utc) + timedelta(minutes=25)  # 5 min buffer
            
            await self._save_token_to_file()
            return self._token
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid credentials")
            raise AuthenticationError(f"Authentication failed: {e}")
        except Exception as e:
            raise AuthenticationError(f"Authentication error: {e}")
    
    async def get_valid_token(self) -> str:
        """Get a valid access token, authenticating if necessary"""
        # Try to load existing token
        if not self._token:
            await self._load_token_from_file()
        
        # Check if current token is valid
        if self._token and self._token_expires and self._token_expires > datetime.now(timezone.utc):
            return self._token
        
        # Need to authenticate
        return await self._authenticate()
    
    async def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with valid authentication token"""
        token = await self.get_valid_token()
        return {"Authorization": f"Bearer {token}"}
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 