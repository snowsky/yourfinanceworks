"""
License activation, deactivation, trial management, installation ID management,
and status reporting mixin.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from core.models.models_per_tenant import InstallationInfo
from core.models.models import GlobalInstallationInfo, Tenant

from ._shared import TRIAL_DURATION_DAYS, GRACE_PERIOD_DAYS, VALIDATION_CACHE_TTL_HOURS

logger = logging.getLogger(__name__)


class LicenseActivationMixin:
    """Mixin providing trial management, license activation/deactivation, installation ID
    management, and comprehensive status reporting."""

    # ==================== Installation Helpers ====================

    def _get_or_create_global_installation(self) -> GlobalInstallationInfo:
        """Get or create the global installation info in the master database"""
        if not self.master_db:
            # Fallback for when master_db is not provided (should be rare)
            from core.models.database import get_master_db
            try:
                self.master_db = next(get_master_db())
            except Exception as e:
                logger.error(f"Failed to get master_db for global installation: {e}")
                raise RuntimeError("Master database session is required for global licensing operations")

        global_info = self.master_db.query(GlobalInstallationInfo).first()

        if not global_info:
            # Auto-create global installation record
            global_info = GlobalInstallationInfo(
                installation_id=str(uuid.uuid4()),
                license_status="invalid",
            )
            self.master_db.add(global_info)
            self.master_db.commit()
            self.master_db.refresh(global_info)

            # Log system-wide installation creation
            self._log_global_validation(
                action="installation_created",
                status="success",
                installation_id=global_info.installation_id
            )

        return global_info

    def _get_or_create_installation(self) -> InstallationInfo:
        """Get existing installation or create new one synced with global ID"""
        from sqlalchemy.exc import ProgrammingError
        from sqlalchemy import inspect
        inspector = inspect(self.db.get_bind())

        # Get the global installation ID to ensure consistency across all tenants
        global_info = self._get_or_create_global_installation()
        global_id = global_info.installation_id

        # Handle case where table doesn't exist (e.g. Master DB check or uninitialized tenant)
        try:
            if not inspector.has_table(InstallationInfo.__tablename__):
                logger.debug("Using master/missing context for license check (installation_info table missing)")
                # Return a virtual installation object for master-only context
                return InstallationInfo(
                    installation_id=global_id,
                    license_status="invalid",
                    usage_type=None,
                    trial_start_date=None,
                    trial_end_date=None,
                )
        except Exception as e:
            logger.warning(f"Error checking for installation_info table: {e}")
            return InstallationInfo(
                installation_id=global_id,
                license_status="invalid",
            )

        installation = self.db.query(InstallationInfo).first()

        if not installation:
            # Auto-create local installation record synced with global ID
            # NO LONGER AUTO-CREATE TRIAL - only create basic installation record
            installation = InstallationInfo(
                installation_id=global_id,
                original_installation_id=global_id,  # Store original global ID
                license_status="invalid",  # Changed from "trial" to "invalid"
                usage_type=None,
                trial_start_date=None,  # Removed automatic trial creation
                trial_end_date=None,  # Removed automatic trial creation
            )
            self.db.add(installation)
            self.db.commit()
            self.db.refresh(installation)

            # Log local installation creation (no trial)
            self._log_validation(
                installation=installation,
                validation_type="installation_created",
                validation_result="success",
            )
        elif installation.installation_id != global_id and not installation.custom_installation_id:
            # Auto-sync with global ID if no custom ID is set
            # This is critical for cloud deployments where ID is injected via env var
            logger.info(f"Syncing local installation ID from {installation.installation_id} to global ID {global_id}")
            installation.installation_id = global_id
            installation.original_installation_id = global_id
            self.db.commit()
            self.db.refresh(installation)

        return installation

    # ==================== Trial Management ====================

    def select_usage_type(
        self,
        usage_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Select usage type: personal (free) or business (30-day trial).

        Args:
            usage_type: Either "personal" or "business"
            user_id: ID of user making the selection
            ip_address: IP address of request
            user_agent: User agent string

        Returns:
            Dict with selection result
        """
        if usage_type not in ["personal", "business"]:
            return {
                "success": False,
                "message": "Invalid usage type. Must be 'personal' or 'business'",
                "error": "INVALID_USAGE_TYPE",
            }

        installation = self._get_or_create_installation()

        # Check if usage type already selected
        if installation.usage_type is not None:
            return {
                "success": False,
                "message": f"Usage type already selected as '{installation.usage_type}'",
                "error": "ALREADY_SELECTED",
            }

        now = datetime.now(timezone.utc)
        installation.usage_type = usage_type
        installation.usage_type_selected_at = now

        if usage_type == "personal":
            # Personal use: free forever, all features enabled
            installation.license_status = "personal"
            installation.trial_start_date = None
            installation.trial_end_date = None

            self.db.commit()
            self.db.refresh(installation)

            # Log personal use selection
            self._log_validation(
                installation=installation,
                validation_type="usage_type_selected",
                validation_result="success",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "success": True,
                "message": "Personal use selected. All features are available for free.",
                "usage_type": "personal",
                "license_status": "personal",
            }

        else:  # business
            # Business use: requires license activation via JWT - do not auto-create trial
            # Keep license_status as "invalid" until proper license is activated
            self.db.commit()
            self.db.refresh(installation)

            # Log business use selection (no trial created)
            self._log_validation(
                installation=installation,
                validation_type="usage_type_selected",
                validation_result="success",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "success": True,
                "message": "Business use selected. Please activate a license to enable features.",
                "usage_type": "business",
                "license_status": "invalid",
            }

    def get_usage_type_status(self) -> Dict[str, Any]:
        """
        Get usage type selection status.

        Returns:
            Dict with usage type information
        """
        installation = self._get_or_create_installation()

        return {
            "usage_type": installation.usage_type,
            "usage_type_selected": installation.usage_type is not None,
            "usage_type_selected_at": (
                installation.usage_type_selected_at.isoformat()
                if installation.usage_type_selected_at
                else None
            ),
            "license_status": installation.license_status,
        }

    def is_trial_active(self) -> bool:
        """
        Check if 30-day trial is still active.

        Returns:
            True if trial is active, False otherwise
        """
        installation = self._get_or_create_installation()
        now = datetime.now(timezone.utc)

        # If licensed or personal use, trial is not active
        local_exp = self._ensure_utc(installation.license_expires_at)
        if installation.license_status in ["active", "personal", "commercial", "trial"] and (not local_exp or local_exp > now) and (installation.license_key if installation.license_status == "trial" else True):
            return False

        # If global license is active, trial is not active
        global_info = self._get_or_create_global_installation()
        global_exp = self._ensure_utc(global_info.license_expires_at)
        if global_info.license_status in ["active", "commercial", "trial"] and (not global_exp or global_exp > now) and (global_info.license_key if global_info.license_status == "trial" else True):
            return False

        # If no trial dates set, trial is not active
        if not installation.trial_end_date:
            return False

        # Check if trial extension exists
        if installation.trial_extended_until:
            trial_extended = self._ensure_utc(installation.trial_extended_until)
            return now <= trial_extended

        # Check standard trial period
        trial_end = self._ensure_utc(installation.trial_end_date)
        return now <= trial_end

    def get_trial_status(self) -> Dict[str, Any]:
        """
        Get detailed trial status information.

        Returns:
            Dict with trial status:
            {
                "is_trial": bool,
                "trial_active": bool,
                "trial_start_date": datetime,
                "trial_end_date": datetime,
                "days_remaining": int,
                "in_grace_period": bool,
                "grace_period_end": datetime or None
            }
        """
        installation = self._get_or_create_installation()
        now = datetime.now(timezone.utc)

        # If no trial dates, return inactive trial status
        if not installation.trial_end_date:
            return {
                "is_trial": installation.license_status == "trial",
                "trial_active": False,
                "trial_start_date": installation.trial_start_date,
                "trial_end_date": None,
                "days_remaining": 0,
                "in_grace_period": False,
                "grace_period_end": None,
            }

        # Determine effective trial end date
        trial_end = self._ensure_utc(installation.trial_extended_until or installation.trial_end_date)

        # Calculate days remaining
        days_remaining = (trial_end - now).days if now <= trial_end else 0

        # Check if in grace period
        grace_period_end = trial_end + timedelta(days=GRACE_PERIOD_DAYS)
        in_grace_period = trial_end < now <= grace_period_end

        # Trial is only "active" if no better license is in place
        global_info = self._get_or_create_global_installation()
        local_exp = self._ensure_utc(installation.license_expires_at)
        global_exp = self._ensure_utc(global_info.license_expires_at)

        has_local = installation.license_status in ["active", "commercial", "trial"] and (not local_exp or local_exp > now) and (installation.license_key if installation.license_status == "trial" else True)
        has_global = global_info.license_status in ["active", "commercial", "trial"] and (not global_exp or global_exp > now) and (global_info.license_key if global_info.license_status == "trial" else True)
        is_personal = installation.license_status == "personal"

        trial_suppressed = has_local or has_global or is_personal

        return {
            "is_trial": installation.license_status == "trial" and not trial_suppressed,
            "trial_active": (now <= trial_end) and not trial_suppressed,
            "trial_start_date": installation.trial_start_date,
            "trial_end_date": trial_end,
            "days_remaining": max(0, days_remaining) if not trial_suppressed else 0,
            "in_grace_period": in_grace_period and not trial_suppressed,
            "grace_period_end": grace_period_end if (in_grace_period and not trial_suppressed) else None,
        }

    def is_in_grace_period(self) -> bool:
        """
        Check if installation is in grace period (7 days after trial expiration).

        Returns:
            True if in grace period, False otherwise
        """
        trial_status = self.get_trial_status()
        return trial_status["in_grace_period"]

    # ==================== License Activation ====================

    def activate_license(
        self,
        license_key: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Activate a license key and save to database.

        Args:
            license_key: JWT license key to activate
            user_id: ID of user activating the license
            ip_address: IP address of activation request
            user_agent: User agent string

        Returns:
            Dict with activation result:
            {
                "success": bool,
                "message": str,
                "features": list or None,
                "expires_at": datetime or None,
                "error": str or None
            }
        """
        # Verify license
        verification = self.verify_license(license_key)

        installation = self._get_or_create_installation()

        if not verification["valid"]:
            # Log failed activation
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code=verification["error_code"],
                error_message=verification["error"],
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "success": False,
                "message": verification["error"],
                "features": None,
                "expires_at": None,
                "error": verification["error"],
            }

        # Extract and Validate license information
        payload = verification["payload"]

        # Verify required fields for activation
        required_fields = ["customer_email", "features"]
        missing_fields = [f for f in required_fields if f not in payload]
        if missing_fields:
            error_msg = f"License is missing required fields: {', '.join(missing_fields)}"
            logger.warning(f"Activation Failed: {error_msg}")
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code="MISSING_FIELDS",
                error_message=f"License is missing required fields: {', '.join(missing_fields)}",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return {
                "success": False,
                "message": f"License is missing required fields: {', '.join(missing_fields)}",
                "features": None,
                "expires_at": None,
                "error": "MISSING_FIELDS",
            }

        features = payload.get("features", [])
        exp_timestamp = payload.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            if exp_timestamp
            else None
        )

        # BLOCK GLOBAL LICENSE AS LOCAL
        license_scope = payload.get("license_scope") or payload.get("metadata", {}).get("license_scope")
        if license_scope == "global":
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code="SCOPE_MISMATCH",
                error_message="A global system license cannot be activated as a local organization license.",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return {
                "success": False,
                "message": "Global system licenses cannot be used locally. Please use a tenant-specific license.",
                "features": None,
                "expires_at": None,
                "error": "SCOPE_MISMATCH",
            }

        # Extract max_tenants if available
        max_tenants = payload.get("max_tenants")
        if max_tenants is None:
            # Check in metadata for backward compatibility or nested structure
            metadata = payload.get("metadata", {})
            max_tenants = metadata.get("max_tenants")

        # Ensure max_tenants is an integer if present
        if max_tenants is not None:
            try:
                max_tenants = int(max_tenants)
            except (ValueError, TypeError):
                max_tenants = None

        # Verify installation ID matches
        license_installation_id = payload.get("installation_id")
        if not license_installation_id:
            # Check if installation_id is in metadata (for backward compatibility)
            metadata = payload.get("metadata", {})
            license_installation_id = metadata.get("installation_id")

        if not license_installation_id:
            logger.warning("Activation Failed: MISSING_INSTALLATION_ID")
            # Log failed activation - missing installation ID
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code="MISSING_INSTALLATION_ID",
                error_message="License is missing installation_id field",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "success": False,
                "message": "License is missing installation identifier",
                "features": None,
                "expires_at": None,
                "error": "MISSING_INSTALLATION_ID",
            }

        if license_installation_id != installation.installation_id:
            # Log failed activation - installation ID mismatch
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code="INSTALLATION_ID_MISMATCH",
                error_message=f"License installation_id '{license_installation_id}' does not match current installation '{installation.installation_id}'",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "success": False,
                "message": "This license is not valid for this installation",
                "features": None,
                "expires_at": None,
                "error": "INSTALLATION_ID_MISMATCH",
            }

        # Update installation record
        now = datetime.now(timezone.utc)
        installation.license_key = license_key
        installation.license_activated_at = now
        installation.license_expires_at = expires_at
        installation.license_status = payload.get("license_type", "active")
        installation.is_licensed = True
        installation.licensed_features = features
        installation.customer_name = payload.get("customer_name")
        installation.organization_name = payload.get("organization_name")
        installation.max_tenants = max_tenants
        installation.license_scope = license_scope

        # If usage type not set, set it to business (since they're activating a paid license)
        if not installation.usage_type:
            installation.usage_type = "business"
            installation.usage_type_selected_at = now

        # Update validation cache
        installation.last_validation_at = now
        installation.last_validation_result = True
        installation.validation_cache_expires_at = now + timedelta(
            hours=VALIDATION_CACHE_TTL_HOURS
        )

        self.db.commit()
        self.db.refresh(installation)

        # Enforce tenant limits based on new license
        try:
            from core.models.database import get_master_db
            from core.models.models import MasterUser
            from core.services.tenant_management_service import TenantManagementService

            # Get master database session
            master_db = next(get_master_db())

            # Find super admin user
            super_admin = (
                master_db.query(MasterUser)
                .filter(MasterUser.is_superuser == True)
                .first()
            )

            if super_admin:
                # Create tenant management service and enforce limits
                tenant_service = TenantManagementService(master_db, self.db)
                enforcement_result = tenant_service.enforce_tenant_limits(super_admin)

                if enforcement_result["success"]:
                    logger.info(
                        f"Tenant limits enforced after license activation: {enforcement_result['message']}"
                    )
                else:
                    logger.warning(
                        f"Failed to enforce tenant limits: {enforcement_result.get('error', 'Unknown error')}"
                    )
            else:
                logger.warning("No super admin found - cannot enforce tenant limits")

            master_db.close()

        except Exception as e:
            logger.error(
                f"Failed to enforce tenant limits after license activation: {e}"
            )
            # Don't fail the license activation if tenant enforcement fails

        # Log successful activation
        self._log_validation(
            installation=installation,
            validation_type="activation",
            validation_result="success",
            license_key=license_key,
            features=features,
            expiration_date=expires_at,
            max_tenants=max_tenants,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "success": True,
            "message": "License activated successfully",
            "features": features,
            "expires_at": expires_at,
            "error": None,
        }

    def deactivate_license(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deactivate the current license and revert to trial.

        Args:
            user_id: ID of user deactivating the license
            ip_address: IP address of deactivation request
            user_agent: User agent string

        Returns:
            Dict with deactivation result:
            {
                "success": bool,
                "message": str
            }
        """
        installation = self._get_or_create_installation()

        # Store old license key for logging
        old_license_key = installation.license_key

        # Clear license information
        installation.license_key = None
        installation.license_activated_at = None
        installation.license_expires_at = None
        installation.license_status = "trial"
        installation.is_licensed = False
        installation.licensed_features = None
        installation.customer_email = None
        installation.customer_name = None
        installation.organization_name = None

        # Clear validation cache
        installation.last_validation_at = None
        installation.last_validation_result = None
        installation.validation_cache_expires_at = None

        self.db.commit()

        # Log deactivation
        self._log_validation(
            installation=installation,
            validation_type="deactivation",
            validation_result="success",
            license_key=old_license_key,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"success": True, "message": "License deactivated successfully"}

    def activate_global_license(
        self,
        license_key: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Activate a license key system-wide (stored in master database).
        This makes the license available to all current and future tenants.
        """
        verification = self.verify_license(license_key)
        global_info = self._get_or_create_global_installation()

        if not verification["valid"]:
            self._log_global_validation(
                action="activate_global",
                status="failed",
                installation_id=global_info.installation_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=verification["error"],
                details={"error_code": verification["error_code"]}
            )
            return {
                "success": False,
                "message": verification["error"],
                "error": verification["error_code"]
            }

        payload = verification["payload"]

        # Extract installation ID first (needed for scope check)
        license_installation_id = payload.get("installation_id") or payload.get("metadata", {}).get("installation_id")

        # CHECK LICENSE SCOPE FOR GLOBAL ACTIVATION
        license_scope = payload.get("license_scope") or payload.get("metadata", {}).get("license_scope")

        # Allow activation if:
        # 1. Explicitly global scope, OR
        # 2. No scope specified (treat as global for backward compatibility), OR
        # 3. Scope is "system" (alternative global scope), OR
        # 4. Scope is "local" but installation ID matches (for system-wide deployment)
        if license_scope and license_scope not in ["global", "system"] and not (
            license_scope == "local" and license_installation_id == global_info.installation_id
        ):
            self._log_global_validation(
                action="activate_global",
                status="failed",
                installation_id=global_info.installation_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="Only global licenses can be activated system-wide.",
                details={"error_code": "SCOPE_MISMATCH"}
            )
            return {
                "success": False,
                "message": "Only global system licenses can be activated globally.",
                "error": "SCOPE_MISMATCH"
            }

        if not license_installation_id:
            return {"success": False, "message": "License missing installation ID", "error": "MISSING_ID"}

        if license_installation_id != global_info.installation_id:
            return {
                "success": False,
                "message": "License not valid for this system installation",
                "error": "ID_MISMATCH"
            }

        # Update global record
        now = datetime.now(timezone.utc)
        global_info.license_key = license_key
        global_info.license_activated_at = now
        global_info.license_status = payload.get("license_type", "active")
        global_info.is_licensed = True
        global_info.licensed_features = payload.get("features", [])
        global_info.customer_name = payload.get("customer_name")
        global_info.organization_name = payload.get("organization_name")
        global_info.license_scope = license_scope

        expires_at = payload.get("exp")
        if expires_at:
            global_info.license_expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)

        max_tenants = payload.get("max_tenants") or payload.get("metadata", {}).get("max_tenants")
        if max_tenants:
            try:
                global_info.max_tenants = int(max_tenants)
            except Exception:
                pass

        max_users = payload.get("max_users") or payload.get("metadata", {}).get("max_users")
        if max_users:
            try:
                global_info.max_users = int(max_users)
            except Exception:
                pass

        self.master_db.commit()

        # Log success
        self._log_global_validation(
            action="activate_global",
            status="success",
            installation_id=global_info.installation_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "success": True,
            "message": "Global license activated successfully",
            "expires_at": global_info.license_expires_at
        }

    def deactivate_global_license(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Remove the global license from the master database."""
        global_info = self._get_or_create_global_installation()
        old_key = global_info.license_key

        global_info.license_key = None
        global_info.license_activated_at = None
        global_info.license_status = "invalid"
        global_info.is_licensed = False
        global_info.license_expires_at = None
        global_info.licensed_features = None

        self.master_db.commit()

        self._log_global_validation(
            action="deactivate_global",
            status="success",
            installation_id=global_info.installation_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"old_key_hash": self._get_license_key_hash(old_key) if old_key else None}
        )

        return {"success": True, "message": "Global license deactivated"}

    # ==================== Installation ID Management ====================

    def regenerate_installation_id(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Regenerate the installation ID for a tenant.
        This enables extracting a tenant from the global license system.
        Allowed only ONCE per tenant.
        """
        installation = self._get_or_create_installation()

        # Check if already regenerated
        if installation.custom_installation_id:
            return {
                "success": False,
                "message": "Installation ID has already been regenerated. This action can only be performed once.",
                "error": "ALREADY_REGENERATED"
            }

        new_id = str(uuid.uuid4())

        # Save current ID as original if not already saved
        if not installation.original_installation_id:
            from core.models.models import GlobalInstallationInfo
            global_info = self.master_db.query(GlobalInstallationInfo).first()
            installation.original_installation_id = global_info.installation_id if global_info else installation.installation_id

        # Update IDs
        old_id = installation.installation_id
        installation.custom_installation_id = new_id
        installation.installation_id = new_id

        # Reset license status as the old license is no longer valid for this new ID
        installation.license_status = "invalid"  # Changed from "trial" to "invalid"
        installation.is_licensed = False
        installation.license_key = None
        installation.license_activated_at = None
        installation.license_expires_at = None
        installation.licensed_features = None

        self.db.commit()
        self.db.refresh(installation)

        # Log change
        self._log_validation(
            installation=installation,
            validation_type="regenerate_id",
            validation_result="success",
            details={"old_id": old_id, "new_id": new_id},
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "success": True,
            "message": "Transportation ID regenerated successfully. Please active a new license.",
            "installation_id": new_id
        }

    def update_installation_id(
        self,
        new_installation_id: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the installation ID for a tenant to a specific value.

        This allows setting a custom installation ID for license management.
        Unlike regenerate_installation_id, this can be done multiple times
        but requires admin privileges.
        """
        installation = self._get_or_create_installation()

        # Validate UUID format (already validated in router, but double-check)
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
        if not uuid_pattern.match(new_installation_id):
            return {
                "success": False,
                "message": "Invalid UUID format. Expected format: 123e4567-e89b-12d3-a456-426614174000"
            }

        # Check if the new ID is the same as current
        if installation.installation_id == new_installation_id:
            return {
                "success": False,
                "message": "New installation ID is the same as the current one."
            }

        old_id = installation.installation_id

        # Save current ID as original if not already saved and this is the first custom ID
        if not installation.original_installation_id and not installation.custom_installation_id:
            from core.models.models import GlobalInstallationInfo
            global_info = self.master_db.query(GlobalInstallationInfo).first()
            installation.original_installation_id = global_info.installation_id if global_info else installation.installation_id

        # Update installation ID
        installation.custom_installation_id = new_installation_id
        installation.installation_id = new_installation_id

        # Reset license status as the old license is no longer valid for this new ID
        installation.license_status = "invalid"  # Changed from "trial" to "invalid"
        installation.is_licensed = False
        installation.license_key = None
        installation.license_activated_at = None
        installation.license_expires_at = None
        installation.licensed_features = None

        self.db.commit()
        self.db.refresh(installation)

        # Log change
        self._log_validation(
            installation=installation,
            validation_type="update_id",
            validation_result="success",
            details={"old_id": old_id, "new_id": new_installation_id},
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "success": True,
            "message": "Installation ID updated successfully. Please activate a new license.",
            "old_installation_id": old_id,
            "installation_id": new_installation_id
        }

    def switch_license_mode(
        self,
        mode: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Switch between 'global' and 'local' license modes.
        global: uses the system-wide installation ID
        local: uses the custom designated installation ID (if exists)
        """
        if mode not in ["global", "local"]:
            return {"success": False, "message": "Invalid mode. Must be 'global' or 'local'."}

        installation = self._get_or_create_installation()
        global_info = self._get_or_create_global_installation()

        target_id = None
        if mode == "global":
            target_id = global_info.installation_id
        else:  # local
            if not installation.custom_installation_id:
                return {
                    "success": False,
                    "message": "No custom installation ID found. Please regenerate ID first.",
                    "error": "NO_CUSTOM_ID"
                }
            target_id = installation.custom_installation_id

        if installation.installation_id == target_id:
            return {"success": True, "message": f"Already in {mode} mode"}

        # Perform switch
        old_id = installation.installation_id
        installation.installation_id = target_id

        # Reset license status on switch to ensure validity check happens against new ID
        installation.license_status = "invalid"  # Changed from "trial" to "invalid"
        installation.is_licensed = False
        installation.license_key = None
        installation.licensed_features = None

        self.db.commit()

        self._log_validation(
            installation=installation,
            validation_type="switch_mode",
            validation_result="success",
            details={"mode": mode, "old_id": old_id, "new_id": target_id},
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {"success": True, "message": f"Switched to {mode} license mode"}

    # ==================== Status Information ====================

    def is_license_expired(self) -> bool:
        """
        Check if any previously active license (local or global) has expired,
        and no license is currently active.
        """
        installation = self._get_or_create_installation()
        global_info = self._get_or_create_global_installation()
        now = datetime.now(timezone.utc)

        # 1. Determine if any license is CURRENTLY active
        # Local active check
        local_exp = self._ensure_utc(installation.license_expires_at)
        local_active = (installation.license_status in ["active", "commercial", "trial"] and (installation.license_key if installation.license_status == "trial" else True)) and (not local_exp or local_exp > now)

        # Global active check - ONLY if IDs match
        ids_match = installation.installation_id == global_info.installation_id

        global_exp = self._ensure_utc(global_info.license_expires_at)
        global_active = (
            ids_match
            and global_info.license_status in ["active", "commercial", "trial"]
            and (global_info.license_key if global_info.license_status == "trial" else True)
            and (not global_exp or global_exp > now)
        )

        if local_active or global_active:
            return False

        # 2. Check if any was previously active but now expired
        if local_exp and now > local_exp:
            return True

        # Global expired check - only if we are still attached to global
        if ids_match and global_exp and now > global_exp:
            return True

        return False

    def get_license_status(self) -> Dict[str, Any]:
        """
        Get comprehensive license status information including global fallback.
        """
        installation = self._get_or_create_installation()
        global_info = self._get_or_create_global_installation()
        trial_status = self.get_trial_status()
        enabled_features = self.get_enabled_features()

        is_expired = self.is_license_expired()

        # Determine effective source and status
        local_exp = self._ensure_utc(installation.license_expires_at)
        global_exp = self._ensure_utc(global_info.license_expires_at)
        now = datetime.now(timezone.utc)

        local_active = installation.license_status in ["active", "commercial", "trial"] and (installation.license_key if installation.license_status == "trial" else True) and (not local_exp or local_exp > now)

        # Global active only if IDs match
        ids_match = installation.installation_id == global_info.installation_id
        global_active = (
            ids_match
            and global_info.license_status in ["active", "commercial", "trial"]
            and (global_info.license_key if global_info.license_status == "trial" else True)
            and (not global_exp or global_exp > now)
        )

        effective_source = "local" if local_active else "global" if global_active else "none"

        # Determine effective status string
        effective_status = installation.license_status
        if effective_source == "global":
            effective_status = global_info.license_status
        elif effective_source == "none":
            if local_exp and now > local_exp:
                effective_status = "expired"
            elif ids_match and global_exp and now > global_exp:
                effective_status = "expired"

        return {
            "installation_id": installation.installation_id,
            "license_status": effective_status,
            "usage_type": installation.usage_type,
            "usage_type_selected": installation.usage_type is not None,
            "is_licensed": effective_source != "none",
            "is_personal": effective_status == "personal",
            "is_trial": effective_status == "trial",
            "license_type": effective_status,
            "is_license_expired": is_expired,
            "effective_source": effective_source,
            "license_scope": installation.license_scope if effective_source == "local" else global_info.license_scope if effective_source == "global" else None,
            "is_exempt_from_global_license": self._is_tenant_exempted(),
            "custom_installation_id": installation.custom_installation_id,
            "original_installation_id": installation.original_installation_id,
            "trial_info": trial_status,
            "license_info": {
                "activated_at": installation.license_activated_at,
                "expires_at": installation.license_expires_at,
                "customer_email": installation.customer_email,
                "customer_name": installation.customer_name,
                "organization_name": installation.organization_name,
                "max_tenants": installation.max_tenants or 1,
                "license_scope": installation.license_scope,
            } if local_active else None,
            "global_license_info": {
                "activated_at": global_info.license_activated_at,
                "expires_at": global_info.license_expires_at,
                "customer_email": global_info.customer_email,
                "customer_name": global_info.customer_name,
                "organization_name": global_info.organization_name,
                "max_tenants": global_info.max_tenants or 1,
                "license_scope": global_info.license_scope,
            } if global_info.license_status in ["active", "commercial", "trial"] and global_info.is_licensed else None,
            "enabled_features": enabled_features,
            "expired_features": self.get_expired_features(),
            "has_all_features": "all" in enabled_features,
            "allow_password_signup": global_info.allow_password_signup,
            "allow_sso_signup": global_info.allow_sso_signup,
            "user_licensing_info": {
                "max_users": global_info.max_users,
                "current_users_count": self.get_current_user_count(),
            } if global_info.is_licensed else None,
        }

    def get_current_user_count(self) -> int:
        """
        Get the number of users that count against the global license.
        A user counts if both they and their tenant are NOT exempted.
        """
        if not self.master_db:
            return 0
        from core.models.models import MasterUser, Tenant
        return (
            self.master_db.query(MasterUser)
            .join(Tenant, MasterUser.tenant_id == Tenant.id)
            .filter(MasterUser.count_against_license == True)
            .filter(Tenant.count_against_license == True)
            .count()
        )

    def get_all_tenants_license_info(self) -> List[Dict[str, Any]]:
        """
        Super Admin Monitoring: Get license usage across all tenants.
        """
        if not self.master_db:
            return []

        tenants = self.master_db.query(Tenant).all()
        self._get_or_create_global_installation()

        results = []
        for tenant in tenants:
            # Note: We can't easily query the tenant's local InstallationInfo from here
            # without switching DB sessions for EVERY tenant, which is slow.
            # For monitoring, we'll mostly rely on the Tenant model flags.
            results.append({
                "id": tenant.id,
                "name": tenant.name,
                "is_active": tenant.is_active,
                "is_enabled": tenant.is_enabled,
                "count_against_license": tenant.count_against_license,
                # In a real impl, we'd cache the 'effective_source' in the Tenant model
                # for faster monitoring access.
            })

        return results

    def update_tenant_capacity_control(self, tenant_id: int, counts: bool) -> bool:
        """
        Update whether a tenant counts against the global license capacity.
        """
        if not self.master_db:
            return False

        tenant = self.master_db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return False

        tenant.count_against_license = counts
        self.master_db.commit()
        return True

    def get_all_users_license_info(self) -> List[Dict[str, Any]]:
        """
        Super Admin Monitoring: Get license usage across all users.
        """
        if not self.master_db:
            return []
        from core.models.models import MasterUser, Tenant

        # Use a join to get tenant information in one query
        users_with_tenants = self.master_db.query(MasterUser, Tenant).join(Tenant, MasterUser.tenant_id == Tenant.id).all()

        results = []
        for user, tenant in users_with_tenants:
            results.append({
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "count_against_license": user.count_against_license,
                "tenant_name": tenant.name,
                "tenant_count_against_license": tenant.count_against_license,
                "effectively_exempt": not (user.count_against_license and tenant.count_against_license)
            })
        return results

    def update_user_capacity_control(self, user_id: int, counts: bool) -> bool:
        """
        Update whether a user counts against the global license capacity.
        """
        if not self.master_db:
            return False
        from core.models.models import MasterUser
        user = self.master_db.query(MasterUser).filter(MasterUser.id == user_id).first()
        if not user:
            return False
        user.count_against_license = counts
        self.master_db.commit()
        return True

    def update_global_signup_settings(
        self,
        allow_password: Optional[bool] = None,
        allow_sso: Optional[bool] = None,
        max_tenants: Optional[int] = None,
        max_users: Optional[int] = None,
    ) -> bool:
        """
        Update global signup controls and capacity limits.
        """
        global_info = self._get_or_create_global_installation()

        updated = False
        if allow_password is not None:
            global_info.allow_password_signup = allow_password
            updated = True
        if allow_sso is not None:
            global_info.allow_sso_signup = allow_sso
            updated = True
        if max_tenants is not None:
            global_info.max_tenants = max_tenants
            updated = True
        if max_users is not None:
            global_info.max_users = max_users
            updated = True

        if updated:
            self.master_db.commit()
            return True
        return False
