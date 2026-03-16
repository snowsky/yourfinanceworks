"""
Payment-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ListPaymentsArgs(BaseModel):
    skip: int = Field(default=0, description="Number of payments to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of payments to return")


class CreatePaymentArgs(BaseModel):
    invoice_id: int = Field(description="ID of the invoice this payment is for")
    amount: float = Field(description="Payment amount")
    payment_date: str = Field(description="Payment date in ISO format (YYYY-MM-DD)")
    payment_method: str = Field(description="Payment method (cash, check, credit_card, etc.)")
    reference: Optional[str] = Field(default=None, description="Payment reference number")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class PaymentToolsMixin:
    # Payments
    async def list_payments(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List all payments"""
        try:
            response = await self.api_client.list_payments(skip=skip, limit=limit)

            # Extract payments from response
            payments = self._extract_items_from_response(response, ["data", "items", "payments"])

            # Prepare chart data for smaller datasets only
            chart_data = None
            if len(payments) <= 500:  # Only generate charts for reasonable dataset sizes
                chart_data = self._prepare_payment_chart_data(payments)

            return {
                "success": True,
                "data": payments,
                "count": len(payments),
                "pagination": {
                    "skip": skip,
                    "limit": limit
                },
                "chart_data": chart_data
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to list payments: {e}"}

    async def query_payments(self, query: str) -> Dict[str, Any]:
        """Query payments using natural language (e.g., 'payments yesterday', 'payments this week')"""
        try:
            from datetime import datetime, date, timedelta

            # Get all payments first
            payments = await self.api_client.list_payments(skip=0, limit=1000)

            # Parse the query for date-related keywords
            query_lower = query.lower()
            filtered_payments = payments
            date_filter_applied = False
            date_description = ""

            # Parse date-related keywords using helper method
            date_filter_result = self._parse_date_filter(query_lower, payments)
            if date_filter_result:
                filtered_payments, date_filter_applied, date_description = date_filter_result
            else:
                date_filter_applied = False
                date_description = ""


            # Parse payment method filters
            if "credit card" in query_lower or "card" in query_lower:
                filtered_payments = [
                    p for p in filtered_payments
                    if p.get('payment_method') and 'credit' in p['payment_method'].lower()
                ]
            elif "cash" in query_lower:
                filtered_payments = [
                    p for p in filtered_payments
                    if p.get('payment_method') and 'cash' in p['payment_method'].lower()
                ]
            elif "check" in query_lower or "cheque" in query_lower:
                filtered_payments = [
                    p for p in filtered_payments
                    if p.get('payment_method') and 'check' in p['payment_method'].lower()
                ]

            # Parse amount filters
            if "over" in query_lower or "above" in query_lower:
                import re
                amount_match = re.search(r'(?:over|above)\s*\$?(\d+(?:\.\d+)?)', query_lower)
                if amount_match:
                    min_amount = float(amount_match.group(1))
                    filtered_payments = [
                        p for p in filtered_payments
                        if p.get('amount') and float(p['amount']) > min_amount
                    ]
            elif "under" in query_lower or "below" in query_lower:
                import re
                amount_match = re.search(r'(?:under|below)\s*\$?(\d+(?:\.\d+)?)', query_lower)
                if amount_match:
                    max_amount = float(amount_match.group(1))
                    filtered_payments = [
                        p for p in filtered_payments
                        if p.get('amount') and float(p['amount']) < max_amount
                    ]

            # Parse client filters
            if "from" in query_lower and "client" in query_lower:
                # This is already handled by the existing filtering logic
                pass

            return {
                "success": True,
                "data": filtered_payments,
                "count": len(filtered_payments),
                "query": query,
                "date_filter_applied": date_filter_applied,
                "date_description": date_description,
                "total_payments_checked": len(payments)
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to query payments: {e}"}

    async def create_payment(self, invoice_id: int, amount: float, payment_date: str, payment_method: str, reference: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """Create a new payment"""
        try:
            payment_data = {
                "invoice_id": invoice_id,
                "amount": amount,
                "payment_date": payment_date,
                "payment_method": payment_method
            }
            if reference:
                payment_data["reference"] = reference
            if notes:
                payment_data["notes"] = notes

            payment = await self.api_client.create_payment(payment_data)

            return {
                "success": True,
                "data": payment,
                "message": "Payment created successfully"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create payment: {e}"}
