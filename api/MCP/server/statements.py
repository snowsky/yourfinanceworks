"""Statement Management tool registrations.

Covers: statement list/view/update/delete, recycle bin, approval workflow,
report generation, advanced search, and enhanced reports.
"""
from datetime import datetime
from typing import List, Optional

from ._shared import mcp, server_context


# Statement Management Tools

@mcp.tool()
async def list_statements(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    account_name: Optional[str] = None,
    month: Optional[str] = None,
) -> dict:
    """
    List all bank statements with optional filtering and pagination.

    Args:
        skip: Number of statements to skip for pagination (default: 0)
        limit: Maximum number of statements to return (default: 100)
        status: Filter by processing status (e.g., 'processed', 'processing', 'failed')
        account_name: Filter by account name (note: this searches in filename and labels)
        month: Filter by month in format 'YYYY-MM' or 'Month YYYY' (e.g., '2024-01' or 'January 2024')

    Returns:
        Formatted list of bank statements with readable information.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    result = await server_context.tools.list_bank_statements(
        skip=skip, limit=limit, status=status, account_name=account_name
    )

    if result.get("success") and result.get("data"):
        statements = result["data"]

        if month:
            try:
                if "-" in month:  # YYYY-MM format
                    target_month = datetime.strptime(month, "%Y-%m")
                else:  # Month YYYY format
                    target_month = datetime.strptime(month, "%B %Y")

                filtered_statements = []
                for stmt in statements:
                    if stmt.get("created_at"):
                        try:
                            stmt_date = datetime.fromisoformat(
                                stmt["created_at"].replace("Z", "+00:00")
                            )
                            if (
                                stmt_date.year == target_month.year
                                and stmt_date.month == target_month.month
                            ):
                                filtered_statements.append(stmt)
                        except Exception:
                            pass

                statements = filtered_statements
                result["data"] = statements
                result["count"] = len(statements)
            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid month format. Use 'YYYY-MM' or 'Month YYYY' (e.g., '2024-01' or 'January 2024')",
                }

        summary = f"Found {len(statements)} bank statement(s)"
        if month:
            summary += f" for {month}"
        summary += ":\n\n"

        for stmt in statements:
            status_emoji = (
                "✅"
                if stmt.get("status") == "Processed"
                else "🔄" if stmt.get("status") == "Processing" else "❌"
            )
            transaction_info = (
                f"{stmt.get('transaction_count', 'N/A')} transactions"
                if stmt.get("transaction_count") != "N/A"
                else "No transactions extracted"
            )

            summary += f"Statement #{stmt.get('id')}\n"
            summary += f"  🏦 Account: {stmt.get('account_name', 'Unknown')}\n"
            summary += f"  📅 Period: {stmt.get('period', 'N/A')}\n"
            summary += f"  📊 Status: {status_emoji} {stmt.get('status', 'Unknown')}\n"
            summary += f"  📄 Transactions: {transaction_info}\n"
            summary += f"  📅 Imported: {stmt.get('created_at', 'Unknown')[:10] if stmt.get('created_at') else 'Unknown'}\n"
            summary += "\n"

        result["summary"] = summary

    return result


@mcp.tool()
async def get_bank_statement(statement_id: int) -> dict:
    """Get a specific bank statement with all its transactions."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_bank_statement(statement_id=statement_id)


@mcp.tool()
async def reprocess_bank_statement(statement_id: int) -> dict:
    """Reprocess a bank statement to extract transactions again."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.reprocess_bank_statement(statement_id=statement_id)


@mcp.tool()
async def update_bank_statement_meta(
    statement_id: int,
    notes: Optional[str] = None,
    labels: Optional[List[str]] = None,
) -> dict:
    """Update bank statement metadata like notes and labels."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_bank_statement_meta(
        statement_id=statement_id, notes=notes, labels=labels
    )


@mcp.tool()
async def delete_bank_statement(statement_id: int) -> dict:
    """Delete a bank statement and its associated file."""
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_bank_statement(statement_id=statement_id)


# === Recycle Bin Management Tools ===

@mcp.tool()
async def list_deleted_statements(skip: int = 0, limit: int = 100) -> dict:
    """
    List all deleted statements in the recycle bin.

    Args:
        skip: Number of statements to skip for pagination
        limit: Maximum number of statements to return
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_deleted_statements(skip=skip, limit=limit)


@mcp.tool()
async def restore_statement(statement_id: int) -> dict:
    """
    Restore a deleted statement from the recycle bin.

    Args:
        statement_id: ID of the statement to restore
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.restore_statement(statement_id=statement_id)


@mcp.tool()
async def permanently_delete_statement(
    statement_id: int, confirm_permanent: bool = False
) -> dict:
    """
    Permanently delete a statement from the recycle bin.

    Args:
        statement_id: ID of the statement to permanently delete
        confirm_permanent: Confirmation that this is a permanent deletion
    """
    if not confirm_permanent:
        return {
            "success": False,
            "error": "Permanent deletion requires confirmation. Set confirm_permanent=True.",
        }

    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.permanently_delete_statement(statement_id=statement_id)


