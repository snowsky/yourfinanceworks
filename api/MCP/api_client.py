"""
API Client for YourFinanceWorks Application MCP integration
"""

from typing import List, Dict, Any, Optional
from httpx import AsyncClient, HTTPStatusError
from datetime import datetime, timezone
import logging
import os
import mimetypes

from .auth_client import InvoiceAPIAuthClient, AuthenticationError
from .config import config

logger = logging.getLogger(__name__)


class InvoiceAPIClient:
    """Client for interacting with the Invoice API"""

    def __init__(self, base_url: str = None, email: str = None, password: str = None):
        self.base_url = base_url or config.API_BASE_URL
        self.auth_client = InvoiceAPIAuthClient(base_url, email, password)
        self._client = AsyncClient(timeout=config.REQUEST_TIMEOUT)

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Make authenticated request to the API"""
        try:
            headers = await self.auth_client.get_auth_headers()
            headers.update(kwargs.pop("headers", {}))

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
            raise Exception(
                f"API request failed: {e.response.status_code} - {e.response.text}"
            )
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Request error: {e}")

    # Client Management Methods
    async def list_clients(
        self, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
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

    async def search_clients(
        self, query: str, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
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
                name = client.get("name", "")
                if query_lower in name.lower():
                    filtered_clients.append(client)
                    continue

                email = client.get("email", "")
                if email and query_lower in email.lower():
                    filtered_clients.append(client)
                    continue

                phone = client.get("phone", "")
                if phone and query_lower in phone.lower():
                    filtered_clients.append(client)
                    continue

                address = client.get("address", "")
                if address and query_lower in address.lower():
                    filtered_clients.append(client)

            current_skip += batch_size

            # Early termination if we have enough results
            if len(filtered_clients) >= skip + limit:
                break

        return filtered_clients[skip : skip + limit]

    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client"""
        return await self._make_request("POST", "/clients/", json=client_data)

    async def update_client(
        self, client_id: int, client_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing client"""
        return await self._make_request(
            "PUT", f"/clients/{client_id}", json=client_data
        )

    async def delete_client(self, client_id: int) -> bool:
        """Delete a client"""
        try:
            await self._make_request("DELETE", f"/clients/{client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete client {client_id}: {e}")
            return False

    # Invoice Management Methods
    async def list_invoices(
        self, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
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

    async def search_invoices(
        self, query: str, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
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
                number = invoice.get("number", "")
                if query_lower in number.lower():
                    filtered_invoices.append(invoice)
                    continue

                client_name = invoice.get("client_name", "")
                if client_name and query_lower in client_name.lower():
                    filtered_invoices.append(invoice)
                    continue

                status = invoice.get("status", "")
                if status and query_lower in status.lower():
                    filtered_invoices.append(invoice)
                    continue

                notes = invoice.get("notes", "")
                if notes and query_lower in notes.lower():
                    filtered_invoices.append(invoice)
                    continue

                amount = str(invoice.get("amount", ""))
                if amount and query_lower in amount.lower():
                    filtered_invoices.append(invoice)

            current_skip += batch_size

            # Early termination if we have enough results
            if len(filtered_invoices) >= skip + limit:
                break

        return filtered_invoices[skip : skip + limit]

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new invoice"""
        return await self._make_request("POST", "/invoices/", json=invoice_data)

    async def update_invoice(
        self, invoice_id: int, invoice_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing invoice"""
        return await self._make_request(
            "PUT", f"/invoices/{invoice_id}", json=invoice_data
        )

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

    async def convert_currency(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        conversion_date: Optional[str] = None,
    ) -> Dict[str, Any]:
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
    async def list_payments(
        self, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
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

    # Expense Management Methods
    async def list_expenses(
        self,
        skip: int = 0,
        limit: int = None,
        category: Optional[str] = None,
        invoice_id: Optional[int] = None,
        unlinked_only: bool = False,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List expenses with optional filters"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)

        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if category is not None:
            params["category"] = category
        if invoice_id is not None:
            params["invoice_id"] = invoice_id
        if unlinked_only:
            params["unlinked_only"] = True
        if search is not None:
            params["search"] = search

        return await self._make_request("GET", "/expenses/", params=params)

    async def get_expense(self, expense_id: int) -> Dict[str, Any]:
        """Get a specific expense by ID"""
        return await self._make_request("GET", f"/expenses/{expense_id}")

    async def search_expenses(
        self, query: str, skip: int = 0, limit: int = None
    ) -> Dict[str, Any]:
        """Search expenses by vendor, category, notes, or other fields"""
        return await self.list_expenses(search=query, skip=skip, limit=limit)

    async def get_expense(self, expense_id: int) -> Dict[str, Any]:
        """Get a specific expense by ID"""
        return await self._make_request("GET", f"/expenses/{expense_id}")

    async def create_expense(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new expense"""
        return await self._make_request("POST", "/expenses/", json=expense_data)

    async def update_expense(
        self, expense_id: int, expense_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing expense"""
        return await self._make_request(
            "PUT", f"/expenses/{expense_id}", json=expense_data
        )

    async def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense by ID"""
        try:
            await self._make_request("DELETE", f"/expenses/{expense_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete expense {expense_id}: {e}")
            return False

    async def upload_expense_receipt(
        self,
        expense_id: int,
        file_path: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a receipt/attachment file for a given expense"""
        # Validate file path before opening
        from core.utils.file_validation import validate_file_path
        validated_path = validate_file_path(file_path)

        headers = await self.auth_client.get_auth_headers()
        # httpx requires no Content-Type header set for multipart; remove if present
        headers.pop("Content-Type", None)

        final_filename = filename or os.path.basename(validated_path)
        final_content_type = content_type or (
            mimetypes.guess_type(final_filename)[0] or "application/octet-stream"
        )

        with open(validated_path, "rb") as fp:
            files = {"file": (final_filename, fp, final_content_type)}
            resp = await self._client.post(
                url=f"{self.base_url}/expenses/{expense_id}/upload-receipt",
                headers=headers,
                files=files,
            )
            resp.raise_for_status()
            return resp.json()

    async def list_expense_attachments(self, expense_id: int) -> List[Dict[str, Any]]:
        """List attachments for an expense"""
        return await self._make_request("GET", f"/expenses/{expense_id}/attachments")

    async def delete_expense_attachment(
        self, expense_id: int, attachment_id: int
    ) -> bool:
        """Delete an attachment for an expense"""
        try:
            await self._make_request(
                "DELETE", f"/expenses/{expense_id}/attachments/{attachment_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete expense attachment {attachment_id} for expense {expense_id}: {e}")
            return False

    async def download_expense_attachment(
        self, expense_id: int, attachment_id: int
    ) -> Dict[str, Any]:
        """Download an expense attachment and return raw content with metadata"""
        headers = await self.auth_client.get_auth_headers()
        resp = await self._client.get(
            url=f"{self.base_url}/expenses/{expense_id}/attachments/{attachment_id}/download",
            headers=headers,
        )
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("content-type", "application/octet-stream")
        disposition = resp.headers.get("content-disposition", "")
        filename = None
        if "filename=" in disposition:
            # naive parse for filename="..."
            try:
                filename = disposition.split("filename=")[1].strip().strip('"')
            except Exception:
                filename = None
        return {"content": content, "content_type": content_type, "filename": filename}

    # Statement Management Methods
    async def list_statements(self) -> List[Dict[str, Any]]:
        """List all statements"""
        return await self._make_request("GET", "/statements/")

    async def get_bank_statement(self, statement_id: int) -> Dict[str, Any]:
        """Get a specific bank statement with transactions"""
        return await self._make_request("GET", f"/statements/{statement_id}")

    async def upload_statements(
        self, files_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Upload statement files"""
        return await self._make_request(
            "POST", "/statements/upload", json={"files": files_data}
        )

    async def reprocess_bank_statement(self, statement_id: int) -> Dict[str, Any]:
        """Reprocess a bank statement"""
        return await self._make_request("POST", f"/statements/{statement_id}/reprocess")

    async def update_bank_statement_meta(
        self, statement_id: int, meta_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update bank statement metadata"""
        return await self._make_request(
            "PUT", f"/statements/{statement_id}", json=meta_data
        )

    async def replace_bank_statement_transactions(
        self, statement_id: int, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Replace bank statement transactions"""
        return await self._make_request(
            "PUT",
            f"/statements/{statement_id}/transactions",
            json={"transactions": transactions},
        )

    async def delete_bank_statement(self, statement_id: int) -> bool:
        """Delete a bank statement"""
        try:
            await self._make_request("DELETE", f"/statements/{statement_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete bank statement {statement_id}: {e}")
            return False

    async def download_bank_statement_file(
        self, statement_id: int, inline: bool = False
    ) -> Dict[str, Any]:
        """Download bank statement file"""
        headers = await self.auth_client.get_auth_headers()
        params = {"inline": inline} if inline else {}

        response = await self._make_request(
            "GET",
            f"/statements/{statement_id}/download",
            params=params,
            return_response=True,
        )

        # Handle file download response
        content_disposition = response.headers.get("content-disposition", "")
        filename = "statement.pdf"
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')

        content_type = response.headers.get("content-type", "application/pdf")
        content = await response.aread()

        return {"content": content, "content_type": content_type, "filename": filename}

    # Recycle Bin Methods
    async def list_deleted_statements(
        self, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List all deleted statements in recycle bin"""
        return await self._make_request(
            "GET", "/statements/recycle-bin", params={"skip": skip, "limit": limit}
        )

    async def restore_statement(self, statement_id: int) -> Dict[str, Any]:
        """Restore a deleted statement from recycle bin"""
        return await self._make_request("POST", f"/statements/{statement_id}/restore")

    async def permanently_delete_statement(self, statement_id: int) -> bool:
        """Permanently delete a statement from recycle bin"""
        try:
            await self._make_request("DELETE", f"/statements/{statement_id}/permanent")
            return True
        except Exception as e:
            logger.error(f"Failed to permanently delete bank statement {statement_id}: {e}")
            return False

    # Approval Workflow Methods
    async def submit_expense_for_approval(
        self, expense_id: int, notes: str = None
    ) -> Dict[str, Any]:
        """Submit an expense for approval workflow"""
        data = {"expense_id": expense_id}
        if notes:
            data["notes"] = notes
        return await self._make_request("POST", "/approvals/submit", json=data)

    async def get_pending_approvals(
        self, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending approvals for current user"""
        return await self._make_request(
            "GET", "/approvals/pending", params={"skip": skip, "limit": limit}
        )

    async def approve_expense(
        self, approval_id: int, decision: str, notes: str = None
    ) -> Dict[str, Any]:
        """Approve or reject an expense"""
        data = {"decision": decision}
        if notes:
            data["notes"] = notes
        return await self._make_request(
            "POST", f"/approvals/{approval_id}/decision", json=data
        )

    async def get_approval_history(
        self,
        entity_type: str = None,
        entity_id: int = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get approval history"""
        params = {"skip": skip, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        if entity_id:
            params["entity_id"] = entity_id
        return await self._make_request("GET", "/approvals/history", params=params)

    # Reports Generation Methods
    async def generate_report(
        self, report_type: str, start_date: str, end_date: str, format: str = "pdf"
    ) -> Dict[str, Any]:
        """Generate a business report"""
        params = {
            "report_type": report_type,
            "start_date": start_date,
            "end_date": end_date,
            "format": format
        }
        return await self._make_request("POST", "/reports/generate", json=params)

    async def list_report_templates(self) -> List[Dict[str, Any]]:
        """List available report templates"""
        return await self._make_request("GET", "/reports/templates")

    async def get_report_history(
        self, skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get report generation history"""
        return await self._make_request(
            "GET", "/reports/history", params={"skip": skip, "limit": limit}
        )

    # Advanced Search Methods
    async def global_search(
        self, query: str, entity_types: List[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        """Perform global search across all entities"""
        params = {"q": query, "limit": limit}
        if entity_types:
            params["types"] = ",".join(entity_types)
        return await self._make_request("GET", "/search", params=params)

    async def search_suggestions(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Get search suggestions based on partial query"""
        params = {"q": query, "limit": limit}
        return await self._make_request("GET", "/search/suggestions", params=params)

    async def reindex_all_data(self) -> Dict[str, Any]:
        """Reindex all data for search (admin only)"""
        return await self._make_request("POST", "/search/reindex")

    async def get_search_status(self) -> Dict[str, Any]:
        """Get search service status"""
        return await self._make_request("GET", "/search/status")

    # Enhanced Reports Methods
    async def preview_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Preview a report with limited results"""
        return await self._make_request("POST", "/reports/preview", json=report_config)

    async def create_report_template(
        self, template_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new report template"""
        return await self._make_request(
            "POST", "/reports/templates", json=template_data
        )

    async def get_scheduled_reports(
        self, skip: int = 0, limit: int = 100, active_only: bool = False
    ) -> Dict[str, Any]:
        """Get scheduled reports"""
        params = {"skip": skip, "limit": limit, "active_only": active_only}
        return await self._make_request("GET", "/reports/scheduled", params=params)

    async def download_report(self, report_id: int) -> Dict[str, Any]:
        """Download a generated report file"""
        return await self._make_request(
            "GET", f"/reports/download/{report_id}", return_response=True
        )

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

    async def update_discount_rule(
        self, rule_id: int, rule_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing discount rule"""
        return await self._make_request(
            "PUT", f"/discount-rules/{rule_id}", json=rule_data
        )

    async def delete_discount_rule(self, rule_id: int) -> bool:
        """Delete a discount rule"""
        try:
            await self._make_request("DELETE", f"/discount-rules/{rule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete discount rule {rule_id}: {e}")
            return False

    # CRM Methods
    async def create_client_note(
        self, client_id: int, note_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a note for a client"""
        return await self._make_request(
            "POST", f"/crm/clients/{client_id}/notes", json=note_data
        )

    async def list_client_notes(self, client_id: int) -> List[Dict[str, Any]]:
        """List notes for a client"""
        return await self._make_request("GET", f"/crm/clients/{client_id}/notes")

    # Email Methods
    async def send_invoice_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send an invoice via email"""
        return await self._make_request("POST", "/email/send-invoice", json=email_data)

    async def test_email_configuration(self, test_email: str) -> Dict[str, Any]:
        """Test email configuration"""
        return await self._make_request(
            "POST", "/email/test", json={"test_email": test_email}
        )

    # AI Configuration Methods
    async def list_ai_configs(self) -> List[Dict[str, Any]]:
        """List all AI configurations"""
        return await self._make_request("GET", "/ai-config/")

    async def get_ai_config(self, config_id: int) -> Dict[str, Any]:
        """Get a specific AI configuration"""
        return await self._make_request("GET", f"/ai-config/{config_id}")

    async def create_ai_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new AI configuration"""
        return await self._make_request("POST", "/ai-config/", json=config_data)

    async def update_ai_config(
        self, config_id: int, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an AI configuration"""
        return await self._make_request(
            "PUT", f"/ai-config/{config_id}", json=config_data
        )

    async def delete_ai_config(self, config_id: int) -> bool:
        """Delete an AI configuration"""
        try:
            await self._make_request("DELETE", f"/ai-config/{config_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete AI config {config_id}: {e}")
            return False

    async def test_ai_config(
        self, config_id: int, test_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Test an AI configuration"""
        test_data = test_data or {}
        return await self._make_request(
            "POST", f"/ai-config/{config_id}/test", json=test_data
        )

    # Analytics Methods
    async def get_page_views_analytics(
        self, days: int = 7, path_filter: str = None
    ) -> Dict[str, Any]:
        """Get page view analytics"""
        params = {"days": days}
        if path_filter:
            params["path_filter"] = path_filter
        return await self._make_request("GET", "/analytics/page-views", params=params)

    # Audit Log Methods
    async def get_audit_logs(
        self,
        user_id: int = None,
        user_email: str = None,
        action: str = None,
        resource_type: str = None,
        resource_id: str = None,
        status: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get audit logs with optional filters"""
        # Validate pagination parameters
        if offset < 0:
            offset = 0
        if limit < 1:
            limit = 100
        if limit > 10000:  # Prevent excessive load
            limit = 10000

        params = {"limit": limit, "offset": offset}
        if user_id is not None:
            params["user_id"] = user_id
        if user_email:
            params["user_email"] = user_email
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if resource_id:
            params["resource_id"] = resource_id
        if status:
            params["status"] = status
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self._make_request("GET", "/audit-logs", params=params)

    # Notification Methods
    async def get_notification_settings(self) -> Dict[str, Any]:
        """Get current user's notification settings"""
        return await self._make_request("GET", "/notifications/settings")

    async def update_notification_settings(
        self, settings_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update current user's notification settings"""
        return await self._make_request(
            "PUT", "/notifications/settings", json=settings_data
        )

    # PDF Processing Methods
    async def get_ai_status(self) -> Dict[str, Any]:
        """Get AI status for PDF processing"""
        return await self._make_request("GET", "/invoices/ai-status")

    async def process_pdf_upload(
        self, file_path: str, filename: str = None
    ) -> Dict[str, Any]:
        """Upload and process a PDF file"""
        # Validate file path before opening
        from core.utils.file_validation import validate_file_path
        validated_path = validate_file_path(file_path)

        headers = await self.auth_client.get_auth_headers()
        # httpx requires no Content-Type header set for multipart; remove if present
        headers.pop("Content-Type", None)

        with open(validated_path, "rb") as fp:
            files = {
                "file": (
                    filename or os.path.basename(validated_path),
                    fp,
                    "application/pdf",
                )
            }
            resp = await self._client.post(
                url=f"{self.base_url}/invoices/upload-pdf",
                headers=headers,
                files=files,
            )
            resp.raise_for_status()
            return resp.json()

    # Accounting Export Methods
    async def export_accounting_journal(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_drafts: bool = False,
        tax_only: bool = False,
        include_expenses: bool = True,
        include_invoices: bool = True,
        include_payments: bool = True,
    ) -> Dict[str, Any]:
        """Download accounting journal CSV export."""
        params: Dict[str, Any] = {
            "include_drafts": include_drafts,
            "tax_only": tax_only,
            "include_expenses": include_expenses,
            "include_invoices": include_invoices,
            "include_payments": include_payments,
        }
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return await self._download_text_export("/accounting-export/journal", params=params)

    async def export_tax_summary(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_drafts: bool = False,
        include_expenses: bool = True,
        include_invoices: bool = True,
    ) -> Dict[str, Any]:
        """Download tax summary CSV export."""
        params: Dict[str, Any] = {
            "include_drafts": include_drafts,
            "include_expenses": include_expenses,
            "include_invoices": include_invoices,
        }
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return await self._download_text_export("/accounting-export/tax-summary", params=params)

    async def _download_text_export(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Download text-based export (CSV) while preserving filename metadata."""
        try:
            headers = await self.auth_client.get_auth_headers()
            response = await self._client.get(
                url=f"{self.base_url}{endpoint}",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            content_disposition = response.headers.get("content-disposition", "")
            filename = "export.csv"
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=", 1)[1].strip().strip('"')

            content = response.text
            return {
                "filename": filename,
                "content_type": response.headers.get("content-type", "text/csv"),
                "content": content,
                "size": len(content.encode("utf-8")),
            }
        except HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed - check credentials")
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise Exception(
                f"API request failed: {e.response.status_code} - {e.response.text}"
            )
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Request error: {e}")

    # Tenant Methods
    async def get_tenant_info(self) -> Dict[str, Any]:
        """Get current tenant information"""
        return await self._make_request("GET", "/tenants/me")

    async def list_tenants(
        self, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
        """List all tenants (superuser only)"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)

        return await self._make_request(
            "GET",
            "/tenants/",
            params={"skip": skip, "limit": limit}
        )

    async def get_tenant_stats(self, tenant_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific tenant"""
        return await self._make_request(
            "GET", f"/super-admin/tenants/{tenant_id}/stats"
        )

    async def create_tenant(self, tenant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tenant"""
        return await self._make_request(
            "POST", "/super-admin/tenants", json=tenant_data
        )

    async def update_tenant(
        self, tenant_id: int, tenant_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update tenant information"""
        return await self._make_request(
            "PUT", f"/super-admin/tenants/{tenant_id}", json=tenant_data
        )

    async def delete_tenant(self, tenant_id: int) -> bool:
        """Delete a tenant"""
        try:
            await self._make_request("DELETE", f"/super-admin/tenants/{tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            return False

    async def list_tenant_users(
        self, tenant_id: int, skip: int = 0, limit: int = None
    ) -> List[Dict[str, Any]]:
        """List users in a specific tenant"""
        limit = limit or config.DEFAULT_PAGE_SIZE
        limit = min(limit, config.MAX_PAGE_SIZE)

        return await self._make_request(
            "GET",
            f"/super-admin/tenants/{tenant_id}/users",
            params={"skip": skip, "limit": limit}
        )

    async def create_tenant_user(
        self, tenant_id: int, user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a user in a specific tenant"""
        return await self._make_request(
            "POST", f"/super-admin/tenants/{tenant_id}/users", json=user_data
        )

    async def update_tenant_user(
        self, tenant_id: int, user_id: int, user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a user in a specific tenant"""
        return await self._make_request(
            "PUT", f"/super-admin/tenants/{tenant_id}/users/{user_id}", json=user_data
        )

    async def delete_tenant_user(self, tenant_id: int, user_id: int) -> bool:
        """Delete a user from a specific tenant"""
        try:
            await self._make_request(
                "DELETE", f"/super-admin/tenants/{tenant_id}/users/{user_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {user_id} from tenant {tenant_id}: {e}")
            return False

    async def promote_user_to_admin(self, email: str) -> Dict[str, Any]:
        """Promote a user to admin"""
        return await self._make_request(
            "POST", "/super-admin/promote", json={"email": email}
        )

    async def reset_user_password(
        self,
        user_id: int,
        new_password: str,
        confirm_password: str,
        force_reset_on_login: bool = False,
    ) -> Dict[str, Any]:
        """Reset a user's password"""
        data = {
            "new_password": new_password,
            "confirm_password": confirm_password,
            "force_reset_on_login": force_reset_on_login
        }
        return await self._make_request(
            "POST", f"/super-admin/users/{user_id}/reset-password", json=data
        )

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics"""
        return await self._make_request("GET", "/super-admin/system/stats")

    async def export_tenant_data(
        self, tenant_id: int, include_attachments: bool = False
    ) -> Dict[str, Any]:
        """Export tenant data"""
        params = {"include_attachments": include_attachments}
        return await self._make_request(
            "GET", f"/super-admin/tenants/{tenant_id}/export", params=params
        )

    async def import_tenant_data(
        self, tenant_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Import data into a tenant"""
        return await self._make_request(
            "POST", f"/super-admin/tenants/{tenant_id}/import", json=data
        )

    # Statistics and Reporting
    async def get_invoice_stats(self) -> Dict[str, Any]:
        """Get comprehensive invoice statistics"""
        try:
            return await self._make_request("GET", "/invoices/stats/comprehensive")
        except Exception:
            return {"error": "Failed to fetch statistics"}

    async def get_clients_with_outstanding_balance(self) -> List[Dict[str, Any]]:
        """Get clients with outstanding balances"""
        clients = await self.list_clients(limit=config.MAX_PAGE_SIZE)
        return [client for client in clients if client.get("balance", 0) > 0]

    async def get_overdue_invoices(self) -> List[Dict[str, Any]]:
        """Get overdue invoices"""
        invoices = await self.list_invoices(limit=config.MAX_PAGE_SIZE)
        current_date = datetime.now(timezone.utc).date()

        overdue_invoices = []
        for invoice in invoices:
            due_date_str = invoice.get("due_date")
            if due_date_str and invoice.get("status") != "paid":
                try:
                    due_date = datetime.fromisoformat(
                        due_date_str.replace("Z", "+00:00")
                    ).date()
                    if due_date < current_date:
                        overdue_invoices.append(invoice)
                except Exception as e:
                    logger.debug(f"Failed to parse due date for invoice {invoice.get('id')}: {e}")
                    continue

        return overdue_invoices

    # Investment Management Methods
    async def list_portfolios(self, skip: int = 0, limit: int = None) -> Dict[str, Any]:
        """List all investment portfolios"""
        limit = limit or config.DEFAULT_PAGE_SIZE
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

    async def get_portfolio_transactions(self, portfolio_id: int) -> List[Dict[str, Any]]:
        """Get transactions for a specific portfolio."""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/transactions")

    async def get_portfolio_rebalance(self, portfolio_id: int) -> Dict[str, Any]:
        """Get rebalance recommendations for a portfolio."""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/rebalance")

    async def get_portfolio_diversification(self, portfolio_id: int) -> Dict[str, Any]:
        """Get diversification analysis for a specific portfolio."""
        return await self._make_request("GET", f"/investments/portfolios/{portfolio_id}/diversification")

    async def get_cross_portfolio_summary(self) -> Dict[str, Any]:
        """Get cross-portfolio dashboard summary."""
        return await self._make_request("GET", "/investments/cross-portfolio/summary")

    async def get_cross_portfolio_overlap(self) -> Dict[str, Any]:
        """Get overlap analysis across portfolios."""
        return await self._make_request("GET", "/investments/cross-portfolio/overlap-analysis")

    async def get_cross_portfolio_exposure(self) -> Dict[str, Any]:
        """Get concentration/exposure report across portfolios."""
        return await self._make_request("GET", "/investments/cross-portfolio/exposure-report")

    async def get_price_status(self) -> Dict[str, Any]:
        """Get price freshness status across holdings."""
        return await self._make_request("GET", "/investments/holdings/price-status")

    async def update_prices(self) -> Dict[str, Any]:
        """Trigger market price refresh for all tenant holdings."""
        return await self._make_request("POST", "/investments/holdings/update-prices")

    async def close(self):
        """Close the HTTP client and auth client"""
        await self._client.aclose()
        await self.auth_client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
