"""
Invoice-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from pydantic import BaseModel, Field


class ListInvoicesArgs(BaseModel):
    skip: int = Field(default=0, description="Number of invoices to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of invoices to return")


class SearchInvoicesArgs(BaseModel):
    query: str = Field(description="Search query to find invoices by number, client name, status, notes, or amount")
    skip: int = Field(default=0, description="Number of results to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of results to return")


class GetInvoiceArgs(BaseModel):
    invoice_id: int = Field(description="ID of the invoice to retrieve")


class CreateInvoiceArgs(BaseModel):
    client_id: int = Field(description="ID of the client this invoice belongs to")
    amount: float = Field(description="Total amount of the invoice")
    due_date: str = Field(description="Due date of the invoice in ISO format (YYYY-MM-DD)")
    status: str = Field(default="draft", description="Invoice status (draft, sent, paid, etc.)")
    notes: Optional[str] = Field(default=None, description="Optional notes for the invoice")


class SendInvoiceEmailArgs(BaseModel):
    invoice_id: int = Field(description="ID of the invoice to send")
    to_email: Optional[str] = Field(default=None, description="Recipient email address")
    to_name: Optional[str] = Field(default=None, description="Recipient name")
    subject: Optional[str] = Field(default=None, description="Email subject")
    message: Optional[str] = Field(default=None, description="Email message body")


class InvoiceToolsMixin:
    async def list_invoices(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List all invoices"""
        try:
            response = await self.api_client.list_invoices(skip=skip, limit=limit)

            # Extract items from paginated response
            invoices = self._extract_items_from_response(response, ["items", "data", "invoices"])

            return {
                "success": True,
                "data": invoices,
                "count": len(invoices),
                "pagination": {
                    "skip": skip,
                    "limit": limit
                }
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to list invoices: {e}"}

    async def search_invoices(self, query: str, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Search for invoices"""
        try:
            response = await self.api_client.search_invoices(
                query=query,
                skip=skip,
                limit=limit
            )

            # Extract items from paginated response
            invoices = self._extract_items_from_response(response, ["items", "data", "invoices"])

            return {
                "success": True,
                "data": invoices,
                "count": len(invoices),
                "search_query": query,
                "pagination": {
                    "skip": skip,
                    "limit": limit
                }
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to search invoices: {e}"}

    async def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Get a specific invoice"""
        try:
            invoice = await self.api_client.get_invoice(invoice_id)

            return {
                "success": True,
                "data": invoice
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get invoice: {e}"}

    async def create_invoice(self, client_id: int, amount: float, due_date: str, status: str = "draft", notes: Optional[str] = None) -> Dict[str, Any]:
        """Create a new invoice"""
        try:
            invoice_data = {
                "client_id": client_id,
                "amount": amount,
                "due_date": due_date,
                "status": status
            }
            if notes:
                invoice_data["notes"] = notes

            invoice = await self.api_client.create_invoice(invoice_data)

            return {
                "success": True,
                "data": invoice,
                "message": "Invoice created successfully"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create invoice: {e}"}

    async def get_clients_with_outstanding_balance(self) -> Dict[str, Any]:
        """Get clients with outstanding balances"""
        try:
            clients = await self.api_client.get_clients_with_outstanding_balance()

            return {
                "success": True,
                "data": clients,
                "count": len(clients),
                "message": f"Found {len(clients)} clients with outstanding balances"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get clients with outstanding balance: {e}"}

    async def get_overdue_invoices(self) -> Dict[str, Any]:
        """Get overdue invoices"""
        try:
            invoices = await self.api_client.get_overdue_invoices()

            return {
                "success": True,
                "data": invoices,
                "count": len(invoices),
                "message": f"Found {len(invoices)} overdue invoices"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get overdue invoices: {e}"}

    async def get_invoice_stats(self) -> Dict[str, Any]:
        """Get invoice statistics"""
        try:
            stats = await self.api_client.get_invoice_stats()

            return {
                "success": True,
                "data": stats
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get invoice stats: {e}"}

    async def analyze_invoice_patterns(self) -> Dict[str, Any]:
        """Analyze invoice patterns to identify trends and provide recommendations."""
        try:
            # Fetch invoices and clients with pagination for better performance
            # Use smaller initial limit and expand if needed
            invoices = await self.api_client.list_invoices(limit=500)
            clients = await self.api_client.list_clients(limit=500)

            if not invoices:
                return {"success": True, "data": {"message": "No invoices found to analyze."}}

            # Create a client map for easy lookup
            client_map = {client['id']: client for client in clients}

            # Analysis variables
            total_invoices = len(invoices)
            paid_invoices = [inv for inv in invoices if inv['status'] == 'paid']
            unpaid_invoices = [inv for inv in invoices if inv['status'] != 'paid']
            overdue_invoices = [inv for inv in unpaid_invoices if inv.get('due_date') and inv['due_date'] < datetime.now().isoformat()]

            total_revenue = sum(inv['amount'] for inv in paid_invoices)
            outstanding_revenue = sum(inv['amount'] for inv in unpaid_invoices)

            # Client analysis
            client_payment_times = {}
            for inv in paid_invoices:
                if inv.get('paid_date') and inv.get('created_at'):
                    client_id = inv['client_id']
                    paid_date = datetime.fromisoformat(inv['paid_date'])
                    created_date = datetime.fromisoformat(inv['created_at'])
                    payment_time = (paid_date - created_date).days

                    if client_id not in client_payment_times:
                        client_payment_times[client_id] = []
                    client_payment_times[client_id].append(payment_time)

            avg_payment_times = {
                client_map.get(cid, {}).get('name', f"Client {cid}"): sum(times) / len(times)
                for cid, times in client_payment_times.items()
            }

            fastest_paying_clients = sorted(avg_payment_times.items(), key=lambda item: item[1])[:3]
            slowest_paying_clients = sorted(avg_payment_times.items(), key=lambda item: item[1], reverse=True)[:3]

            # Recommendations
            recommendations = []
            if overdue_invoices:
                recommendations.append(f"You have {len(overdue_invoices)} overdue invoices. Consider sending reminders.")
            if slowest_paying_clients:
                slow_client_name = slowest_paying_clients[0][0]
                recommendations.append(f"'{slow_client_name}' is your slowest paying client. Consider shortening their payment terms.")

            analysis_data = {
                "total_invoices": total_invoices,
                "paid_invoices": len(paid_invoices),
                "unpaid_invoices": len(unpaid_invoices),
                "overdue_invoices": len(overdue_invoices),
                "total_revenue": total_revenue,
                "outstanding_revenue": outstanding_revenue,
                "average_payment_time_days": sum(avg_payment_times.values()) / len(avg_payment_times) if avg_payment_times else 0,
                "fastest_paying_clients": fastest_paying_clients,
                "slowest_paying_clients": slowest_paying_clients,
                "recommendations": recommendations
            }

            return {"success": True, "data": analysis_data}

        except Exception as e:
            return {"success": False, "error": f"Failed to analyze invoice patterns: {e}"}

    async def suggest_invoice_actions(self) -> Dict[str, Any]:
        """Suggest actionable items based on invoice analysis."""
        try:
            analysis_result = await self.analyze_invoice_patterns()
            if not analysis_result.get("success"):
                return analysis_result

            analysis_data = analysis_result.get("data", {})
            recommendations = analysis_data.get("recommendations", [])
            overdue_invoices_count = analysis_data.get("overdue_invoices", 0)

            actions = []
            if overdue_invoices_count > 0:
                actions.append({
                    "action": "send_reminders",
                    "description": f"You have {overdue_invoices_count} overdue invoices. Would you like to draft reminder emails?",
                    "tool_to_use": "draft_reminder_email(invoice_id)"
                })

            if analysis_data.get("slowest_paying_clients"):
                slow_client = analysis_data["slowest_paying_clients"][0]
                actions.append({
                    "action": "review_payment_terms",
                    "description": f"'{slow_client[0]}' is your slowest paying client (avg. {slow_client[1]:.1f} days). Consider shortening their payment terms.",
                    "client_name": slow_client[0]
                })

            if not actions:
                actions.append({"action": "no_suggestions", "description": "Everything looks good! No immediate actions suggested."})

            return {"success": True, "data": {"suggested_actions": actions, "raw_analysis": analysis_data}}

        except Exception as e:
            return {"success": False, "error": f"Failed to suggest invoice actions: {e}"}

    async def send_invoice_email(self, invoice_id: int, to_email: Optional[str] = None, to_name: Optional[str] = None, subject: Optional[str] = None, message: Optional[str] = None) -> Dict[str, Any]:
        """Send an invoice via email"""
        try:
            email_data = {"invoice_id": invoice_id}
            if to_email:
                email_data["to_email"] = to_email
            if to_name:
                email_data["to_name"] = to_name
            if subject:
                email_data["subject"] = subject
            if message:
                email_data["message"] = message

            result = await self.api_client.send_invoice_email(email_data)

            return {
                "success": True,
                "data": result,
                "message": "Invoice email sent successfully"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to send invoice email: {e}"}
