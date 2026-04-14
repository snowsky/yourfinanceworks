# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

import json
import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


# Helper class for authenticated API requests
class AuthenticatedAPIClient:
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.jwt_token = jwt_token
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request using JWT token"""
        try:
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
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
            # Try to parse the error response
            try:
                # Start by getting the response text to debug
                error_text = e.response.text
                logger.debug(f"HTTP Error Response: {error_text}")

                try:
                    error_data = e.response.json()
                    # Handle standard FastAPI error format {"detail": ...}
                    if "detail" in error_data:
                        detail = error_data["detail"]
                        if isinstance(detail, list):
                            # Handle validation errors which are lists
                            errors = [f"{d.get('loc', [])[-1]}: {d.get('msg')}" for d in detail]
                            raise Exception(f"Validation error: {', '.join(errors)}")

                        # Map error codes to friendly messages
                        if detail == "CLIENT_ALREADY_EXISTS":
                            raise Exception("A client with this email address already exists.")

                        raise Exception(f"{detail}")
                    # Handle other JSON error formats
                    raise Exception(f"{error_data}")
                except json.JSONDecodeError:
                    # Fallback to text if not JSON
                    raise Exception(f"API Error: {error_text}")
            except Exception as inner_e:
                # If our custom parsing fails, raise the inner exception but preserve context
                # Check if it's the exception we just raised
                if str(inner_e) != "Request error: " + str(e):
                        raise inner_e
                raise Exception(f"Request error: {e}")
        except Exception as e:
                logger.error(f"General Request Error: {e}")
                raise Exception(f"Request error: {e}")

    # Client Management Methods
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client"""
        return await self._make_request("POST", "/tools/clients/", json=client_data)

    async def list_clients(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._make_request(
            "GET",
            "/tools/clients/",
            params={"skip": skip, "limit": limit}
        )

    async def search_clients(self, query: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        # Get all clients and filter locally
        clients = await self.list_clients(skip=0, limit=1000)
        query_lower = query.lower()
        filtered_clients = []

        for client in clients:
            searchable_fields = [
                client.get('name', ''),
                client.get('email', ''),
                client.get('phone', ''),
                client.get('address', '')
            ]

            if any(query_lower in str(field).lower() for field in searchable_fields if field):
                filtered_clients.append(client)

        end_idx = skip + limit
        return filtered_clients[skip:end_idx]

    # Invoice Management Methods
    async def list_invoices(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._make_request(
            "GET",
            "/tools/invoices/",
            params={"skip": skip, "limit": limit}
        )

    async def search_invoices(self, query: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        # Get all invoices and filter locally
        invoices = await self.list_invoices(skip=0, limit=1000)
        query_lower = query.lower()
        filtered_invoices = []

        for invoice in invoices:
            searchable_fields = [
                invoice.get('number', ''),
                invoice.get('client_name', ''),
                invoice.get('status', ''),
                invoice.get('notes', ''),
                str(invoice.get('amount', ''))
            ]

            if any(query_lower in str(field).lower() for field in searchable_fields if field):
                filtered_invoices.append(invoice)

        end_idx = skip + limit
        return filtered_invoices[skip:end_idx]

    # Payment Management Methods
    async def list_payments(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._make_request(
            "GET",
            "/tools/payments/",
            params={"skip": skip, "limit": limit}
        )

    # Currency Management Methods
    async def list_currencies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        return await self._make_request(
            "GET",
            "/currency/supported",
            params={"active_only": active_only}
        )

    # Analytics Methods
    async def get_clients_with_outstanding_balance(self) -> List[Dict[str, Any]]:
        return await self._make_request("GET", "/tools/clients/with-outstanding-balance")

    async def get_overdue_invoices(self) -> List[Dict[str, Any]]:
        return await self._make_request("GET", "/tools/invoices/overdue")

    async def get_invoice_stats(self) -> Dict[str, Any]:
        return await self._make_request("GET", "/tools/invoices/stats")

    async def analyze_invoice_patterns(self) -> Dict[str, Any]:
        return await self._make_request("GET", "/ai/analyze-patterns")

    async def suggest_invoice_actions(self) -> Dict[str, Any]:
        return await self._make_request("GET", "/ai/suggest-actions")

    # Expense Management Methods
    async def create_expense(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._make_request("POST", "/tools/expenses/", json=expense_data)

    async def list_expenses(self, skip: int = 0, limit: int = 100, category: str = None, invoice_id: int = None, **kwargs) -> List[Dict[str, Any]]:
        params = {"skip": skip, "limit": limit}
        if category:
            params["category"] = category
        if invoice_id:
            params["invoice_id"] = invoice_id
        return await self._make_request(
            "GET",
            "/tools/expenses/",
            params=params
        )

    async def search_expenses(self, query: str, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        # Get all expenses and filter locally
        expenses = await self.list_expenses(skip=0, limit=1000)
        query_lower = query.lower()
        filtered_expenses = []

        for expense in expenses:
            searchable_fields = [
                expense.get('category', ''),
                expense.get('vendor', ''),
                expense.get('notes', ''),
                str(expense.get('amount', ''))
            ]

            if any(query_lower in str(field).lower() for field in searchable_fields if field):
                filtered_expenses.append(expense)

        end_idx = skip + limit
        return {
            "success": True,
            "data": filtered_expenses[skip:end_idx]
        }

    # Statement Management Methods
    async def list_statements(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        result = await self._make_request(
            "GET",
            "/tools/statements/",
            params={"skip": skip, "limit": limit}
        )
        return {
            "success": True,
            "data": result if isinstance(result, list) else result.get("statements", result.get("data", []))
        }

    async def get_bank_statement(self, statement_id: int) -> Dict[str, Any]:
        """Get a specific bank statement with transactions"""
        return await self._make_request("GET", f"/tools/statements/{statement_id}")

    async def replace_bank_statement_transactions(
        self, statement_id: int, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Replace bank statement transactions"""
        return await self._make_request(
            "PUT",
            f"/tools/statements/{statement_id}/transactions",
            json={"transactions": transactions}
        )

    # Investment Management Methods
    async def list_portfolios(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List all investment portfolios"""
        return await self._make_request(
            "GET",
            "/investments/portfolios",
            params={"skip": skip, "limit": limit}
        )

    async def get_portfolio(self, portfolio_id: int) -> Dict[str, Any]:
        """Get a specific portfolio by ID"""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}")

    async def get_portfolio_holdings(self, portfolio_id: int) -> List[Dict[str, Any]]:
        """Get holdings for a specific portfolio"""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/holdings")

    async def get_portfolio_performance(self, portfolio_id: int) -> Dict[str, Any]:
        """Get performance metrics for a specific portfolio"""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/performance")

    async def get_portfolio_allocation(self, portfolio_id: int) -> Dict[str, Any]:
        """Get asset allocation for a specific portfolio"""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/allocation")

    async def get_portfolio_dividends(self, portfolio_id: int) -> Dict[str, Any]:
        """Get dividend summary for a specific portfolio"""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/dividends")

    async def close(self):
        await self._client.aclose()
