"""PDF Processing and Accounting Export tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


# PDF Processing Tools

@mcp.tool()
async def get_ai_status() -> dict:
    """
    Get AI status for PDF processing to check if AI is configured and available.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_ai_status()


@mcp.tool()
async def process_pdf_upload(file_path: str, filename: Optional[str] = None) -> dict:
    """
    Upload and process a PDF file using AI for invoice data extraction.

    Args:
        file_path: Path to the PDF file to upload
        filename: Override filename (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.process_pdf_upload(file_path=file_path, filename=filename)


# Accounting Export Tools

@mcp.tool()
async def export_accounting_journal(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_drafts: bool = False,
    tax_only: bool = False,
    include_expenses: bool = True,
    include_invoices: bool = True,
    include_payments: bool = True,
) -> dict:
    """
    Download accountant-ready accounting journal CSV from invoices, expenses, and payments.

    Args:
        date_from: ISO datetime lower bound (inclusive), e.g. 2026-01-01T00:00:00Z
        date_to: ISO datetime upper bound (inclusive), e.g. 2026-01-31T23:59:59Z
        include_drafts: Include draft invoices (default: False)
        tax_only: Include only tax-relevant expenses/invoices/payments (default: False)
        include_expenses: Include expenses (default: True)
        include_invoices: Include invoices (default: True)
        include_payments: Include payments (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.export_accounting_journal(
        date_from=date_from,
        date_to=date_to,
        include_drafts=include_drafts,
        tax_only=tax_only,
        include_expenses=include_expenses,
        include_invoices=include_invoices,
        include_payments=include_payments,
    )


@mcp.tool()
async def export_tax_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_drafts: bool = False,
    include_expenses: bool = True,
    include_invoices: bool = True,
) -> dict:
    """
    Download tax summary CSV grouped by input/output tax rates.

    Args:
        date_from: ISO datetime lower bound (inclusive), e.g. 2026-01-01T00:00:00Z
        date_to: ISO datetime upper bound (inclusive), e.g. 2026-01-31T23:59:59Z
        include_drafts: Include draft invoices (default: False)
        include_expenses: Include expenses (default: True)
        include_invoices: Include invoices (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.export_tax_summary(
        date_from=date_from,
        date_to=date_to,
        include_drafts=include_drafts,
        include_expenses=include_expenses,
        include_invoices=include_invoices,
    )
