"""
Tax Service Integration Service
Handles communication between Invoice App and Tax Service API
"""

import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import json
from urllib.parse import urljoin
from dateutil import parser

logger = logging.getLogger(__name__)


def safe_date_to_iso(date_value: Any) -> str:
    """Safely convert a date value to ISO format string"""
    if date_value is None:
        return datetime.now(timezone.utc).isoformat()

    # If it's already a datetime object
    if isinstance(date_value, datetime):
        # Ensure it has timezone info
        if date_value.tzinfo is None:
            date_value = date_value.replace(tzinfo=timezone.utc)
        return date_value.isoformat()

    # If it's a string, try to parse it
    if isinstance(date_value, str):
        try:
            parsed_date = parser.parse(date_value)
            # Ensure it has timezone info
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            return parsed_date.isoformat()
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date string '{date_value}': {e}")
            return datetime.now(timezone.utc).isoformat()

    # For any other type, use current time
    logger.warning(f"Unexpected date type: {type(date_value)}, value: {date_value}")
    return datetime.now(timezone.utc).isoformat()


class IntegrationType(Enum):
    EXPENSE = "expense"
    INVOICE = "invoice"


class IntegrationStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class IntegrationResult:
    """Result of an integration attempt"""
    success: bool
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


@dataclass
class TaxServiceConfig:
    """Configuration for tax service integration"""
    base_url: str
    api_key: str
    timeout: int = 30
    retry_attempts: int = 3
    enabled: bool = True


