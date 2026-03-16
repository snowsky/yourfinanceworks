"""
Shared helper mixin methods for InvoiceTools.
"""
from typing import Any, Dict, List, Optional


class ToolHelpersMixin:
    def _extract_items_from_response(self, response: Any, keys: List[str] = None) -> List[Dict[str, Any]]:
        """Extract items list from various response formats"""
        if isinstance(response, list):
            return response

        if isinstance(response, dict):
            if keys:
                for key in keys:
                    if key in response:
                        value = response[key]
                        if isinstance(value, list):
                            return value

            # Try common keys if none specified or none found
            for key in ["items", "data", "results"]:
                if key in response:
                    value = response[key]
                    if isinstance(value, list):
                        return value

            # If the dict itself is data-like, wrap it
            return []

        return []

    def _prepare_payment_chart_data(self, payments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare payment data for charts"""
        try:
            from datetime import datetime
            from collections import defaultdict

            # Group payments by date for timeline chart
            payments_by_date = defaultdict(float)
            payments_by_method = defaultdict(float)
            payments_by_invoice = defaultdict(list)

            for payment in payments:
                # Date grouping
                if payment.get('payment_date'):
                    try:
                        payment_date = datetime.fromisoformat(str(payment['payment_date'])).strftime('%Y-%m-%d')
                        payments_by_date[payment_date] += float(payment.get('amount', 0))
                    except:
                        pass

                # Payment method grouping
                method = payment.get('payment_method', 'unknown')
                payments_by_method[method] += float(payment.get('amount', 0))

                # Invoice grouping
                invoice_id = payment.get('invoice_id')
                if invoice_id:
                    payments_by_invoice[invoice_id].append({
                        'id': payment.get('id'),
                        'amount': payment.get('amount'),
                        'date': payment.get('payment_date'),
                        'method': payment.get('payment_method')
                    })

            # Prepare chart datasets
            timeline_data = [
                {'date': date, 'amount': amount}
                for date, amount in sorted(payments_by_date.items())
            ]

            method_data = [
                {'method': method, 'amount': amount}
                for method, amount in payments_by_method.items()
            ]

            # Calculate summary stats
            total_amount = sum(float(payment.get('amount', 0)) for payment in payments)
            avg_amount = total_amount / len(payments) if payments else 0

            return {
                'timeline': timeline_data,
                'by_method': method_data,
                'summary': {
                    'total_amount': total_amount,
                    'total_payments': len(payments),
                    'average_amount': avg_amount,
                    'date_range': {
                        'earliest': min(payments_by_date.keys()) if payments_by_date else None,
                        'latest': max(payments_by_date.keys()) if payments_by_date else None
                    }
                }
            }

        except Exception as e:
            return {'error': f'Failed to prepare chart data: {e}'}

    def _parse_date_filter(self, query_lower: str, payments: List[Dict[str, Any]]) -> Optional[tuple]:
        """Parse date-related keywords and filter payments accordingly"""
        from datetime import datetime, timedelta

        if "yesterday" in query_lower:
            yesterday = (datetime.now() - timedelta(days=1)).date()
            filtered = [p for p in payments if p.get('payment_date') and datetime.fromisoformat(str(p['payment_date'])).date() == yesterday]
            return filtered, True, "yesterday"
        elif "today" in query_lower:
            today = datetime.now().date()
            filtered = [p for p in payments if p.get('payment_date') and datetime.fromisoformat(str(p['payment_date'])).date() == today]
            return filtered, True, "today"
        elif "this week" in query_lower:
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            filtered = [p for p in payments if p.get('payment_date') and datetime.fromisoformat(str(p['payment_date'])) >= start_of_week]
            return filtered, True, "this week"
        elif "last week" in query_lower:
            today = datetime.now()
            start_of_this_week = today - timedelta(days=today.weekday())
            start_of_last_week = start_of_this_week - timedelta(days=7)
            end_of_last_week = start_of_this_week - timedelta(seconds=1)
            filtered = [p for p in payments if p.get('payment_date') and start_of_last_week <= datetime.fromisoformat(str(p['payment_date'])) <= end_of_last_week]
            return filtered, True, "last week"
        elif "this month" in query_lower:
            today = datetime.now()
            start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            filtered = [p for p in payments if p.get('payment_date') and datetime.fromisoformat(str(p['payment_date'])) >= start_of_month]
            return filtered, True, "this month"
        elif "last month" in query_lower:
            today = datetime.now()
            first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if today.month == 1:
                first_day_last_month = first_day_this_month.replace(year=today.year-1, month=12)
            else:
                first_day_last_month = first_day_this_month.replace(month=today.month-1)
            last_day_last_month = first_day_this_month - timedelta(seconds=1)
            filtered = [p for p in payments if p.get('payment_date') and first_day_last_month <= datetime.fromisoformat(str(p['payment_date'])) <= last_day_last_month]
            return filtered, True, "last month"
        elif "past week" in query_lower:
            week_ago = datetime.now() - timedelta(days=7)
            filtered = [p for p in payments if p.get('payment_date') and datetime.fromisoformat(str(p['payment_date'])) >= week_ago]
            return filtered, True, "in the past 7 days"
        elif "past month" in query_lower:
            month_ago = datetime.now() - timedelta(days=30)
            filtered = [p for p in payments if p.get('payment_date') and datetime.fromisoformat(str(p['payment_date'])) >= month_ago]
            return filtered, True, "in the past 30 days"
        return None

    def _format_statement_for_display(self, stmt: Dict[str, Any]) -> Dict[str, Any]:
        """Format a bank statement for better user display"""
        # Extract account name from filename or labels
        account_name = "Unknown"
        if stmt.get("original_filename"):
            # Try to extract account name from filename
            filename = stmt["original_filename"].lower()
            if "checking" in filename:
                account_name = "Checking Account"
            elif "savings" in filename:
                account_name = "Savings Account"
            elif "credit" in filename:
                account_name = "Credit Card"
            elif "business" in filename:
                account_name = "Business Account"
            else:
                # Use filename as fallback
                account_name = stmt["original_filename"].replace(".pdf", "").replace("_", " ").title()

        # Extract period from filename or created date
        period = "N/A"
        if stmt.get("created_at"):
            try:
                from datetime import datetime
                created_date = datetime.fromisoformat(stmt["created_at"].replace("Z", "+00:00"))
                period = created_date.strftime("%B %Y")
            except:
                pass

        # Get transaction count
        transaction_count = stmt.get("extracted_count", 0)
        if transaction_count == 0:
            transaction_count = "N/A"

        # Format status for display
        status = stmt.get("status", "Unknown")
        status_display = status.replace("_", " ").title()

        return {
            "id": stmt.get("id"),
            "account_name": account_name,
            "period": period,
            "status": status_display,
            "transaction_count": transaction_count,
            "original_filename": stmt.get("original_filename"),
            "created_at": stmt.get("created_at"),
            "extracted_count": stmt.get("extracted_count", 0),
            "labels": stmt.get("labels", []),
            "notes": stmt.get("notes"),
            "review_status": stmt.get("review_status", "not_started")
        }
