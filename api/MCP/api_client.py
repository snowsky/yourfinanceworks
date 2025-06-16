"""
API Client for Invoice Application MCP integration
"""
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime

from .auth_client import InvoiceAPIAuthClient, AuthenticationError
from .config import config


class InvoiceAPIClient:
    """Client for interacting with the Invoice API"""
    
    def __init__(self, base_url: str = None, email: str = None, password: str = None):
        self.base_url = base_url or config.API_BASE_URL
        self.auth_client = InvoiceAPIAuthClient(base_url, email, password)
        self._client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to the API"""
        try:
            headers = await self.auth_client.get_auth_headers()
            headers.update(kwargs.pop('headers', {}))
            
            response = await self._client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed - check credentials")
            raise Exception(f"API request failed: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Request error: {e}")
    
    # Client Management Methods
    async def list_clients(self, skip: int = 0, limit: int = None) -> List[Dict[str, Any]]:
        """List all clients with pagination"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)
        
        return await self._make_request(
            "GET", 
            "/clients/",
            params={"skip": skip, "limit": limit}
        )
    
    async def get_client(self, client_id: int) -> Dict[str, Any]:
        """Get a specific client by ID"""
        return await self._make_request("GET", f"/clients/{client_id}")
    
    async def search_clients(self, query: str, skip: int = 0, limit: int = None) -> List[Dict[str, Any]]:
        """Search clients by name, email, or other fields"""
        # Get all clients and filter locally since the API doesn't have search endpoint
        clients = await self.list_clients(skip=0, limit=config.MAX_PAGE_SIZE)
        
        query_lower = query.lower()
        filtered_clients = []
        
        for client in clients:
            # Search in name, email, phone, and address
            searchable_fields = [
                client.get('name', ''),
                client.get('email', ''),
                client.get('phone', ''),
                client.get('address', '')
            ]
            
            if any(query_lower in str(field).lower() for field in searchable_fields if field):
                filtered_clients.append(client)
        
        # Apply pagination to filtered results
        limit = limit or config.DEFAULT_PAGE_SIZE
        end_idx = skip + limit
        return filtered_clients[skip:end_idx]
    
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client"""
        return await self._make_request("POST", "/clients/", json=client_data)
    
    async def update_client(self, client_id: int, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing client"""
        return await self._make_request("PUT", f"/clients/{client_id}", json=client_data)
    
    async def delete_client(self, client_id: int) -> bool:
        """Delete a client"""
        try:
            await self._make_request("DELETE", f"/clients/{client_id}")
            return True
        except Exception:
            return False
    
    # Invoice Management Methods
    async def list_invoices(self, skip: int = 0, limit: int = None) -> List[Dict[str, Any]]:
        """List all invoices with pagination"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)
        
        return await self._make_request(
            "GET", 
            "/invoices/",
            params={"skip": skip, "limit": limit}
        )
    
    async def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Get a specific invoice by ID"""
        return await self._make_request("GET", f"/invoices/{invoice_id}")
    
    async def search_invoices(self, query: str, skip: int = 0, limit: int = None) -> List[Dict[str, Any]]:
        """Search invoices by number, client name, status, or other fields"""
        # Get all invoices and filter locally since the API doesn't have search endpoint
        invoices = await self.list_invoices(skip=0, limit=config.MAX_PAGE_SIZE)
        
        query_lower = query.lower()
        filtered_invoices = []
        
        for invoice in invoices:
            # Search in number, client_name, status, and notes
            searchable_fields = [
                invoice.get('number', ''),
                invoice.get('client_name', ''),
                invoice.get('status', ''),
                invoice.get('notes', ''),
                str(invoice.get('amount', ''))
            ]
            
            if any(query_lower in str(field).lower() for field in searchable_fields if field):
                filtered_invoices.append(invoice)
        
        # Apply pagination to filtered results
        limit = limit or config.DEFAULT_PAGE_SIZE
        end_idx = skip + limit
        return filtered_invoices[skip:end_idx]
    
    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new invoice"""
        return await self._make_request("POST", "/invoices/", json=invoice_data)
    
    async def update_invoice(self, invoice_id: int, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing invoice"""
        return await self._make_request("PUT", f"/invoices/{invoice_id}", json=invoice_data)
    
    async def delete_invoice(self, invoice_id: int) -> bool:
        """Delete an invoice"""
        try:
            await self._make_request("DELETE", f"/invoices/{invoice_id}")
            return True
        except Exception:
            return False
    
    # Statistics and Reporting
    async def get_invoice_stats(self) -> Dict[str, Any]:
        """Get invoice statistics"""
        try:
            return await self._make_request("GET", "/invoices/stats/total-income")
        except Exception:
            return {"error": "Failed to fetch statistics"}
    
    async def get_clients_with_outstanding_balance(self) -> List[Dict[str, Any]]:
        """Get clients with outstanding balances"""
        clients = await self.list_clients(limit=config.MAX_PAGE_SIZE)
        return [client for client in clients if client.get('balance', 0) > 0]
    
    async def get_overdue_invoices(self) -> List[Dict[str, Any]]:
        """Get overdue invoices"""
        invoices = await self.list_invoices(limit=config.MAX_PAGE_SIZE)
        current_date = datetime.now().date()
        
        overdue_invoices = []
        for invoice in invoices:
            due_date_str = invoice.get('due_date')
            if due_date_str and invoice.get('status') != 'paid':
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')).date()
                    if due_date < current_date:
                        overdue_invoices.append(invoice)
                except Exception:
                    continue
        
        return overdue_invoices
    
    async def close(self):
        """Close the HTTP client and auth client"""
        await self._client.aclose()
        await self.auth_client.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 