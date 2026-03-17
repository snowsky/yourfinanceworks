"""
Reporting-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReportingToolsMixin:
    # Reports Generation
    async def generate_report(self, report_type: str, start_date: str, end_date: str, format: str = "pdf") -> Dict[str, Any]:
        """Generate a business report"""
        if format not in ["pdf", "excel", "csv"]:
            return {"success": False, "error": "Format must be 'pdf', 'excel', or 'csv'"}

        try:
            result = await self.api_client.generate_report(
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                format=format
            )
            return {
                "success": True,
                "data": result,
                "message": f"Report '{report_type}' generated successfully in {format.upper()} format"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to generate report: {e}"}

    async def list_report_templates(self) -> Dict[str, Any]:
        """List available report templates"""
        try:
            response = await self.api_client.list_report_templates()

            # Extract items from paginated response
            templates = self._extract_items_from_response(response, ["items", "data", "templates"])

            return {
                "success": True,
                "data": templates,
                "count": len(templates)
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to list report templates: {e}"}

    async def get_report_history(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Get report generation history"""
        try:
            history = await self.api_client.get_report_history(skip=skip, limit=limit)

            return {
                "success": True,
                "data": history,
                "count": len(history),
                "pagination": {"skip": skip, "limit": limit}
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get report history: {e}"}

    # Enhanced Reports Tools
    async def preview_report(self, report_config: Dict[str, Any]) -> Dict[str, Any]:
        """Preview a report with limited results"""
        if not report_config.get("report_type"):
            return {"success": False, "error": "Report type is required"}

        try:
            result = await self.api_client.preview_report(report_config)
            return {
                "success": True,
                "data": result,
                "message": "Report preview generated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to preview report: {e}"}

    async def create_report_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new report template"""
        required_fields = ["name", "report_type", "description"]
        for field in required_fields:
            if not template_data.get(field):
                return {"success": False, "error": f"Required field missing: {field}"}

        try:
            result = await self.api_client.create_report_template(template_data)
            return {
                "success": True,
                "data": result,
                "message": "Report template created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create report template: {e}"}

    async def get_scheduled_reports(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> Dict[str, Any]:
        """Get scheduled reports"""
        if limit < 1 or limit > 1000:
            return {"success": False, "error": "Limit must be between 1 and 1000"}

        try:
            result = await self.api_client.get_scheduled_reports(skip=skip, limit=limit, active_only=active_only)
            return {
                "success": True,
                "data": result,
                "count": len(result.get("scheduled_reports", [])),
                "pagination": {"skip": skip, "limit": limit, "active_only": active_only}
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get scheduled reports: {e}"}

    async def download_report(self, report_id: int) -> Dict[str, Any]:
        """Download a generated report file"""
        if not report_id or report_id <= 0:
            return {"success": False, "error": "Valid report ID is required"}

        try:
            response = await self.api_client.download_report(report_id)

            # Handle file download response
            content_disposition = response.headers.get("content-disposition", "")
            filename = f"report_{report_id}.pdf"
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[1].strip('"')

            content_type = response.headers.get("content-type", "application/pdf")
            content = await response.aread()

            return {
                "success": True,
                "data": {
                    "content": content,
                    "content_type": content_type,
                    "filename": filename,
                    "size": len(content)
                },
                "message": f"Report '{filename}' downloaded successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to download report: {e}"}

    # Accounting Export Tools
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
        if not any([include_expenses, include_invoices, include_payments]):
            return {
                "success": False,
                "error": "At least one source must be included: expenses, invoices, or payments"
            }

        try:
            result = await self.api_client.export_accounting_journal(
                date_from=date_from,
                date_to=date_to,
                include_drafts=include_drafts,
                tax_only=tax_only,
                include_expenses=include_expenses,
                include_invoices=include_invoices,
                include_payments=include_payments,
            )
            return {
                "success": True,
                "data": result,
                "message": f"Accounting journal export generated: {result['filename']}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to export accounting journal: {e}"}

    async def export_tax_summary(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_drafts: bool = False,
        include_expenses: bool = True,
        include_invoices: bool = True,
    ) -> Dict[str, Any]:
        """Download tax summary CSV export."""
        if not any([include_expenses, include_invoices]):
            return {
                "success": False,
                "error": "At least one source must be included: expenses or invoices"
            }

        try:
            result = await self.api_client.export_tax_summary(
                date_from=date_from,
                date_to=date_to,
                include_drafts=include_drafts,
                include_expenses=include_expenses,
                include_invoices=include_invoices,
            )
            return {
                "success": True,
                "data": result,
                "message": f"Tax summary export generated: {result['filename']}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to export tax summary: {e}"}
