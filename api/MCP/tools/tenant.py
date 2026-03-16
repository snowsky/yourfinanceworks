"""
Tenant and super-admin-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GetTenantArgs(BaseModel):
    pass  # No arguments needed for getting tenant info


class GetTenantStatsArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant to get stats for")


class CreateTenantArgs(BaseModel):
    name: str = Field(description="Tenant name")
    domain: str = Field(description="Tenant domain")
    company_name: Optional[str] = Field(default=None, description="Company name")
    logo_url: Optional[str] = Field(default=None, description="Logo URL")
    is_active: bool = Field(default=True, description="Whether tenant is active")
    max_users: Optional[int] = Field(default=None, description="Maximum number of users")
    subscription_plan: Optional[str] = Field(default=None, description="Subscription plan")


class UpdateTenantArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant to update")
    name: Optional[str] = Field(default=None, description="Tenant name")
    domain: Optional[str] = Field(default=None, description="Tenant domain")
    company_name: Optional[str] = Field(default=None, description="Company name")
    logo_url: Optional[str] = Field(default=None, description="Logo URL")
    is_active: Optional[bool] = Field(default=None, description="Whether tenant is active")
    max_users: Optional[int] = Field(default=None, description="Maximum number of users")
    subscription_plan: Optional[str] = Field(default=None, description="Subscription plan")


class ListTenantUsersArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant")
    skip: int = Field(default=0, description="Number of users to skip")
    limit: int = Field(default=100, description="Maximum number of users to return")


class CreateTenantUserArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant")
    email: str = Field(description="User email")
    first_name: str = Field(description="First name")
    last_name: str = Field(description="Last name")
    role: str = Field(default="user", description="User role")
    is_active: bool = Field(default=True, description="Whether user is active")


class UpdateTenantUserArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant")
    user_id: int = Field(description="ID of the user to update")
    email: Optional[str] = Field(default=None, description="User email")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    role: Optional[str] = Field(default=None, description="User role")
    is_active: Optional[bool] = Field(default=None, description="Whether user is active")


class PromoteUserToAdminArgs(BaseModel):
    email: str = Field(description="Email of the user to promote")


class ResetUserPasswordArgs(BaseModel):
    user_id: int = Field(description="ID of the user")
    new_password: str = Field(description="New password")
    confirm_password: str = Field(description="Confirm new password")
    force_reset_on_login: bool = Field(default=False, description="Force password reset on login")


class ExportTenantDataArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant to export")
    include_attachments: bool = Field(default=False, description="Include attachments in export")


class ImportTenantDataArgs(BaseModel):
    tenant_id: int = Field(description="ID of the tenant to import into")
    data: Dict[str, Any] = Field(description="Data to import")


class TenantToolsMixin:
    # Tenant
    async def get_tenant_info(self) -> Dict[str, Any]:
        """Get current tenant information"""
        try:
            tenant = await self.api_client.get_tenant_info()

            return {
                "success": True,
                "data": tenant
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get tenant info: {e}"}

    # Super Admin Tools
    async def get_tenant_stats(self, tenant_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific tenant"""
        try:
            stats = await self.api_client.get_tenant_stats(tenant_id)
            return {
                "success": True,
                "data": stats,
                "message": f"Retrieved stats for tenant {tenant_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get tenant stats: {e}"}

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics"""
        try:
            stats = await self.api_client.get_system_stats()
            return {
                "success": True,
                "data": stats,
                "message": "System statistics retrieved"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get system stats: {e}"}

    async def create_tenant(
        self,
        name: str,
        domain: str,
        company_name: Optional[str] = None,
        logo_url: Optional[str] = None,
        is_active: bool = True,
        max_users: Optional[int] = None,
        subscription_plan: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new tenant"""
        try:
            tenant_data = {
                "name": name,
                "domain": domain,
                "is_active": is_active
            }
            if company_name:
                tenant_data["company_name"] = company_name
            if logo_url:
                tenant_data["logo_url"] = logo_url
            if max_users is not None:
                tenant_data["max_users"] = max_users
            if subscription_plan:
                tenant_data["subscription_plan"] = subscription_plan

            tenant = await self.api_client.create_tenant(tenant_data)
            return {
                "success": True,
                "data": tenant,
                "message": "Tenant created successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create tenant: {e}"}

    async def update_tenant(
        self,
        tenant_id: int,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        logo_url: Optional[str] = None,
        is_active: Optional[bool] = None,
        max_users: Optional[int] = None,
        subscription_plan: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update tenant information"""
        try:
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if domain is not None:
                update_data["domain"] = domain
            if company_name is not None:
                update_data["company_name"] = company_name
            if logo_url is not None:
                update_data["logo_url"] = logo_url
            if is_active is not None:
                update_data["is_active"] = is_active
            if max_users is not None:
                update_data["max_users"] = max_users
            if subscription_plan is not None:
                update_data["subscription_plan"] = subscription_plan

            tenant = await self.api_client.update_tenant(tenant_id, update_data)
            return {
                "success": True,
                "data": tenant,
                "message": f"Tenant {tenant_id} updated successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update tenant: {e}"}

    async def delete_tenant(self, tenant_id: int) -> Dict[str, Any]:
        """Delete a tenant"""
        try:
            success = await self.api_client.delete_tenant(tenant_id)
            if success:
                return {
                    "success": True,
                    "message": f"Tenant {tenant_id} deleted successfully"
                }
            else:
                return {"success": False, "error": "Failed to delete tenant"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete tenant: {e}"}

    async def list_tenant_users(self, tenant_id: int, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List users in a specific tenant"""
        try:
            response = await self.api_client.list_tenant_users(tenant_id, skip=skip, limit=limit)

            # Extract items from paginated response
            users = self._extract_items_from_response(response, ["items", "data", "users"])

            return {
                "success": True,
                "data": users,
                "count": len(users),
                "pagination": {"skip": skip, "limit": limit},
                "message": f"Found {len(users)} users in tenant {tenant_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list tenant users: {e}"}

    async def create_tenant_user(
        self,
        tenant_id: int,
        email: str,
        first_name: str,
        last_name: str,
        role: str = "user",
        is_active: bool = True
    ) -> Dict[str, Any]:
        """Create a user in a specific tenant"""
        try:
            user_data = {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "is_active": is_active
            }

            user = await self.api_client.create_tenant_user(tenant_id, user_data)
            return {
                "success": True,
                "data": user,
                "message": f"User created successfully in tenant {tenant_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create tenant user: {e}"}

    async def update_tenant_user(
        self,
        tenant_id: int,
        user_id: int,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update a user in a specific tenant"""
        try:
            update_data = {}
            if email is not None:
                update_data["email"] = email
            if first_name is not None:
                update_data["first_name"] = first_name
            if last_name is not None:
                update_data["last_name"] = last_name
            if role is not None:
                update_data["role"] = role
            if is_active is not None:
                update_data["is_active"] = is_active

            user = await self.api_client.update_tenant_user(tenant_id, user_id, update_data)
            return {
                "success": True,
                "data": user,
                "message": f"User {user_id} updated successfully in tenant {tenant_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update tenant user: {e}"}

    async def delete_tenant_user(self, tenant_id: int, user_id: int) -> Dict[str, Any]:
        """Delete a user from a specific tenant"""
        try:
            success = await self.api_client.delete_tenant_user(tenant_id, user_id)
            if success:
                return {
                    "success": True,
                    "message": f"User {user_id} deleted successfully from tenant {tenant_id}"
                }
            else:
                return {"success": False, "error": "Failed to delete tenant user"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete tenant user: {e}"}

    async def promote_user_to_admin(self, email: str) -> Dict[str, Any]:
        """Promote a user to admin"""
        try:
            result = await self.api_client.promote_user_to_admin(email)
            return {
                "success": True,
                "data": result,
                "message": f"User {email} promoted to admin successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to promote user to admin: {e}"}

    async def reset_user_password(self, user_id: int, new_password: str, confirm_password: str, force_reset_on_login: bool = False) -> Dict[str, Any]:
        """Reset a user's password"""
        try:
            result = await self.api_client.reset_user_password(user_id, new_password, confirm_password, force_reset_on_login)
            return {
                "success": True,
                "data": result,
                "message": f"Password reset successfully for user {user_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to reset user password: {e}"}

    async def export_tenant_data(self, tenant_id: int, include_attachments: bool = False) -> Dict[str, Any]:
        """Export tenant data"""
        try:
            result = await self.api_client.export_tenant_data(tenant_id, include_attachments)
            return {
                "success": True,
                "data": result,
                "message": f"Tenant {tenant_id} data exported successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to export tenant data: {e}"}

    async def import_tenant_data(self, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Import data into a tenant"""
        try:
            result = await self.api_client.import_tenant_data(tenant_id, data)
            return {
                "success": True,
                "data": result,
                "message": f"Data imported successfully into tenant {tenant_id}"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to import tenant data: {e}"}
