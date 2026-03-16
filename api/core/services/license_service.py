"""
License Service for Customer-Side License Verification

This service handles:
- License verification with JWT signature validation
- Trial management (30-day trial + 7-day grace period)
- License activation and deactivation
- Feature availability checks
- Caching for performance optimization
"""

import jwt
import hashlib
import uuid
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.models.models_per_tenant import InstallationInfo, LicenseValidationLog
from core.models.models import GlobalInstallationInfo, GlobalLicenseValidationLog, Tenant, TenantPluginSettings

logger = logging.getLogger(__name__)


# Default key ID for licenses without explicit kid
DEFAULT_KEY_ID = os.getenv("LICENSE_DEFAULT_KEY_ID", "v2")

# Keys directory path
KEYS_DIR = Path(__file__).parent.parent / "keys"


def generate_key_pair() -> tuple[str, str]:
    """
    Generate a new RSA key pair for license signing.

    Returns:
        Tuple of (private_key_pem, public_key_pem) as strings
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        print("Generating new RSA key pair (2048-bit)...")

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Get public key
        public_key = private_key.public_key()

        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return private_pem, public_pem

    except ImportError:
        raise ImportError(
            "cryptography package is required to generate keys. "
            "Install it with: pip install cryptography"
        )


def save_generated_keys(private_key: str, public_key: str, version: str = None) -> None:
    """
    Save generated keys to the keys directory.

    Args:
        private_key: Private key PEM string
        public_key: Public key PEM string
        version: Optional version identifier (e.g., "v2")
    """
    # Create keys directory if it doesn't exist
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    # Determine filenames
    if version:
        private_path = KEYS_DIR / f"private_key_{version}.pem"
        public_path = KEYS_DIR / f"public_key_{version}.pem"
    else:
        private_path = KEYS_DIR / "private_key.pem"
        public_path = KEYS_DIR / "public_key.pem"

    # Save private key
    private_path.write_text(private_key)
    os.chmod(private_path, 0o600)  # Secure permissions
    print(f"✓ Saved private key to: {private_path}")

    # Save public key
    public_path.write_text(public_key)
    os.chmod(public_path, 0o644)  # Readable by all
    print(f"✓ Saved public key to: {public_path}")

    # Create README if it doesn't exist
    readme_path = KEYS_DIR / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            """# Auto-Generated License Keys

These keys were automatically generated on first startup.

## Security Notes

⚠️ **IMPORTANT**: The private key must be kept secure!

- **private_key.pem** - Used to sign licenses (KEEP SECURE!)
  - Should only be on the license server
  - Never commit to version control
  - Permissions: 600 (owner read/write only)

- **public_key.pem** - Used to verify licenses
  - Embedded in the application
  - Safe to distribute
  - Permissions: 644 (readable by all)

## Key Rotation

