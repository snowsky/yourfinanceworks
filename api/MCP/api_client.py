"""
API Client for Invoice Application MCP integration
"""
from typing import List, Dict, Any, Optional
from httpx import AsyncClient, HTTPStatusError
from datetime import datetime, timezone
import logging

from .auth_client import InvoiceAPIAuthClient, AuthenticationError
from .config import config

logger = logging.getLogger(__name__)


class InvoiceAPIClient:
    """Client for interacting with the Invoice API"""
    
    def __init__(self, base_url: str = None, email: str = None, password: str = None):
        self.base_url = base_url or config.API_BASE_URL
        self.auth_client = InvoiceAPIAuthClient(base_url, email, password)
        self._client = AsyncClient(timeout=config.REQUEST_TIMEOUT)
    
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
            
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed - check credentials")
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise Exception(f"API request failed: {e.response.status_code} - {e.response.text}")
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
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
        limit = limit or config.DEFAULT_PAGE_SIZE
        query_lower = query.lower()
        filtered_clients = []
        current_skip = 0
        batch_size = min(100, config.MAX_PAGE_SIZE)
        
        # Process clients in batches with early termination
        while len(filtered_clients) < skip + limit:
            batch = await self.list_clients(skip=current_skip, limit=batch_size)
            if not batch:
                break
                
            for client in batch:
                # Optimized field access with early exit
                name = client.get('name', '')
                if query_lower in name.lower():
                    filtered_clients.append(client)
                    continue
                    
                email = client.get('email', '')
                if email and query_lower in email.lower():
                    filtered_clients.append(client)
                    continue
                    
                phone = client.get('phone', '')
                if phone and query_lower in phone.lower():
                    filtered_clients.append(client)
                    continue
                    
                address = client.get('address', '')
                if address and query_lower in address.lower():
                    filtered_clients.append(client)
            
            current_skip += batch_size
            
            # Early termination if we have enough results
            if len(filtered_clients) >= skip + limit:
                break
        
        return filtered_clients[skip:skip + limit]
    
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
        except Exception as e:
            logger.error(f"Failed to delete client {client_id}: {e}")
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
        limit = limit or config.DEFAULT_PAGE_SIZE
        query_lower = query.lower()
        filtered_invoices = []
        current_skip = 0
        batch_size = min(100, config.MAX_PAGE_SIZE)
        
        # Process invoices in batches with early termination
        while len(filtered_invoices) < skip + limit:
            batch = await self.list_invoices(skip=current_skip, limit=batch_size)
            if not batch:
                break
                
            for invoice in batch:
                # Optimized field access with early exit
                number = invoice.get('number', '')
                if query_lower in number.lower():
                    filtered_invoices.append(invoice)
                    continue
                    
                client_name = invoice.get('client_name', '')
                if client_name and query_lower in client_name.lower():
                    filtered_invoices.append(invoice)
                    continue
                    
                status = invoice.get('status', '')
                if status and query_lower in status.lower():
                    filtered_invoices.append(invoice)
                    continue
                    
                notes = invoice.get('notes', '')
                if notes and query_lower in notes.lower():
                    filtered_invoices.append(invoice)
                    continue
                    
                amount = str(invoice.get('amount', ''))
                if amount and query_lower in amount.lower():
                    filtered_invoices.append(invoice)
            
            current_skip += batch_size
            
            # Early termination if we have enough results
            if len(filtered_invoices) >= skip + limit:
                break
        
        return filtered_invoices[skip:skip + limit]
    
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
        except Exception as e:
            logger.error(f"Failed to delete invoice {invoice_id}: {e}")
            return False
    
    # Currency Management Methods
    async def list_currencies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List supported currencies"""
        return await self._make_request(
            "GET", 
            "/currency/supported",
            params={"active_only": active_only}
        )
    
    async def create_currency(self, currency_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a custom currency"""
        return await self._make_request("POST", "/currency/custom", json=currency_data)
    
    async def convert_currency(self, amount: float, from_currency: str, to_currency: str, conversion_date: Optional[str] = None) -> Dict[str, Any]:
        """Convert amount from one currency to another"""
        params = {
            "amount": amount,
            "from_currency": from_currency,
            "to_currency": to_currency
        }
        if conversion_date:
            params["conversion_date"] = conversion_date
            
        return await self._make_request("POST", "/currency/convert", params=params)
    
    # Payment Management Methods
    async def list_payments(self, skip: int = 0, limit: int = None) -> List[Dict[str, Any]]:
        """List all payments with pagination"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)
        
        return await self._make_request(
            "GET", 
            "/payments/",
            params={"skip": skip, "limit": limit}
        )
    
    async def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new payment"""
        return await self._make_request("POST", "/payments/", json=payment_data)
    
    async def get_payment(self, payment_id: int) -> Dict[str, Any]:
        """Get a specific payment by ID"""
        return await self._make_request("GET", f"/payments/{payment_id}")
    
    # Settings Methods
    async def get_settings(self) -> Dict[str, Any]:
        """Get tenant settings"""
        return await self._make_request("GET", "/settings/")
    
    # Discount Rules Methods
    async def list_discount_rules(self) -> List[Dict[str, Any]]:
        """List all discount rules"""
        return await self._make_request("GET", "/discount-rules/")
    
    async def create_discount_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new discount rule"""
        return await self._make_request("POST", "/discount-rules/", json=rule_data)
    
    async def update_discount_rule(self, rule_id: int, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing discount rule"""
        return await self._make_request("PUT", f"/discount-rules/{rule_id}", json=rule_data)
    
    async def delete_discount_rule(self, rule_id: int) -> bool:
        """Delete a discount rule"""
        try:
            await self._make_request("DELETE", f"/discount-rules/{rule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete discount rule {rule_id}: {e}")
            return False
    
    # CRM Methods
    async def create_client_note(self, client_id: int, note_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a note for a client"""
        return await self._make_request("POST", f"/crm/clients/{client_id}/notes", json=note_data)
    
    async def list_client_notes(self, client_id: int) -> List[Dict[str, Any]]:
        """List notes for a client"""
        return await self._make_request("GET", f"/crm/clients/{client_id}/notes")
    
    # Email Methods
    async def send_invoice_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send an invoice via email"""
        return await self._make_request("POST", "/email/send-invoice", json=email_data)
    
    async def test_email_configuration(self, test_email: str) -> Dict[str, Any]:
        """Test email configuration"""
        return await self._make_request("POST", "/email/test", json={"test_email": test_email})
    
    # Tenant Methods
    async def get_tenant_info(self) -> Dict[str, Any]:
        """Get current tenant information"""
        return await self._make_request("GET", "/tenants/me")
    
    async def list_tenants(self, skip: int = 0, limit: int = None) -> List[Dict[str, Any]]:
        """List all tenants (superuser only)"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)
        
        return await self._make_request(
            "GET", 
            "/tenants/",
            params={"skip": skip, "limit": limit}
        )
    
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
        current_date = datetime.now(timezone.utc).date()
        
        overdue_invoices = []
        for invoice in invoices:
            due_date_str = invoice.get('due_date')
            if due_date_str and invoice.get('status') != 'paid':
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')).date()
                    if due_date < current_date:
                        overdue_invoices.append(invoice)
                except Exception as e:
                    logger.debug(f"Failed to parse due date for invoice {invoice.get('id')}: {e}")
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