# === Approval Workflow Tools ===

@mcp.tool()
async def submit_expense_for_approval(expense_id: int, notes: str = None) -> dict:
    """
    Submit an expense for approval workflow.

    Args:
        expense_id: ID of the expense to submit for approval
        notes: Optional notes for the approval request
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.submit_expense_for_approval(expense_id=expense_id, notes=notes)


@mcp.tool()
async def get_pending_approvals(skip: int = 0, limit: int = 100) -> dict:
    """
    Get pending approvals for the current user.

    Args:
        skip: Number of approvals to skip for pagination
        limit: Maximum number of approvals to return
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_pending_approvals(skip=skip, limit=limit)


@mcp.tool()
async def approve_expense(approval_id: int, decision: str, notes: str = None) -> dict:
    """
    Approve or reject an expense in the approval workflow.

    Args:
        approval_id: ID of the approval to process
        decision: Decision must be 'approved' or 'rejected'
        notes: Optional notes explaining the decision
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.approve_expense(
        approval_id=approval_id, decision=decision, notes=notes
    )


@mcp.tool()
async def get_approval_history(
    entity_type: str = None,
    entity_id: int = None,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """
    Get approval history with optional filtering.

    Args:
        entity_type: Filter by entity type (e.g., 'expense')
        entity_id: Filter by specific entity ID
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_approval_history(
        entity_type=entity_type, entity_id=entity_id, skip=skip, limit=limit
    )


# === Reports Generation Tools ===

@mcp.tool()
async def generate_report(
    report_type: str, start_date: str, end_date: str, format: str = "pdf"
) -> dict:
    """
    Generate a business report for a specific date range.

    Args:
        report_type: Type of report to generate (e.g., 'financial_summary', 'invoice_report', 'expense_analysis')
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        format: Output format ('pdf', 'excel', or 'csv')
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.generate_report(
        report_type=report_type, start_date=start_date, end_date=end_date, format=format
    )


@mcp.tool()
async def list_report_templates() -> dict:
    """
    List all available report templates.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_report_templates()


@mcp.tool()
async def get_report_history(skip: int = 0, limit: int = 100) -> dict:
    """
    Get report generation history.

    Args:
        skip: Number of reports to skip for pagination
        limit: Maximum number of reports to return
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_report_history(skip=skip, limit=limit)


# === Advanced Search Tools ===

@mcp.tool()
async def global_search(
    query: str, entity_types: List[str] = None, limit: int = 50
) -> dict:
    """
    Perform global search across all system entities.

    Args:
        query: Search query string (minimum 1 character)
        entity_types: Optional list of entity types to search (invoices, clients, payments, expenses, statements, attachments, inventory, reminders)
        limit: Maximum number of results to return (1-100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.global_search(
        query=query, entity_types=entity_types, limit=limit
    )


@mcp.tool()
async def search_suggestions(query: str, limit: int = 10) -> dict:
    """
    Get search suggestions based on partial query.

    Args:
        query: Partial search query (minimum 1 character)
        limit: Maximum number of suggestions to return (1-20)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.search_suggestions(query=query, limit=limit)


@mcp.tool()
async def reindex_all_data() -> dict:
    """
    Reindex all data for search functionality (admin only).

    This operation rebuilds the search index for all entities in the current tenant.
    May take several minutes for large datasets.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.reindex_all_data()


@mcp.tool()
async def get_search_status() -> dict:
    """
    Get the current status of the search service.

    Returns information about OpenSearch connectivity, health, and fallback availability.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_search_status()


# === Enhanced Reports Tools ===

@mcp.tool()
async def preview_report(report_config: dict) -> dict:
    """
    Preview a report with limited results before generating the full report.

    Args:
        report_config: Report configuration including report_type and filters
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.preview_report(report_config=report_config)


@mcp.tool()
async def create_report_template(template_data: dict) -> dict:
    """
    Create a new report template for future use.

    Args:
        template_data: Template data including name, report_type, and description
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_report_template(template_data=template_data)


@mcp.tool()
async def get_scheduled_reports(
    skip: int = 0, limit: int = 100, active_only: bool = False
) -> dict:
    """
    Get scheduled reports for automated generation.

    Args:
        skip: Number of reports to skip for pagination
        limit: Maximum number of reports to return (1-1000)
        active_only: Filter to only show active scheduled reports
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_scheduled_reports(
        skip=skip, limit=limit, active_only=active_only
    )


@mcp.tool()
async def download_report(report_id: int) -> dict:
    """
    Download a generated report file.

    Args:
        report_id: ID of the report to download
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.download_report(report_id=report_id)
