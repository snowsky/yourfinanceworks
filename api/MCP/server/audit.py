"""Analytics, Audit Log, and Notification tool registrations."""
from typing import Optional

from ._shared import mcp, server_context


# Analytics Tools

@mcp.tool()
async def get_page_views_analytics(days: int = 7, path_filter: Optional[str] = None) -> dict:
    """
    Get page view analytics for the current tenant.

    Args:
        days: Number of days to look back (default: 7)
        path_filter: Filter by path (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_page_views_analytics(days=days, path_filter=path_filter)


# Audit Log Tools

@mcp.tool()
async def get_audit_logs(
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    Get audit logs with optional filters for tracking system activities.

    Args:
        user_id: Filter by user ID (optional)
        user_email: Filter by user email (optional)
        action: Filter by action (optional)
        resource_type: Filter by resource type (optional)
        resource_id: Filter by resource ID (optional)
        status: Filter by status (optional)
        start_date: Start date (YYYY-MM-DD) (optional)
        end_date: End date (YYYY-MM-DD) (optional)
        limit: Maximum number of results (default: 100)
        offset: Number of results to skip (default: 0)
    """
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 100
    if limit > 10000:
        limit = 10000

    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_audit_logs(
        user_id=user_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


# Notification Tools

@mcp.tool()
async def get_notification_settings() -> dict:
    """
    Get current user's notification settings.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_notification_settings()


@mcp.tool()
async def update_notification_settings(
    invoice_created: bool = True,
    invoice_paid: bool = True,
    payment_received: bool = True,
    client_created: bool = False,
    overdue_invoice: bool = True,
    email_enabled: bool = True,
) -> dict:
    """
    Update current user's notification settings.

    Args:
        invoice_created: Notify when invoices are created (default: True)
        invoice_paid: Notify when invoices are paid (default: True)
        payment_received: Notify when payments are received (default: True)
        client_created: Notify when clients are created (default: False)
        overdue_invoice: Notify about overdue invoices (default: True)
        email_enabled: Enable email notifications (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_notification_settings(
        invoice_created=invoice_created,
        invoice_paid=invoice_paid,
        payment_received=payment_received,
        client_created=client_created,
        overdue_invoice=overdue_invoice,
        email_enabled=email_enabled,
    )
