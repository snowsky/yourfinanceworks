"""
License verification and validation logging mixin.
"""

import jwt
import hashlib
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from core.models.models_per_tenant import InstallationInfo, LicenseValidationLog
from core.models.models import GlobalLicenseValidationLog

from ._shared import DEFAULT_KEY_ID, PUBLIC_KEYS

logger = logging.getLogger(__name__)


class LicenseValidationMixin:
    """Mixin providing license verification and validation logging."""

    def verify_license(self, license_key: str) -> Dict[str, Any]:
        """
        Verify a license key using JWT signature verification.
        Supports multiple public keys for key rotation.

        Args:
            license_key: JWT license key to verify

        Returns:
            Dict with verification result:
            {
                "valid": bool,
                "payload": dict or None,
                "error": str or None,
                "error_code": str or None
            }
        """
        # First, decode without verification to get the key ID
        try:
            unverified_payload = jwt.decode(
                license_key, options={"verify_signature": False}
            )
            key_id = unverified_payload.get("kid", DEFAULT_KEY_ID)
        except Exception:
            # If we can't decode at all, try with default key
            key_id = DEFAULT_KEY_ID

        # Get the appropriate public key
        public_key = PUBLIC_KEYS.get(key_id)
        if not public_key:
            return {
                "valid": False,
                "payload": None,
                "error": f"Unknown key ID: {key_id}. This license may be from an unsupported version.",
                "error_code": "UNKNOWN_KEY_ID",
            }

        try:
            # Check if we should allow expired licenses for testing
            allow_expired = (
                os.getenv("ALLOW_EXPIRED_LICENSES", "false").lower() == "true"
            )

            # Decode and verify JWT signature with the correct key
            if allow_expired:
                # For testing: decode without expiration verification, then check manually
                payload = jwt.decode(
                    license_key,
                    public_key,
                    algorithms=["RS256"],
                    options={
                        "verify_exp": False
                    },  # Don't verify expiration automatically
                )

                # Manual expiration check with warning
                exp_timestamp = payload.get("exp")
                if exp_timestamp:
                    exp_date = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    if datetime.now(timezone.utc) > exp_date:
                        import warnings

                        warnings.warn(
                            "Expired license being activated (ALLOW_EXPIRED_LICENSES=true)",
                            UserWarning,
                        )
            else:
                # Normal verification with automatic expiration checking
                payload = jwt.decode(license_key, public_key, algorithms=["RS256"])

            return {
                "valid": True,
                "payload": payload,
                "error": None,
                "error_code": None,
            }

        except jwt.ExpiredSignatureError:
            # Check if we should allow expired licenses for testing
            allow_expired = (
                os.getenv("ALLOW_EXPIRED_LICENSES", "false").lower() == "true"
            )

            if allow_expired:
                # For testing: decode without verification to get the payload
                try:
                    payload = jwt.decode(
                        license_key,
                        options={"verify_signature": False, "verify_exp": False},
                    )
                    import warnings

                    warnings.warn(
                        "Expired license being activated (ALLOW_EXPIRED_LICENSES=true)",
                        UserWarning,
                    )
                    return {
                        "valid": True,
                        "payload": payload,
                        "error": None,
                        "error_code": None,
                    }
                except Exception:
                    pass

            return {
                "valid": False,
                "payload": None,
                "error": "License signature has expired",
                "error_code": "EXPIRED",
            }
        except jwt.InvalidSignatureError:
            return {
                "valid": False,
                "payload": None,
                "error": "Invalid license signature",
                "error_code": "INVALID_SIGNATURE",
            }
        except jwt.DecodeError:
            return {
                "valid": False,
                "payload": None,
                "error": "Malformed license key",
                "error_code": "MALFORMED",
            }
        except Exception as e:
            return {
                "valid": False,
                "payload": None,
                "error": f"License verification failed: {str(e)}",
                "error_code": "VERIFICATION_ERROR",
            }

    def _get_license_key_hash(self, license_key: str) -> str:
        """Generate SHA-256 hash of license key for logging"""
        return hashlib.sha256(license_key.encode()).hexdigest()

    def _log_validation(
        self,
        installation: InstallationInfo,
        validation_type: str,
        validation_result: str,
        license_key: Optional[str] = None,
        features: Optional[List[str]] = None,
        expiration_date: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        max_tenants: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs  # Accept extra arguments like 'details' without crashing
    ) -> None:
        """Log license validation attempt"""
        try:
            log_entry = LicenseValidationLog(
                installation_id=installation.id,
                validation_type=validation_type,
                validation_result=validation_result,
                license_key_hash=(
                    self._get_license_key_hash(license_key) if license_key else None
                ),
                features_validated=features,
                expiration_date=expiration_date,
                max_tenants_validated=max_tenants,
                error_code=error_code,
                error_message=error_message,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            # Log the error but don't fail the operation
            logger.error(f"Failed to log promotion to tenant audit log: {e}")
            self.db.rollback()

    def _log_global_validation(
        self,
        action: str,
        status: str,
        installation_id: str,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Log system-wide license validation attempt"""
        if not self.master_db:
            return

        try:
            log_entry = GlobalLicenseValidationLog(
                action=action,
                status=status,
                installation_id=installation_id,
                tenant_id=tenant_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                error_message=error_message,
            )
            self.master_db.add(log_entry)
            self.master_db.commit()
        except Exception as e:
            logger.error(f"Failed to log global license action: {e}")
            self.master_db.rollback()