To rotate keys, see: docs/admin-guide/LICENSE_KEY_ROTATION_GUIDE.md
"""
        )

    print("\n" + "=" * 60)
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("=" * 60)
    print(f"- Private key saved to: {private_path}")
    print(f"- Keep the private key SECURE and NEVER commit to version control")
    print(f"- Add '{private_path.name}' to .gitignore")
    print(f"- Public key saved to: {public_path}")
    print(f"- The public key is safe to distribute with the application")
    print("=" * 60 + "\n")


def create_symlinks_to_latest_version() -> None:
    """
    Create symlinks from non-versioned names to the latest versioned files.

    This allows using 'private_key.pem' which points to 'private_key_v2.pem'
    making it easier to use without specifying versions.
    """
    if not KEYS_DIR.exists():
        return

    # Find the latest version by looking at versioned files
    versioned_private_keys = list(KEYS_DIR.glob("private_key_v*.pem"))
    versioned_public_keys = list(KEYS_DIR.glob("public_key_v*.pem"))

    if not versioned_private_keys and not versioned_public_keys:
        return  # No versioned keys to link to

    # Extract versions and find the latest (e.g., v2, v3, v10)
    versions = set()
    for key_file in versioned_private_keys + versioned_public_keys:
        # Extract version from filename (e.g., private_key_v2.pem -> v2)
        version = key_file.stem.split("_")[-1]  # Get last part after underscore
        if version.startswith("v"):
            versions.add(version)

    if not versions:
        return

    # Sort versions (v2, v3, v10, etc.) - handle numeric sorting
    def version_key(v):
        try:
            return int(v[1:])  # Remove 'v' and convert to int
        except:
            return 0

    latest_version = sorted(versions, key=version_key)[-1]

    # Create symlinks if they don't exist or point to wrong version
    private_link = KEYS_DIR / "private_key.pem"
    public_link = KEYS_DIR / "public_key.pem"

    private_target = f"private_key_{latest_version}.pem"
    public_target = f"public_key_{latest_version}.pem"

    # Check if target files exist
    if (
        not (KEYS_DIR / private_target).exists()
        or not (KEYS_DIR / public_target).exists()
    ):
        return

    # Create/update private key symlink
    if private_link.is_symlink():
        current_target = os.readlink(private_link)
        if current_target != private_target:
            private_link.unlink()
            private_link.symlink_to(private_target)
            print(f"Updated symlink: private_key.pem -> {private_target}")
    elif not private_link.exists():
        private_link.symlink_to(private_target)
        print(f"Created symlink: private_key.pem -> {private_target}")

    # Create/update public key symlink
    if public_link.is_symlink():
        current_target = os.readlink(public_link)
        if current_target != public_target:
            public_link.unlink()
            public_link.symlink_to(public_target)
            print(f"Updated symlink: public_key.pem -> {public_target}")
    elif not public_link.exists():
        public_link.symlink_to(public_target)
        print(f"Created symlink: public_key.pem -> {public_target}")


def load_public_keys() -> Dict[str, str]:
    """
    Load public keys from files in the keys directory.

    If no keys are found, automatically generates a new key pair.
    Automatically creates symlinks from non-versioned names to latest version.

    Looks for files matching pattern: public_key_*.pem or public_key.pem
    The key version is extracted from the filename.

    Also supports loading from environment variables:
    - LICENSE_PUBLIC_KEY_V2, LICENSE_PUBLIC_KEY_V3, etc.

    Returns:
        Dict mapping key version to public key content
    """
    public_keys = {}

    # Create symlinks to latest version if versioned keys exist
    try:
        create_symlinks_to_latest_version()
    except Exception as e:
        print(f"Warning: Failed to create symlinks: {e}")

    # Load from environment variables first (highest priority)
    for env_var, value in os.environ.items():
        if env_var.startswith("LICENSE_PUBLIC_KEY_"):
            # Extract version from env var name (e.g., LICENSE_PUBLIC_KEY_V2 -> v2)
            version = env_var.replace("LICENSE_PUBLIC_KEY_", "").lower()
            public_keys[version] = value
            print(f"Loaded public key {version} from environment variable")

    # Load master public key from environment variable (highest priority for server_v1)
    master_key_env = os.getenv("LICENSE_MASTER_PUBLIC_KEY")
    if master_key_env:
        public_keys["server_v1"] = master_key_env
        print("Loaded master public key from LICENSE_MASTER_PUBLIC_KEY environment variable")

    # Load from files in keys directory
    if KEYS_DIR.exists():
        # Look for versioned keys: public_key_v2.pem, public_key_v3.pem, etc.
        for key_file in KEYS_DIR.glob("public_key_v*.pem"):
            # Extract version from filename (e.g., public_key_v2.pem -> v2)
            version = key_file.stem.replace("public_key_", "")
            if version not in public_keys:  # Don't override env vars
                try:
                    # Resolve symlinks to get actual file
                    actual_file = key_file.resolve()
                    with open(actual_file, "r") as f:
                        public_keys[version] = f.read()
                    print(f"Loaded public key {version} from {key_file}")
                except Exception as e:
                    print(f"Warning: Failed to load {key_file}: {e}")

        # Also check for default public_key.pem (maps to DEFAULT_KEY_ID)
        default_key_file = KEYS_DIR / "public_key.pem"
        if default_key_file.exists() and DEFAULT_KEY_ID not in public_keys:
            try:
                # Resolve symlinks to get actual file
                actual_file = default_key_file.resolve()
                with open(actual_file, "r") as f:
                    public_keys[DEFAULT_KEY_ID] = f.read()
                print(
                    f"Loaded default public key as {DEFAULT_KEY_ID} from {default_key_file}"
                )
            except Exception as e:
                print(f"Warning: Failed to load {default_key_file}: {e}")

        # Explicitly check for master_public_key.pem (central server key)
        # This allows verifying licenses signed by the server's master key
        master_key_file = KEYS_DIR / "master_public_key.pem"
        if master_key_file.exists():
            try:
                with open(master_key_file, "r") as f:
                    master_key_content = f.read()
                    # 'server_v1' is the dedicated ID for the master key
                    public_keys["server_v1"] = master_key_content
                print(f"Loaded master public key as 'server_v1' from {master_key_file}")
            except Exception as e:
                print(f"Warning: Failed to load {master_key_file}: {e}")

    # Warn if private key files are on the filesystem — recommend using env vars instead
    if KEYS_DIR.exists():
        fs_private_keys = list(KEYS_DIR.glob("private_key*.pem"))
        if fs_private_keys:
            env_key_provided = bool(
                os.getenv("DEPLOYMENT_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
            )
            if not env_key_provided:
                print(
                    "\nWARNING: License private key(s) found on filesystem: "
                    + ", ".join(str(p) for p in fs_private_keys)
                    + "\n  Consider moving private keys to a secret manager and injecting via "
                    "DEPLOYMENT_PRIVATE_KEY env var to avoid storing credentials on disk.\n"
                )

    # Check if we have LOCAL signing keys (not just the master server key)
    # The master_public_key.pem (server_v1) is for verifying server-issued licenses,
    # but we also need local keys for signing our own licenses
    local_keys = {k: v for k, v in public_keys.items() if k not in ["server_v1"]}

    # Check environment variable to control RSA key pair auto-generation
    auto_generate_keys = os.getenv("LICENSE_KEY_AUTO_GENERATE", "true").lower() == "true"

    # Auto-generate RSA key pair if no local signing keys found and auto-generation is enabled
    if not local_keys and auto_generate_keys:
        print("\n" + "=" * 60)
        print("No local license keys found - generating new key pair...")
        print("(master_public_key.pem exists for server license verification)")
        print("=" * 60 + "\n")

        try:
            private_key, public_key = generate_key_pair()
            save_generated_keys(private_key, public_key, version=DEFAULT_KEY_ID)

            # Use the generated public key
            public_keys[DEFAULT_KEY_ID] = public_key
            print(f"✓ Generated and loaded new key pair as version {DEFAULT_KEY_ID}")

        except Exception as e:
            print(f"✗ Failed to generate keys: {e}")
            print(
                "Please generate keys manually using: python api/scripts/generate_license_keys.py"
            )
            raise RuntimeError(
                f"No local license keys found and auto-generation failed: {e}\n"
                "Please generate keys manually or provide them via environment variables."
            )
    elif not local_keys and not auto_generate_keys:
        print("\n" + "=" * 60)
        print("WARNING: No local RSA key pairs found and auto-generation is disabled")
        print("Set LICENSE_KEY_AUTO_GENERATE=true to enable auto-generation")
        print("Or generate keys manually: python api/scripts/generate_license_keys.py")
        print("=" * 60 + "\n")

    return public_keys


# Load public keys on module import
PUBLIC_KEYS = load_public_keys()

# Trial configuration
TRIAL_DURATION_DAYS = 30
GRACE_PERIOD_DAYS = 7
VALIDATION_CACHE_TTL_HOURS = 1


class LicenseService:
    """Service for managing license verification and trial functionality"""

    def __init__(self, db: Session, master_db: Optional[Session] = None):
        self.db = db
        self.master_db = master_db

    # ==================== License Verification ====================

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
        **kwargs # Accept extra arguments like 'details' without crashing
    ):
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
    ):
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

    # ==================== Usage Type Selection ====================

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

    # ==================== Trial Management ====================

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
                original_installation_id=global_id, # Store original global ID
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
            except:
                pass

        max_users = payload.get("max_users") or payload.get("metadata", {}).get("max_users")
        if max_users:
            try:
                global_info.max_users = int(max_users)
            except:
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

    def deactivate_global_license(self, user_id=None, ip_address=None, user_agent=None) -> Dict[str, Any]:
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

    # ==================== Feature Checks ====================

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


    # ==================== Installation ID Management ====================

    def regenerate_installation_id(self, user_id=None, ip_address=None, user_agent=None) -> Dict[str, Any]:
        """
        Regenerate the installation ID for a tenant.
        This enables extracting a tenant from the global license system.
        allowed only ONCE per tenant.
        """
        installation = self._get_or_create_installation()

        # Check if already regenerated
        if installation.custom_installation_id:
             return {
                "success": False,
                "message": "Installation ID has already been regenerated. This action can only be performed once.",
                "error": "ALREADY_REGENERATED"
            }

        # Check if tenant is exempted (technically enforced by checking if global applies, but explicit check here)
        # We allow regeneration even if not strictly exempted in DB settings, as this action essentially exempts them
        # However, to be safe, we should ensure they know what they are doing.

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
        installation.license_status = "invalid" # Changed from "trial" to "invalid"
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

    def update_installation_id(self, new_installation_id: str, user_id=None, ip_address=None, user_agent=None) -> Dict[str, Any]:
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

    def switch_license_mode(self, mode: str, user_id=None, ip_address=None, user_agent=None) -> Dict[str, Any]:
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
        else: # local
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

    def _ensure_utc(self, dt: datetime) -> datetime:
        """Helper to ensure a datetime is timezone-aware and in UTC"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

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
        global_info = self._get_or_create_global_installation()

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

    def update_global_signup_settings(self, allow_password: Optional[bool] = None, allow_sso: Optional[bool] = None, max_tenants: Optional[int] = None, max_users: Optional[int] = None) -> bool:
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
