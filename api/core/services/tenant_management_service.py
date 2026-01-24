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
        self.license_service = LicenseService(tenant_db, master_db=master_db)

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

            # Identify tenants that count against the license limit
            counted_tenants = [t for t in all_tenants if t.count_against_license]

            logger.info(
                f"Enforcing tenant limits: max={max_tenants}, current_total={len(all_tenants)}, current_counted={len(counted_tenants)}"
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
        Handle single tenant limitation by leveraging the reduced limit logic.
        """
        return self._handle_reduced_tenant_limit(super_admin_user, all_tenants, 1)

    def _handle_reduced_tenant_limit(
        self, super_admin_user: MasterUser, all_tenants: List[Tenant], max_tenants: int
    ) -> Dict[str, Any]:
        """
        Handle reduced tenant limits while respecting exemptions.
        """
        try:
            # Categorize tenants
            exempt_tenants = [t for t in all_tenants if not t.count_against_license]
            counted_tenants = [t for t in all_tenants if t.count_against_license]

            # Exempt tenants are always enabled
            for tenant in exempt_tenants:
                tenant.is_enabled = True

            if len(counted_tenants) <= max_tenants:
                # All counted tenants can also be enabled
                for tenant in counted_tenants:
                    tenant.is_enabled = True
                self.master_db.commit()

                return {
                    "success": True,
                    "message": f"All tenants are within the limit ({len(counted_tenants)} counted against {max_tenants} max).",
                    "enabled_tenants": [t.name for t in all_tenants],
                    "disabled_tenants": [],
                    "total_tenants": len(all_tenants),
                    "counted_tenants": len(counted_tenants),
                    "max_tenants": max_tenants,
                }

            # Find super admin's tenant (which is likely a counted tenant)
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

            # Filter counted tenants to exclude super admin's
            other_counted_tenants = [t for t in counted_tenants if t.id != super_admin_tenant.id]

            # Calculate additional slots for other counted tenants
            # If super admin tenant is exempt, they don't take a slot
            reserved_slots = 1 if super_admin_tenant.count_against_license else 0
            additional_slots = max(0, max_tenants - reserved_slots)

            # Preserve currently enabled other counted tenants
            currently_enabled_others = [t for t in other_counted_tenants if t.is_enabled]

            if len(currently_enabled_others) <= additional_slots:
                enabled_other_counted = currently_enabled_others
                disabled_other_counted = []
            else:
                enabled_other_counted = currently_enabled_others[:additional_slots]
                disabled_other_counted = currently_enabled_others[additional_slots:]

            # Update tenant states
            super_admin_tenant.is_enabled = True

            for tenant in other_counted_tenants:
                if tenant in enabled_other_counted:
                    tenant.is_enabled = True
                else:
                    tenant.is_enabled = False

            self.master_db.commit()

            enabled_names = [t.name for t in all_tenants if t.is_enabled]
            disabled_names = [t.name for t in all_tenants if not t.is_enabled]

            logger.info(
                f"Reduced tenant limit enforced: {len(enabled_names)} enabled ({len(exempt_tenants)} exempt), {len(disabled_names)} disabled"
            )

            return {
                "success": True,
                "message": f"Tenant limit of {max_tenants} enforced for counted organizations. Exempt organizations remain enabled.",
                "enabled_tenants": enabled_names,
                "disabled_tenants": disabled_names,
                "total_tenants": len(all_tenants),
                "counted_tenants": len(counted_tenants),
                "max_tenants": max_tenants,
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

            # Find exempt tenants (always included and enabled)
            exempt_tenants = [t for t in all_tenants if not t.count_against_license]

            # Form final selection
            final_selection = list(set(selected_tenants + exempt_tenants))

            # Count only those that count against the license
            counted_selection = [t for t in final_selection if t.count_against_license]

            # Check limit
            if len(counted_selection) > max_tenants:
                return {
                    "success": False,
                    "error": f"Cannot enable {len(counted_selection)} counted tenants. License limit is {max_tenants}.",
                    "message": "Tenant selection exceeds license limit",
                }

            # Handle single tenant case
            if max_tenants == 1:
                # Only super admin's tenant (if counted) and exempt tenants should be enabled
                for tenant in all_tenants:
                    if tenant.count_against_license:
                        tenant.is_enabled = tenant.id == super_admin_tenant.id
                    else:
                        tenant.is_enabled = True
            else:
                # Enable selection (contains both manually selected + all exempt)
                for tenant in all_tenants:
                    tenant.is_enabled = tenant in final_selection

            self.master_db.commit()

            enabled_names = [t.name for t in final_selection]
            disabled_names = [t.name for t in all_tenants if t not in final_selection]

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
