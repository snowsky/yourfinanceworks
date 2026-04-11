"""Super Admin tool registrations."""
from typing import Any, Dict, Optional

from ._shared import mcp, server_context


@mcp.tool()
async def get_tenant_stats(tenant_id: int) -> dict:
    """
    Get detailed statistics for a specific tenant including user count, clients, invoices, and payments.

    Args:
        tenant_id: ID of the tenant to get statistics for
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_tenant_stats(tenant_id=tenant_id)


@mcp.tool()
async def create_tenant(
    name: str,
    domain: str,
    company_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    is_active: bool = True,
    max_users: Optional[int] = None,
    subscription_plan: Optional[str] = None,
) -> dict:
    """
    Create a new tenant with the specified configuration.

    Args:
        name: Tenant name
        domain: Tenant domain
        company_name: Company name (optional)
        logo_url: Logo URL (optional)
        is_active: Whether tenant is active (default: True)
        max_users: Maximum number of users (optional)
        subscription_plan: Subscription plan (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_tenant(
        name=name,
        domain=domain,
        company_name=company_name,
        logo_url=logo_url,
        is_active=is_active,
        max_users=max_users,
        subscription_plan=subscription_plan,
    )


@mcp.tool()
async def update_tenant(
    tenant_id: int,
    name: Optional[str] = None,
    domain: Optional[str] = None,
    company_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    is_active: Optional[bool] = None,
    max_users: Optional[int] = None,
    subscription_plan: Optional[str] = None,
) -> dict:
    """
    Update tenant information.

    Args:
        tenant_id: ID of the tenant to update
        name: Tenant name (optional)
        domain: Tenant domain (optional)
        company_name: Company name (optional)
        logo_url: Logo URL (optional)
        is_active: Whether tenant is active (optional)
        max_users: Maximum number of users (optional)
        subscription_plan: Subscription plan (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_tenant(
        tenant_id=tenant_id,
        name=name,
        domain=domain,
        company_name=company_name,
        logo_url=logo_url,
        is_active=is_active,
        max_users=max_users,
        subscription_plan=subscription_plan,
    )


@mcp.tool()
async def delete_tenant(tenant_id: int) -> dict:
    """
    Delete a tenant and all associated data.

    Args:
        tenant_id: ID of the tenant to delete
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_tenant(tenant_id=tenant_id)


@mcp.tool()
async def list_tenant_users(tenant_id: int, skip: int = 0, limit: int = 100) -> dict:
    """
    List all users in a specific tenant.

    Args:
        tenant_id: ID of the tenant
        skip: Number of users to skip for pagination (default: 0)
        limit: Maximum number of users to return (default: 100)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.list_tenant_users(
        tenant_id=tenant_id, skip=skip, limit=limit
    )


@mcp.tool()
async def create_tenant_user(
    tenant_id: int,
    email: str,
    first_name: str,
    last_name: str,
    role: str = "user",
    is_active: bool = True,
) -> dict:
    """
    Create a new user in a specific tenant.

    Args:
        tenant_id: ID of the tenant
        email: User email address
        first_name: User's first name
        last_name: User's last name
        role: User role (default: "user")
        is_active: Whether user is active (default: True)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.create_tenant_user(
        tenant_id=tenant_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=is_active,
    )


@mcp.tool()
async def update_tenant_user(
    tenant_id: int,
    user_id: int,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> dict:
    """
    Update a user in a specific tenant.

    Args:
        tenant_id: ID of the tenant
        user_id: ID of the user to update
        email: User email address (optional)
        first_name: User's first name (optional)
        last_name: User's last name (optional)
        role: User role (optional)
        is_active: Whether user is active (optional)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.update_tenant_user(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=is_active,
    )


@mcp.tool()
async def delete_tenant_user(tenant_id: int, user_id: int) -> dict:
    """
    Delete a user from a specific tenant.

    Args:
        tenant_id: ID of the tenant
        user_id: ID of the user to delete
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.delete_tenant_user(tenant_id=tenant_id, user_id=user_id)


@mcp.tool()
async def promote_user_to_admin(email: str) -> dict:
    """
    Promote a user to admin role.

    Args:
        email: Email address of the user to promote
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.promote_user_to_admin(email=email)


@mcp.tool()
async def reset_user_password(
    user_id: int,
    new_password: str,
    confirm_password: str,
    force_reset_on_login: bool = False,
) -> dict:
    """
    Reset a user's password.

    Args:
        user_id: ID of the user
        new_password: New password
        confirm_password: Confirm new password
        force_reset_on_login: Force password reset on login (default: False)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.reset_user_password(
        user_id=user_id,
        new_password=new_password,
        confirm_password=confirm_password,
        force_reset_on_login=force_reset_on_login,
    )


@mcp.tool()
async def get_system_stats() -> dict:
    """
    Get system-wide statistics across all tenants.
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.get_system_stats()


@mcp.tool()
async def export_tenant_data(tenant_id: int, include_attachments: bool = False) -> dict:
    """
    Export all data for a specific tenant.

    Args:
        tenant_id: ID of the tenant to export
        include_attachments: Include attachments in export (default: False)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.export_tenant_data(
        tenant_id=tenant_id, include_attachments=include_attachments
    )


@mcp.tool()
async def import_tenant_data(tenant_id: int, data: Dict[str, Any]) -> dict:
    """
    Import data into a specific tenant.

    Args:
        tenant_id: ID of the tenant to import into
        data: Data to import (JSON format)
    """
    if server_context.tools is None:
        return {"success": False, "error": "Server not properly initialized"}

    return await server_context.tools.import_tenant_data(tenant_id=tenant_id, data=data)
