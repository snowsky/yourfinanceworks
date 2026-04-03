"""
Feature availability and gating mixin.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger(__name__)


class LicenseFeaturesMixin:
    """Mixin providing feature availability checks and gating."""

    def _ensure_utc(self, dt: datetime) -> Optional[datetime]:
        """Helper to ensure a datetime is timezone-aware and in UTC"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _is_tenant_exempted(self) -> bool:
        """Check if current tenant is exempted from global license counting"""
        from core.models.database import get_tenant_context
        curr_tenant_id = get_tenant_context()
        if curr_tenant_id and self.master_db:
            from core.models.models import Tenant
            tenant = self.master_db.query(Tenant).filter(Tenant.id == curr_tenant_id).first()
            if tenant and not tenant.count_against_license:
                return True
        return False

    def get_enabled_features(self) -> List[str]:
        """
        Get list of licensed features.

        Returns:
            List of feature IDs that are enabled
        """
        installation = self._get_or_create_installation()
        enabled_features = ["core"]

        # 1. Check local license status first
        if installation.license_status == "personal":
            # Personal use: only core features
            pass
        elif self.is_trial_active() or self.is_in_grace_period():
            return ["all"]
        elif installation.license_status in ["active", "commercial", "trial"] and (installation.license_key if installation.license_status == "trial" else True):
            # Verify local license isn't expired
            exp_date = installation.license_expires_at
            if exp_date and exp_date.tzinfo is None:
                exp_date = exp_date.replace(tzinfo=timezone.utc)
            if not exp_date or datetime.now(timezone.utc) <= exp_date:
                enabled_features.extend(installation.licensed_features or [])

        # 2. Local license missing or expired - Fallback to Global license
        if len(enabled_features) <= 1:
            global_info = self._get_or_create_global_installation()
            ids_match = installation.installation_id == global_info.installation_id

            if ids_match and global_info.license_status in ["active", "commercial", "trial"] and (global_info.license_key if global_info.license_status == "trial" else True):
                # Verify global license isn't expired
                global_exp = global_info.license_expires_at
                if global_exp and global_exp.tzinfo is None:
                    global_exp = global_exp.replace(tzinfo=timezone.utc)
                if not global_exp or datetime.now(timezone.utc) <= global_exp:
                    enabled_features.extend(global_info.licensed_features or [])

        # 3. Add enabled plugins from TenantPluginSettings (Master DB)
        try:
            from core.models.database import get_tenant_context
            from core.models.models import TenantPluginSettings
            tenant_id = get_tenant_context()

            # Use master_db if available
            if tenant_id and self.master_db:
                settings = self.master_db.query(TenantPluginSettings).filter(
                    TenantPluginSettings.tenant_id == tenant_id
                ).first()
                if settings and settings.enabled_plugins:
                    for plugin_id in settings.enabled_plugins:
                        if plugin_id not in enabled_features:
                            enabled_features.append(plugin_id)
        except Exception as e:
            logger.warning(f"Failed to fetch enabled plugins for feature check: {e}")

        return list(set(enabled_features))

    def get_expired_features(self) -> List[str]:
        """
        Get list of features that were previously licensed but now expired,
        UNLESS they are currently covered by another active license (e.g., Global).
        """
        installation = self._get_or_create_installation()
        global_info = self._get_or_create_global_installation()

        now = datetime.now(timezone.utc)
        enabled = set(self.get_enabled_features())
        expired = set()

        # Check local
        if installation.license_expires_at:
            local_exp = installation.license_expires_at.replace(tzinfo=timezone.utc)
            if now > local_exp:
                for f in (installation.licensed_features or []):
                    if f not in enabled:
                        expired.add(f)

        # Check global
        if global_info.license_expires_at:
            global_exp = global_info.license_expires_at.replace(tzinfo=timezone.utc)
            if now > global_exp:
                for f in (global_info.licensed_features or []):
                    if f not in enabled:
                        expired.add(f)

        return list(expired)

    def has_feature(self, feature_id: str, tier: str = "commercial") -> bool:
        """
        Check if a specific feature is enabled.

        Args:
            feature_id: Feature ID to check (e.g., "ai_invoice", "tax_integration")
            tier: License tier of the feature ("core" or "commercial")

        Returns:
            True if feature is enabled, False otherwise
        """
        enabled_features = self.get_enabled_features()

        # "all" means all features are enabled (trial/grace period)
        if "all" in enabled_features:
            return True

        # If checking for a core feature, it's enabled if "core" is in the list
        if tier == "core":
            return "core" in enabled_features or "all" in enabled_features

        # For commercial features, check specific ID
        return feature_id in enabled_features

    def has_feature_for_gating(self, feature_id: str, tier: str = "commercial") -> bool:
        """
        Check if a specific feature is enabled for API gating purposes.
        This method ignores ALLOW_EXPIRED_LICENSES and checks actual expiration status.
        """
        enabled_features = self.get_enabled_features()

        # If no features enabled, definitely False
        if not enabled_features:
            return False

        # "all" means all features are enabled (trial/grace period)
        if "all" in enabled_features:
            return True

        if tier == "core":
            return "core" in enabled_features

        return feature_id in enabled_features

    def has_feature_read_only(self, feature_id: str, tier: str = "commercial") -> bool:
        """
        Check if a specific feature is enabled for read-only access.
        """
        # Read-only allows access to features that were previously licensed
        # even if they are now expired.
        enabled_features = self.get_enabled_features()
        if feature_id in enabled_features or "all" in enabled_features:
            return True

        expired_features = self.get_expired_features()
        if feature_id in expired_features:
            return True

        if tier == "core":
            return "core" in enabled_features or "core" in expired_features

        return False

    def get_max_tenants(self) -> int:
        """
        Get maximum number of tenants allowed by current license.
        Uses the highest limit between global and local licenses.
        """
        installation = self._get_or_create_installation()
        global_info = self._get_or_create_global_installation()

        # personal or trial: no limit
        if (
            installation.license_status == "personal"
            or self.is_trial_active()
            or self.is_in_grace_period()
        ):
            return 999999

        # commercial: check local first, then global
        local_limit = installation.max_tenants if installation.license_status in ["active", "commercial"] else 0
        global_limit = global_info.max_tenants if global_info.license_status in ["active", "commercial"] else 0

        # Take the maximum allowed across all active licenses
        limit = max(local_limit or 1, global_limit or 1)

        # If no active license, return 1 as base limit
        if installation.license_status not in ["active", "commercial"] and global_info.license_status not in ["active", "commercial"]:
            return 1

        return limit