class TaxIntegrationService:
    """Service for integrating with the Tax Service API"""

    def __init__(self, config: TaxServiceConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.config.api_key
            }
        )

    async def close(self):
        """Clean up HTTP client"""
        await self.client.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = urljoin(self.config.base_url, endpoint)

        try:
            if method.upper() == "POST":
                response = await self.client.post(url, json=data)
            elif method.upper() == "GET":
                response = await self.client.get(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            if retry_count < self.config.retry_attempts:
                logger.info(f"Retrying request (attempt {retry_count + 1})")
                return await self._make_request(method, endpoint, data, retry_count + 1)
            raise

        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            if retry_count < self.config.retry_attempts:
                logger.info(f"Retrying request (attempt {retry_count + 1})")
                return await self._make_request(method, endpoint, data, retry_count + 1)
            raise

    def _map_expense_to_transaction(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map invoice app expense to tax service transaction format"""
        # Generate unique transaction ID
        expense_id = expense_data.get('id')
        timestamp = int(datetime.now(timezone.utc).timestamp())
        external_transaction_id = f"invoice_app_expense_{expense_id}_{timestamp}"

        # Map expense data to transaction format
        transaction_data = {
            "external_transaction_id": external_transaction_id,
            "amount": abs(float(expense_data.get('amount', 0))),
            "currency": expense_data.get('currency', 'USD'),
            "date": safe_date_to_iso(expense_data.get('expense_date')),
            "description": expense_data.get('notes', f"Expense: {expense_data.get('vendor', 'Unknown vendor')}"),
            "source_system": "invoice_app",
            "category": expense_data.get('category', 'expense'),
            "vendor": expense_data.get('vendor'),
            "reference_number": expense_data.get('reference_number'),
            "payment_method": expense_data.get('payment_method'),
            "tax_amount": expense_data.get('tax_amount'),
            "tax_rate": expense_data.get('tax_rate'),
            "labels": expense_data.get('labels', []),
            "metadata": {
                "invoice_app_id": expense_id,
                "integration_type": "expense",
                "total_amount": expense_data.get('total_amount'),
                "status": expense_data.get('status')
            }
        }

        return transaction_data

    def _map_invoice_to_transaction(self, invoice_data: Dict[str, Any], client_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Map invoice app invoice to tax service transaction format"""
        # Generate unique transaction ID
        invoice_id = invoice_data.get('id')
        timestamp = int(datetime.now(timezone.utc).timestamp())
        external_transaction_id = f"invoice_app_invoice_{invoice_id}_{timestamp}"

        # Get client info if available
        client_name = ""
        if client_data:
            client_name = client_data.get('name', '')

        # Map invoice data to transaction format
        transaction_data = {
            "external_transaction_id": external_transaction_id,
            "amount": float(invoice_data.get('amount', 0)),
            "currency": invoice_data.get('currency', 'USD'),
            "date": safe_date_to_iso(invoice_data.get('created_at')),
            "description": f"Invoice: {invoice_data.get('number', '')} - {client_name}",
            "source_system": "invoice_app",
            "category": "income",
            "client_name": client_name,
            "invoice_number": invoice_data.get('number'),
            "due_date": safe_date_to_iso(invoice_data.get('due_date')),
            "status": invoice_data.get('status'),
            "tax_amount": invoice_data.get('tax_amount'),
            "discount_amount": invoice_data.get('discount_value'),
            "subtotal": invoice_data.get('subtotal'),
            "metadata": {
                "invoice_app_id": invoice_id,
                "integration_type": "invoice",
                "client_id": invoice_data.get('client_id'),
                "total_paid": invoice_data.get('total_paid', 0),
                "items_count": len(invoice_data.get('items', []))
            }
        }

        return transaction_data

    async def send_expense_to_tax_service(self, expense_data: Dict[str, Any]) -> IntegrationResult:
        """Send expense to tax service as expense transaction"""
        try:
            if not self.config.enabled:
                return IntegrationResult(
                    success=False,
                    error_message="Tax service integration is disabled"
                )

            transaction_data = self._map_expense_to_transaction(expense_data)

            logger.info(f"Sending expense {expense_data.get('id')} to tax service")

            response_data = await self._make_request(
                "POST",
                "/api/v1/transactions/expenses",
                transaction_data
            )

            external_transaction_id = response_data.get('external_transaction_id')

            logger.info(f"Successfully sent expense to tax service: {external_transaction_id}")

            return IntegrationResult(
                success=True,
                transaction_id=external_transaction_id,
                response_data=response_data
            )

        except Exception as e:
            error_msg = f"Failed to send expense to tax service: {str(e)}"
            logger.error(error_msg)
            return IntegrationResult(
                success=False,
                error_message=error_msg
            )

    async def send_invoice_to_tax_service(
        self,
        invoice_data: Dict[str, Any],
        client_data: Optional[Dict[str, Any]] = None
    ) -> IntegrationResult:
        """Send invoice to tax service as income transaction"""
        try:
            if not self.config.enabled:
                return IntegrationResult(
                    success=False,
                    error_message="Tax service integration is disabled"
                )

            transaction_data = self._map_invoice_to_transaction(invoice_data, client_data)

            logger.info(f"Sending invoice {invoice_data.get('id')} to tax service")

            response_data = await self._make_request(
                "POST",
                "/api/v1/transactions/income",
                transaction_data
            )

            external_transaction_id = response_data.get('external_transaction_id')

            logger.info(f"Successfully sent invoice to tax service: {external_transaction_id}")

            return IntegrationResult(
                success=True,
                transaction_id=external_transaction_id,
                response_data=response_data
            )

        except Exception as e:
            error_msg = f"Failed to send invoice to tax service: {str(e)}"
            logger.error(error_msg)
            return IntegrationResult(
                success=False,
                error_message=error_msg
            )

    async def send_bulk_expenses_to_tax_service(self, expenses_data: List[Dict[str, Any]]) -> List[IntegrationResult]:
        """Send multiple expenses to tax service"""
        results = []

        for expense_data in expenses_data:
            result = await self.send_expense_to_tax_service(expense_data)
            results.append(result)

            # Add small delay between requests to avoid overwhelming the API
            if len(results) < len(expenses_data):
                await asyncio.sleep(0.1)

        return results

    async def send_bulk_invoices_to_tax_service(
        self,
        invoices_data: List[Dict[str, Any]],
        clients_data: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> List[IntegrationResult]:
        """Send multiple invoices to tax service"""
        results = []

        for invoice_data in invoices_data:
            client_data = None
            if clients_data and invoice_data.get('client_id'):
                client_data = clients_data.get(invoice_data['client_id'])

            result = await self.send_invoice_to_tax_service(invoice_data, client_data)
            results.append(result)

            # Add small delay between requests to avoid overwhelming the API
            if len(results) < len(invoices_data):
                await asyncio.sleep(0.1)

        return results

    async def test_connection(self) -> bool:
        """Test connection to tax service"""
        try:
            # Simple health check - try to access a basic endpoint
            await self._make_request("GET", "/health")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False


# Global service instance (will be initialized from config)
tax_integration_service: Optional[TaxIntegrationService] = None


def get_tax_integration_service() -> Optional[TaxIntegrationService]:
    """Get the global tax integration service instance"""
    return tax_integration_service


def initialize_tax_integration_service(config: TaxServiceConfig):
    """Initialize the global tax integration service"""
    global tax_integration_service
    tax_integration_service = TaxIntegrationService(config)
    logger.info("Tax integration service initialized")


async def cleanup_tax_integration_service():
    """Clean up the tax integration service"""
    global tax_integration_service
    if tax_integration_service:
        await tax_integration_service.close()
        tax_integration_service = None
