"""
Tenant Management Service

This service handles tenant management based on license limits:
- Enforces tenant limits during license changes
- Handles single tenant limitation (only super admin's tenant enabled)
- Manages tenant selection when limits are reduced
- Provides super admin functionality to select enabled tenants
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models import Tenant, MasterUser
from core.models.models_per_tenant import InstallationInfo
from core.services.license_service import LicenseService

logger = logging.getLogger(__name__)


class TenantManagementService:
    """Service for managing tenants based on license limits"""

    def __init__(self, master_db: Session, tenant_db: Session):
        self.master_db = master_db
        self.tenant_db = tenant_db
        self.license_service = LicenseService(tenant_db)

    def enforce_tenant_limits(self, super_admin_user: MasterUser) -> Dict[str, Any]:
        """
        Enforce tenant limits based on current license.

        This method should be called after license activation or changes.

        Args:
            super_admin_user: The super admin user

        Returns:
            Dict with enforcement results
        """
        try:
            max_tenants = self.license_service.get_max_tenants()
            all_tenants = self.master_db.query(Tenant).all()

            logger.info(
                f"Enforcing tenant limits: max={max_tenants}, current={len(all_tenants)}"
            )

            # Handle single tenant limitation
            if max_tenants == 1:
                return self._handle_single_tenant_limit(super_admin_user, all_tenants)

            # Handle reduced tenant limits
            return self._handle_reduced_tenant_limit(
                super_admin_user, all_tenants, max_tenants
            )

        except Exception as e:
            logger.error(f"Failed to enforce tenant limits: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to enforce tenant limits",
            }

    def _handle_single_tenant_limit(
        self, super_admin_user: MasterUser, all_tenants: List[Tenant]
    ) -> Dict[str, Any]:
        """
        Handle single tenant limitation - only super admin's tenant remains enabled.

        Args:
            super_admin_user: The super admin user
            all_tenants: List of all tenants

        Returns:
            Dict with operation results
        """
        try:
            # Find super admin's tenant
            super_admin_tenant = (
                self.master_db.query(Tenant)
                .filter(Tenant.id == super_admin_user.tenant_id)
                .first()
            )

            if not super_admin_tenant:
                return {
                    "success": False,
                    "error": "Super admin tenant not found",
                    "message": "Cannot determine super admin's primary tenant",
                }

            # Disable all tenants except super admin's tenant
            disabled_tenants = []
            for tenant in all_tenants:
                if tenant.id != super_admin_tenant.id:
                    tenant.is_enabled = False
                    disabled_tenants.append(tenant.name)

            # Ensure super admin's tenant is enabled
            super_admin_tenant.is_enabled = True

            self.master_db.commit()

            logger.info(
                f"Single tenant limit enforced: only '{super_admin_tenant.name}' enabled, {len(disabled_tenants)} disabled"
            )

            return {
                "success": True,
                "message": f"Single tenant limit enforced. Only '{super_admin_tenant.name}' is accessible.",
                "enabled_tenants": [super_admin_tenant.name],
                "disabled_tenants": disabled_tenants,
                "total_tenants": len(all_tenants),
                "max_tenants": 1,
            }

        except Exception as e:
            self.master_db.rollback()
            logger.error(f"Failed to handle single tenant limit: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to enforce single tenant limit",
            }

    def _handle_reduced_tenant_limit(
        self, super_admin_user: MasterUser, all_tenants: List[Tenant], max_tenants: int
    ) -> Dict[str, Any]:
        """
        Handle reduced tenant limits - keep super admin's tenant + select random tenants.

        Args:
            super_admin_user: The super admin user
            all_tenants: List of all tenants
            max_tenants: Maximum number of tenants allowed

        Returns:
            Dict with operation results
        """
        try:
            if len(all_tenants) <= max_tenants:
                # All tenants can be enabled
                for tenant in all_tenants:
                    tenant.is_enabled = True
                self.master_db.commit()

                return {
                    "success": True,
                    "message": f"All {len(all_tenants)} tenants are within the limit of {max_tenants}.",
                    "enabled_tenants": [t.name for t in all_tenants],
                    "disabled_tenants": [],
                    "total_tenants": len(all_tenants),
                    "max_tenants": max_tenants,
                }

            # Find super admin's tenant
            super_admin_tenant = (
                self.master_db.query(Tenant)
                .filter(Tenant.id == super_admin_user.tenant_id)
                .first()
            )

            if not super_admin_tenant:
                return {
                    "success": False,
                    "error": "Super admin tenant not found",
                    "message": "Cannot determine super admin's primary tenant",
                }

            # Get other tenants (excluding super admin's tenant)
            other_tenants = [t for t in all_tenants if t.id != super_admin_tenant.id]

            # Calculate how many additional tenants can be enabled
            additional_slots = (
                max_tenants - 1
            )  # Reserve 1 slot for super admin's tenant

            # If there are existing enabled tenants, try to preserve them first
            currently_enabled_others = [t for t in other_tenants if t.is_enabled]

            if len(currently_enabled_others) <= additional_slots:
                # All currently enabled tenants can remain enabled
                enabled_other_tenants = currently_enabled_others
                disabled_other_tenants = []
            else:
                # Need to disable some tenants - select first N enabled tenants
                enabled_other_tenants = currently_enabled_others[:additional_slots]
                disabled_other_tenants = currently_enabled_others[additional_slots:]

            # Update tenant states
            super_admin_tenant.is_enabled = True

            for tenant in other_tenants:
                if tenant in enabled_other_tenants:
                    tenant.is_enabled = True
                else:
                    tenant.is_enabled = False

            self.master_db.commit()

            enabled_names = [super_admin_tenant.name] + [
                t.name for t in enabled_other_tenants
            ]
            disabled_names = [t.name for t in disabled_other_tenants]

            logger.info(
                f"Reduced tenant limit enforced: {len(enabled_names)} enabled, {len(disabled_names)} disabled"
            )

            return {
                "success": True,
                "message": f"Tenant limit of {max_tenants} enforced. Super admin can select which tenants to enable.",
                "enabled_tenants": enabled_names,
                "disabled_tenants": disabled_names,
                "total_tenants": len(all_tenants),
                "max_tenants": max_tenants,
                "super_admin_tenant": super_admin_tenant.name,
            }

        except Exception as e:
            self.master_db.rollback()
            logger.error(f"Failed to handle reduced tenant limit: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to enforce reduced tenant limit",
            }

    def select_enabled_tenants(
        self, super_admin_user: MasterUser, selected_tenant_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Allow super admin to select which tenants to enable (within license limits).

        Args:
            super_admin_user: The super admin user
            selected_tenant_ids: List of tenant IDs to enable

        Returns:
            Dict with operation results
        """
        try:
            max_tenants = self.license_service.get_max_tenants()
            all_tenants = self.master_db.query(Tenant).all()

            # Find super admin's tenant
            super_admin_tenant = (
                self.master_db.query(Tenant)
                .filter(Tenant.id == super_admin_user.tenant_id)
                .first()
            )

            if not super_admin_tenant:
                return {
                    "success": False,
                    "error": "Super admin tenant not found",
                    "message": "Cannot determine super admin's primary tenant",
                }

            # Validate selected tenants exist
            selected_tenants = []
            for tenant_id in selected_tenant_ids:
                tenant = (
                    self.master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
                )
                if not tenant:
                    return {
                        "success": False,
                        "error": f"Tenant with ID {tenant_id} not found",
                        "message": "Invalid tenant selection",
                    }
                selected_tenants.append(tenant)

            # Check if super admin's tenant is included (always include it)
            if super_admin_tenant not in selected_tenants:
                selected_tenants.append(super_admin_tenant)

            # Check limit
            if len(selected_tenants) > max_tenants:
                return {
                    "success": False,
                    "error": f"Cannot enable {len(selected_tenants)} tenants. License limit is {max_tenants}.",
                    "message": "Tenant selection exceeds license limit",
                }

            # Handle single tenant case
            if max_tenants == 1:
                # Only super admin's tenant should be enabled
                for tenant in all_tenants:
                    tenant.is_enabled = tenant.id == super_admin_tenant.id
            else:
                # Enable selected tenants, disable others
                for tenant in all_tenants:
                    tenant.is_enabled = tenant in selected_tenants

            self.master_db.commit()

            enabled_names = [t.name for t in selected_tenants]
            disabled_names = [t.name for t in all_tenants if t not in selected_tenants]

            logger.info(
                f"Super admin {super_admin_user.email} selected {len(enabled_names)} tenants to enable"
            )

            return {
                "success": True,
                "message": f"Successfully enabled {len(enabled_names)} tenants.",
                "enabled_tenants": enabled_names,
                "disabled_tenants": disabled_names,
                "total_tenants": len(all_tenants),
                "max_tenants": max_tenants,
            }

        except Exception as e:
            self.master_db.rollback()
            logger.error(f"Failed to select enabled tenants: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to update tenant selection",
            }

    def get_tenant_status(self) -> Dict[str, Any]:
        """
        Get current tenant status and license information.

        Returns:
            Dict with tenant status information
        """
        try:
            max_tenants = self.license_service.get_max_tenants()
            all_tenants = self.master_db.query(Tenant).all()

            enabled_tenants = [t for t in all_tenants if t.is_enabled]
            disabled_tenants = [t for t in all_tenants if not t.is_enabled]

            return {
                "max_tenants": max_tenants,
                "total_tenants": len(all_tenants),
                "enabled_tenants": len(enabled_tenants),
                "disabled_tenants": len(disabled_tenants),
                "tenant_details": {
                    "enabled": [
                        {
                            "id": t.id,
                            "name": t.name,
                            "subdomain": t.subdomain,
                            "created_at": (
                                t.created_at.isoformat() if t.created_at else None
                            ),
                        }
                        for t in enabled_tenants
                    ],
                    "disabled": [
                        {
                            "id": t.id,
                            "name": t.name,
                            "subdomain": t.subdomain,
                            "created_at": (
                                t.created_at.isoformat() if t.created_at else None
                            ),
                        }
                        for t in disabled_tenants
                    ],
                },
            }

        except Exception as e:
            logger.error(f"Failed to get tenant status: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to retrieve tenant status",
            }
